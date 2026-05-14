export function initProjectFileBrowser({ fetchWithApiFallback, prefersServerPicker }) {
    const browseExistingPath = document.getElementById('browseExistingPath');
    if (!browseExistingPath) {
        return;
    }

    let currentPath = null;
    let selectedProjectJson = null;

    const modalEl = document.getElementById('projectFileBrowserModal');
    const listEl = document.getElementById('fsBrowserList');
    const currentPathEl = document.getElementById('fsBrowserCurrentPath');
    const upBtn = document.getElementById('fsBrowserUp');
    const selectBtn = document.getElementById('fsBrowserSelectBtn');
    const selectedHintEl = document.getElementById('fsBrowserSelectedHint');
    const selectedPathEl = document.getElementById('fsBrowserSelectedPath');

    function escHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    async function load(path) {
        listEl.innerHTML = '<div class="d-flex justify-content-center align-items-center py-5 text-muted"><span><i class="fas fa-spinner fa-spin me-2"></i>Loading…</span></div>';
        selectedProjectJson = null;
        selectBtn.disabled = true;
        selectedHintEl.style.display = 'none';

        try {
            const url = path ? '/api/fs/browse?path=' + encodeURIComponent(path) : '/api/fs/browse';
            const res = await fetchWithApiFallback(url);
            if (!res.ok) {
                listEl.innerHTML = '<div class="text-danger px-3 py-3"><i class="fas fa-exclamation-triangle me-1"></i>Could not load directory.</div>';
                return;
            }

            const data = await res.json();
            currentPath = data.path;
            currentPathEl.textContent = data.path;
            upBtn.disabled = !data.parent;

            let html = '';

            if (data.has_project_json) {
                html += `<button type="button" class="d-flex align-items-center w-100 px-3 py-2 border-0 border-bottom fb-project-json text-start" style="cursor:pointer;background:#e8f5e9;" data-pjson="${escHtml(data.project_json_path)}" aria-label="Select project.json at ${escHtml(data.project_json_path)}">
                    <i class="fas fa-file-code text-success me-2"></i>
                    <span class="fw-semibold text-success">project.json</span>
                    <span class="ms-auto badge bg-success">Select</span>
                </button>`;
                selectedProjectJson = data.project_json_path;
                selectBtn.disabled = false;
                selectedPathEl.textContent = data.project_json_path;
                selectedHintEl.style.display = '';
            }

            if (data.dirs && data.dirs.length > 0) {
                data.dirs.forEach(dir => {
                    html += `<button type="button" class="d-flex align-items-center w-100 px-3 py-2 border-0 border-bottom fb-dir text-start bg-white" style="cursor:pointer;" data-path="${escHtml(dir.path)}" aria-label="Open folder ${escHtml(dir.name)}">
                        <i class="fas fa-folder text-warning me-2"></i>
                        <span>${escHtml(dir.name)}</span>
                        <i class="fas fa-chevron-right ms-auto text-muted small"></i>
                    </button>`;
                });
            }

            if (!html) {
                html = '<div class="text-muted px-3 py-3"><i class="fas fa-folder-open me-1"></i>Empty folder</div>';
            }

            listEl.innerHTML = html;

            listEl.querySelectorAll('.fb-project-json').forEach(el => {
                el.addEventListener('click', () => {
                    selectedProjectJson = el.dataset.pjson;
                    selectBtn.disabled = false;
                    selectedPathEl.textContent = selectedProjectJson;
                    selectedHintEl.style.display = '';
                });
            });

            listEl.querySelectorAll('.fb-dir').forEach(el => {
                el.addEventListener('click', () => load(el.dataset.path));
            });
        } catch (err) {
            console.error('File browser error:', err);
            listEl.innerHTML = '<div class="text-danger px-3 py-3"><i class="fas fa-exclamation-triangle me-1"></i>Error loading directory.</div>';
        }
    }

    browseExistingPath.addEventListener('click', async function() {
        if (prefersServerPicker()
            && window.PrismFileSystemMode
            && typeof window.PrismFileSystemMode.pickFile === 'function') {
            const existingInput = document.getElementById('existingPath');
            const pickedPath = await window.PrismFileSystemMode.pickFile({
                title: 'Select project.json on Server',
                confirmLabel: 'Use This File',
                extensions: '.json',
                startPath: existingInput && existingInput.value ? existingInput.value : ''
            });

            if (pickedPath && existingInput) {
                existingInput.value = pickedPath;
            }
            return;
        }

        const existing = (document.getElementById('existingPath')?.value || '').trim();
        let startPath = null;
        if (existing) {
            const lastSep = Math.max(existing.lastIndexOf('/'), existing.lastIndexOf('\\'));
            if (lastSep > 0) {
                startPath = existing.substring(0, lastSep);
            }
        }

        load(startPath || null);
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    });

    if (upBtn) {
        upBtn.addEventListener('click', async function() {
            if (!currentPath) return;
            const url = '/api/fs/browse?path=' + encodeURIComponent(currentPath);
            const res = await fetchWithApiFallback(url);
            if (!res.ok) return;
            const data = await res.json();
            if (data.parent) load(data.parent);
        });
    }

    if (selectBtn) {
        selectBtn.addEventListener('click', function() {
            if (selectedProjectJson) {
                const input = document.getElementById('existingPath');
                if (input) input.value = selectedProjectJson;
                bootstrap.Modal.getInstance(modalEl)?.hide();
            }
        });
    }
}