/**
 * Shared download utilities
 */

/**
 * Decode a base64-encoded ZIP and trigger a browser download.
 * @param {string} base64Data - Base64-encoded ZIP content
 * @param {string} filename - Suggested filename for the download
 */
export function downloadBase64Zip(base64Data, filename) {
    const binaryString = window.atob(base64Data);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: 'application/zip' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
}
