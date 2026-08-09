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

    const protocol = (window.location && window.location.protocol) ? window.location.protocol : '';
    const currentOrigin = (window.location && typeof window.location.origin === 'string')
        ? window.location.origin.trim()
        : '';
    if ((protocol === 'http:' || protocol === 'https:') && currentOrigin && currentOrigin !== 'null') {
        return currentOrigin.replace(/\/$/, '');
    }

    return 'http://127.0.0.1:5001';
}

function canRetryApiWithFallback(url) {
    const protocol = (window.location && window.location.protocol) ? window.location.protocol : '';
    const isRelativeApiRequest = typeof url === 'string' && (
        url.startsWith('/api/') || url.startsWith('/editor/api/')
    );
    return isRelativeApiRequest && protocol !== 'http:' && protocol !== 'https:';
}

function canRetryRelativePathWithFallback(url) {
    const protocol = (window.location && window.location.protocol) ? window.location.protocol : '';
    const isRelativePathRequest = typeof url === 'string' && url.startsWith('/');
    return isRelativePathRequest && protocol !== 'http:' && protocol !== 'https:';
}

function normalizeFetchOptionsForRuntime(url, options = {}) {
    if (!options || Object.prototype.hasOwnProperty.call(options, 'credentials')) {
        return options;
    }

    const protocol = (window.location && window.location.protocol) ? window.location.protocol : '';
    const isAbsoluteHttpUrl = typeof url === 'string' && /^https?:\/\//i.test(url);

    if (!isAbsoluteHttpUrl) {
        return options;
    }

    if (protocol !== 'http:' && protocol !== 'https:') {
        return { ...options, credentials: 'include' };
    }

    try {
        const requestOrigin = new URL(url, window.location.href).origin;
        if (requestOrigin !== window.location.origin) {
            return { ...options, credentials: 'include' };
        }
    } catch (_error) {
        return { ...options, credentials: 'include' };
    }

    return options;
}

async function fetchWithFallbackUsing(fetchImpl, url, options = {}, fallbackMessage, canRetryWithFallback) {
    if (typeof fetchImpl !== 'function') {
        throw new Error('Fetch is not available in this runtime.');
    }

    try {
        return await fetchImpl(url, normalizeFetchOptionsForRuntime(url, options));
    } catch (primaryError) {
        if (typeof canRetryWithFallback !== 'function' || !canRetryWithFallback(url)) {
            throw primaryError;
        }

        const fallbackUrl = `${getFallbackApiOrigin()}${url}`;
        try {
            return await fetchImpl(
                fallbackUrl,
                normalizeFetchOptionsForRuntime(fallbackUrl, options)
            );
        } catch (_fallbackError) {
            throw new Error(fallbackMessage);
        }
    }
}

async function fetchWithApiFallbackUsing(fetchImpl, url, options = {}, fallbackMessage) {
    return fetchWithFallbackUsing(
        fetchImpl,
        url,
        options,
        fallbackMessage,
        canRetryApiWithFallback
    );
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
 * Make a request and retry any relative path against the desktop loopback backend when running off file://.
 * This is used by classic pages that post to non-API routes like /upload or /validate_folder.
 * @param {string} url - The endpoint URL
 * @param {object} options - Optional fetch options
 * @param {string} fallbackMessage - Error to surface when both attempts fail
 * @returns {Promise<Response>} Fetch response
 */
export async function fetchWithRelativePathFallback(
    url,
    options = {},
    fallbackMessage = 'Cannot reach PRISM backend API. Please restart PRISM Studio and try again.'
) {
    return fetchWithFallbackUsing(
        nativeFetch,
        url,
        options,
        fallbackMessage,
        canRetryRelativePathWithFallback
    );
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

