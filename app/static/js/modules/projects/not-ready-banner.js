export function notReadyText(missing) {
    if (!missing || !missing.length) return '';
    return `Saved. Tools are blocked until these are filled: ${missing.join(', ')}.`;
}

// Show/hide the persistent banner; text comes from the backend list.
export function renderNotReadyBanner(missing) {
    const el = document.getElementById('smNotReadyBanner');
    if (!el) return;
    const text = notReadyText(missing);
    el.textContent = text;
    el.classList.toggle('d-none', !text);
}
