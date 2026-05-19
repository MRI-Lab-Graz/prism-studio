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

export function prefersServerPicker() {
    const pathPicker = getPathPicker();
    if (pathPicker && typeof pathPicker.prefersServerPicker === 'function') {
        return Boolean(pathPicker.prefersServerPicker());
    }

    return Boolean(
        window.PrismFileSystemMode
        && typeof window.PrismFileSystemMode.prefersServerPicker === 'function'
        && window.PrismFileSystemMode.prefersServerPicker()
    );
}

export async function browseFolderWithFallback(_fetchWithApiFallback, options = {}) {
    return requirePathPicker('browseFolder').browseFolder(options);
}

export async function browseFileWithFallback(_fetchWithApiFallback, options = {}) {
    return requirePathPicker('browseFile').browseFile(options);
}