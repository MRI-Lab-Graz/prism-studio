// The wording comes from the backend (not_ready_message); only "Saved." is added here.
export function bannerText(message, justSaved) {
    if (!message) return '';
    return justSaved ? `Saved. ${message}` : message;
}

export function renderNotReadyBanner(message, justSaved = false) {
    const el = document.getElementById('smNotReadyBanner');
    if (!el) return;
    const text = bannerText(message, justSaved);
    el.textContent = text;
    el.classList.toggle('d-none', !text);
}
