/**
 * Projects Module - Helpers
 * UI helper functions for button states, alerts, toasts, and feedback
 */

/**
 * Set button loading state
 * @param {HTMLButtonElement} btn - Button element
 * @param {boolean} isLoading - Whether to show loading state
 * @param {string} loadingText - Text to show while loading
 * @param {string|null} originalText - Original HTML (returned on first call)
 * @returns {string|null} Original button HTML if loading, null if restoring
 */
export function setButtonLoading(btn, isLoading, loadingText = 'Loading...', originalText = null) {
    if (!btn) {
        return null;
    }

    if (isLoading) {
        const current = btn.innerHTML;
        btn.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i>${loadingText}`;
        btn.disabled = true;
        return current;
    }
    btn.innerHTML = originalText || btn.innerHTML.replace(/<i[^>]*spinner[^>]*>.*?<\/i>\s*/, '');
    btn.disabled = false;
    return null;
}

/**
 * Show alert in a container
 * @param {string} containerId - ID of container element
 * @param {string} type - Alert type (success, danger, warning, info)
 * @param {string} title - Alert title
 * @param {string} message - Alert message
 */
export function showAlert(containerId, type, title, message) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const iconMap = {
        success: 'check-circle',
        danger: 'exclamation-circle',
        warning: 'exclamation-triangle',
        info: 'info-circle'
    };

    const icon = iconMap[type] || 'info-circle';
    const titleHtml = title ? `<h5><i class="fas fa-${icon} me-2"></i>${title}</h5>` : '';

    container.innerHTML = `
        <div class="alert alert-${type}">
            ${titleHtml}
            ${message ? `<p class="mb-0">${message}</p>` : ''}
        </div>
    `;
    container.style.display = 'block';
}

/**
 * Show toast notification
 * @param {string} message - Toast message
 * @param {string} type - Toast type (success, danger, warning, info)
 */
export function showToast(message, type = 'success') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }

    // Determine alert class and icon
    const alertClass = type === 'danger' ? 'danger' : (type === 'warning' ? 'warning' : 'success');
    const icon = type === 'danger'
        ? 'fa-exclamation-circle'
        : (type === 'warning' ? 'fa-exclamation-triangle' : 'fa-check-circle');

    // Create toast element
    const toastId = 'toast-' + Date.now();
    const toastHTML = `
        <div class="toast show shadow-sm rounded" id="${toastId}" role="alert" aria-live="polite" aria-atomic="true">
            <div class="toast-body alert-${alertClass} d-flex align-items-center gap-2 p-3 rounded">
                <i class="fas ${icon} flex-shrink-0"></i>
                <span>${message}</span>
                <button type="button" class="btn-close btn-sm ms-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', toastHTML);

    // Auto-dismiss after 4 seconds
    const toastElement = document.getElementById(toastId);
    if (toastElement) {
        setTimeout(() => {
            toastElement.style.opacity = '0';
            toastElement.style.transition = 'opacity 0.3s ease-out';
            setTimeout(() => toastElement.remove(), 300);
        }, 4000);
    }
}

/**
 * Show feedback banner at top of page
 * @param {string} message - Feedback message
 * @param {string} type - Feedback type (success, danger, warning, info)
 */
export function showTopFeedback(message, type = 'success') {
    const level = (type || 'success').toLowerCase();
    const bsType = level === 'danger' ? 'danger' : (level === 'warning' ? 'warning' : 'success');
    const icon = bsType === 'danger'
        ? 'fa-exclamation-triangle'
        : (bsType === 'warning' ? 'fa-exclamation-circle' : 'fa-check-circle');

    let host = document.getElementById('topFeedbackHost');
    if (!host) {
        host = document.createElement('div');
        host.id = 'topFeedbackHost';
        host.className = 'container-fluid mt-2';

        const target = document.querySelector('main')
            || document.querySelector('.container-fluid')
            || document.body;
        if (target.prepend) {
            target.prepend(host);
        } else {
            document.body.insertBefore(host, document.body.firstChild);
        }
    }

    host.innerHTML = `
        <div class="alert alert-${bsType} alert-dismissible fade show shadow-sm" role="alert">
            <i class="fas ${icon} me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

/**
 * Convert newline-separated text to array
 * @param {string} val - Text value with newlines
 * @returns {Array|undefined} Array of trimmed lines or undefined
 */
export function textToArray(val) {
    if (!val) return undefined;
    return val.split('\n').map(s => s.trim()).filter(s => s);
}
