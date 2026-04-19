/**
 * Shared API utilities for making HTTP requests
 * Used across projects, converters, surveys, and tools
 */

const nativeFetch = (typeof window !== 'undefined' && typeof window.fetch === 'function')
    ? window.fetch.bind(window)
    : null;

function getFallbackApiOrigin() {
    const configuredOrigin = (window.PRISM_API_ORIGIN || '').trim();
    if (configuredOrigin) {
        return configuredOrigin.replace(/\/$/, '');
    }
    return 'http://127.0.0.1:5001';
}

function canRetryApiWithFallback(url) {
    const protocol = (window.location && window.location.protocol) ? window.location.protocol : '';
    const isRelativeApiRequest = typeof url === 'string' && url.startsWith('/api/');
    return isRelativeApiRequest && protocol !== 'http:' && protocol !== 'https:';
}

async function fetchWithApiFallbackUsing(fetchImpl, url, options = {}, fallbackMessage) {
    if (typeof fetchImpl !== 'function') {
        throw new Error('Fetch is not available in this runtime.');
    }

    try {
        return await fetchImpl(url, options);
    } catch (primaryError) {
        if (!canRetryApiWithFallback(url)) {
            throw primaryError;
        }

        const fallbackUrl = `${getFallbackApiOrigin()}${url}`;
        try {
            return await fetchImpl(fallbackUrl, options);
        } catch (_fallbackError) {
            throw new Error(fallbackMessage);
        }
    }
}

/**
 * Make a request and retry API calls against the desktop loopback backend when running off file://.
 * @param {string} url - The endpoint URL
 * @param {object} options - Optional fetch options
 * @param {string} fallbackMessage - Error to surface when both attempts fail
 * @returns {Promise<Response>} Fetch response
 */
export async function fetchWithApiFallback(
    url,
    options = {},
    fallbackMessage = 'Cannot reach PRISM backend API. Please restart PRISM Studio and try again.'
) {
    return fetchWithApiFallbackUsing(nativeFetch, url, options, fallbackMessage);
}

/**
 * Install one page-scoped fetch wrapper so existing raw fetch('/api/...') calls
 * on module-heavy pages can retry against the desktop loopback backend.
 */
export function installApiFetchFallback() {
    if (typeof window === 'undefined' || typeof nativeFetch !== 'function') {
        return;
    }
    if (window.__prismApiFetchFallbackInstalled) {
        return;
    }

    window.__prismApiFetchFallbackInstalled = true;
    window.fetch = function prismApiFetchWithFallback(url, options = {}) {
        return fetchWithApiFallbackUsing(
            nativeFetch,
            url,
            options,
            'Cannot reach PRISM backend API. Please restart PRISM Studio and try again.'
        );
    };
}

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
