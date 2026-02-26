/**
 * Shared storage utilities for localStorage and sessionStorage
 */

/**
 * Get item from localStorage
 * @param {string} key - Storage key
 * @param {*} defaultValue - Default value if key not found
 * @returns {*} Stored value or default
 */
export function getLocalStorage(key, defaultValue = null) {
    try {
        const item = window.localStorage.getItem(key);
        if (item === null) {
            return defaultValue;
        }
        
        // Try to parse as JSON, fall back to string
        try {
            return JSON.parse(item);
        } catch {
            return item;
        }
    } catch (err) {
        console.error(`Error reading localStorage: ${err}`);
        return defaultValue;
    }
}

/**
 * Set item in localStorage
 * @param {string} key - Storage key
 * @param {*} value - Value to store
 * @returns {boolean} True if successful
 */
export function setLocalStorage(key, value) {
    try {
        const storedValue = typeof value === 'string' ? value : JSON.stringify(value);
        window.localStorage.setItem(key, storedValue);
        return true;
    } catch (err) {
        console.error(`Error writing to localStorage: ${err}`);
        return false;
    }
}

/**
 * Remove item from localStorage
 * @param {string} key - Storage key
 * @returns {boolean} True if successful
 */
export function removeLocalStorage(key) {
    try {
        window.localStorage.removeItem(key);
        return true;
    } catch (err) {
        console.error(`Error removing from localStorage: ${err}`);
        return false;
    }
}

/**
 * Clear all localStorage
 * @returns {boolean} True if successful
 */
export function clearLocalStorage() {
    try {
        window.localStorage.clear();
        return true;
    } catch (err) {
        console.error(`Error clearing localStorage: ${err}`);
        return false;
    }
}

/**
 * Get item from sessionStorage
 * @param {string} key - Storage key
 * @param {*} defaultValue - Default value if key not found
 * @returns {*} Stored value or default
 */
export function getSessionStorage(key, defaultValue = null) {
    try {
        const item = window.sessionStorage.getItem(key);
        if (item === null) {
            return defaultValue;
        }
        
        // Try to parse as JSON, fall back to string
        try {
            return JSON.parse(item);
        } catch {
            return item;
        }
    } catch (err) {
        console.error(`Error reading sessionStorage: ${err}`);
        return defaultValue;
    }
}

/**
 * Set item in sessionStorage
 * @param {string} key - Storage key
 * @param {*} value - Value to store
 * @returns {boolean} True if successful
 */
export function setSessionStorage(key, value) {
    try {
        const storedValue = typeof value === 'string' ? value : JSON.stringify(value);
        window.sessionStorage.setItem(key, storedValue);
        return true;
    } catch (err) {
        console.error(`Error writing to sessionStorage: ${err}`);
        return false;
    }
}

/**
 * Remove item from sessionStorage
 * @param {string} key - Storage key
 * @returns {boolean} True if successful
 */
export function removeSessionStorage(key) {
    try {
        window.sessionStorage.removeItem(key);
        return true;
    } catch (err) {
        console.error(`Error removing from sessionStorage: ${err}`);
        return false;
    }
}

/**
 * Clear all sessionStorage
 * @returns {boolean} True if successful
 */
export function clearSessionStorage() {
    try {
        window.sessionStorage.clear();
        return true;
    } catch (err) {
        console.error(`Error clearing sessionStorage: ${err}`);
        return false;
    }
}
