import { prefersServerPicker } from '../../shared/path-picker.js';

export { prefersServerPicker };

function getPathPicker() {
    return typeof window !== 'undefined' ? window.PrismPathPicker : null;
}

export async function pickServerFile(options) {
    const pathPicker = getPathPicker();
    if (!(pathPicker && typeof pathPicker.pickServerFile === 'function')) {
        return '';
    }

    return pathPicker.pickServerFile(options);
}

export async function pickServerFolder(options) {
    const pathPicker = getPathPicker();
    if (!(pathPicker && typeof pathPicker.pickServerFolder === 'function')) {
        return '';
    }

    return pathPicker.pickServerFolder(options);
}