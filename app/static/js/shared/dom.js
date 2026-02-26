/**
 * Shared DOM manipulation utilities
 */

/**
 * Safely get an element by ID
 * @param {string} id - Element ID
 * @returns {HTMLElement|null} Element or null if not found
 */
export function getById(id) {
    return document.getElementById(id) || null;
}

/**
 * Safely query selector
 * @param {string} selector - CSS selector
 * @param {HTMLElement} parent - Parent element (defaults to document)
 * @returns {HTMLElement|null} Element or null if not found
 */
export function querySelect(selector, parent = document) {
    return parent.querySelector(selector) || null;
}

/**
 * Safely query all elements
 * @param {string} selector - CSS selector
 * @param {HTMLElement} parent - Parent element (defaults to document)
 * @returns {NodeList} List of elements
 */
export function querySelectAll(selector, parent = document) {
    return parent.querySelectorAll(selector);
}

/**
 * Add event listener with error handling
 * @param {HTMLElement} element - Element to attach listener to
 * @param {string} event - Event type
 * @param {Function} callback - Event handler
 * @returns {boolean} True if successful
 */
export function addEvent(element, event, callback) {
    if (!element) return false;
    
    try {
        element.addEventListener(event, callback);
        return true;
    } catch (err) {
        console.error(`Error adding event listener: ${err}`);
        return false;
    }
}

/**
 * Remove event listener
 * @param {HTMLElement} element - Element to remove listener from
 * @param {string} event - Event type
 * @param {Function} callback - Event handler
 * @returns {boolean} True if successful
 */
export function removeEvent(element, event, callback) {
    if (!element) return false;
    
    try {
        element.removeEventListener(event, callback);
        return true;
    } catch (err) {
        console.error(`Error removing event listener: ${err}`);
        return false;
    }
}

/**
 * Show element (removes display: none)
 * @param {HTMLElement} element - Element to show
 */
export function show(element) {
    if (element) {
        element.style.display = '';
    }
}

/**
 * Hide element (sets display: none)
 * @param {HTMLElement} element - Element to hide
 */
export function hide(element) {
    if (element) {
        element.style.display = 'none';
    }
}

/**
 * Toggle element visibility
 * @param {HTMLElement} element - Element to toggle
 */
export function toggle(element) {
    if (element) {
        element.style.display = element.style.display === 'none' ? '' : 'none';
    }
}

/**
 * Add CSS class
 * @param {HTMLElement} element - Element to modify
 * @param {string} className - CSS class name
 */
export function addClass(element, className) {
    if (element) {
        element.classList.add(className);
    }
}

/**
 * Remove CSS class
 * @param {HTMLElement} element - Element to modify
 * @param {string} className - CSS class name
 */
export function removeClass(element, className) {
    if (element) {
        element.classList.remove(className);
    }
}

/**
 * Toggle CSS class
 * @param {HTMLElement} element - Element to modify
 * @param {string} className - CSS class name
 */
export function toggleClass(element, className) {
    if (element) {
        element.classList.toggle(className);
    }
}

/**
 * Check if element has class
 * @param {HTMLElement} element - Element to check
 * @param {string} className - CSS class name
 * @returns {boolean}
 */
export function hasClass(element, className) {
    return element ? element.classList.contains(className) : false;
}

/**
 * Set element text content safely
 * @param {HTMLElement} element - Element to modify
 * @param {string} text - Text content
 */
export function setText(element, text) {
    if (element) {
        element.textContent = text;
    }
}

/**
 * Get element text content
 * @param {HTMLElement} element - Element to read
 * @returns {string} Text content
 */
export function getText(element) {
    return element ? element.textContent : '';
}

/**
 * Set element HTML safely (use with caution!)
 * @param {HTMLElement} element - Element to modify
 * @param {string} html - HTML content
 */
export function setHtml(element, html) {
    if (element) {
        element.innerHTML = html;
    }
}

/**
 * Get element HTML
 * @param {HTMLElement} element - Element to read
 * @returns {string} HTML content
 */
export function getHtml(element) {
    return element ? element.innerHTML : '';
}

/**
 * Scroll element into view
 * @param {HTMLElement} element - Element to scroll to
 */
export function scrollIntoView(element) {
    if (element && typeof element.scrollIntoView === 'function') {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

/**
 * Focus element if it exists
 * @param {HTMLElement} element - Element to focus
 */
export function focus(element) {
    if (element && typeof element.focus === 'function') {
        element.focus();
    }
}

/**
 * Blur element
 * @param {HTMLElement} element - Element to blur
 */
export function blur(element) {
    if (element && typeof element.blur === 'function') {
        element.blur();
    }
}
