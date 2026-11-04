// Project page: the git name + email DataLad signs this project's snapshots with (stored in the project, not the machine).
export function initGitIdentityCard({ fetchWithApiFallback }) {
    const card = document.getElementById('gitIdentityCard');
    if (!card) return;
    const name = document.getElementById('gitIdentityName');
    const email = document.getElementById('gitIdentityEmail');
    const badge = document.getElementById('gitIdentityBadge');
    const feedback = document.getElementById('gitIdentityFeedback');
    let projectPath = '';

    const show = (ok, text) => {
        feedback.className = `small mt-2 ${ok ? 'text-success' : 'text-danger'}`;
        feedback.textContent = text;
    };
    const render = (data) => {
        name.value = data.name || '';
        email.value = data.email || '';
        const set = Boolean(data.name && data.email);
        badge.textContent = set ? 'Set' : 'Not set';
        badge.className = `badge ${set ? 'bg-success' : 'bg-secondary'}`;
    };

    async function showFor(path) {
        projectPath = String(path || '').trim();
        card.classList.toggle('d-none', !projectPath);
        feedback.textContent = '';
        if (!projectPath) return;
        try {
            const response = await fetchWithApiFallback(`/api/projects/git-identity?project_path=${encodeURIComponent(projectPath)}`);
            render(await response.json());
        } catch (error) {
            console.error('Error loading the project git identity:', error);
        }
    }

    document.getElementById('gitIdentityForm').addEventListener('submit', async (event) => {
        event.preventDefault();
        try {
            const response = await fetchWithApiFallback('/api/projects/git-identity', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_path: projectPath, name: name.value, email: email.value })
            });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || 'Could not save.');
            render(data);
            show(true, 'Saved.');
        } catch (error) {
            show(false, error.message || 'Could not save.');
        }
    });

    window.addEventListener('prism-project-opened', (event) => showFor(event.detail?.path));
    fetchWithApiFallback('/api/projects/current')
        .then((response) => response.json())
        .then((current) => showFor(current?.path))
        .catch(() => {});
}
