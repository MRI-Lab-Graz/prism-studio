export function summarizeServerResponseText(rawText) {
    const compact = String(rawText || '')
        .replace(/<[^>]+>/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    if (!compact) {
        return '';
    }
    if (compact.length <= 220) {
        return compact;
    }
    return `${compact.slice(0, 217)}...`;
}

export async function parseJsonResponse(response, requestLabel = 'Request') {
    const statusCode = Number(response && response.status);
    const statusText = String((response && response.statusText) || '').trim();
    const statusLabel = Number.isFinite(statusCode) && statusCode > 0
        ? `HTTP ${statusCode}${statusText ? ` ${statusText}` : ''}`
        : 'HTTP response';

    let responseText = '';
    try {
        responseText = await response.text();
    } catch (_readError) {
        throw new Error(`${requestLabel} returned an unreadable response (${statusLabel}).`);
    }

    const trimmed = String(responseText || '').trim();
    if (!trimmed) {
        return {};
    }

    try {
        return JSON.parse(trimmed);
    } catch (_parseError) {
        const snippet = summarizeServerResponseText(trimmed);
        const suffix = snippet ? ` Response: ${snippet}` : '';
        throw new Error(`${requestLabel} returned a non-JSON response (${statusLabel}).${suffix}`);
    }
}
