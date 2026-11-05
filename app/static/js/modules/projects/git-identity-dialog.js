// Pop-up asking for the name and email git signs saved changes with. Saves through the Settings route:
// the identity belongs to the person (this computer's git config), never to the project.
// Resolves true once saved, false when the user cancels.
export async function askGitIdentity({ fetchWithApiFallback }) {
    const modalElement = document.getElementById('gitIdentityModal');
    if (!modalElement || !window.bootstrap) return false;
    const form = document.getElementById('gitIdentityModalForm');
    const name = document.getElementById('gitIdentityModalName');
    const email = document.getElementById('gitIdentityModalEmail');
    const error = document.getElementById('gitIdentityModalError');
    error.textContent = '';

    try {
        const data = await (await fetchWithApiFallback('/api/settings/git-identity')).json();
        name.value = data.name || '';
        email.value = data.email || '';
    } catch (_) { /* leave the fields empty */ }

    const modal = window.bootstrap.Modal.getOrCreateInstance(modalElement);
    return new Promise((resolve) => {
        let saved = false;
        form.onsubmit = async (event) => {
            event.preventDefault();
            try {
                const response = await fetchWithApiFallback('/api/settings/git-identity', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name.value, email: email.value })
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
