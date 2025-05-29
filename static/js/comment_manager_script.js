document.addEventListener('DOMContentLoaded', async function() {
    // Get DOM elements
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    const filters = {
        positive: document.getElementById('positive-filter'),
        negative: document.getElementById('negative-filter'),
        questions: document.getElementById('questions-filter'),
        suggestions: document.getElementById('suggestions-filter')
    };

    // Global state
    window.commentCache = window.commentCache || {};
    window.currentSearchQuery = '';
    window.isSearching = false;
    window.advancedOptions = {
        threshold: 0.4,
        clusters: 3
    };

    // Store all comments data
    let allCommentsData = {};
    let currentComments = [];

    // Add advanced options UI
    addAdvancedOptionsUI();

    // Check if we have cached data from video page
    if (window.analysisData && window.analysisData.results) {
        // Use cached data to avoid re-fetching
        processCachedResults(window.analysisData.results);
    } else {
        // Load initial data
        await loadAllCategories();
    }

    // Search functionality
    async function handleSearch() {
        const searchTerm = searchInput.value.trim();

        // Prevent duplicate searches
        if (searchTerm === window.currentSearchQuery && window.isSearching) {
            console.log('Search already in progress for:', searchTerm);
            return;
        }

        if (!searchTerm) {
            // Show filtered results based on checkboxes
            showFilteredComments();
            return;
        }

        // Check cache first
        const cacheKey = `${searchTerm}:${window.advancedOptions.threshold}:${window.advancedOptions.clusters}`;
        if (window.commentCache[cacheKey]) {
            console.log('Using cached results for:', searchTerm);
            displaySearchResults(window.commentCache[cacheKey]);
            return;
        }

        window.currentSearchQuery = searchTerm;
        window.isSearching = true;

        // Show loading state
        const container = document.querySelector('.comments-container');
        container.innerHTML = `
            <div class="search-loading">
                <div class="spinner"></div>
                <p>Searching for "${searchTerm}"...</p>
            </div>
        `;

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    category: searchTerm,
                    threshold: window.advancedOptions.threshold,
                    n_clusters: window.advancedOptions.clusters,
                    popularity_impact: 0.7
                })
            });

            const data = await response.json();

            if (data.success) {
                // Cache the results
                window.commentCache[cacheKey] = data;
                displaySearchResults(data);
            } else {
                showError('No results found for your search');
                container.innerHTML = '';
            }
        } catch (error) {
            console.error('Search error:', error);
            showError('Error performing search');
            container.innerHTML = '';
        } finally {
            window.isSearching = false;
        }
    }

    function displaySearchResults(data) {
        // Convert to comment format
        const searchResults = [];
        data.clusters.forEach(cluster => {
            cluster.all_comments.forEach((comment, idx) => {
                searchResults.push({
                    id: `search-${cluster.id}-${idx}`,
                    text: comment.text || comment,
                    type: 'custom',
                    author: comment.author,
                    timestamp: 'Recent'
                });
            });
        });

        currentComments = searchResults;

        // Show results header
        const container = document.querySelector('.comments-container');
        container.innerHTML = `
            <div class="search-results-header">
                <h3>Found ${data.total_found} comments (${data.percentage.toFixed(1)}% of total)</h3>
                <button onclick="clearSearch()" class="clear-search-btn">Clear Search</button>
            </div>
        `;

        // Display comments
        displayComments(searchResults);
    }

    function processCachedResults(results) {
        // Process cached results from video page
        Object.entries(results).forEach(([category, result]) => {
            const comments = [];

            result.clusters.forEach(cluster => {
                cluster.representative_comments.forEach((comment, idx) => {
                    comments.push({
                        id: `${category}-${cluster.id}-${idx}`,
                        text: comment.text || comment,
                        type: mapCategoryToType(category),
                        author: comment.author,
                        timestamp: 'Recent'
                    });
                });
            });

            allCommentsData[mapCategoryToType(category)] = comments;
        });

        // Show all comments initially
        showFilteredComments();
    }

    // Load all category data
    async function loadAllCategories() {
        const container = document.querySelector('.comments-container');
        container.innerHTML = `
            <div class="loading-state">
                <div class="spinner"></div>
                <p>Loading comments...</p>
            </div>
        `;

        try {
            const response = await fetch('/api/batch_analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    categories: [
                        { name: 'positive', threshold: 0.35 },
                        { name: 'negative', threshold: 0.4 },
                        { name: 'questions', threshold: 0.4 },
                        { name: 'suggestions for improvement', threshold: 0.4 }
                    ]
                })
            });

            const data = await response.json();

            if (data.success) {
                processCachedResults(data.results);

                if (data.from_cache) {
                    showNotification('Using cached comment data', 'info');
                }
            } else {
                container.innerHTML = '<p class="error">Failed to load comments</p>';
            }
        } catch (error) {
            console.error('Error loading comments:', error);
            container.innerHTML = '<p class="error">Error loading comments</p>';
        }
    }

    // Filter comments based on checkboxes
    function showFilteredComments() {
        const activeFilters = Object.entries(filters)
            .filter(([_, element]) => element.checked)
            .map(([key]) => key);

        let commentsToShow = [];

        if (activeFilters.length === 0) {
            // Show all comments
            Object.values(allCommentsData).forEach(comments => {
                commentsToShow = commentsToShow.concat(comments);
            });
        } else {
            // Show only filtered comments
            activeFilters.forEach(filter => {
                if (allCommentsData[filter]) {
                    commentsToShow = commentsToShow.concat(allCommentsData[filter]);
                }
            });
        }

        currentComments = commentsToShow;
        displayComments(commentsToShow);
    }

    // Display comments
    function displayComments(commentsToShow) {
        const container = document.querySelector('.comments-container');
        const commentsHtml = commentsToShow.map(comment => `
            <div class="comment-card">
                <div class="comment-header">
                    <img src="${comment.author?.profileImageUrl || '/static/images/user-avatar.png'}" alt="User Avatar" class="user-avatar">
                    <div class="comment-info">
                        <div class="username">${escapeHtml(comment.author?.name || 'Anonymous')}</div>
                        <div class="timestamp">${comment.timestamp}</div>
                    </div>
                    <span class="comment-type ${comment.type}">${capitalizeFirst(comment.type)}</span>
                </div>
                <div class="comment-text">
                    ${escapeHtml(comment.text)}
                </div>
            </div>
        `).join('');

        container.innerHTML = commentsHtml || '<p class="no-results">No comments found</p>';
    }

    // Add advanced options UI
    function addAdvancedOptionsUI() {
        const searchSection = document.querySelector('.search-section');
        const advancedDiv = document.createElement('div');
        advancedDiv.className = 'advanced-options';
        advancedDiv.innerHTML = `
            <div class="advanced-toggle">
                <button onclick="toggleAdvancedOptions()" class="advanced-btn">
                    ⚙️ Advanced Options
                </button>
            </div>
            <div class="advanced-content" style="display: none;">
                <div class="option-group">
                    <label>
                        Search Threshold
                        <input type="range" id="threshold-slider" min="0.2" max="0.6" step="0.05" value="0.4">
                        <span id="threshold-value">0.4</span>
                    </label>
                    <p class="option-help">Lower = stricter matching, Higher = more inclusive</p>
                </div>
                <div class="option-group">
                    <label>
                        Number of Clusters
                        <input type="range" id="clusters-slider" min="1" max="5" step="1" value="3">
                        <span id="clusters-value">3</span>
                    </label>
                    <p class="option-help">Group similar comments into clusters</p>
                </div>
            </div>
        `;

        searchSection.appendChild(advancedDiv);

        // Add event listeners
        const thresholdSlider = document.getElementById('threshold-slider');
        const clustersSlider = document.getElementById('clusters-slider');

        thresholdSlider.addEventListener('input', function() {
            window.advancedOptions.threshold = parseFloat(this.value);
            document.getElementById('threshold-value').textContent = this.value;
        });

        clustersSlider.addEventListener('input', function() {
            window.advancedOptions.clusters = parseInt(this.value);
            document.getElementById('clusters-value').textContent = this.value;
        });
    }

    // Helper functions
    function mapCategoryToType(category) {
        const mapping = {
            'positive': 'positive',
            'negative': 'negative',
            'questions': 'question',
            'suggestions for improvement': 'suggestion'
        };
        return mapping[category] || 'other';
    }

    function capitalizeFirst(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    function escapeHtml(text) {
        // Create a textarea element to decode HTML entities
        const textarea = document.createElement('textarea');
        textarea.innerHTML = text;
        // Get decoded text and trim any leading/trailing whitespace
        const decodedText = textarea.value;
        // Replace line breaks with proper HTML line breaks and remove extra spaces
        return decodedText
            .replace(/\r?\n/g, '<br>')
            .replace(/^\s+/gm, ''); // Remove leading spaces from each line
    }

    function showError(message) {
        const container = document.querySelector('.comments-container');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        container.prepend(errorDiv);

        setTimeout(() => errorDiv.remove(), 3000);
    }

    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    // Event listeners
    searchBtn.addEventListener('click', handleSearch);
    searchInput.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') handleSearch();
    });

    // Add event listeners for filters
    Object.values(filters).forEach(filter => {
        filter.addEventListener('change', showFilteredComments);
    });

    // Global functions
    window.toggleAdvancedOptions = function() {
        const content = document.querySelector('.advanced-content');
        content.style.display = content.style.display === 'none' ? 'block' : 'none';
    };

    window.clearSearch = function() {
        searchInput.value = '';
        window.currentSearchQuery = '';
        showFilteredComments();
    };
});

// Add additional styles
const style = document.createElement('style');
style.textContent = `
    .search-loading {
        text-align: center;
        padding: 3rem;
    }
    
    .spinner {
        width: 40px;
        height: 40px;
        border: 3px solid #f3f3f3;
        border-top: 3px solid var(--primary-red);
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 0 auto 1rem;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    .cluster-info {
        font-size: 0.85rem;
        color: #666;
        font-style: italic;
        margin-top: 0.5rem;
        padding: 0.5rem;
        background: rgba(255, 0, 0, 0.03);
        border-radius: 6px;
    }
    
    .comment-type.other {
        background-color: rgba(128, 128, 128, 0.1);
        color: #666;
    }
    
    .no-comments {
        text-align: center;
        color: #666;
        padding: 3rem;
        font-size: 1.1rem;
    }
    
    .error {
        text-align: center;
        padding: 2rem;
        color: #d32f2f;
    }
    
    .error-message {
        background: #fee;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        color: #c00;
        text-align: center;
    }
    
    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        background: #4CAF50;
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        z-index: 1000;
        animation: slideIn 0.3s ease-out;
    }
    
    .search-results-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem;
        background: rgba(255, 0, 0, 0.03);
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    
    .search-results-header h3 {
        margin: 0;
        color: var(--primary-red);
        font-size: 1.1rem;
    }
    
    .clear-search-btn {
        background: white;
        border: 1px solid var(--primary-red);
        color: var(--primary-red);
        padding: 0.4rem 1rem;
        border-radius: 20px;
        cursor: pointer;
        font-size: 0.9rem;
        transition: all 0.3s ease;
    }
    
    .clear-search-btn:hover {
        background: var(--primary-red);
        color: white;
    }
    
    .advanced-options {
        margin-top: 1.5rem;
        border-top: 1px solid var(--border-color);
        padding-top: 1rem;
    }
    
    .advanced-btn {
        background: none;
        border: 1px solid var(--border-color);
        padding: 0.5rem 1rem;
        border-radius: 20px;
        cursor: pointer;
        font-size: 0.9rem;
        color: var(--text-gray);
        transition: all 0.3s ease;
    }
    
    .advanced-btn:hover {
        border-color: var(--primary-red);
        color: var(--primary-red);
    }
    
    .advanced-content {
        margin-top: 1rem;
        padding: 1rem;
        background: rgba(0, 0, 0, 0.02);
        border-radius: 8px;
    }
    
    .option-group {
        margin-bottom: 1rem;
    }
    
    .option-group label {
        display: block;
        font-weight: 600;
        margin-bottom: 0.5rem;
        color: var(--text-dark);
    }
    
    .option-group input[type="range"] {
        width: 100%;
        margin: 0.5rem 0;
    }
    
    .option-help {
        font-size: 0.85rem;
        color: var(--text-gray);
        margin-top: 0.3rem;
    }
    
    #threshold-value, #clusters-value {
        display: inline-block;
        min-width: 2rem;
        text-align: center;
        font-weight: bold;
        color: var(--primary-red);
    }
    
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);