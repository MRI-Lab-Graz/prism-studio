/** What the read-only box next to a Browse button shows: the picked server path, or the chosen file(s). */
export function pickedLabel({ files = [], path = '', empty = 'No file selected' } = {}) {
    if (path) return path;
    const list = Array.from(files || []);
    if (list.length === 1) return list[0].name;
    return list.length > 1 ? `${list.length} files selected` : empty;
}

export function syncPickedLabel(element, options) {
    if (!element) return;
    element.value = pickedLabel(options);
    element.title = element.value;
}
