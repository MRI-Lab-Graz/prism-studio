// Pop-up asking who signs a project's DataLad snapshots. Saves through the same route as the project page card.
// Resolves true once saved, false when the user cancels.
export async function askGitIdentity({ fetchWithApiFallback, projectPath }) {
    const modalElement = document.getElementById('gitIdentityModal');
    if (!modalElement || !window.bootstrap) return false;
    const form = document.getElementById('gitIdentityModalForm');
    const name = document.getElementById('gitIdentityModalName');
    const email = document.getElementById('gitIdentityModalEmail');
    const error = document.getElementById('gitIdentityModalError');
    error.textContent = '';

    // Prefill with the project's identity, else the computer's, so a personal user only confirms.
    for (const url of [`/api/projects/git-identity?project_path=${encodeURIComponent(projectPath)}`, '/api/settings/git-identity']) {
        try {
            const data = await (await fetchWithApiFallback(url)).json();
            if (data.name && data.email) {
                name.value = data.name;
                email.value = data.email;
                break;
            }
        } catch (_) { /* leave the fields empty */ }
    }

    const modal = window.bootstrap.Modal.getOrCreateInstance(modalElement);
    return new Promise((resolve) => {
        let saved = false;
        form.onsubmit = async (event) => {
            event.preventDefault();
            try {
                const response = await fetchWithApiFallback('/api/projects/git-identity', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project_path: projectPath, name: name.value, email: email.value })
                });
                const data = await response.json();
                if (!response.ok || !data.success) throw new Error(data.error || 'Could not save.');
                saved = true;
                modal.hide();
            } catch (err) {
                error.textContent = err.message || 'Could not save.';
            }
        };
        modalElement.addEventListener('hidden.bs.modal', () => resolve(saved), { once: true });
        modal.show();
    });
}
