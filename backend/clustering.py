"""
Simplified interface for YouTube comment clustering analysis
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import numpy as np

from analyzer import Comment, YouTubeCommentAnalyzer
from config import DEFAULT_N_CLUSTERS, DEFAULT_POPULARITY_IMPACT, DEFAULT_DISTANCE_METHOD


@dataclass
class Cluster:
    """Represents a cluster of related comments with metadata."""
    id: int
    comments: List[str]  # Array of comment texts
    summary: str  # AI-generated summary of the cluster
    size: int  # Number of comments in cluster
    avg_likes: float  # Average likes in cluster
    max_likes: int  # Maximum likes in cluster
    min_likes: int  # Minimum likes in cluster
    avg_distance: float  # Average semantic distance from category
    representative_comments: List[str]  # Top 3 most popular comments


def analyze_comments(
        comments: List[Dict[str, Any]],
        filter_query: str,
        threshold: float,
        google_api_key: str,
        n_clusters: int = 5,
        popularity_impact: float = 0.5,
        debug: bool = False
) -> List[Cluster]:
    """
    Analyze YouTube comments and return clusters.

    Args:
        comments: List of comment dictionaries with 'text', 'likes', 'reply_count' keys
        filter_query: Category to filter by (e.g., "positive", "negative", "confused")
        threshold: Distance threshold (0-1, lower is stricter)
        google_api_key: Google API key for Gemini
        n_clusters: Number of clusters to create (default: 5)
        popularity_impact: How much to weight popular comments in clustering (0-1)
        debug: Whether to print debug information

    Returns:
        List of Cluster objects containing grouped comments and metadata

    Example:
        comments = [
            {"text": "Great video!", "likes": 100, "reply_count": 5},
            {"text": "This helped me a lot", "likes": 50, "reply_count": 2},
            # ... more comments
        ]

        clusters = analyze_comments(
            comments=comments,
            filter_query="positive",
            threshold=0.35,
            google_api_key=API_KEY
        )

        for cluster in clusters:
            print(f"Cluster {cluster.id}: {cluster.size} comments")
            print(f"Summary: {cluster.summary}")
            print(f"Average likes: {cluster.avg_likes:.1f}")
    """
    # Create Comment objects
    comment_objects = []
    for c in comments:
        comment_objects.append(Comment(
            text=c.get('text', ''),
            likes=c.get('likes', 0),
            reply_count=c.get('reply_count', 0),
            comment_id=c.get('comment_id'),
            author=c.get('author')
        ))

    # Initialize analyzer
    analyzer = YouTubeCommentAnalyzer(
        google_api_key=google_api_key,
        debug=debug
    )
    analyzer.add_comments(comment_objects)

    # Run analysis
    results = analyzer.analyze_with_threshold(
        filter_query=filter_query,
        distance_threshold=threshold,
        n_clusters=n_clusters,
        popularity_impact=popularity_impact,
        ignore_popularity=True,  # Pure semantic filtering
        distance_method=DEFAULT_DISTANCE_METHOD
    )

    # Convert results to Cluster objects
    clusters = []

    # Create a map of comments to their distances
    comment_distances = {}
    for comment, _, distance in results['filtered_comments']:
        comment_distances[comment.comment_id or comment.text] = distance

    for cluster_id, cluster_comments in results['clusters'].items():
        # Extract comment texts
        comment_texts = [c.text for c in cluster_comments]

        # Calculate statistics
        likes_list = [c.likes for c in cluster_comments]
        avg_likes = np.mean(likes_list) if likes_list else 0
        max_likes = max(likes_list) if likes_list else 0
        min_likes = min(likes_list) if likes_list else 0

        # Calculate average distance for this cluster
        cluster_distances = []
        for c in cluster_comments:
            key = c.comment_id or c.text
            if key in comment_distances:
                cluster_distances.append(comment_distances[key])
        avg_distance = np.mean(cluster_distances) if cluster_distances else 0

        # Get representatives (top 3 by popularity)
        representatives = results['representatives'].get(cluster_id, [])
        representative_texts = [rep.text for rep in representatives[:3]]

        # Get summary
        summary = results['summaries'].get(cluster_id, "No summary available")

        # Create Cluster object
        cluster = Cluster(
            id=cluster_id,
            comments=comment_texts,
            summary=summary,
            size=len(cluster_comments),
            avg_likes=float(avg_likes),
            max_likes=int(max_likes),
            min_likes=int(min_likes),
            avg_distance=float(avg_distance),
            representative_comments=representative_texts
        )

        clusters.append(cluster)

    # Sort clusters by size (largest first)
    clusters.sort(key=lambda c: c.size, reverse=True)

    return clusters


def analyze_comments_simple(
        comment_texts: List[str],
        filter_query: str,
        threshold: float,
        google_api_key: str,
        n_clusters: int = 5
) -> List[Cluster]:
    """
    Simplified version that takes just comment texts (no metadata).

    Args:
        comment_texts: List of comment text strings
        filter_query: Category to filter by
        threshold: Distance threshold
        google_api_key: Google API key
        n_clusters: Number of clusters

    Returns:
        List of Cluster objects

    Example:
        texts = [
            "Great video!",
            "This helped me a lot",
            "Amazing content"
        ]

        clusters = analyze_comments_simple(
            comment_texts=texts,
            filter_query="positive",
            threshold=0.35,
            google_api_key=API_KEY
        )
    """
    # Convert to comment dictionaries with default metadata
    comments = [
        {"text": text, "likes": 0, "reply_count": 0}
        for text in comment_texts
    ]

    return analyze_comments(
        comments=comments,
        filter_query=filter_query,
        threshold=threshold,
        google_api_key=google_api_key,
        n_clusters=n_clusters,
        popularity_impact=0.0  # No popularity weighting without metadata
    )


# Convenience functions for common use cases
def find_positive_clusters(comments: List[Dict[str, Any]], google_api_key: str, threshold: float = 0.35) -> List[
    Cluster]:
    """Find clusters of positive comments."""
    return analyze_comments(comments, "positive", threshold, google_api_key)


def find_negative_clusters(comments: List[Dict[str, Any]], google_api_key: str, threshold: float = 0.4) -> List[
    Cluster]:
    """Find clusters of negative comments."""
    return analyze_comments(comments, "negative", threshold, google_api_key)


def find_confused_clusters(comments: List[Dict[str, Any]], google_api_key: str, threshold: float = 0.4) -> List[
    Cluster]:
    """Find clusters of confused/question comments."""
    return analyze_comments(comments, "confused", threshold, google_api_key)


def find_technical_clusters(comments: List[Dict[str, Any]], google_api_key: str, threshold: float = 0.35) -> List[
    Cluster]:
    """Find clusters of technical discussion comments."""
    return analyze_comments(comments, "technical", threshold, google_api_key)


# Utility function to print cluster report
def print_cluster_report(clusters: List[Cluster], max_comments_per_cluster: int = 3):
    """
    Print a formatted report of clusters.

    Args:
        clusters: List of Cluster objects
        max_comments_per_cluster: Maximum comments to show per cluster
    """
    total_comments = sum(c.size for c in clusters)

    print(f"\n{'=' * 70}")
    print(f"CLUSTER ANALYSIS REPORT")
    print(f"{'=' * 70}")
    print(f"Total clusters: {len(clusters)}")
    print(f"Total comments: {total_comments}")

    for cluster in clusters:
        print(f"\n{'-' * 60}")
        print(f"Cluster {cluster.id} ({cluster.size} comments, {cluster.size / total_comments * 100:.1f}%)")
        print(f"Average likes: {cluster.avg_likes:.1f} (range: {cluster.min_likes}-{cluster.max_likes})")
        print(f"Average distance: {cluster.avg_distance:.3f}")
        print(f"\nSummary: {cluster.summary}")

        if cluster.representative_comments:
            print(f"\nTop comments:")
            for i, comment in enumerate(cluster.representative_comments[:max_comments_per_cluster], 1):
                # Truncate long comments
                display_text = comment[:100] + "..." if len(comment) > 100 else comment
                print(f"  {i}. {display_text}")

    print(f"\n{'=' * 70}")


# Export cluster data to various formats
def clusters_to_dict(clusters: List[Cluster]) -> List[Dict[str, Any]]:
    """Convert clusters to dictionary format for JSON export."""
    return [
        {
            "id": cluster.id,
            "size": cluster.size,
            "summary": cluster.summary,
            "avg_likes": cluster.avg_likes,
            "max_likes": cluster.max_likes,
            "min_likes": cluster.min_likes,
            "avg_distance": cluster.avg_distance,
            "representative_comments": cluster.representative_comments,
            "all_comments": cluster.comments
        }
        for cluster in clusters
    ]


def clusters_to_csv_data(clusters: List[Cluster]) -> List[Dict[str, Any]]:
    """Convert clusters to flat format suitable for CSV export."""
    rows = []
    for cluster in clusters:
        for comment in cluster.comments:
            rows.append({
                "cluster_id": cluster.id,
                "cluster_size": cluster.size,
                "cluster_summary": cluster.summary,
                "cluster_avg_likes": cluster.avg_likes,
                "comment": comment
            })
    return rows