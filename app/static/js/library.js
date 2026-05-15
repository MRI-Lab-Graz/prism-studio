import { fetchWithRelativePathFallback } from './shared/api.js';

async function fetchLibraryApi(path, options = {}) {
    const response = await fetchWithRelativePathFallback(path, options);
    const payload = await response.json().catch(() => ({}));

    if (!response.ok || !payload.success) {
        throw new Error(payload.error || `Request failed (${response.status})`);
    }

    return payload;
}

function reloadPage() {
    window.location.reload();
}

async function createDraft(filename) {
    await fetchLibraryApi(`/library/api/draft/${encodeURIComponent(filename)}`, {
        method: 'POST',
    });
    reloadPage();
}

async function publishSurvey(filename) {
    const confirmed = window.confirm(
        `Are you sure you want to SUBMIT ${filename} for review? This will move the draft to the merge requests folder.`
    );
    if (!confirmed) return;

    await fetchLibraryApi(`/library/api/publish/${encodeURIComponent(filename)}`, {
        method: 'POST',
    });
    reloadPage();
}

async function discardDraft(filename) {
    const confirmed = window.confirm(
        `Discard draft for ${filename}? All unsaved changes will be lost.`
    );
    if (!confirmed) return;

    await fetchLibraryApi(`/library/api/draft/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
    });
    reloadPage();
}

document.addEventListener('DOMContentLoaded', () => {
    const tableBody = document.querySelector('table tbody');
    if (!tableBody) return;

    tableBody.addEventListener('click', async (event) => {
        const button = event.target.closest('button[data-action][data-filename]');
        if (!button) return;

        const action = button.getAttribute('data-action');
        const filename = button.getAttribute('data-filename');
        if (!filename) return;

        try {
            if (action === 'create-draft') {
                await createDraft(filename);
                return;
            }
            if (action === 'publish-survey') {
                await publishSurvey(filename);
                return;
            }
            if (action === 'discard-draft') {
                await discardDraft(filename);
            }
        } catch (error) {
            window.alert(error.message || 'Network error while processing library action.');
        }
    });
});
