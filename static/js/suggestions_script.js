document.addEventListener('DOMContentLoaded', async function() {
    // Check if we have cached suggestions
    window.suggestionsData = window.suggestionsData || {};

    // Load suggestions data
    await loadSuggestions();
});

async function loadSuggestions(forceRefresh = false) {
    // Update viewer interests section
    const viewerList = document.querySelector('.viewer-list');
    const suggestionButtons = document.querySelector('.suggestion-buttons');

    // Check cache first
    if (window.suggestionsData.suggestions && !forceRefresh) {
        displaySuggestions(window.suggestionsData);
        return;
    }

    // Show loading state
    viewerList.innerHTML = '<li class="loading-item"><div class="mini-spinner"></div> Loading viewer interests...</li>';
    suggestionButtons.innerHTML = '<div class="suggestion-btn loading"><div class="mini-spinner"></div> Analyzing viewer feedback...</div>';

    try {
        const response = await fetch('/api/get_suggestions');
        const data = await response.json();

        if (data.success) {
            // Cache the data
            window.suggestionsData = data;
            displaySuggestions(data);
        } else {
            showError('Failed to load suggestions');
            displayDefaultContent();
        }
    } catch (error) {
        console.error('Error loading suggestions:', error);
        showError('Error loading suggestions');
        displayDefaultContent();
    }
}

function displaySuggestions(data) {
    const viewerList = document.querySelector('.viewer-list');
    const suggestionButtons = document.querySelector('.suggestion-buttons');

    // Update viewer interests
    if (data.viewer_interests && data.viewer_interests.length > 0) {
        const defaultInterests = [
            'Behind the scenes of your creative process',
            'Q&A sessions with your audience',
            'Tips and tutorials for beginners'
        ];

        // Combine detected interests with some defaults
        const interests = [
            ...data.viewer_interests.slice(0, 3),
            ...defaultInterests.slice(0, Math.max(0, 5 - data.viewer_interests.length))
        ];

        viewerList.innerHTML = interests.slice(0, 5).map((interest, idx) => {
            // If the interest is a quoted comment, show a quote icon and style as a quote
            if (interest.startsWith('"') && interest.endsWith('"')) {
                return `<li class="interest-item quote-item" style="animation-delay: ${idx * 0.1}s">
                    <span class="interest-icon">\u201C</span>
                    <span class="interest-quote">${interest}</span>
                </li>`;
            } else {
                return `<li class="interest-item" style="animation-delay: ${idx * 0.1}s">
                    <span class="interest-icon">${getInterestIcon(interest)}</span>
                    ${interest}
                </li>`;
            }
        }).join('');
    } else {
        displayDefaultInterests();
    }

    // Update suggestions
    if (data.suggestions && data.suggestions.length > 0) {
        // Group suggestions by type
        const groupedSuggestions = groupSuggestionsByType(data.suggestions);

        suggestionButtons.innerHTML = groupedSuggestions.slice(0, 3).map((suggestion, idx) => `
            <div class="suggestion-btn ${suggestion.type}" 
                 data-support="${suggestion.support_count}"
                 style="animation-delay: ${idx * 0.1}s">
                <div class="suggestion-header">
                    <span class="suggestion-icon">${getSuggestionIcon(suggestion.type)}</span>
                    <span class="suggestion-type">${capitalizeFirst(suggestion.type)}</span>
                </div>
                <div class="suggestion-title">${cleanSuggestionTitle(suggestion.title)}</div>
                <div class="suggestion-footer">
                    <span class="support-count">
                        <span class="count-icon">👥</span> ${suggestion.support_count} viewers interested
                    </span>
                    <span class="engagement">
                        <span class="engagement-icon">❤️</span> ${suggestion.avg_engagement.toFixed(0)} avg likes
                    </span>
                </div>
            </div>
        `).join('');

        // Add more suggestions button if there are more
        if (data.suggestions.length > 3) {
            suggestionButtons.innerHTML += `
                <button class="more-suggestions-btn" onclick="showAllSuggestions()">
                    View ${data.suggestions.length - 3} more suggestions →
                </button>
            `;
        }
    } else {
        displayDefaultSuggestions();
    }

    // Add click handlers to suggestion buttons
    document.querySelectorAll('.suggestion-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            if (!this.classList.contains('loading')) {
                showSuggestionDetails(this);
            }
        });
    });

    // Add refresh button
    addRefreshButton();
}

function groupSuggestionsByType(suggestions) {
    // Prioritize by type and support
    const priority = {
        'request': 3,
        'clarification': 2,
        'improvement': 1
    };

    return suggestions.sort((a, b) => {
        const priorityDiff = (priority[b.type] || 0) - (priority[a.type] || 0);
        if (priorityDiff !== 0) return priorityDiff;
        return (b.support_count * 2 + b.avg_engagement) - (a.support_count * 2 + a.avg_engagement);
    });
}

function cleanSuggestionTitle(title) {
    // Remove redundant prefixes
    return title
        .replace(/^(Video request:|Clarification video on:|Improvement:)\s*/i, '')
        .replace(/^(Create|Make|Do)\s+(a\s+)?/i, '')
        .trim();
}

function getSuggestionIcon(type) {
    const icons = {
        'request': '🎬',
        'clarification': '💡',
        'improvement': '⚡'
    };
    return icons[type] || '📝';
}

function getInterestIcon(interest) {
    if (interest.includes('tutorial') || interest.includes('how-to')) return '📚';
    if (interest.includes('behind') || interest.includes('scenes')) return '🎥';
    if (interest.includes('tips') || interest.includes('tricks')) return '💡';
    if (interest.includes('deep') || interest.includes('advanced')) return '🔬';
    if (interest.includes('beginner')) return '🌱';
    return '✨';
}

function displayDefaultContent() {
    displayDefaultInterests();
    displayDefaultSuggestions();
}

function displayDefaultInterests() {
    const viewerList = document.querySelector('.viewer-list');
    viewerList.innerHTML = `
        <li>Behind the scenes of your creative process</li>
        <li>Q&A with your team</li>
        <li>Tips for beginners in your field</li>
        <li>Day in the life vlog</li>
        <li>How you edit your videos</li>
    `;
}

function displayDefaultSuggestions() {
    const suggestionButtons = document.querySelector('.suggestion-buttons');
    suggestionButtons.innerHTML = `
        <div class="suggestion-btn default">
            <div class="suggestion-header">
                <span class="suggestion-icon">📈</span>
                <span class="suggestion-type">Growth</span>
            </div>
            <div class="suggestion-title">How to grow your channel in 2024</div>
        </div>
        <div class="suggestion-btn default">
            <div class="suggestion-header">
                <span class="suggestion-icon">🎨</span>
                <span class="suggestion-type">Technical</span>
            </div>
            <div class="suggestion-title">Deep dive into editing techniques</div>
        </div>
        <div class="suggestion-btn default">
            <div class="suggestion-header">
                <span class="suggestion-icon">🤝</span>
                <span class="suggestion-type">Community</span>
            </div>
            <div class="suggestion-title">Collaborating with other creators</div>
        </div>
    `;
}

function showSuggestionDetails(button) {
    // Visual feedback
    button.classList.add('clicked');

    // Create modal or expand view
    const supportCount = button.dataset.support;
    const title = button.querySelector('.suggestion-title').textContent;

    // Simple animation for now
    setTimeout(() => {
        button.classList.remove('clicked');
    }, 300);

    // You could add a modal here with more details
    console.log(`Suggestion: ${title} - ${supportCount} viewers interested`);
}

function showAllSuggestions() {
    // Expand to show all suggestions
    const suggestionButtons = document.querySelector('.suggestion-buttons');
    const allSuggestions = window.suggestionsData.suggestions;

    suggestionButtons.innerHTML = allSuggestions.map((suggestion, idx) => `
        <div class="suggestion-btn ${suggestion.type}" 
             data-support="${suggestion.support_count}"
             style="animation-delay: ${idx * 0.05}s">
            <div class="suggestion-header">
                <span class="suggestion-icon">${getSuggestionIcon(suggestion.type)}</span>
                <span class="suggestion-type">${capitalizeFirst(suggestion.type)}</span>
            </div>
            <div class="suggestion-title">${cleanSuggestionTitle(suggestion.title)}</div>
            <div class="suggestion-footer">
                <span class="support-count">👥 ${suggestion.support_count} interested</span>
                <span class="engagement">❤️ ${suggestion.avg_engagement.toFixed(0)}</span>
            </div>
        </div>
    `).join('');

    // Re-add click handlers
    document.querySelectorAll('.suggestion-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            showSuggestionDetails(this);
        });
    });
}

function addRefreshButton() {
    const suggestionInfo = document.querySelector('.suggestion-info');
    if (!document.querySelector('.refresh-suggestions-btn')) {
        const refreshBtn = document.createElement('button');
        refreshBtn.className = 'refresh-suggestions-btn';
        refreshBtn.innerHTML = '🔄 Refresh Suggestions';
        refreshBtn.onclick = () => loadSuggestions(true);
        suggestionInfo.parentElement.insertBefore(refreshBtn, suggestionInfo.nextSibling);
    }
}

function showError(message) {
    console.error(message);
    // Could add a visual error notification here
}

function capitalizeFirst(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// Global functions
window.showAllSuggestions = showAllSuggestions;

// Add enhanced styles
const style = document.createElement('style');
style.textContent = `
    .loading-item {
        opacity: 0.6;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .mini-spinner {
        width: 16px;
        height: 16px;
        border: 2px solid #f3f3f3;
        border-top: 2px solid var(--primary-color);
        border-radius: 50%;
        animation: spin 1s linear infinite;
        display: inline-block;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    .interest-item {
        animation: fadeInUp 0.5s ease-out forwards;
        opacity: 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .interest-icon {
        font-size: 1.2rem;
    }
    
    .suggestion-btn {
        position: relative;
        transition: all 0.3s ease;
        cursor: pointer;
        animation: fadeInUp 0.5s ease-out forwards;
        opacity: 0;
        display: flex;
        flex-direction: column;
        gap: 0.8rem;
    }
    
    .suggestion-btn.loading {
        justify-content: center;
        align-items: center;
        opacity: 0.6;
    }
    
    .suggestion-header {
        display: flex;
        align-items: center;
        gap: 0.8rem;
    }
    
    .suggestion-icon {
        font-size: 1.5rem;
    }
    
    .suggestion-type {
        font-size: 0.9rem;
        opacity: 0.8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .suggestion-title {
        font-size: 1.25rem;
        line-height: 1.4;
    }
    
    .suggestion-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.9rem;
        opacity: 0.9;
    }
    
    .support-count, .engagement {
        display: flex;
        align-items: center;
        gap: 0.3rem;
    }
    
    .count-icon, .engagement-icon {
        font-size: 1rem;
    }
    
    .suggestion-btn.request {
        background: linear-gradient(135deg, #ff6b6b 0%, #ff0000 100%);
    }
    
    .suggestion-btn.clarification {
        background: linear-gradient(135deg, #4ecdc4 0%, #44a3aa 100%);
    }
    
    .suggestion-btn.improvement {
        background: linear-gradient(135deg, #95e1d3 0%, #3fc1c9 100%);
    }
    
    .suggestion-btn.default {
        background: linear-gradient(90deg, #ff6a6a 0%, #ff0000 100%);
    }
    
    .suggestion-btn:hover {
        transform: translateY(-3px) scale(1.02);
        box-shadow: 0 12px 32px 0 var(--shadow-color);
    }
    
    .suggestion-btn.clicked {
        transform: scale(0.98);
        box-shadow: 0 4px 16px 0 var(--shadow-color);
    }
    
    .more-suggestions-btn {
        background: transparent;
        border: 2px solid var(--primary-color);
        color: var(--primary-color);
        padding: 1rem 2rem;
        border-radius: 2rem;
        font-size: 1.1rem;
        cursor: pointer;
        transition: all 0.3s ease;
        width: 90%;
        margin-top: 1rem;
    }
    
    .more-suggestions-btn:hover {
        background: var(--primary-color);
        color: white;
        transform: translateY(-2px);
    }
    
    .refresh-suggestions-btn {
        background: rgba(255, 255, 255, 0.9);
        border: 1px solid var(--primary-color);
        color: var(--primary-color);
        padding: 0.6rem 1.2rem;
        border-radius: 20px;
        font-size: 0.9rem;
        cursor: pointer;
        transition: all 0.3s ease;
        margin-top: 1rem;
        align-self: flex-end;
    }
    
    .refresh-suggestions-btn:hover {
        background: var(--primary-color);
        color: white;
        transform: translateY(-2px);
    }
    
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
`;
document.head.appendChild(style);