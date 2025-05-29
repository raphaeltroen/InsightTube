"""
YouTube Comment Analysis Backend
Clean API with separated initialization and search functionality
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import numpy as np
from googleapiclient.discovery import build
import time

# Import the analyzer components
from analyzer import Comment, YouTubeCommentAnalyzer
from clustering import Cluster, analyze_comments


@dataclass
class VideoData:
    """Stores video metadata and comments"""
    video_id: str
    title: str
    channel: str
    views: int
    likes: int
    comment_count: int
    thumbnail_url: str
    comments: List[Dict[str, Any]]


@dataclass
class AnalysisResult:
    """Result from analyzing comments"""
    category: str
    threshold: float
    clusters: List[Cluster]
    total_comments_found: int
    percentage_of_total: float


class YouTubeAnalysisBackend:
    """
    Backend API for YouTube comment analysis.

    Usage:
        # Initialize once with video
        backend = YouTubeAnalysisBackend(youtube_api_key, google_api_key)
        backend.initialize_video("video_id_or_url", max_comments=1000)

        # Search multiple times with different filters
        positive_results = backend.search_comments("positive", threshold=0.35)
        negative_results = backend.search_comments("negative", threshold=0.4)
        custom_results = backend.search_comments("excited about features", threshold=0.3)
    """

    def __init__(self, youtube_api_key: str, google_api_key: str, debug: bool = False):
        """
        Initialize the backend with API keys.

        Args:
            youtube_api_key: YouTube Data API key
            google_api_key: Google AI API key for embeddings
            debug: Enable debug output
        """
        self.youtube_api_key = youtube_api_key
        self.google_api_key = google_api_key
        self.debug = debug

        # Will be set after initialization
        self.video_data: Optional[VideoData] = None
        self.analyzer: Optional[YouTubeCommentAnalyzer] = None
        self._embeddings_computed = False

    def initialize_video(self, video_id_or_url: str, max_comments: int = 1000) -> VideoData:
        """
        Initialize with a YouTube video. This fetches video info and comments,
        and prepares embeddings for fast searching.

        Args:
            video_id_or_url: YouTube video ID or URL
            max_comments: Maximum number of comments to fetch

        Returns:
            VideoData object with video information

        Raises:
            ValueError: If video ID is invalid or video not found
            Exception: If API calls fail
        """
        # Extract video ID
        video_id = self._extract_video_id(video_id_or_url)
        if not video_id:
            raise ValueError("Invalid YouTube URL or video ID")

        # Fetch video info
        print(f"Fetching video information for {video_id}...")
        video_info = self._fetch_video_info(video_id)
        if not video_info:
            raise ValueError("Video not found or API error")

        # Fetch comments
        print(f"Fetching up to {max_comments} comments...")
        comments = self._fetch_comments(video_id, max_comments)
        if not comments:
            raise ValueError("No comments found or API error")

        print(f"Successfully fetched {len(comments)} comments")

        # Store video data
        self.video_data = VideoData(
            video_id=video_id,
            title=video_info['snippet']['title'],
            channel=video_info['snippet']['channelTitle'],
            views=int(video_info['statistics'].get('viewCount', 0)),
            likes=int(video_info['statistics'].get('likeCount', 0)),
            comment_count=int(video_info['statistics'].get('commentCount', 0)),
            thumbnail_url=video_info['snippet']['thumbnails']['medium']['url'],
            comments=comments
        )

        # Initialize analyzer
        print("Initializing comment analyzer...")
        self.analyzer = YouTubeCommentAnalyzer(
            google_api_key=self.google_api_key,
            debug=self.debug
        )

        # Convert comments to Comment objects
        comment_objects = []
        for c in comments:
            comment_objects.append(Comment(
                text=c['text'],
                likes=c['likes'],
                reply_count=c['reply_count'],
                comment_id=c.get('comment_id'),
                author=c.get('author')
            ))

        self.analyzer.add_comments(comment_objects)

        # Pre-compute embeddings for faster searching
        print("Computing comment embeddings (this may take a moment)...")
        start_time = time.time()
        self.analyzer._generate_embeddings()
        self._embeddings_computed = True
        print(f"Embeddings computed in {time.time() - start_time:.1f} seconds")

        return self.video_data

    def search_comments(self,
                        filter_query: str,
                        threshold: float = 0.4,
                        n_clusters: int = 3,
                        popularity_impact: float = 0.7) -> AnalysisResult:
        """
        Search for comments matching a filter query.

        Args:
            filter_query: What to search for. Can be:
                - Predefined: "positive", "negative", "confused", "technical"
                - Custom: "excited about features", "asking for help", etc.
            threshold: Distance threshold (0-1, lower is stricter)
            n_clusters: Number of clusters to create
            popularity_impact: How much to weight popular comments in clustering

        Returns:
            AnalysisResult with clusters and statistics

        Raises:
            RuntimeError: If initialize_video() hasn't been called
        """
        if not self.analyzer or not self.video_data:
            raise RuntimeError("Must call initialize_video() before searching")

        if not self._embeddings_computed:
            print("Computing embeddings...")
            self.analyzer._generate_embeddings()
            self._embeddings_computed = True

        print(f"\nSearching for '{filter_query}' comments...")

        # Use the analyze_comments function from clustering module
        clusters = analyze_comments(
            comments=self.video_data.comments,
            filter_query=filter_query,
            threshold=threshold,
            google_api_key=self.google_api_key,
            n_clusters=n_clusters,
            popularity_impact=popularity_impact,
            debug=self.debug
        )

        # Calculate statistics
        total_found = sum(c.size for c in clusters)
        percentage = (total_found / len(self.video_data.comments)) * 100 if self.video_data.comments else 0

        print(f"Found {total_found} {filter_query} comments ({percentage:.1f}%)")

        return AnalysisResult(
            category=filter_query,
            threshold=threshold,
            clusters=clusters,
            total_comments_found=total_found,
            percentage_of_total=percentage
        )

    def get_video_info(self) -> Optional[VideoData]:
        """Get the currently loaded video data."""
        return self.video_data

    def reset(self):
        """Reset the backend to analyze a different video."""
        self.video_data = None
        self.analyzer = None
        self._embeddings_computed = False

    # Private helper methods

    def _extract_video_id(self, url_or_id: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats."""
        import re

        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:watch\?v=)([0-9A-Za-z_-]{11})',
            r'youtu\.be\/([0-9A-Za-z_-]{11})'
        ]

        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)

        # If no pattern matches, check if it's already a video ID
        if len(url_or_id) == 11:
            return url_or_id

        return None

    def _fetch_video_info(self, video_id: str) -> Optional[Dict]:
        """Fetch video metadata from YouTube API."""
        try:
            youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
            request = youtube.videos().list(
                part='snippet,statistics',
                id=video_id
            )
            response = request.execute()

            if response['items']:
                return response['items'][0]
            return None
        except Exception as e:
            if self.debug:
                print(f"Error fetching video info: {e}")
            return None

    def _fetch_comments(self, video_id: str, max_results: int) -> List[Dict[str, Any]]:
        """Fetch comments from YouTube API."""
        try:
            youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)

            comments = []
            next_page_token = None

            while len(comments) < max_results:
                request = youtube.commentThreads().list(
                    part='snippet',
                    videoId=video_id,
                    maxResults=min(100, max_results - len(comments)),
                    pageToken=next_page_token
                )
                response = request.execute()

                for item in response['items']:
                    snippet = item['snippet']['topLevelComment']['snippet']
                    comments.append({
                        'text': snippet['textDisplay'],
                        'likes': snippet['likeCount'],
                        'reply_count': item['snippet']['totalReplyCount'],
                        'comment_id': item['id'],
                        'author': snippet['authorDisplayName'],
                        'published_at': snippet.get('publishedAt', '')
                    })

                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break

                # Show progress
                if self.debug and len(comments) % 100 == 0:
                    print(f"  Fetched {len(comments)} comments so far...")

            return comments

        except Exception as e:
            if self.debug:
                print(f"Error fetching comments: {e}")
            return []


# Convenience functions for quick analysis

def quick_analyze(video_url: str, youtube_api_key: str, google_api_key: str,
                  categories: List[str] = None) -> Dict[str, AnalysisResult]:
    """
    Quick analysis of a video with default settings.

    Args:
        video_url: YouTube video URL or ID
        youtube_api_key: YouTube API key
        google_api_key: Google AI API key
        categories: List of categories to analyze (default: ["positive", "negative", "confused"])

    Returns:
        Dictionary mapping category names to AnalysisResult objects
    """
    if categories is None:
        categories = ["positive", "negative", "confused"]

    # Initialize backend
    backend = YouTubeAnalysisBackend(youtube_api_key, google_api_key)
    backend.initialize_video(video_url, max_comments=1000)

    # Analyze each category
    results = {}
    for category in categories:
        threshold = 0.35 if category == "positive" else 0.4
        results[category] = backend.search_comments(category, threshold=threshold)

    return results


def export_results(results: Dict[str, AnalysisResult], video_data: VideoData,
                   filename: str = "analysis_results.json"):
    """Export analysis results to JSON file."""
    import json
    from datetime import datetime

    export_data = {
        "video": {
            "id": video_data.video_id,
            "title": video_data.title,
            "channel": video_data.channel,
            "views": video_data.views,
            "likes": video_data.likes,
            "total_comments": len(video_data.comments)
        },
        "analysis_date": datetime.now().isoformat(),
        "categories": {}
    }

    for category, result in results.items():
        export_data["categories"][category] = {
            "total_found": result.total_comments_found,
            "percentage": result.percentage_of_total,
            "threshold": result.threshold,
            "clusters": [
                {
                    "id": cluster.id,
                    "size": cluster.size,
                    "summary": cluster.summary,
                    "avg_likes": cluster.avg_likes,
                    "top_comments": cluster.representative_comments[:3]
                }
                for cluster in result.clusters
            ]
        }

    with open(filename, 'w') as f:
        json.dump(export_data, f, indent=2)

    print(f"Results exported to {filename}")