function getFileSystemMode() {
    return typeof window !== 'undefined' ? window.PrismFileSystemMode : null;
}

export function prefersServerPicker() {
    const fileSystemMode = getFileSystemMode();
    return Boolean(
        fileSystemMode
        && typeof fileSystemMode.prefersServerPicker === 'function'
        && fileSystemMode.prefersServerPicker()
    );
}

export async function pickServerFile(options) {
    const fileSystemMode = getFileSystemMode();
    if (!(fileSystemMode && typeof fileSystemMode.pickFile === 'function')) {
        return '';
    }

    return fileSystemMode.pickFile(options);
}

export async function pickServerFolder(options) {
    const fileSystemMode = getFileSystemMode();
    if (!(fileSystemMode && typeof fileSystemMode.pickFolder === 'function')) {
        return '';
    }

    return fileSystemMode.pickFolder(options);
}