document.addEventListener('DOMContentLoaded', async function() {
    // Global state
    window.analysisData = window.analysisData || {};
    window.isAnalyzing = false;

    // Load video data
    const videoData = JSON.parse(localStorage.getItem('video_data') || '{}');
    const videoId = localStorage.getItem('current_video_id');

    // Update video info
    if (videoData.title) {
        document.getElementById('video-title').textContent = videoData.title;
        document.getElementById('video-thumbnail').src = videoData.thumbnail_url;
    }

    // Load initial analysis (only if not already loaded)
    if (!window.analysisData.results) {
        await loadAnalysis();
    } else {
        displayAnalysisResults(window.analysisData.results);
    }

    // Popup handlers
    const typicalViewerBtn = document.getElementById('typical-viewer-btn');
    if (typicalViewerBtn) {
        typicalViewerBtn.addEventListener('click', loadTypicalViewer);
    }

    // Close popup handlers
    const closeButton = document.querySelector('.close-button');
    if (closeButton) {
        closeButton.addEventListener('click', function() {
            document.getElementById('popup-overlay').style.display = 'none';
        });
    }

    const popupOverlay = document.getElementById('popup-overlay');
    if (popupOverlay) {
        popupOverlay.addEventListener('click', function(e) {
            if (e.target === this) {
                this.style.display = 'none';
            }
        });
    }

    // Tab click handlers with video ID
    const suggestionsTab = document.getElementById('suggestions-tab');
    if (suggestionsTab) {
        suggestionsTab.href = `/suggestions/${videoId}`;
    }

    const commentsManagerTab = document.getElementById('comments-manager-tab');
    if (commentsManagerTab) {
        commentsManagerTab.href = `/comments/${videoId}`;
    }
});

async function loadAnalysis(forceRefresh = false) {
    // Prevent duplicate calls
    if (window.isAnalyzing && !forceRefresh) {
        console.log('Analysis already in progress');
        return;
    }

    window.isAnalyzing = true;
    const conclusionsContent = document.querySelector('.conclusions-content');

    // Show loading state
    conclusionsContent.innerHTML = `
        <div class="loading-state">
            <div class="spinner"></div>
            <p>Analyzing comments...</p>
            <p class="loading-sub">This may take a moment on first load</p>
        </div>
    `;

    try {
        // Check if we have cached data and not forcing refresh
        if (window.analysisData.results && !forceRefresh) {
            displayAnalysisResults(window.analysisData.results);
            return;
        }

        // Batch analyze main categories
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
                    { name: 'suggestions', threshold: 0.4 }
                ],
                force_refresh: forceRefresh
            })
        });

        const data = await response.json();

        if (data.success) {
            // Cache the results
            window.analysisData.results = data.results;
            window.analysisData.fromCache = data.from_cache;

            console.log('Analysis results:', data.results);

            // Display results
            displayAnalysisResults(data.results);

            // Show cache indicator
            if (data.from_cache) {
                showNotification('Using cached analysis results', 'info');
            }
        } else {
            console.error('Analysis failed:', data.error);
            conclusionsContent.innerHTML = '<p class="error">Failed to load analysis. Please try again.</p>';
        }
    } catch (error) {
        console.error('Error loading analysis:', error);
        conclusionsContent.innerHTML = '<p class="error">Error loading analysis. Please refresh the page.</p>';
    } finally {
        window.isAnalyzing = false;
    }
}

function displayAnalysisResults(results) {
    console.log('Displaying results:', results);
    const conclusionsContent = document.querySelector('.conclusions-content');

    // Build conclusions HTML
    let html = '<div class="analysis-results">';

    // Overall sentiment with visual indicator
    const totalComments = Object.values(results).reduce((sum, r) => sum + r.total_found, 0);
    const positivePercent = results.positive?.percentage || 0;
    const negativePercent = results.negative?.percentage || 0;
    const sentiment = positivePercent > negativePercent ? 'positive' : 'mixed';

    html += `
        <div class="sentiment-overview ${sentiment}">
            <h4>Overall Sentiment</h4>
            <div class="sentiment-bar">
                <div class="sentiment-positive" style="width: ${positivePercent}%"></div>
                <div class="sentiment-negative" style="width: ${negativePercent}%"></div>
            </div>
            <p>${positivePercent > negativePercent ? '✅ Mostly Positive' : '⚠️ Mixed Feedback'} 
            (${positivePercent.toFixed(1)}% positive, ${negativePercent.toFixed(1)}% negative)</p>
        </div>
    `;

    // Key insights from each category
    const categoryIcons = {
        'positive': '👍',
        'negative': '👎',
        'questions': '❓',
        'suggestions': '💡'
    };

    for (const [category, result] of Object.entries(results)) {
        if (result.category_summary) {
            const icon = categoryIcons[category] || '📝';
            html += `
                <div class="category-summary">
                    <h4>${icon} ${capitalizeFirst(category)} Comments 
                        <span class="percentage">${result.percentage.toFixed(1)}%</span>
                    </h4>
                    <div class="category-insight">
                        ${result.category_summary}
                    </div>
                </div>
            `;
        }
    }

    // Add refresh button
    html += `
        <div class="analysis-actions">
            <button onclick="refreshAnalysis()" class="refresh-btn">
                🔄 Refresh Analysis
            </button>
        </div>
    `;

    html += '</div>';
    conclusionsContent.innerHTML = html;
}

async function loadTypicalViewer() {
    const popupOverlay = document.getElementById('popup-overlay');
    popupOverlay.style.display = 'flex';

    // Check if we have cached viewer data
    if (window.analysisData.typicalViewer) {
        displayTypicalViewer(window.analysisData.typicalViewer);
        return;
    }

    // Update popup content with loading state
    const likesSection = document.querySelector('.likes ul');
    const dislikesSection = document.querySelector('.dislikes ul');

    likesSection.innerHTML = '<li>Loading viewer profile...</li>';
    dislikesSection.innerHTML = '<li>Please wait...</li>';

    try {
        const response = await fetch('/api/typical_viewer');
        const data = await response.json();

        if (data.success) {
            // Cache the data
            window.analysisData.typicalViewer = data.profile;
            displayTypicalViewer(data.profile);
        } else {
            likesSection.innerHTML = '<li>Failed to load profile</li>';
            dislikesSection.innerHTML = '<li>Please try again</li>';
        }
    } catch (error) {
        console.error('Error loading typical viewer:', error);
        likesSection.innerHTML = '<li>Error loading profile</li>';
        dislikesSection.innerHTML = '<li>Please try again</li>';
    }
}

function displayTypicalViewer(profile) {
    const likesSection = document.querySelector('.likes ul');
    const dislikesSection = document.querySelector('.dislikes ul');

    // Update likes with bullet points
    likesSection.innerHTML = profile.likes.map(like =>
        `<li>${like}</li>`
    ).join('');

    // Update dislikes with bullet points
    dislikesSection.innerHTML = profile.dislikes.map(dislike =>
        `<li>${dislike}</li>`
    ).join('');

    // Update profile details
    const profileTitle = document.querySelector('.profile-title p');
    profileTitle.textContent = `${profile.engagement_level} engagement viewer • ${profile.stats.positive_percentage}% positive`;

    // Add characteristics if available
    if (profile.characteristics && profile.characteristics.length > 0) {
        const profileHeader = document.querySelector('.profile-header');
        if (!document.querySelector('.viewer-traits')) {
            const traitsDiv = document.createElement('div');
            traitsDiv.className = 'viewer-traits';
            traitsDiv.innerHTML = `
                <h4>Viewer Traits</h4>
                <ul>${profile.characteristics.map(trait => `<li>${trait}</li>`).join('')}</ul>
            `;
            profileHeader.parentElement.insertBefore(traitsDiv, profileHeader.nextSibling);
        }
    }
}

function refreshAnalysis() {
    loadAnalysis(true);
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'info' ? '#4CAF50' : '#ff4444'};
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        z-index: 1000;
        animation: slideIn 0.3s ease-out;
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function capitalizeFirst(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// Make refresh function global
window.refreshAnalysis = refreshAnalysis;

// Add enhanced styles
const style = document.createElement('style');
style.textContent = `
    .analysis-results {
        display: flex;
        flex-direction: column;
        gap: 1.2rem;
    }
    
    .sentiment-overview {
        background: rgba(255, 0, 0, 0.05);
        padding: 1.2rem;
        border-radius: 12px;
        border-left: 4px solid var(--primary-red);
    }
    
    .sentiment-overview.positive {
        background: rgba(76, 175, 80, 0.05);
        border-left-color: #4CAF50;
    }
    
    .sentiment-bar {
        height: 20px;
        background: #f0f0f0;
        border-radius: 10px;
        overflow: hidden;
        margin: 0.8rem 0;
        display: flex;
    }
    
    .sentiment-positive {
        background: #4CAF50;
        transition: width 0.5s ease;
    }
    
    .sentiment-negative {
        background: #f44336;
        transition: width 0.5s ease;
    }
    
    .sentiment-overview h4 {
        margin: 0 0 0.8rem 0;
        color: var(--dark-red);
        font-size: 1.1rem;
    }
    
    .category-summary {
        background: rgba(255, 255, 255, 0.8);
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    
    .category-summary h4 {
        color: var(--dark-red);
        font-size: 1rem;
        margin-bottom: 0.6rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .percentage {
        font-size: 0.85rem;
        color: #666;
        font-weight: normal;
    }
    
    .category-summary ul {
        list-style: none;
        padding-left: 0;
    }
    
    .category-summary li {
        padding: 0.5rem 0;
        color: var(--text-gray);
        font-size: 0.9rem;
        border-bottom: 1px solid rgba(0, 0, 0, 0.05);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .category-summary li:last-child {
        border-bottom: none;
    }
    
    .cluster-size {
        font-size: 0.8rem;
        color: #999;
        white-space: nowrap;
    }
    
    .loading-state {
        text-align: center;
        padding: 2rem;
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
    
    .loading-sub {
        font-size: 0.85rem;
        color: #999;
        margin-top: 0.5rem;
    }
    
    .error {
        color: #d32f2f;
        text-align: center;
        padding: 1rem;
    }
    
    .analysis-actions {
        margin-top: 1rem;
        text-align: center;
    }
    
    .refresh-btn {
        background: var(--primary-red);
        color: white;
        border: none;
        padding: 0.6rem 1.2rem;
        border-radius: 20px;
        cursor: pointer;
        font-size: 0.9rem;
        transition: all 0.3s ease;
    }
    
    .refresh-btn:hover {
        background: var(--dark-red);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(255, 0, 0, 0.2);
    }
    
    .viewer-traits {
        margin-top: 1rem;
        padding: 1rem;
        background: rgba(0, 0, 0, 0.03);
        border-radius: 8px;
    }
    
    .viewer-traits h4 {
        margin: 0 0 0.5rem 0;
        font-size: 1rem;
        color: #666;
    }
    
    .viewer-traits ul {
        list-style: none;
        padding: 0;
    }
    
    .viewer-traits li {
        padding: 0.3rem 0;
        font-size: 0.9rem;
        color: #555;
    }
    
    .notification {
        animation: slideIn 0.3s ease-out;
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