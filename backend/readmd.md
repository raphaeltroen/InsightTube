# YouTube Comment Analyzer - Documentation

A powerful tool for analyzing YouTube comments using AI-powered semantic search and clustering.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install streamlit pandas plotly google-api-python-client google-generativeai scikit-learn numpy
```

### 2. Set Up API Keys

Create `API_KEYS.py`:

```python
YOUTUBE_API_KEY = 'your-youtube-data-api-key'
GOOGLE_API_KEY = 'your-google-ai-api-key'
```

Get your keys from:
- **YouTube API**: [Google Cloud Console](https://console.cloud.google.com/)
- **Google AI**: [Google AI Studio](https://makersuite.google.com/app/apikey)

### 3. Run the UI

```bash
streamlit run youtube_ui.py
```

## 📁 Architecture

The system is split into backend and frontend:

```
youtube_backend.py   # Core API - handles data fetching and analysis
youtube_ui.py        # Streamlit UI - user interface
analyzer.py          # Low-level analyzer with embeddings
clustering.py        # Cluster analysis utilities
config.py           # Configuration settings
```

## 🎯 Backend API Usage

### Basic Usage

```python
from youtube_backend import YouTubeAnalysisBackend

# Initialize backend
backend = YouTubeAnalysisBackend(
    youtube_api_key="your-key",
    google_api_key="your-key"
)

# Load a video (fetches comments and computes embeddings)
video_data = backend.initialize_video(
    "https://www.youtube.com/watch?v=aircAruvnKk",
    max_comments=1000
)

# Search for different types of comments
positive = backend.search_comments("positive", threshold=0.35)
negative = backend.search_comments("negative", threshold=0.4)
technical = backend.search_comments("technical discussion", threshold=0.35)

# Custom searches
excited = backend.search_comments("excited about features", threshold=0.3)
questions = backend.search_comments("asking for help", threshold=0.4)
```

### Search Results

Each search returns an `AnalysisResult` object:

```python
result = backend.search_comments("positive", threshold=0.35)

# Access the data
print(f"Found {result.total_comments_found} comments")
print(f"That's {result.percentage_of_total:.1f}% of all comments")

# Iterate through clusters
for cluster in result.clusters:
    print(f"\nCluster {cluster.id}:")
    print(f"  Size: {cluster.size} comments")
    print(f"  Summary: {cluster.summary}")
    print(f"  Average likes: {cluster.avg_likes:.1f}")
    
    # Show top comments
    for comment in cluster.representative_comments[:3]:
        print(f"  - {comment}")
```

### Quick Analysis Function

```python
from youtube_backend import quick_analyze

# Analyze a video with one function call
results = quick_analyze(
    video_url="https://youtube.com/watch?v=...",
    youtube_api_key="your-key",
    google_api_key="your-key",
    categories=["positive", "negative", "technical", "confused"]
)

# results is a dict: category -> AnalysisResult
for category, result in results.items():
    print(f"{category}: {result.total_comments_found} comments")
```

## 🔍 Search Types

### Predefined Categories

- **"positive"** - Appreciative, enthusiastic comments
- **"negative"** - Critical, disappointed comments  
- **"confused"** - Questions, confusion, asking for clarification
- **"technical"** - Technical discussions, code, algorithms
- **"humor"** - Jokes, memes, funny comments
- **"constructive criticism"** - Helpful feedback with suggestions

### Custom Searches

You can search for anything! Examples:

```python
# Specific reactions
backend.search_comments("excited about the announcement")
backend.search_comments("disappointed with changes")

# Questions about specific topics
backend.search_comments("questions about pricing")
backend.search_comments("asking about release date")

# Feature requests
backend.search_comments("requesting new features")
backend.search_comments("suggestions for improvement")

# Comparisons
backend.search_comments("comparing to competitors")
backend.search_comments("mentioning alternative products")
```

## ⚙️ Parameters

### Threshold

Controls how strict the matching is:
- **0.20-0.30**: Very strict, high precision
- **0.30-0.35**: Recommended for most uses
- **0.35-0.40**: More inclusive, good recall
- **0.40-0.50**: Very inclusive, may include false positives

### Clustering Parameters

- **n_clusters**: Number of sub-groups to create (default: 3)
- **popularity_impact**: How much to weight popular comments (0-1, default: 0.7)

## 💡 Advanced Examples

### Analyzing Comment Trends

```python
# Initialize once
backend.initialize_video("video_url", max_comments=2000)

# Search for different sentiments over time
sentiments = ["very positive", "neutral", "very negative"]
threshold_map = {"very positive": 0.3, "neutral": 0.4, "very negative": 0.35}

results = {}
for sentiment in sentiments:
    results[sentiment] = backend.search_comments(
        sentiment, 
        threshold=threshold_map[sentiment]
    )

# Compare results
for sentiment, result in results.items():
    print(f"{sentiment}: {result.percentage_of_total:.1f}%")
```

### Finding Specific Feedback

```python
# Look for specific types of feedback
feedback_types = [
    ("audio quality complaints", 0.35),
    ("video editing feedback", 0.35),
    ("content suggestions", 0.4),
    ("technical corrections", 0.3)
]

for query, threshold in feedback_types:
    result = backend.search_comments(query, threshold)
    if result.total_comments_found > 0:
        print(f"\n{query}: {result.total_comments_found} comments")
        # Show the main theme
        if result.clusters:
            print(f"Main theme: {result.clusters[0].summary}")
```

### Exporting Results

```python
from youtube_backend import export_results

# After running analyses
all_results = {
    "positive": backend.search_comments("positive", 0.35),
    "negative": backend.search_comments("negative", 0.4),
    "questions": backend.search_comments("questions", 0.4)
}

# Export to JSON
export_results(
    results=all_results,
    video_data=backend.get_video_info(),
    filename="my_analysis.json"
)
```

## 🐛 Troubleshooting

### Common Issues

1. **"No module named 'clustering'"**
   - Make sure you have `clustering.py` from the cluster_analysis module
   - The file should be in the same directory as the other files

2. **API Quota Errors**
   - YouTube API has daily quotas
   - Reduce `max_comments` to fetch fewer comments
   - Use caching to avoid re-fetching

3. **Slow Embedding Generation**
   - First run computes embeddings for all comments
   - This is cached for subsequent searches
   - Reduce comment count for faster testing

4. **No Results Found**
   - Try increasing the threshold (make it less strict)
   - Check if your search query makes sense
   - Try simpler, more general queries

### Performance Tips

1. **Use Caching**: The backend caches embeddings after first computation
2. **Batch Operations**: Initialize once, then run multiple searches
3. **Reasonable Limits**: 500-1000 comments is usually sufficient
4. **Specific Searches**: More specific queries often work better

## 📊 UI Features

The Streamlit UI provides:

- **Video Loading**: Enter any YouTube URL
- **Quick Searches**: One-click for common categories
- **Custom Search**: Search for anything you want
- **Visual Results**: Charts and cluster visualization
- **Export**: Download results as JSON
- **Multiple Searches**: Compare different search results

## 🔧 Configuration

Edit `config.py` to change defaults:

```python
DEFAULT_DISTANCE_THRESHOLD = 0.4    # Default threshold
DEFAULT_N_CLUSTERS = 3              # Default number of clusters  
DEFAULT_POPULARITY_IMPACT = 0.7     # Weight for popular comments
BATCH_SIZE = 20                     # API batch size
```

## 📚 API Reference

### YouTubeAnalysisBackend

```python
class YouTubeAnalysisBackend:
    def __init__(youtube_api_key: str, google_api_key: str, debug: bool = False)
    def initialize_video(video_id_or_url: str, max_comments: int) -> VideoData
    def search_comments(filter_query: str, threshold: float, n_clusters: int, popularity_impact: float) -> AnalysisResult
    def get_video_info() -> VideoData
    def reset()
```

### Data Classes

```python
@dataclass
class VideoData:
    video_id: str
    title: str
    channel: str
    views: int
    likes: int
    comment_count: int
    thumbnail_url: str
    comments: List[Dict]

@dataclass  
class AnalysisResult:
    category: str
    threshold: float
    clusters: List[Cluster]
    total_comments_found: int
    percentage_of_total: float

@dataclass
class Cluster:
    id: int
    comments: List[str]
    summary: str
    size: int
    avg_likes: float
    max_likes: int
    min_likes: int
    avg_distance: float
    representative_comments: List[str]
```

## 🚀 Next Steps

1. Try different search queries to find insights
2. Adjust thresholds for better results
3. Export and analyze trends
4. Create custom categories for your needs
5. Build on top of the backend API

Happy analyzing! 🎉