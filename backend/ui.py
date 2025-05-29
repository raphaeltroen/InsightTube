"""
Fixed Streamlit UI for YouTube Comment Analysis
This version includes better error handling and workarounds for common issues
Run with: streamlit run ui_fixed.py
"""

# Fix for sklearn joblib issue
import os
os.environ["LOKY_PICKLER"] = "cloudpickle"

import streamlit as st
import pandas as pd
import time
import re
from datetime import datetime
import json

# Set page config first
st.set_page_config(
    page_title="YouTube Comment Analyzer",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Handle imports with detailed error messages
missing_dependencies = []

try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError as e:
    missing_dependencies.append("plotly")
    st.error(f"Plotly not installed: {e}")

try:
    from googleapiclient.discovery import build
except ImportError as e:
    missing_dependencies.append("google-api-python-client")
    st.error(f"Google API client not installed: {e}")

# Check for required files
if not os.path.exists("cluster_analysis.py") and not os.path.exists("clustering.py"):
    st.error("❌ cluster_analysis.py not found in current directory")
    st.info("Please ensure all files are in the same directory as ui_fixed.py")
    st.stop()

if not os.path.exists("API_KEYS.py"):
    st.error("❌ API_KEYS.py not found")
    st.code("""
# Create API_KEYS.py with:
YOUTUBE_API_KEY = 'your-youtube-api-key'
GOOGLE_API_KEY = 'your-google-api-key'
""")
    st.stop()

# Try to import cluster analysis
try:
    from clustering import analyze_comments, Cluster
except ImportError:
    try:
        from clustering import analyze_comments, Cluster
    except ImportError as e:
        st.error(f"❌ Could not import cluster_analysis: {e}")
        st.stop()

# Try to import API keys
try:
    from API_KEYS import YOUTUBE_API_KEY, GOOGLE_API_KEY
except ImportError as e:
    st.error(f"❌ Could not import API_KEYS: {e}")
    st.stop()

# Check if we have all dependencies
if missing_dependencies:
    st.error(f"❌ Missing dependencies: {', '.join(missing_dependencies)}")
    st.code(f"pip install {' '.join(missing_dependencies)}")
    st.stop()

# Simple CSS for better appearance
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem;
        background: linear-gradient(90deg, #ff0066 0%, #ff6b6b 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .cluster-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-left: 4px solid #ff0066;
    }
    .comment-box {
        background: #f8f9fa;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 5px;
        border-left: 3px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'comments' not in st.session_state:
    st.session_state.comments = []

def extract_video_id(url_or_id):
    """Extract video ID from YouTube URL."""
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

    if len(url_or_id) == 11:
        return url_or_id

    return None

@st.cache_data
def fetch_video_info(video_id):
    """Fetch video metadata from YouTube."""
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        request = youtube.videos().list(
            part='snippet,statistics',
            id=video_id
        )
        response = request.execute()

        if response['items']:
            return response['items'][0]
        return None
    except Exception as e:
        st.error(f"Error fetching video info: {e}")
        return None

@st.cache_data
def fetch_comments_cached(video_id, max_results=1000):
    """Fetch comments from YouTube."""
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

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

        return comments
    except Exception as e:
        st.error(f"Error fetching comments: {e}")
        return []

def create_simple_visualizations(clusters, category):
    """Create simple visualizations."""
    if not clusters:
        return None

    # Create data for visualization
    cluster_data = pd.DataFrame({
        'Cluster': [f"Cluster {c.id}" for c in clusters],
        'Size': [c.size for c in clusters],
        'Average Likes': [c.avg_likes for c in clusters]
    })

    # Create a simple bar chart
    fig = px.bar(
        cluster_data,
        x='Cluster',
        y='Size',
        title=f"{category.title()} Comments by Cluster",
        color='Average Likes',
        color_continuous_scale='Reds'
    )

    return fig

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🎬 YouTube Comment Analyzer</h1>
        <p>Discover insights from your audience with AI-powered analysis</p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")

        # Video input
        st.subheader("Video Selection")
        video_input = st.text_input(
            "Enter YouTube URL or Video ID",
            placeholder="https://www.youtube.com/watch?v=..."
        )

        # Analysis settings
        st.subheader("Analysis Parameters")

        max_comments = st.slider(
            "Maximum comments to analyze",
            min_value=100,
            max_value=2000,
            value=500,
            step=100
        )

        # Category settings
        st.subheader("Categories to Analyze")

        analyze_positive = st.checkbox("Positive Comments", value=True)
        positive_threshold = st.slider("Positive threshold", 0.2, 0.5, 0.35, 0.05,
                                     disabled=not analyze_positive)

        analyze_negative = st.checkbox("Negative Comments", value=True)
        negative_threshold = st.slider("Negative threshold", 0.2, 0.5, 0.4, 0.05,
                                     disabled=not analyze_negative)

        analyze_questions = st.checkbox("Questions/Confused", value=True)
        questions_threshold = st.slider("Questions threshold", 0.2, 0.5, 0.4, 0.05,
                                      disabled=not analyze_questions)

        # Custom filter
        st.subheader("Custom Filter (Optional)")
        custom_filter_enabled = st.checkbox("Enable custom filter")
        if custom_filter_enabled:
            custom_filter_name = st.text_input("Filter description",
                                             placeholder="e.g., 'excited about features'")
            custom_threshold = st.slider("Custom threshold", 0.2, 0.5, 0.35, 0.05)

        # Clustering settings
        st.subheader("Clustering Settings")
        n_clusters = st.slider("Clusters per category", 2, 5, 3)
        popularity_impact = st.slider("Popularity impact", 0.0, 1.0, 0.7, 0.1)

        # Analyze button
        analyze_button = st.button("🔍 Analyze Comments", type="primary", use_container_width=True)

    # Main content area
    if video_input and analyze_button:
        video_id = extract_video_id(video_input)

        if not video_id:
            st.error("Invalid YouTube URL or video ID")
            return

        # Fetch video info
        with st.spinner("Fetching video information..."):
            video_info = fetch_video_info(video_id)

        if not video_info:
            st.error("Could not fetch video information. Please check the video ID and your API key.")
            return

        # Display video info
        col1, col2 = st.columns([1, 3])
        with col1:
            st.image(video_info['snippet']['thumbnails']['medium']['url'])
        with col2:
            st.subheader(video_info['snippet']['title'])
            st.write(f"**Channel:** {video_info['snippet']['channelTitle']}")

            # Display metrics
            col_metrics = st.columns(3)
            with col_metrics[0]:
                views = int(video_info['statistics'].get('viewCount', 0))
                st.markdown(f"""
                <div class="metric-card">
                    <h3>{views:,}</h3>
                    <p>Views</p>
                </div>
                """, unsafe_allow_html=True)
            with col_metrics[1]:
                likes = int(video_info['statistics'].get('likeCount', 0))
                st.markdown(f"""
                <div class="metric-card">
                    <h3>{likes:,}</h3>
                    <p>Likes</p>
                </div>
                """, unsafe_allow_html=True)
            with col_metrics[2]:
                comment_count = int(video_info['statistics'].get('commentCount', 0))
                st.markdown(f"""
                <div class="metric-card">
                    <h3>{comment_count:,}</h3>
                    <p>Comments</p>
                </div>
                """, unsafe_allow_html=True)

        st.divider()

        # Fetch comments
        with st.spinner(f"Fetching up to {max_comments} comments..."):
            comments = fetch_comments_cached(video_id, max_comments)
            st.session_state.comments = comments

        if not comments:
            st.error("Could not fetch comments. Please check your API key and quota.")
            return

        st.success(f"Fetched {len(comments)} comments")

        # Prepare categories
        categories = []
        if analyze_positive:
            categories.append(("positive", positive_threshold))
        if analyze_negative:
            categories.append(("negative", negative_threshold))
        if analyze_questions:
            categories.append(("confused", questions_threshold))
        if custom_filter_enabled and custom_filter_name:
            categories.append((custom_filter_name, custom_threshold))

        if not categories:
            st.warning("Please select at least one category to analyze")
            return

        # Analyze comments
        st.header("📊 Analysis Results")

        results = {}

        for category, threshold in categories:
            with st.spinner(f"Analyzing {category} comments..."):
                try:
                    clusters = analyze_comments(
                        comments=comments,
                        filter_query=category,
                        threshold=threshold,
                        google_api_key=GOOGLE_API_KEY,
                        n_clusters=n_clusters,
                        popularity_impact=popularity_impact,
                        debug=False
                    )
                    results[category] = clusters

                    if clusters:
                        st.subheader(f"{category.title()} Comments")

                        # Summary
                        total_in_category = sum(c.size for c in clusters)
                        percentage = (total_in_category / len(comments)) * 100
                        st.write(f"Found **{total_in_category}** {category} comments ({percentage:.1f}% of total)")

                        # Visualization
                        fig = create_simple_visualizations(clusters, category)
                        if fig:
                            st.plotly_chart(fig, use_container_width=True)

                        # Cluster details
                        for cluster in sorted(clusters, key=lambda c: c.size, reverse=True):
                            st.markdown(f"""
                            <div class="cluster-card">
                                <h3>Cluster {cluster.id} ({cluster.size} comments)</h3>
                                <p><strong>Summary:</strong> {cluster.summary}</p>
                                <p><strong>Average likes:</strong> {cluster.avg_likes:.1f} | 
                                   <strong>Max likes:</strong> {cluster.max_likes}</p>
                            </div>
                            """, unsafe_allow_html=True)

                            # Show top comments
                            if cluster.representative_comments:
                                with st.expander("Show top comments"):
                                    for comment in cluster.representative_comments[:3]:
                                        st.markdown(f"""
                                        <div class="comment-box">
                                            {comment[:200] + '...' if len(comment) > 200 else comment}
                                        </div>
                                        """, unsafe_allow_html=True)
                    else:
                        st.info(f"No {category} comments found with threshold {threshold}")

                except Exception as e:
                    st.error(f"Error analyzing {category}: {str(e)}")
                    st.info("Try adjusting the threshold or check your API quota")

        st.session_state.analysis_results = results

        # Export functionality
        if results:
            st.divider()
            st.subheader("💾 Export Results")

            # Prepare export data
            export_data = {
                "video_id": video_id,
                "video_title": video_info['snippet']['title'],
                "analysis_date": datetime.now().isoformat(),
                "total_comments": len(comments),
                "categories": {}
            }

            for category, clusters in results.items():
                export_data["categories"][category] = [
                    {
                        "cluster_id": c.id,
                        "size": c.size,
                        "summary": c.summary,
                        "avg_likes": c.avg_likes,
                        "top_comments": c.representative_comments[:3] if hasattr(c, 'representative_comments') else []
                    }
                    for c in clusters
                ]

            # Download button
            st.download_button(
                label="📥 Download JSON Report",
                data=json.dumps(export_data, indent=2),
                file_name=f"youtube_analysis_{video_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )

            st.success("Analysis complete! 🎉")

    elif not video_input:
        # Welcome message
        st.info("👈 Enter a YouTube video URL in the sidebar to get started!")

        # Example videos
        st.subheader("Example Videos to Try:")
        examples = [
            ("3Blue1Brown - Neural Networks", "https://www.youtube.com/watch?v=aircAruvnKk"),
            ("Veritasium - Math Video", "https://www.youtube.com/watch?v=HeQX2HjkcNo"),
            ("Any YouTube URL", "Just paste the URL in the sidebar!")
        ]

        for title, url in examples:
            st.write(f"• **{title}**: `{url}`")

if __name__ == "__main__":
    main()