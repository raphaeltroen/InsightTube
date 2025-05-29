import os
from googleapiclient.discovery import build

from API_KEYS import YOUTUBE_API_KEY, GOOGLE_API_KEY
from analyzer import Comment, YouTubeCommentAnalyzer
from config import DEFAULT_N_CLUSTERS, DEFAULT_DISTANCE_THRESHOLD, DEFAULT_POPULARITY_IMPACT


def fetch_youtube_comments(video_id: str, api_key: str, max_results: int = 100):
    """
    Fetch comments from a YouTube video

    Args:
        video_id: YouTube video ID
        api_key: YouTube Data API key
        max_results: Maximum number of comments to fetch

    Returns:
        List of Comment objects
    """
    youtube = build('youtube', 'v3', developerKey=api_key)

    comments = []
    next_page_token = None

    while len(comments) < max_results:
        # Request comments
        request = youtube.commentThreads().list(
            part='snippet',
            videoId=video_id,
            maxResults=min(100, max_results - len(comments)),
            pageToken=next_page_token
        )
        response = request.execute()

        # Parse comments
        for item in response['items']:
            snippet = item['snippet']['topLevelComment']['snippet']
            comment = Comment(
                text=snippet['textDisplay'],
                likes=snippet['likeCount'],
                reply_count=item['snippet']['totalReplyCount'],
                comment_id=item['id'],
                author=snippet['authorDisplayName']
            )
            comments.append(comment)

        # Check for next page
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break

    return comments


def main():
    # Video ID to analyze
    VIDEO_ID = 'DZIASl9q90s'  # Replace with your video ID

    # Fetch comments from YouTube
    print("Fetching comments from YouTube...")
    comments = fetch_youtube_comments(VIDEO_ID, YOUTUBE_API_KEY, max_results=200)
    print(f"Fetched {len(comments)} comments")

    # Initialize analyzer with Google embeddings (debug=True to see generated examples)
    analyzer = YouTubeCommentAnalyzer(google_api_key=GOOGLE_API_KEY, debug=True)

    # Add comments to analyzer
    analyzer.add_comments(comments)

    # Define categories to analyze with their thresholds
    categories_with_thresholds = [
        ("positive", 0.35),  # Stricter threshold for positive comments
        ("criticize", 0.35),  # More lenient for criticism
        ("negative", 0.35),
        ("confused", 0.35)
    ]

    print("\n" + "="*70)
    print("THRESHOLD-BASED CATEGORY DETECTION WITH WEIGHTED CLUSTERING")
    print("="*70)
    print(f"\nDefault popularity impact in clustering: {DEFAULT_POPULARITY_IMPACT}")

    for category, threshold in categories_with_thresholds:
        print(f"\n{'=' * 60}")
        print(f"Category: '{category}' (threshold: {threshold})")
        print('=' * 60)

        try:
            results = analyzer.analyze_with_threshold(
                filter_query=category,
                distance_threshold=threshold,
                n_clusters=3,  # Try to find 3 sub-themes within each category
                ignore_popularity=True,  # Pure semantic filtering
                distance_method="minimum",
                popularity_impact=0.7  # High impact of popularity in clustering
            )

            # Show statistics
            stats = results['stats']
            print(f"\nStatistics:")
            print(f"  Total comments analyzed: {stats['total_comments']:,}")
            print(f"  Comments matching '{category}': {stats['filtered_comments']:,}")
            print(f"  Percentage: {100 * stats['filtered_comments'] / stats['total_comments']:.1f}%")
            print(f"  Distance range: {stats['min_distance']:.3f} - {stats['max_distance']:.3f}")
            print(f"  Average distance: {stats['avg_distance']:.3f}")
            print(f"  Clusters created: {stats['clusters_created']}")

            # Show top comments from each cluster
            print(f"\nClusters and their themes:")
            for cluster_id, cluster_comments in results['clusters'].items():
                # Get cluster summary
                summary = results['summaries'].get(cluster_id, "No summary available")
                
                # Calculate cluster statistics
                cluster_likes = [c.likes for c in cluster_comments]
                avg_likes = sum(cluster_likes) / len(cluster_likes) if cluster_likes else 0
                max_likes = max(cluster_likes) if cluster_likes else 0
                
                print(f"\n--- Cluster {cluster_id} ({len(cluster_comments)} comments) ---")
                print(f"Average likes: {avg_likes:.1f}, Max likes: {max_likes}")
                print(f"Theme: {summary}")
                
                # Show top 3 representatives
                reps = results['representatives'].get(cluster_id, [])[:3]
                if reps:
                    print("\nTop comments:")
                    for i, comment in enumerate(reps, 1):
                        text = comment.text[:100] + "..." if len(comment.text) > 100 else comment.text
                        print(f"  {i}. [Likes: {comment.likes}] {text}")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Test different thresholds for a single category
    print("\n\n" + "="*70)
    print("THRESHOLD SENSITIVITY ANALYSIS")
    print("="*70)
    
    test_category = "positive"
    thresholds = [0.3, 0.35, 0.4, 0.45, 0.5]
    
    print(f"\nTesting different thresholds for '{test_category}':")
    print(f"{'Threshold':<10} {'Comments':<10} {'Percentage':<10} {'Avg Dist':<10}")
    print("-" * 40)
    
    for threshold in thresholds:
        results = analyzer.analyze_with_threshold(
            filter_query=test_category,
            distance_threshold=threshold,
            n_clusters=3,
            ignore_popularity=True,
            distance_method="minimum",
            popularity_impact=0.5
        )
        
        stats = results['stats']
        percentage = 100 * stats['filtered_comments'] / stats['total_comments']
        print(f"{threshold:<10.2f} {stats['filtered_comments']:<10} {percentage:<10.1f} {stats['avg_distance']:<10.3f}")

    # Demonstrate finding very specific types with strict thresholds
    print("\n\n" + "="*70)
    print("FINDING SPECIFIC COMMENT TYPES WITH STRICT THRESHOLDS")
    print("="*70)
    
    specific_queries = [
        ("questions about implementation", 0.3),
        ("complaints about audio quality", 0.35),
        ("expressing confusion about math", 0.35),
        ("extremely positive feedback", 0.25)
    ]
    
    # Turn off debug for cleaner output
    analyzer.debug = False
    
    for query, threshold in specific_queries:
        print(f"\n--- {query} (threshold: {threshold}) ---")
        results = analyzer.analyze_with_threshold(
            filter_query=query,
            distance_threshold=threshold,
            n_clusters=2,
            ignore_popularity=True,
            distance_method="minimum",
            popularity_impact=0.5
        )
        
        stats = results['stats']
        print(f"Found {stats['filtered_comments']} matching comments")
        
        if stats['filtered_comments'] > 0:
            # Show top 3 by popularity from all filtered comments
            filtered_sorted = sorted(results['filtered_comments'], 
                                   key=lambda x: x[0].likes, 
                                   reverse=True)[:3]
            
            print("\nMost popular matches:")
            for i, (comment, _, dist) in enumerate(filtered_sorted, 1):
                text = comment.text[:80] + "..." if len(comment.text) > 80 else comment.text
                print(f"{i}. [Dist: {dist:.3f}, Likes: {comment.likes}] {text}")


if __name__ == "__main__":
    main()