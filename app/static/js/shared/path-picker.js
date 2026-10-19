function getPathPicker() {
    return typeof window !== 'undefined' ? window.PrismPathPicker : null;
}

function requirePathPicker(methodName) {
    const pathPicker = getPathPicker();
    if (!(pathPicker && typeof pathPicker[methodName] === 'function')) {
        throw new Error('Shared path picker is unavailable.');
    }
    return pathPicker;
}

export async function browseFolderWithFallback(_fetchWithApiFallback, options = {}) {
    return requirePathPicker('browseFolder').browseFolder(options);
}

export async function browseFileWithFallback(_fetchWithApiFallback, options = {}) {
    return requirePathPicker('browseFile').browseFile(options);
}

export async function browseSaveFileWithFallback(_fetchWithApiFallback, options = {}) {
    return requirePathPicker('browseSaveFile').browseSaveFile(options);
}

export function isProjectJsonPath(path) {
    return /(^|[\\/])project\.json$/.test(String(path || ''));
}
