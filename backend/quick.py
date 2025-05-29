"""
Quick test to verify the analyzer is working correctly
"""

from API_KEYS import GOOGLE_API_KEY
from analyzer import Comment, YouTubeCommentAnalyzer


def quick_test():
    # Create some test comments
    test_comments = [
        # Positive
        Comment("This is amazing! Best video ever!", likes=100, reply_count=5),
        Comment("Love this so much, thank you!", likes=50, reply_count=2),

        # Constructive criticism
        Comment("Great content but the audio could be clearer", likes=30, reply_count=3),
        Comment("Good video, though I'd suggest adding timestamps", likes=25, reply_count=1),

        # Negative
        Comment("This video is terrible, waste of time", likes=5, reply_count=0),
        Comment("I don't like this at all", likes=3, reply_count=0),

        # Confused
        Comment("I don't understand the part about matrices", likes=10, reply_count=5),
        Comment("Can someone explain this? I'm lost", likes=8, reply_count=3),
    ]

    # Initialize analyzer
    print("Initializing analyzer...")
    analyzer = YouTubeCommentAnalyzer(google_api_key=GOOGLE_API_KEY, debug=True)
    analyzer.add_comments(test_comments)

    # Test different categories
    categories_to_test = [
        "positive",
        "constructive criticism",
        "negative",
        "confused"
    ]

    print("\nTesting category detection with minimum distance method:\n")

    for category in categories_to_test:
        print(f"\n{'=' * 60}")
        print(f"Testing category: '{category}'")
        print('=' * 60)

        try:
            results = analyzer.analyze(
                filter_query=category,
                k_comments=3,
                n_clusters=1,
                ignore_popularity=True,
                distance_method="minimum"
            )

            print("\nTop matches:")
            for i, (comment, _, dist) in enumerate(results['filtered_comments'], 1):
                print(f"{i}. [Distance: {dist:.3f}] {comment.text}")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    quick_test()