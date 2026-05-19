export function prefersServerPicker() {
    return Boolean(
        window.PrismFileSystemMode
        && typeof window.PrismFileSystemMode.prefersServerPicker === 'function'
        && window.PrismFileSystemMode.prefersServerPicker()
    );
}

function openInAppPicker(options = {}) {
    if (!(window.PrismFolderBrowser && typeof window.PrismFolderBrowser.open === 'function')) {
        return null;
    }

    return window.PrismFolderBrowser.open(options);
}

async function runInAppFallback(options = {}, fallback = null) {
    if (typeof fallback === 'function') {
        return fallback();
    }

    const inAppResult = openInAppPicker(options);
    if (inAppResult !== null) {
        return inAppResult;
    }

    throw new Error('In-app picker unavailable.');
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
        return runInAppFallback({
            title: options.title || 'Select Folder',
            confirmLabel: options.confirmLabel || 'Select Folder',
            startPath: options.startPath || ''
        }, options.fallback);
    }
}

export async function browseFileWithFallback(fetchWithApiFallback, options = {}) {
    const projectJsonOnly = options.projectJsonOnly !== false;

    if (prefersServerPicker()
        && window.PrismFileSystemMode
        && typeof window.PrismFileSystemMode.pickFile === 'function') {
        return window.PrismFileSystemMode.pickFile({
            title: options.title || 'Select File',
            confirmLabel: options.confirmLabel || 'Use This File',
            startPath: options.startPath || '',
            extensions: options.extensions || ''
        });
    }

    try {
        const query = projectJsonOnly ? '' : '?project_json_only=0';
        const response = await fetchWithApiFallback(`/api/browse-file${query}`);
        const data = await response.json();
        if (!response.ok || data.error) {
            throw new Error(data.error || 'File picker unavailable.');
        }
        return (data.path || '').trim();
    } catch (error) {
        console.warn('Native file picker failed, falling back to in-app browser:', error);
        return runInAppFallback({
            title: options.title || 'Select File',
            confirmLabel: options.confirmLabel || 'Use This File',
            startPath: options.startPath || '',
            mode: 'file'
        }, options.fallback);
    }
}