# YouTube Comment Analyzer Configuration

# Embedding Configuration
EMBED_MODEL = "models/text-embedding-004"  # Google's embedding model
EMBED_DIM = 768  # Dimension for text-embedding-004
BATCH_SIZE = 20  # Max texts per embedding API call

# Generation Configuration
GENERATION_MODEL = "gemini-2.0-flash"  # Model for generating examples and summaries
NUM_EXAMPLES = 10  # Number of examples to generate per category
EXAMPLE_GENERATION_TEMPERATURE = 0.3  # Lower temperature for more consistent examples

# Retry Configuration
BACKOFF_DELAYS = [0.5, 1, 2, 4]  # Seconds between retries on API errors

# Analysis Configuration
DEFAULT_K_COMMENTS = 50  # Default number of top comments to retrieve
DEFAULT_N_CLUSTERS = 5  # Default number of clusters
DEFAULT_POPULARITY_WEIGHT = 0.3  # Default weight for popularity vs semantic similarity
DEFAULT_IGNORE_POPULARITY = True  # Default to pure semantic search
DEFAULT_DISTANCE_METHOD = "minimum"  # Default distance calculation method ("minimum" works best)
DEFAULT_DISTANCE_THRESHOLD = 0.4  # Default distance threshold (0-1, lower is stricter)
DEFAULT_POPULARITY_IMPACT = 0.5  # How much to weight popular comments in clustering (0-1)

# Clustering Configuration
KMEANS_N_INIT = 10  # Number of times KMeans will run with different seeds
KMEANS_RANDOM_STATE = 42  # Random state for reproducibility

# Summarization Configuration
MAX_COMMENTS_PER_CLUSTER_SUMMARY = 10  # Max comments to include in cluster summary