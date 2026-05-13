export function activateConverterTab(target, { focus = false } = {}) {
    const normalizedTarget = String(target || '').trim().toLowerCase();
    if (!normalizedTarget) {
        return false;
    }

    const tabButton = document.getElementById(`${normalizedTarget}-tab`);
    if (!tabButton) {
        return false;
    }

    if (
        window.bootstrap
        && window.bootstrap.Tab
        && typeof window.bootstrap.Tab.getOrCreateInstance === 'function'
    ) {
        window.bootstrap.Tab.getOrCreateInstance(tabButton).show();
    } else {
        tabButton.click();
    }

    if (focus && typeof tabButton.focus === 'function') {
        tabButton.focus();
    }

    return true;
}

export function activateConverterTabFromQuery(search = window.location.search) {
    const requestedTab = new URLSearchParams(search).get('tab');
    return activateConverterTab(requestedTab);
}