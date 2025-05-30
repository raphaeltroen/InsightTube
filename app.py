from flask import Flask, render_template, request, jsonify, session
import os
import sys
import json
from datetime import datetime
import hashlib
import time

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from youtube_backend import YouTubeAnalysisBackend, VideoData, AnalysisResult
from backend.API_KEYS import YOUTUBE_API_KEY, GOOGLE_API_KEY

app = Flask(__name__,
            static_folder='static',
            template_folder='templates')
app.secret_key = 'your-secret-key-here'  # Change this in production

# Global storage
backends = {}
search_cache = {}  # Cache for search results
video_cache = {}  # Cache for video data


class CachedBackend:
    """Wrapper around YouTubeAnalysisBackend with caching"""

    def __init__(self, backend):
        self.backend = backend
        self.search_cache = {}
        self.last_batch_analyze = None

    def search_comments(self, filter_query, threshold, n_clusters, popularity_impact):
        # Create cache key
        cache_key = f"{filter_query}:{threshold}:{n_clusters}:{popularity_impact}"

        # Check cache
        if cache_key in self.search_cache:
            print(f"[CACHE HIT] Returning cached results for: {filter_query}")
            return self.search_cache[cache_key]

        # Perform search
        print(f"[CACHE MISS] Performing new search for: {filter_query}")
        result = self.backend.search_comments(filter_query, threshold, n_clusters, popularity_impact)

        # Cache result
        self.search_cache[cache_key] = result
        return result


@app.route('/')
def index():
    return render_template('main_page.html')


@app.route('/video/<video_id>')
def video_page(video_id):
    return render_template('video_page.html')


@app.route('/comments/<video_id>')
def comments_page(video_id):
    return render_template('comment_manager.html')


@app.route('/suggestions/<video_id>')
def suggestions_page(video_id):
    # Try to get video_data from cache or backend
    video_data = None
    if video_id in video_cache:
        video_data = video_cache[video_id]
    else:
        # Try to get from backend if available
        session_id = session.get('session_id')
        if session_id and session_id in backends:
            backend = backends[session_id].backend
            if backend.video_data and backend.video_data.video_id == video_id:
                video_data = {
                    'title': backend.video_data.title,
                    'channel': backend.video_data.channel,
                    'views': backend.video_data.views,
                    'likes': backend.video_data.likes,
                    'comment_count': backend.video_data.comment_count,
                    'thumbnail_url': backend.video_data.thumbnail_url,
                    'channel_profile_pic': backend.video_data.channel_profile_pic,
                    'total_fetched': len(backend.video_data.comments)
                }
    return render_template('suggestions.html', video_data=video_data)


@app.route('/api/process', methods=['POST'])
def process_video():
    """Initialize video and prepare for analysis"""
    try:
        data = request.get_json()
        video_url = data.get('url', '')

        # Extract video ID for caching
        import re
        video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', video_url)
        video_id = video_id_match.group(1) if video_id_match else None

        if not video_id:
            return jsonify({'success': False, 'error': 'Invalid YouTube URL'}), 400

        # Check video cache first
        if video_id in video_cache:
            print(f"[VIDEO CACHE HIT] Using cached data for video: {video_id}")
            session['video_id'] = video_id
            return jsonify({
                'success': True,
                'video_id': video_id,
                'video_data': video_cache[video_id],
                'from_cache': True
            })

        # Create session ID
        session_id = session.get('session_id', None)
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id

        # Initialize backend
        print(f"[VIDEO CACHE MISS] Fetching new data for video: {video_id}")
        backend = YouTubeAnalysisBackend(
            youtube_api_key=YOUTUBE_API_KEY,
            google_api_key=GOOGLE_API_KEY,
            debug=False
        )

        # Initialize video (fetch comments and compute embeddings)
        start_time = time.time()
        video_data = backend.initialize_video(video_url, max_comments=10)
        print(f"Video initialization took {time.time() - start_time:.2f} seconds")

        # Store backend with caching wrapper
        cached_backend = CachedBackend(backend)
        backends[session_id] = cached_backend

        # Cache video data
        video_info = {
            'title': video_data.title,
            'channel': video_data.channel,
            'views': video_data.views,
            'likes': video_data.likes,
            'comment_count': video_data.comment_count,
            'thumbnail_url': video_data.thumbnail_url,
             'channel_profile_pic': video_data.channel_profile_pic,
            'total_fetched': len(video_data.comments)
        }
        video_cache[video_id] = video_info
        session['video_id'] = video_id

        return jsonify({
            'success': True,
            'video_id': video_data.video_id,
            'video_data': video_info,
            'from_cache': False
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/analyze', methods=['POST'])
def analyze_comments():
    """Analyze comments for a specific category"""
    try:
        data = request.get_json()
        category = data.get('category', 'positive')
        threshold = data.get('threshold', 0.35)
        n_clusters = data.get('n_clusters', 3)
        popularity_impact = data.get('popularity_impact', 0.7)

        # Get backend from session
        session_id = session.get('session_id')
        if not session_id or session_id not in backends:
            return jsonify({
                'success': False,
                'error': 'No video loaded. Please process a video first.'
            }), 400

        cached_backend = backends[session_id]

        # Perform analysis (with caching)
        result = cached_backend.search_comments(
            filter_query=category,
            threshold=threshold,
            n_clusters=n_clusters,
            popularity_impact=popularity_impact
        )

        # Convert clusters to JSON-serializable format
        clusters_data = []
        for cluster in result.clusters:
            clusters_data.append({
                'id': cluster.id,
                'size': cluster.size,
                'summary': cluster.summary,
                'avg_likes': cluster.avg_likes,
                'max_likes': cluster.max_likes,
                'min_likes': cluster.min_likes,
                'representative_comments': cluster.representative_comments[:5],
                'all_comments': cluster.comments[:10]  # Limit for performance
            })

        return jsonify({
            'success': True,
            'category': result.category,
            'total_found': result.total_comments_found,
            'percentage': result.percentage_of_total,
            'clusters': clusters_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/batch_analyze', methods=['POST'])
def batch_analyze():
    """Analyze multiple categories at once with caching"""
    try:
        data = request.get_json()
        categories = data.get('categories', [
            {'name': 'positive', 'threshold': 0.35},
            {'name': 'negative', 'threshold': 0.4},
            {'name': 'confused', 'threshold': 0.4},
            {'name': 'suggestions', 'threshold': 0.4}
        ])
        force_refresh = data.get('force_refresh', False)

        session_id = session.get('session_id')
        if not session_id or session_id not in backends:
            return jsonify({
                'success': False,
                'error': 'No video loaded.'
            }), 400

        cached_backend = backends[session_id]

        # Check if we have cached batch results (unless force refresh)
        if not force_refresh and cached_backend.last_batch_analyze:
            cached_categories = cached_backend.last_batch_analyze.get('categories', [])
            if json.dumps(categories, sort_keys=True) == json.dumps(cached_categories, sort_keys=True):
                print("[BATCH CACHE HIT] Returning cached batch analysis")
                return jsonify({
                    'success': True,
                    'results': cached_backend.last_batch_analyze['results'],
                    'from_cache': True
                })

        print("[BATCH CACHE MISS] Performing new batch analysis")
        results = {}

        for cat in categories:
            result = cached_backend.search_comments(
                filter_query=cat['name'],
                threshold=cat.get('threshold', 0.4),
                n_clusters=cat.get('n_clusters', 3),
                popularity_impact=cat.get('popularity_impact', 0.7)
            )

            clusters_data = []
            for cluster in result.clusters:
                clusters_data.append({
                    'id': cluster.id,
                    'size': cluster.size,
                    'summary': cluster.summary,
                    'avg_likes': cluster.avg_likes,
                    'representative_comments': cluster.representative_comments[:3]
                })

            results[cat['name']] = {
                'total_found': result.total_comments_found,
                'percentage': result.percentage_of_total,
                'clusters': clusters_data,
                'category_summary': result.category_summary
            }

        # Cache batch results
        cached_backend.last_batch_analyze = {
            'categories': categories,
            'results': results
        }

        return jsonify({
            'success': True,
            'results': results,
            'from_cache': False
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/video_info', methods=['GET'])
def get_video_info():
    """Get current video information"""
    video_id = session.get('video_id')
    if video_id and video_id in video_cache:
        return jsonify({
            'success': True,
            'video_data': video_cache[video_id]
        })

    return jsonify({
        'success': False,
        'error': 'No video data available.'
    }), 400


@app.route('/api/typical_viewer', methods=['GET'])
def get_typical_viewer():
    """Generate typical viewer profile based on comments"""
    session_id = session.get('session_id')
    if not session_id or session_id not in backends:
        return jsonify({
            'success': False,
            'error': 'No video loaded.'
        }), 400

    try:
        cached_backend = backends[session_id]

        # Analyze different aspects
        positive = cached_backend.search_comments('positive', threshold=0.35, n_clusters=3, popularity_impact=0.7)
        negative = cached_backend.search_comments('negative or criticism', threshold=0.4, n_clusters=3,
                                                  popularity_impact=0.7)
        questions = cached_backend.search_comments('confused or questions', threshold=0.4, n_clusters=3,
                                                   popularity_impact=0.7)
        technical = cached_backend.search_comments('technical discussion', threshold=0.4, n_clusters=2,
                                                   popularity_impact=0.5)

        # Generate concise bullet points for likes and dislikes
        positive_summaries = [cluster.summary for cluster in positive.clusters if cluster.size > 2]
        negative_summaries = [cluster.summary for cluster in negative.clusters if cluster.size > 1]

        likes = cached_backend.backend.analyzer.generate_concise_bullets(positive_summaries, "positive")
        dislikes = cached_backend.backend.analyzer.generate_concise_bullets(negative_summaries, "negative")

        # Extract other insights
        interests = []
        characteristics = []

        # Process questions for interests
        if questions.clusters:
            for cluster in questions.clusters[:2]:
                if cluster.size > 1:
                    interests.append(f"Frequently asks about: {cluster.summary}")

        # Technical interest level
        tech_percentage = technical.percentage_of_total
        if tech_percentage > 10:
            characteristics.append("Technically inclined")
            interests.append("Interested in technical details and implementation")

        # Engagement level based on positive percentage
        engagement_level = "High" if positive.percentage_of_total > 50 else "Moderate" if positive.percentage_of_total > 30 else "Low"

        # Add some personality traits based on comment patterns
        if positive.percentage_of_total > negative.percentage_of_total * 2:
            characteristics.append("Generally supportive and encouraging")
        if questions.percentage_of_total > 15:
            characteristics.append("Curious and eager to learn")

        return jsonify({
            'success': True,
            'profile': {
                'likes': likes if likes else ["Appreciates clear explanations", "Values quality content", "Enjoys the presentation style"],
                'dislikes': dislikes if dislikes else ["Mentions audio quality issues", "Notes lengthy introductions", "Suggests better pacing"],
                'interests': interests[:3] if interests else ["Your topic area", "Learning new things", "Practical applications"],
                'characteristics': characteristics[:3] if characteristics else ["Engaged viewer", "Regular watcher"],
                'engagement_level': engagement_level,
                'stats': {
                    'positive_percentage': round(positive.percentage_of_total, 1),
                    'question_percentage': round(questions.percentage_of_total, 1),
                    'technical_interest': round(tech_percentage, 1)
                }
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/get_suggestions', methods=['GET'])
def get_suggestions():
    """Get content suggestions based on comment analysis"""
    session_id = session.get('session_id')
    if not session_id or session_id not in backends:
        return jsonify({
            'success': False,
            'error': 'No video loaded.'
        }), 400

    try:
        cached_backend = backends[session_id]

        # Analyze for different types of suggestions
        requests = cached_backend.search_comments('viewers asking for or requesting', threshold=0.4, n_clusters=5,
                                                  popularity_impact=0.8)
        questions = cached_backend.search_comments('questions about specific topics', threshold=0.4, n_clusters=5,
                                                   popularity_impact=0.7)
        improvements = cached_backend.search_comments('suggestions for improvement or better', threshold=0.4,
                                                      n_clusters=3, popularity_impact=0.7)
        confusion = cached_backend.search_comments('confused or unclear about', threshold=0.4, n_clusters=3,
                                                   popularity_impact=0.6)

        all_suggestions = []

        # Extract content requests
        for cluster in requests.clusters:
            if cluster.size >= 2:
                all_suggestions.append({
                    'title': f"Video request: {cluster.summary}",
                    'support_count': cluster.size,
                    'avg_engagement': cluster.avg_likes,
                    'type': 'request'
                })

        # Extract topics that need clarification
        for cluster in confusion.clusters:
            if cluster.size >= 3:
                all_suggestions.append({
                    'title': f"Clarification video on: {cluster.summary}",
                    'support_count': cluster.size,
                    'avg_engagement': cluster.avg_likes,
                    'type': 'clarification'
                })

        # Extract improvement suggestions
        for cluster in improvements.clusters:
            if cluster.size >= 2:
                all_suggestions.append({
                    'title': f"Improvement: {cluster.summary}",
                    'support_count': cluster.size,
                    'avg_engagement': cluster.avg_likes,
                    'type': 'improvement'
                })

        # Sort by support count and engagement
        all_suggestions.sort(key=lambda x: x['support_count'] * 2 + x['avg_engagement'], reverse=True)

        # Analyze what viewers want to see more of (actual comments)
        viewer_interests = []
        # Use a more explicit prompt to find comments suggesting new content
        prompt = (
            "Find 3 comments in which viewers: "
            "(1) request a type of video or content, "
            "(2) suggest a new idea for a video, or "
            "(3) describe a new idea they would like the creator to make. "
            "Return only comments that clearly express a request or suggestion for new content or video ideas."
        )
        result = cached_backend.search_comments(prompt, threshold=0.4, n_clusters=3, popularity_impact=0.7)
        # Collect up to 3 representative comments from the clusters
        for cluster in result.clusters:
            for comment in cluster.representative_comments:
                if len(viewer_interests) < 3:
                    viewer_interests.append(f'"{comment.strip()}"')
                else:
                    break
            if len(viewer_interests) >= 3:
                break
        # If not enough, fallback to previous logic for remaining slots
        if len(viewer_interests) < 3:
            content_types = [
                ('tutorial or how-to content', 'Tutorial videos'),
                ('behind the scenes', 'Behind-the-scenes content'),
                ('deep dive or detailed explanation', 'In-depth analysis videos'),
                ('tips and tricks', 'Tips and tricks videos'),
                ('beginner friendly', 'Beginner-friendly content'),
                ('advanced topics', 'Advanced level content')
            ]
            for search_term, display_name in content_types:
                fallback_result = cached_backend.search_comments(search_term, threshold=0.45, n_clusters=1, popularity_impact=0.5)
                if fallback_result.total_comments_found > 2 and len(viewer_interests) < 3:
                    viewer_interests.append(display_name)
                if len(viewer_interests) >= 3:
                    break

        return jsonify({
            'success': True,
            'suggestions': all_suggestions[:8],  # Top 8 suggestions
            'viewer_interests': viewer_interests[:3]  # Top 3 actual comments or fallback
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/clear_cache', methods=['POST'])
def clear_cache():
    """Clear cache for current session"""
    session_id = session.get('session_id')
    if session_id and session_id in backends:
        backends[session_id].search_cache = {}
        backends[session_id].last_batch_analyze = None
        return jsonify({'success': True, 'message': 'Cache cleared'})
    return jsonify({'success': False, 'error': 'No active session'})


# Cleanup old sessions periodically
@app.before_request
def cleanup_old_sessions():
    global backends
    if len(backends) > 50:  # Increased limit
        # Keep only the 20 most recent sessions
        import itertools
        backends = dict(itertools.islice(backends.items(), 20))


if __name__ == '__main__':
    app.run(debug=True, port=5000)