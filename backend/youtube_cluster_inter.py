"""
Complete example integrating YouTube comment fetching with cluster analysis
"""

from googleapiclient.discovery import build
from cluster_analysis import analyze_comments, print_cluster_report, Cluster
from API_KEYS import YOUTUBE_API_KEY, GOOGLE_API_KEY
import json
from typing import List, Dict, Any


def fetch_youtube_comments(video_id: str, api_key: str, max_results: int = 1000) -> List[Dict[str, Any]]:
    """
    Fetch comments from a YouTube video.

    Returns list of comment dictionaries with text, likes, reply_count
    """
    youtube = build('youtube', 'v3', developerKey=api_key)

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
                'author': snippet['authorDisplayName']
            })

        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break

    return comments


def analyze_youtube_video(video_id: str,
                          categories: List[tuple] = None,
                          max_comments: int = 1000) -> Dict[str, List[Cluster]]:
    """
    Complete analysis of a YouTube video's comments.

    Args:
        video_id: YouTube video ID
        categories: List of (category, threshold) tuples
        max_comments: Maximum comments to fetch

    Returns:
        Dictionary mapping category names to lists of clusters
    """
    if categories is None:
        categories = [
            ("positive", 0.35),
            ("negative", 0.4),
            ("confused", 0.4),
            ("technical", 0.35),
            ("constructive criticism", 0.4)
        ]

    # Fetch comments
    print(f"Fetching comments for video {video_id}...")
    comments = fetch_youtube_comments(video_id, YOUTUBE_API_KEY, max_comments)
    print(f"Fetched {len(comments)} comments")

    # Analyze each category
    results = {}

    for category, threshold in categories:
        print(f"\n{'=' * 60}")
        print(f"Analyzing '{category}' comments (threshold: {threshold})")
        print('=' * 60)

        try:
            clusters = analyze_comments(
                comments=comments,
                filter_query=category,
                threshold=threshold,
                google_api_key=GOOGLE_API_KEY,
                n_clusters=3,
                popularity_impact=0.7,
                debug=False
            )

            results[category] = clusters

            # Print summary
            total_filtered = sum(c.size for c in clusters)
            percentage = (total_filtered / len(comments)) * 100 if comments else 0

            print(f"\nFound {total_filtered} {category} comments ({percentage:.1f}%)")
            print(f"Grouped into {len(clusters)} clusters")

            # Show cluster summaries
            for cluster in clusters:
                print(f"\nCluster {cluster.id} ({cluster.size} comments):")
                print(f"  Summary: {cluster.summary}")
                print(f"  Avg likes: {cluster.avg_likes:.1f}")

        except Exception as e:
            print(f"Error analyzing {category}: {e}")
            results[category] = []

    return results


def generate_video_report(video_id: str, results: Dict[str, List[Cluster]]) -> str:
    """Generate a comprehensive report for a video."""
    report = []
    report.append(f"YouTube Video Analysis Report")
    report.append(f"Video ID: {video_id}")
    report.append(f"{'=' * 70}\n")

    # Overall statistics
    total_clusters = sum(len(clusters) for clusters in results.values())
    total_comments_analyzed = sum(
        sum(c.size for c in clusters)
        for clusters in results.values()
    )

    report.append(f"Total categories analyzed: {len(results)}")
    report.append(f"Total clusters created: {total_clusters}")
    report.append(f"Total comments categorized: {total_comments_analyzed}\n")

    # Category breakdown
    for category, clusters in results.items():
        if not clusters:
            continue

        report.append(f"\n{'-' * 60}")
        report.append(f"CATEGORY: {category.upper()}")
        report.append(f"{'-' * 60}")

        total_in_category = sum(c.size for c in clusters)
        report.append(f"Comments in category: {total_in_category}")
        report.append(f"Number of clusters: {len(clusters)}\n")

        for cluster in clusters:
            report.append(f"Cluster {cluster.id} ({cluster.size} comments):")
            report.append(f"  Summary: {cluster.summary}")
            report.append(f"  Engagement: {cluster.avg_likes:.1f} avg likes")
            report.append(f"  Distance: {cluster.avg_distance:.3f} avg")

            if cluster.representative_comments:
                report.append("  Top comment:")
                top_comment = cluster.representative_comments[0]
                if len(top_comment) > 100:
                    top_comment = top_comment[:97] + "..."
                report.append(f"    \"{top_comment}\"")
            report.append("")

    return "\n".join(report)


def main():
    """Main function demonstrating complete workflow."""

    # Example video IDs (replace with your own)
    VIDEO_IDS = {
        "tutorial": "DZIASl9q90s",  # Replace with actual video ID
        # Add more videos here
    }

    # Analyze a video
    video_id = VIDEO_IDS["tutorial"]

    # Custom categories for educational content
    educational_categories = [
        ("positive feedback", 0.35),
        ("questions and confusion", 0.4),
        ("technical discussion", 0.35),
        ("suggestions for improvement", 0.4),
        ("criticize", 0.4)
    ]

    # Run analysis
    results = analyze_youtube_video(
        video_id=video_id,
        categories=educational_categories,
        max_comments=2000
    )

    # Generate and print report
    report = generate_video_report(video_id, results)
    print("\n\n" + "=" * 70)
    print("FINAL REPORT")
    print("=" * 70)
    print(report)

    # Save results to file
    output_data = {
        "video_id": video_id,
        "analysis": {
            category: [
                {
                    "id": cluster.id,
                    "size": cluster.size,
                    "summary": cluster.summary,
                    "avg_likes": cluster.avg_likes,
                    "avg_distance": cluster.avg_distance,
                    "top_comments": cluster.representative_comments[:3]
                }
                for cluster in clusters
            ]
            for category, clusters in results.items()
        }
    }

    with open(f"video_{video_id}_analysis.json", "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\nResults saved to video_{video_id}_analysis.json")

    # Find insights
    print("\n\nKEY INSIGHTS:")
    print("=" * 50)

    # Most discussed topics
    if results:
        largest_category = max(results.items(),
                               key=lambda x: sum(c.size for c in x[1]))
        total_in_largest = sum(c.size for c in largest_category[1])
        print(f"Most comments are about: {largest_category[0]} ({total_in_largest} comments)")

    # Highest engagement clusters
    all_clusters = []
    for category, clusters in results.items():
        for cluster in clusters:
            cluster.category = category  # Add category info
            all_clusters.append(cluster)

    if all_clusters:
        highest_engagement = max(all_clusters, key=lambda c: c.avg_likes)
        print(f"\nHighest engagement topic: {highest_engagement.category}")
        print(f"  Summary: {highest_engagement.summary}")
        print(f"  Average likes: {highest_engagement.avg_likes:.1f}")


if __name__ == "__main__":
    main()