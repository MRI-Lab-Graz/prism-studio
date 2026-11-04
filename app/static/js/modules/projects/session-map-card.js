import { changedEntries, validSessionName } from '../converter/session-map-panel.js';

// Project page: the saved session map (source label -> session name), editable. Saving is the CLI's
// `session-map set`, through /api/session-map; only the names that changed are sent.
export function initSessionMapCard({ fetchWithApiFallback }) {
    const card = document.getElementById('sessionMapCard');
    if (!card) return;
    const rows = document.getElementById('sessionMapRows');
    const save = document.getElementById('sessionMapSave');
    const feedback = document.getElementById('sessionMapFeedback');
    let projectPath = '';
    let saved = {};
    const typed = {};

    const show = (ok, text) => {
        feedback.className = `small mt-2 ${ok ? 'text-success' : 'text-danger'}`;
        feedback.textContent = text;
    };
    const refresh = () => {
        const bad = Object.values(typed).some((value) => !validSessionName(value));
        save.disabled = bad || Object.keys(changedEntries(saved, typed)).length === 0;
    };
    const render = (map) => {
        saved = map;
        Object.keys(typed).forEach((key) => delete typed[key]);
        rows.replaceChildren(
            ...Object.entries(map).map(([label, name]) => {
                const group = document.createElement('div');
                group.className = 'input-group input-group-sm mb-1';
                const source = document.createElement('span');
                source.className = 'input-group-text';
                source.textContent = label;
                const input = document.createElement('input');
                input.className = 'form-control';
                input.value = name;
                input.setAttribute('aria-label', `Session name for ${label}`);
                input.addEventListener('input', () => {
                    typed[label] = input.value;
                    refresh();
                });
                group.append(source, input);
                return group;
            })
        );
        card.classList.toggle('d-none', Object.keys(map).length === 0);
        refresh();
    };

    async function showFor(path) {
        projectPath = String(path || '').trim();
        card.classList.add('d-none');
        feedback.textContent = '';
        if (!projectPath) return;
        try {
            const response = await fetchWithApiFallback(`/api/session-map?project_path=${encodeURIComponent(projectPath)}`);
            const body = await response.json();
            if (body.ok) render(body.map);
        } catch (error) {
            console.error('Error loading the session map:', error);
        }
    }

    save.addEventListener('click', async () => {
        try {
            const response = await fetchWithApiFallback('/api/session-map', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_path: projectPath, entries: changedEntries(saved, typed) }),
            });
            const body = await response.json();
            if (!response.ok) throw new Error(body.error || 'Could not save.');
            render(body.map);
            show(true, 'Saved. New imports use these names; folders already written are not renamed.');
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
