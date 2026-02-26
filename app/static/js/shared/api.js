/**
 * Shared API utilities for making HTTP requests
 * Used across projects, converters, surveys, and tools
 */

/**
 * Make a GET request
 * @param {string} url - The endpoint URL
 * @param {object} options - Optional fetch options
 * @returns {Promise} JSON response
 */
export async function apiGet(url, options = {}) {
    const response = await fetch(url, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    });
    
    if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }
    
    return response.json();
}

/**
 * Make a POST request
 * @param {string} url - The endpoint URL
 * @param {object} data - Data to send in request body
 * @param {object} options - Optional fetch options
 * @returns {Promise} JSON response
 */
export async function apiPost(url, data, options = {}) {
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        body: JSON.stringify(data),
        ...options
    });
    
    if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }
    
    return response.json();
}

/**
 * Make a PUT request
 * @param {string} url - The endpoint URL
 * @param {object} data - Data to send in request body
 * @param {object} options - Optional fetch options
 * @returns {Promise} JSON response
 */
export async function apiPut(url, data, options = {}) {
    const response = await fetch(url, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        body: JSON.stringify(data),
        ...options
    });
    
    if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }
    
    return response.json();
}

/**
 * Make a DELETE request
 * @param {string} url - The endpoint URL
 * @param {object} options - Optional fetch options
 * @returns {Promise} JSON response
 */
export async function apiDelete(url, options = {}) {
    const response = await fetch(url, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    });
    
    if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }
    
    // DELETE responses may not have content
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
        return response.json();
    }
    return null;
}

/**
 * Upload a file with FormData
 * @param {string} url - The endpoint URL
 * @param {FormData} formData - FormData containing file
 * @param {object} options - Optional fetch options
 * @returns {Promise} JSON response
 */
export async function apiUpload(url, formData, options = {}) {
    const response = await fetch(url, {
        method: 'POST',
        body: formData,
        ...options
    });
    
    if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }
    
    return response.json();
}
