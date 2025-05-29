"""
YouTube comment analyser with robust Gemini-embedding handling,
fast top-k retrieval and safe clustering.

Key features:
- Generates multiple examples per category using Gemini
- Calculates distance to examples using various methods (min, avg, weighted)
- Robust example generation with validation for categories like "constructive criticism"
- Threshold-based filtering and weighted clustering
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Sequence

import numpy as np
from numpy.linalg import matrix_rank
from collections import defaultdict

import google.generativeai as genai
from google.api_core import exceptions as gexc  # for retry logic

from sklearn.cluster import KMeans

# Try to import configuration, use defaults if not available
try:
    from config import (
        EMBED_MODEL, EMBED_DIM, BATCH_SIZE,
        GENERATION_MODEL, NUM_EXAMPLES, EXAMPLE_GENERATION_TEMPERATURE,
        BACKOFF_DELAYS, DEFAULT_K_COMMENTS, DEFAULT_N_CLUSTERS,
        DEFAULT_POPULARITY_WEIGHT, DEFAULT_IGNORE_POPULARITY,
        DEFAULT_DISTANCE_METHOD, DEFAULT_DISTANCE_THRESHOLD, DEFAULT_POPULARITY_IMPACT,
        KMEANS_N_INIT, KMEANS_RANDOM_STATE,
        MAX_COMMENTS_PER_CLUSTER_SUMMARY
    )
except ImportError:
    # Fallback values if config.py is missing or incomplete
    EMBED_MODEL = "models/text-embedding-004"
    EMBED_DIM = 768
    BATCH_SIZE = 20
    GENERATION_MODEL = "gemini-2.0-flash"
    NUM_EXAMPLES = 10
    EXAMPLE_GENERATION_TEMPERATURE = 0.3
    BACKOFF_DELAYS = [0.5, 1, 2, 4]
    DEFAULT_K_COMMENTS = 50
    DEFAULT_N_CLUSTERS = 5
    DEFAULT_POPULARITY_WEIGHT = 0.3
    DEFAULT_IGNORE_POPULARITY = True
    DEFAULT_DISTANCE_METHOD = "minimum"
    DEFAULT_DISTANCE_THRESHOLD = 0.4
    DEFAULT_POPULARITY_IMPACT = 0.5
    KMEANS_N_INIT = 10
    KMEANS_RANDOM_STATE = 42
    MAX_COMMENTS_PER_CLUSTER_SUMMARY = 10


@dataclass
class Comment:
    """Represents a YouTube comment with metadata."""
    text: str
    likes: int
    reply_count: int
    comment_id: Optional[str] = None
    author: Optional[str] = None

    @property
    def popularity_score(self) -> float:
        """A simple logarithmic popularity measure."""
        likes_score = np.log1p(self.likes)          # log(1+likes)
        reply_score = np.log1p(self.reply_count) * 0.5
        return float(likes_score + reply_score)


class YouTubeCommentAnalyzer:
    """
    Analyse and cluster YouTube comments with Gemini embeddings.

    Key features:
    - Generates category examples using Gemini for accurate filtering
    - Threshold-based filtering to get all relevant comments
    - Weighted clustering that gives more influence to popular comments
    - Multiple distance calculation methods (minimum, average, weighted)

    Example usage:
        analyzer = YouTubeCommentAnalyzer(api_key)
        analyzer.add_comments(comments)

        # Find all positive comments with distance < 0.35
        results = analyzer.analyze_with_threshold(
            filter_query="positive",
            distance_threshold=0.35,
            n_clusters=3,
            popularity_impact=0.7  # High weight for popular comments in clustering
        )
    """

    def __init__(self,
                 google_api_key: str,
                 embedding_model: str = EMBED_MODEL,
                 generation_model: str = GENERATION_MODEL,
                 debug: bool = False):
        genai.configure(api_key=google_api_key)
        self.embedding_model = embedding_model
        self.generation_model = generation_model
        self.comments: List[Comment] = []
        self.embeddings: Optional[np.ndarray] = None
        self.debug = debug
        self._example_cache: Dict[str, List[str]] = {}  # Cache generated examples

    # ────────────────────────────────────────────────────────────────────────
    # Public helpers
    # ────────────────────────────────────────────────────────────────────────
    def add_comments(self, comments: List[Comment]) -> None:
        self.comments.extend(comments)
        self.embeddings = None        # invalidate cache

    # ────────────────────────────────────────────────────────────────────────
    # Example generation
    # ────────────────────────────────────────────────────────────────────────
    def _generate_examples(self, category: str, num_examples: int = NUM_EXAMPLES) -> List[str]:
        """Use Gemini to generate diverse examples of YouTube comments for a category."""
        if category in self._example_cache:
            return self._example_cache[category][:num_examples]

        model = genai.GenerativeModel(self.generation_model)

        # More specific prompts for better example generation
        category_prompts = {
            "constructive criticism": """Generate examples of CONSTRUCTIVE CRITICISM YouTube comments that:
- Point out specific problems or issues
- Suggest improvements or changes
- Mix criticism with some appreciation
- Are helpful rather than just negative
- Include phrases like "could be better", "suggestion", "improvement", "however", "but"

Examples should be critical but constructive, NOT just positive comments.""",

            "criticize": """Generate examples of CRITICAL YouTube comments that:
- Point out flaws or problems
- Express disappointment or criticism
- May or may not be constructive
- Include phrases like "not good", "could be better", "disappointed", "expected more"
- Can range from polite criticism to harsh feedback""",

            "positive": """Generate examples of POSITIVE YouTube comments that:
- Express appreciation, love, or enthusiasm
- Thank the creator
- Say how the video helped them
- Use positive adjectives
- Are purely supportive with NO criticism""",

            "humor": """Generate examples of HUMOROUS YouTube comments that:
- Make jokes or puns
- Use sarcasm or wit
- Reference memes
- Are trying to be funny
- Include "LOL", "LMAO", emojis, or joke setups""",

            "confused": """Generate examples of CONFUSED YouTube comments that:
- Express not understanding
- Ask for clarification
- Say they're lost
- Mention specific parts they don't get
- Use phrases like "I don't understand", "confused", "lost me", "what?""",

            "negative": """Generate examples of NEGATIVE YouTube comments that:
- Express dislike or disappointment
- Criticize without being constructive
- Complain about the video
- Are harsh or dismissive
- Use words like "bad", "terrible", "waste", "useless""",

            "technical": """Generate examples of TECHNICAL YouTube comments that:
- Discuss implementation details
- Reference specific algorithms or code
- Use technical terminology
- Correct technical errors
- Share technical insights or resources"""
        }

        # Get specific prompt or use generic
        if category.lower() in category_prompts:
            prompt = category_prompts[category.lower()] + f"\n\nGenerate exactly {num_examples} examples:"
        else:
            prompt = f"""Generate {num_examples} diverse, realistic YouTube comments that represent "{category}" comments.
Make them varied in length, style, and specific aspects of {category}.
Format: Return ONLY the comments, one per line, no numbering or extra formatting.

Generate {num_examples} comments for the category: "{category}"
"""

        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=EXAMPLE_GENERATION_TEMPERATURE,
                    max_output_tokens=1000,
                )
            )

            # Parse response into individual examples
            examples = []
            for line in response.text.strip().split('\n'):
                # Clean up the line
                cleaned = line.strip()
                # Remove bullet points, numbers, etc
                cleaned = re.sub(r'^[\s>*•\-]+|^\d+[\.)]\s*', '', cleaned).strip()
                if cleaned and not cleaned.startswith(('-', '*', '•')):
                    examples.append(cleaned)

            # For constructive criticism, validate examples
            if category.lower() == "constructive criticism":
                criticism_cues = {"could", "should", "however", "but", "suggest", "improve", "improvement", "though", "although"}
                validated = []
                for ex in examples:
                    if any(cue in ex.lower() for cue in criticism_cues):
                        validated.append(ex)
                examples = validated

            # For general criticism, validate examples
            elif category.lower() in ["criticize", "criticism"]:
                criticism_cues = {"not", "could", "should", "better", "disappointed", "expected", "poor", "bad", "wrong", "issue", "problem"}
                validated = []
                for ex in examples:
                    if any(cue in ex.lower() for cue in criticism_cues):
                        validated.append(ex)
                examples = validated

            # Ensure we have enough examples
            if len(examples) < num_examples:
                # Add some fallback examples based on category
                fallbacks = {
                    "positive": ["Great video!", "Love this content!", "Amazing explanation!"],
                    "negative": ["Didn't like this", "Poor quality", "Waste of time"],
                    "constructive criticism": ["Good video but the audio could be better", "Nice content, though I'd suggest adding timestamps", "Great explanation, but maybe slow down a bit"],
                    "criticize": ["Not impressed with this video", "Could be much better", "Expected more from this channel"],
                    "question": ["How does this work?", "Can you explain more?", "Why is this?"],
                    "humor": ["LOL so funny!", "This made me laugh", "Hilarious!"],
                    "confused": ["I don't understand this part", "I'm lost", "Can someone explain?"],
                    "technical": ["The algorithm here is O(n log n)", "Great code example", "Nice implementation"],
                }
                category_lower = category.lower()
                for key, values in fallbacks.items():
                    if key in category_lower:
                        examples.extend(values[:num_examples - len(examples)])
                        break

                if len(examples) < num_examples:
                    # Generic fallback
                    examples.extend([f"This is a {category} comment about the video"] * (num_examples - len(examples)))

            examples = examples[:num_examples]

            if self.debug:
                print(f"\n[DEBUG] Generated {len(examples)} examples for '{category}':")
                for i, ex in enumerate(examples[:3]):  # Show first 3
                    print(f"  {i+1}. {ex[:60]}...")
                if len(examples) > 3:
                    print(f"  ... and {len(examples)-3} more")

            self._example_cache[category] = examples
            return examples

        except Exception as e:
            print(f"[WARN] Failed to generate examples: {e}. Using fallback.")
            # Fallback to basic examples
            fallback = f"This is a {category} comment about the video"
            return [fallback] * num_examples

    # ────────────────────────────────────────────────────────────────────────
    # Embedding helpers
    # ────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _safe_embed(texts: Sequence[str], model: str) -> List[List[float]]:
        """Call gemini embed with polite back-off on 429/503."""
        for delay in BACKOFF_DELAYS + [None]:  # last None = give up
            try:
                rsp = genai.embed_content(
                    model=model,
                    content=texts,
                    task_type="SEMANTIC_SIMILARITY",
                )
                return rsp["embedding"]  # Returns list of embeddings
            except (gexc.ResourceExhausted, gexc.ServiceUnavailable) as e:
                if delay is None:
                    raise
                print(f"[WARN] Rate limit hit, waiting {delay}s...")
                time.sleep(delay)
            except Exception as e:
                if delay is None:
                    raise
                print(f"[WARN] Embedding error: {e}, retrying...")
                time.sleep(delay)

    def _generate_embeddings(self) -> np.ndarray:
        """Generate embeddings for all comments."""
        if self.embeddings is not None:
            return self.embeddings

        texts = [c.text for c in self.comments]
        all_vecs: List[List[float]] = []

        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start:start + BATCH_SIZE]
            try:
                batch_embeddings = self._safe_embed(batch, self.embedding_model)
                all_vecs.extend(batch_embeddings)
            except Exception as exc:
                # Fallback: small random noise so vectors are distinct
                print(f"[WARN] embedding failed for batch {start//BATCH_SIZE}: {exc}")
                noise = np.random.normal(scale=1e-3,
                                        size=(len(batch), EMBED_DIM)).tolist()
                all_vecs.extend(noise)

        emb = np.asarray(all_vecs, dtype=np.float32)
        # L2 normalise rows so cosine distance = 1 − dot
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        emb = emb / (norms + 1e-8)
        self.embeddings = emb
        return emb

    # ────────────────────────────────────────────────────────────────────────
    # Internal maths helpers
    # ────────────────────────────────────────────────────────────────────────
    def _distances_to_examples(self,
                               example_vecs: np.ndarray,
                               indices: List[int],
                               method: str = "average") -> np.ndarray:
        """
        Calculate distance from comments to multiple example vectors.

        Methods:
        - "average": Average distance to all examples
        - "minimum": Minimum distance to any example
        - "weighted": Weighted average giving more weight to closer examples
        """
        comment_embs = self._generate_embeddings()[indices]

        # Calculate distances to each example
        # comment_embs: (n_comments, dim), example_vecs: (n_examples, dim)
        # Result: (n_comments, n_examples)
        similarities = np.dot(comment_embs, example_vecs.T)
        distances = 1.0 - similarities

        if method == "minimum":
            # Find the closest example for each comment
            return np.min(distances, axis=1)
        elif method == "weighted":
            # Weight by inverse distance (closer examples have more influence)
            weights = 1.0 / (distances + 0.1)  # Add small constant to avoid division by zero
            weights = weights / np.sum(weights, axis=1, keepdims=True)
            weighted_distances = np.sum(distances * weights, axis=1)
            return weighted_distances
        else:  # average
            # Simple average distance across all examples
            return np.mean(distances, axis=1)

    def _weighted_scores(self,
                         example_vecs: np.ndarray,
                         indices: List[int],
                         popularity_weight: float,
                         distance_method: str = "average") -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return distance − pop mix where lower is better, plus components for debugging."""
        # Get semantic distances to examples using specified method
        semantic_distances = self._distances_to_examples(example_vecs, indices, distance_method)

        # Get popularity scores
        pop_scores = np.array([self.comments[i].popularity_score for i in indices])

        # Normalize popularity to [0, 1]
        if pop_scores.ptp() > 0:
            pop_normalized = (pop_scores - pop_scores.min()) / pop_scores.ptp()
        else:
            pop_normalized = np.zeros_like(pop_scores)

        # Combined score: lower is better
        # High semantic distance = bad, high popularity = good (so we subtract it)
        combined_scores = (1 - popularity_weight) * semantic_distances - popularity_weight * pop_normalized

        return combined_scores, semantic_distances, pop_scores

    # ────────────────────────────────────────────────────────────────────────
    # High-level operations - NEW THRESHOLD-BASED METHODS
    # ────────────────────────────────────────────────────────────────────────
    def filter_comments_by_threshold(self,
                        filter_query: str,
                        distance_threshold: float = 0.4,
                        popularity_weight: float = DEFAULT_POPULARITY_WEIGHT,
                        ignore_popularity: bool = DEFAULT_IGNORE_POPULARITY,
                        num_examples: int = NUM_EXAMPLES,
                        distance_method: str = "minimum") -> List[Tuple[Comment, float, float]]:
        """
        Filter comments by semantic similarity threshold to generated examples.

        Args:
            filter_query: Category name (e.g., "positive", "technical", "humor")
            distance_threshold: Maximum distance to consider a comment relevant (0-1, lower is stricter)
            popularity_weight: Weight for popularity vs semantic similarity
            ignore_popularity: If True, only use semantic distance for filtering
            num_examples: Number of examples to generate for the category
            distance_method: How to calculate distance to examples

        Returns:
            List of (comment, combined_score, semantic_distance) for all comments below threshold
        """
        # Generate examples for the category
        examples = self._generate_examples(filter_query, num_examples)

        # Embed all examples
        try:
            example_embeddings = []
            for i in range(0, len(examples), BATCH_SIZE):
                batch = examples[i:i + BATCH_SIZE]
                batch_vecs = self._safe_embed(batch, self.embedding_model)
                example_embeddings.extend(batch_vecs)

            example_vecs = np.asarray(example_embeddings, dtype=np.float32)
            # Normalize
            norms = np.linalg.norm(example_vecs, axis=1, keepdims=True)
            example_vecs = example_vecs / (norms + 1e-8)

        except Exception as exc:
            print(f"[ERR] example embedding failed: {exc}. Returning empty results.")
            return []

        # Scores for all comments
        idx_all = list(range(len(self.comments)))

        # Override popularity weight if ignore_popularity is True
        effective_weight = 0.0 if ignore_popularity else popularity_weight

        combined_scores, semantic_distances, pop_scores = self._weighted_scores(
            example_vecs, idx_all, effective_weight, distance_method
        )

        # Filter by threshold
        if ignore_popularity:
            # Use semantic distance directly
            valid_indices = np.where(semantic_distances <= distance_threshold)[0]
        else:
            # Use combined score threshold (adjust threshold for combined scoring)
            # Since combined score subtracts normalized popularity, we need to adjust
            threshold_adjusted = distance_threshold - effective_weight  # Account for popularity benefit
            valid_indices = np.where(combined_scores <= threshold_adjusted)[0]

        # Sort by score (lower is better)
        if ignore_popularity:
            valid_indices = valid_indices[np.argsort(semantic_distances[valid_indices])]
        else:
            valid_indices = valid_indices[np.argsort(combined_scores[valid_indices])]

        # Debug output
        if self.debug:
            print(f"\n[DEBUG] Filter category: '{filter_query}'")
            print(f"[DEBUG] Using {len(examples)} generated examples")
            print(f"[DEBUG] Distance method: {distance_method}")
            print(f"[DEBUG] Distance threshold: {distance_threshold}")
            print(f"[DEBUG] Found {len(valid_indices)} comments below threshold")
            print(f"[DEBUG] Popularity weight: {effective_weight} (ignore_popularity={ignore_popularity})")

            # Show distance distribution
            if len(valid_indices) > 0:
                distances = semantic_distances[valid_indices]
                print(f"[DEBUG] Distance range: {distances.min():.3f} - {distances.max():.3f}")
                print(f"[DEBUG] Average distance: {distances.mean():.3f}")

        # Return comment, combined score, and semantic distance
        return [(self.comments[i], float(combined_scores[i]), float(semantic_distances[i]))
                for i in valid_indices]

    def cluster_comments_weighted(self,
                         comments: List[Comment],
                         n_clusters: int = DEFAULT_N_CLUSTERS,
                         popularity_impact: float = 0.5) -> Dict[int, List[Comment]]:
        """
        Cluster comments using KMeans with popularity weighting.

        Args:
            comments: List of comments to cluster
            n_clusters: Number of clusters to create
            popularity_impact: How much to weight popular comments (0-1)
                              0 = no weighting, 1 = maximum popularity influence
        """
        if not comments:
            return {0: []}

        indices = [self.comments.index(c) for c in comments]
        emb = self._generate_embeddings()[indices]

        # Get popularity scores and create weights
        pop_scores = np.array([c.popularity_score for c in comments])

        # Normalize popularity scores to [0, 1]
        if pop_scores.ptp() > 0:
            pop_normalized = (pop_scores - pop_scores.min()) / pop_scores.ptp()
        else:
            pop_normalized = np.ones_like(pop_scores) * 0.5

        # Create sample weights: base weight + popularity bonus
        # Popular comments will have more influence in clustering
        base_weight = 1.0
        weights = base_weight + popularity_impact * pop_normalized

        # Check embedding diversity
        if self.debug:
            pairwise_sims = np.dot(emb, emb.T)
            avg_sim = (pairwise_sims.sum() - np.trace(pairwise_sims)) / (len(emb) * (len(emb) - 1))
            print(f"\n[DEBUG] Average pairwise similarity: {avg_sim:.3f}")
            print(f"[DEBUG] Weight range: {weights.min():.3f} - {weights.max():.3f}")
            print(f"[DEBUG] Clustering {len(comments)} comments into {n_clusters} clusters")

        rank = matrix_rank(emb)
        n_clusters = max(1, min(n_clusters, rank, len(comments)))

        if n_clusters == 1:
            return {0: comments}

        # Use weighted k-means by duplicating embeddings based on weights
        # Convert weights to integer counts (more weight = more copies)
        weight_counts = np.maximum(1, np.round(weights * 2).astype(int))

        # Create weighted embedding matrix
        weighted_emb = []
        weighted_indices = []
        for i, count in enumerate(weight_counts):
            for _ in range(count):
                weighted_emb.append(emb[i])
                weighted_indices.append(i)

        weighted_emb = np.array(weighted_emb)

        # Perform k-means on weighted embeddings
        km = KMeans(n_clusters=n_clusters, n_init=KMEANS_N_INIT, random_state=KMEANS_RANDOM_STATE)
        weighted_labels = km.fit_predict(weighted_emb)

        # Map back to original comments
        # Vote by majority for each original comment
        label_votes = defaultdict(lambda: defaultdict(int))
        for weighted_idx, label in enumerate(weighted_labels):
            original_idx = weighted_indices[weighted_idx]
            label_votes[original_idx][label] += 1

        # Assign each comment to its most voted cluster
        clusters = defaultdict(list)
        for i, comment in enumerate(comments):
            if i in label_votes:
                # Get the label with the most votes
                best_label = max(label_votes[i].items(), key=lambda x: x[1])[0]
                clusters[int(best_label)].append(comment)
            else:
                # Fallback (shouldn't happen)
                clusters[0].append(comment)

        # Ensure all clusters have at least some comments
        final_clusters = {}
        cluster_id = 0
        for cid in range(n_clusters):
            if cid in clusters and clusters[cid]:
                final_clusters[cluster_id] = clusters[cid]
                cluster_id += 1

        if self.debug:
            print(f"[DEBUG] Created {len(final_clusters)} non-empty clusters")
            for cid, cmts in final_clusters.items():
                avg_pop = np.mean([c.popularity_score for c in cmts])
                print(f"[DEBUG] Cluster {cid}: {len(cmts)} comments, avg popularity: {avg_pop:.2f}")

        return final_clusters

    def analyze_with_threshold(self,
                filter_query: str,
                distance_threshold: float = 0.4,
                n_clusters: int = DEFAULT_N_CLUSTERS,
                popularity_weight: float = DEFAULT_POPULARITY_WEIGHT,
                ignore_popularity: bool = DEFAULT_IGNORE_POPULARITY,
                distance_method: str = "minimum",
                popularity_impact: float = 0.5) -> Dict[str, object]:
        """
        Full analysis pipeline using distance threshold and weighted clustering.

        Args:
            filter_query: Category name (e.g., "positive", "technical discussion", "humor")
            distance_threshold: Maximum distance to consider relevant (0-1, lower is stricter)
            n_clusters: Number of clusters to create
            popularity_weight: Weight for popularity vs semantic similarity in filtering
            ignore_popularity: If True, only use semantic distance for filtering
            distance_method: How to calculate distance ("average", "minimum", "weighted")
            popularity_impact: How much to weight popular comments in clustering (0-1)
        """
        # 1) Filter by threshold
        filtered = self.filter_comments_by_threshold(
            filter_query, distance_threshold, popularity_weight,
            ignore_popularity, num_examples=NUM_EXAMPLES,
            distance_method=distance_method
        )

        if not filtered:
            print(f"[WARN] No comments found below threshold {distance_threshold} for '{filter_query}'")
            return {
                "filtered_comments": [],
                "clusters": {},
                "representatives": {},
                "summaries": {},
                "stats": {
                    "total_comments": len(self.comments),
                    "filtered_comments": 0,
                    "threshold": distance_threshold
                }
            }

        # Extract just comments for clustering
        filtered_comments = [c for c, _, _ in filtered]

        print(f"\n[INFO] Found {len(filtered_comments)} relevant comments for '{filter_query}'")

        # 2) Weighted clustering
        clusters = self.cluster_comments_weighted(filtered_comments, n_clusters, popularity_impact)

        # 3) representatives
        reps = self.get_cluster_representatives(clusters)

        # 4) summaries
        sums = self.summarize_clusters(clusters)

        # 5) Calculate statistics
        distances = [d for _, _, d in filtered]
        stats = {
            "total_comments": len(self.comments),
            "filtered_comments": len(filtered_comments),
            "threshold": distance_threshold,
            "min_distance": min(distances) if distances else 0,
            "max_distance": max(distances) if distances else 0,
            "avg_distance": np.mean(distances) if distances else 0,
            "clusters_created": len(clusters)
        }

        return {
            "filtered_comments": filtered,  # (comment, combined_score, semantic_distance)
            "clusters": clusters,
            "representatives": reps,
            "summaries": sums,
            "stats": stats
        }

    # ────────────────────────────────────────────────────────────────────────
    # Utility methods
    # ────────────────────────────────────────────────────────────────────────
    @staticmethod
    def get_cluster_representatives(clusters: Dict[int, List[Comment]],
                                    n_repr: int = 3) -> Dict[int, List[Comment]]:
        """Get top representatives from each cluster by popularity."""
        reps: Dict[int, List[Comment]] = {}
        for cid, cmts in clusters.items():
            reps[cid] = sorted(cmts, key=lambda c: c.popularity_score, reverse=True)[:n_repr]
        return reps

    def summarize_clusters(self,
                           clusters: Dict[int, List[Comment]],
                           max_comments_per_cluster: int = MAX_COMMENTS_PER_CLUSTER_SUMMARY,
                           model: str = GENERATION_MODEL) -> Dict[int, str]:
        """Generate summaries for each cluster using Gemini."""
        summaries: Dict[int, str] = {}
        gmodel = genai.GenerativeModel(model)

        for cid, cmts in clusters.items():
            if not cmts:
                summaries[cid] = "No comments in this cluster."
                continue

            top_cmts = sorted(cmts, key=lambda c: c.popularity_score, reverse=True)[:max_comments_per_cluster]
            blob = "\n".join(f"- {c.text} (likes: {c.likes}, replies: {c.reply_count})" for c in top_cmts)
            prompt = (
                "Analyze and summarize the main themes and sentiments in these YouTube comments:\n\n"
                f"{blob}\n\nGive a concise 2–3 sentence summary."
            )
            try:
                rsp = gmodel.generate_content(prompt)
                summaries[cid] = rsp.text.strip()
            except Exception as exc:
                summaries[cid] = f"[ERR] summary failed: {exc}"
        return summaries

    # ────────────────────────────────────────────────────────────────────────
    # Backward compatibility methods
    # ────────────────────────────────────────────────────────────────────────
    def filter_comments(self,
                        filter_query: str,
                        k: int = DEFAULT_K_COMMENTS,
                        popularity_weight: float = DEFAULT_POPULARITY_WEIGHT,
                        ignore_popularity: bool = DEFAULT_IGNORE_POPULARITY,
                        num_examples: int = NUM_EXAMPLES,
                        distance_method: str = "minimum") -> List[Tuple[Comment, float, float]]:
        """
        Filter comments by semantic similarity to generated examples (top-k approach).
        Kept for backward compatibility. Consider using filter_comments_by_threshold instead.
        """
        # Use threshold method and return top k
        all_filtered = self.filter_comments_by_threshold(
            filter_query=filter_query,
            distance_threshold=1.0,  # Get all comments
            popularity_weight=popularity_weight,
            ignore_popularity=ignore_popularity,
            num_examples=num_examples,
            distance_method=distance_method
        )

        # Return top k
        return all_filtered[:k]

    def cluster_comments(self,
                         comments: List[Comment],
                         n_clusters: int = DEFAULT_N_CLUSTERS) -> Dict[int, List[Comment]]:
        """
        Cluster comments using KMeans (unweighted).
        Kept for backward compatibility. Consider using cluster_comments_weighted instead.
        """
        return self.cluster_comments_weighted(comments, n_clusters, popularity_impact=0.0)

    def analyze(self,
                filter_query: str,
                k_comments: int = DEFAULT_K_COMMENTS,
                n_clusters: int = DEFAULT_N_CLUSTERS,
                popularity_weight: float = DEFAULT_POPULARITY_WEIGHT,
                ignore_popularity: bool = DEFAULT_IGNORE_POPULARITY,
                distance_method: str = "minimum") -> Dict[str, object]:
        """
        Full analysis pipeline using top-k approach.
        Kept for backward compatibility. Consider using analyze_with_threshold instead.
        """
        # Use threshold method with a high threshold to get all, then take top k
        results = self.analyze_with_threshold(
            filter_query=filter_query,
            distance_threshold=1.0,  # Get all comments
            n_clusters=n_clusters,
            popularity_weight=popularity_weight,
            ignore_popularity=ignore_popularity,
            distance_method=distance_method,
            popularity_impact=0.0  # No weighting for backward compatibility
        )

        # Trim to top k
        if results['filtered_comments']:
            results['filtered_comments'] = results['filtered_comments'][:k_comments]
            # Re-cluster with just top k
            top_comments = [c for c, _, _ in results['filtered_comments']]
            results['clusters'] = self.cluster_comments(top_comments, n_clusters)
            results['representatives'] = self.get_cluster_representatives(results['clusters'])
            results['summaries'] = self.summarize_clusters(results['clusters'])

        return results