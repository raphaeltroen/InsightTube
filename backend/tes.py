"""
Test script to validate that the analyzer correctly distinguishes between different comment categories
"""

from API_KEYS import YOUTUBE_API_KEY, GOOGLE_API_KEY
from analyzer import Comment, YouTubeCommentAnalyzer


def test_category_detection():
    # Create test comments that clearly belong to specific categories
    test_comments = [
        # Positive comments
        Comment("This is amazing! Best explanation ever!", likes=10, reply_count=0),
        Comment("Love this video so much, thank you!", likes=5, reply_count=0),
        Comment("Brilliant work, absolutely fantastic!", likes=3, reply_count=0),

        # Constructive criticism
        Comment("Good video but the audio could be clearer in the second half", likes=15, reply_count=2),
        Comment("Great content! One suggestion: add timestamps for easier navigation", likes=8, reply_count=1),
        Comment("Nice explanation, though I think you could slow down a bit for beginners", likes=12, reply_count=0),

        # Humor
        Comment("LOL the animation at 3:42 killed me 😂", likes=50, reply_count=5),
        Comment("Why did the neural network go to therapy? Too many deep issues!", likes=30, reply_count=3),
        Comment("This video is funnier than my attempts at understanding calculus", likes=20, reply_count=2),

        # Confused
        Comment("I don't understand the part about backpropagation, can someone help?", likes=5, reply_count=10),
        Comment("Lost me at the matrix multiplication... what?", likes=3, reply_count=5),
        Comment("Still confused after watching 3 times, need more basic explanation", likes=7, reply_count=8),

        # Negative
        Comment("This video is useless, doesn't explain anything properly", likes=2, reply_count=1),
        Comment("Waste of time, terrible explanation", likes=1, reply_count=0),
        Comment("Worst tutorial I've seen on this topic", likes=0, reply_count=0),

        # Technical
        Comment("The gradient descent implementation should use adaptive learning rate", likes=25, reply_count=4),
        Comment("For those interested, the time complexity is O(n^2) for this algorithm", likes=18, reply_count=2),
        Comment("You can optimize this using vectorization in NumPy", likes=22, reply_count=6),
    ]

    # Initialize analyzer
    analyzer = YouTubeCommentAnalyzer(google_api_key=GOOGLE_API_KEY, debug=False)
    analyzer.add_comments(test_comments)

    # Test categories
    categories = [
        ("positive", [0, 1, 2]),  # Expected indices of positive comments
        ("constructive criticism", [3, 4, 5]),
        ("humor", [6, 7, 8]),
        ("confused", [9, 10, 11]),
        ("negative", [12, 13, 14]),
        ("technical", [15, 16, 17])
    ]

    print("TESTING CATEGORY DETECTION ACCURACY")
    print("=" * 60)
    print("\nChecking if the analyzer correctly identifies comment categories...")

    for category, expected_indices in categories:
        print(f"\n\nTesting category: '{category}'")
        print("-" * 40)

        # Analyze with minimum distance method
        results = analyzer.analyze(
            filter_query=category,
            k_comments=5,
            ignore_popularity=True,
            distance_method="minimum"
        )

        # Check top 3 results
        print("\nTop 3 detected comments:")
        found_correct = 0

        for i, (comment, _, dist) in enumerate(results['filtered_comments'][:3], 1):
            # Find the index of this comment
            comment_idx = test_comments.index(comment)
            is_correct = comment_idx in expected_indices

            status = "✓ CORRECT" if is_correct else "✗ WRONG"
            if is_correct:
                found_correct += 1

            print(f"\n{i}. [{dist:.3f}] {status}")
            print(f"   {comment.text}")

        accuracy = (found_correct / 3) * 100
        print(f"\nAccuracy for '{category}': {accuracy:.0f}% ({found_correct}/3 correct)")

        # Show what the system thinks are the characteristics
        if found_correct < 3:
            print("\nExpected comments that were NOT in top 3:")
            for idx in expected_indices:
                if test_comments[idx] not in [c for c, _, _ in results['filtered_comments'][:3]]:
                    print(f"  - {test_comments[idx].text}")


def test_distance_methods():
    """Compare how different distance methods perform on ambiguous comments"""

    print("\n\n" + "=" * 60)
    print("TESTING DISTANCE METHODS ON AMBIGUOUS COMMENTS")
    print("=" * 60)

    # Comments that could fit multiple categories
    ambiguous_comments = [
        Comment("Great video! Maybe add subtitles?", likes=10, reply_count=0),
        Comment("LOL this is so confusing but in a funny way", likes=20, reply_count=2),
        Comment("The code example at 5:00 has a bug, should be i < n not i <= n", likes=15, reply_count=3),
    ]

    analyzer = YouTubeCommentAnalyzer(google_api_key=GOOGLE_API_KEY, debug=False)
    analyzer.add_comments(ambiguous_comments)

    categories = ["positive", "constructive criticism", "humor", "technical"]
    methods = ["average", "minimum", "weighted"]

    for i, comment in enumerate(ambiguous_comments):
        print(f"\n\nAmbiguous comment: \"{comment.text}\"")
        print("-" * 50)

        for method in methods:
            print(f"\n{method.upper()} method:")

            category_scores = []
            for category in categories:
                results = analyzer.analyze(
                    filter_query=category,
                    k_comments=1,
                    ignore_popularity=True,
                    distance_method=method
                )

                if results['filtered_comments'] and results['filtered_comments'][0][0] == comment:
                    distance = results['filtered_comments'][0][2]
                    category_scores.append((category, distance))

            # Sort by distance (lower is better)
            category_scores.sort(key=lambda x: x[1])

            for cat, dist in category_scores[:2]:  # Show top 2 matches
                print(f"  {cat}: {dist:.3f}")


if __name__ == "__main__":
    test_category_detection()
    test_distance_methods()