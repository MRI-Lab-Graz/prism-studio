export function prefersServerPicker() {
    return Boolean(
        window.PrismFileSystemMode
        && typeof window.PrismFileSystemMode.prefersServerPicker === 'function'
        && window.PrismFileSystemMode.prefersServerPicker()
    );
}

export async function browseFolderWithFallback(fetchWithApiFallback, options = {}) {
    if (prefersServerPicker()
        && window.PrismFolderBrowser
        && typeof window.PrismFolderBrowser.open === 'function') {
        return window.PrismFolderBrowser.open({
            title: options.title || 'Select Folder',
            confirmLabel: options.confirmLabel || 'Select Folder',
            startPath: options.startPath || ''
        });
    }

    try {
        const response = await fetchWithApiFallback('/api/browse-folder');
        const data = await response.json();
        if (!response.ok || data.error) {
            throw new Error(data.error || 'Folder picker unavailable.');
        }
        return (data.path || '').trim();
    } catch (error) {
        console.warn('Native folder picker failed, falling back to in-app browser:', error);
        if (window.PrismFolderBrowser && typeof window.PrismFolderBrowser.open === 'function') {
            return window.PrismFolderBrowser.open({
                title: options.title || 'Select Folder',
                confirmLabel: options.confirmLabel || 'Select Folder',
                startPath: options.startPath || ''
            });
        }
        throw error;
    }
}