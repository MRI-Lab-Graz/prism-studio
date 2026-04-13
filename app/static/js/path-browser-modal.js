(function () {
    function escHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    const modalEl = document.getElementById('folderBrowserModal');
    if (!modalEl) {
        window.PrismFolderBrowser = {
            async open() {
                return '';
            }
        };
        return;
    }

    const titleEl = document.getElementById('folderBrowserModalLabel');
    const listEl = document.getElementById('folderBrowserList');
    const currentPathEl = document.getElementById('folderBrowserCurrentPath');
    const rootsEl = document.getElementById('folderBrowserRoots');
    const upBtn = document.getElementById('folderBrowserUp');
    const selectBtn = document.getElementById('folderBrowserSelectBtn');
    const selectedHintEl = document.getElementById('folderBrowserSelectedHint');
    const selectedPathEl = document.getElementById('folderBrowserSelectedPath');

    const state = {
        currentPath: '',
        parentPath: '',
        selectedPath: '',
        resolve: null,
        modal: null
    };

    function setSelectedPath(path) {
        state.selectedPath = path || '';
        if (state.selectedPath) {
            selectedPathEl.textContent = state.selectedPath;
            selectedHintEl.style.display = '';
            selectBtn.disabled = false;
        } else {
            selectedPathEl.textContent = '';
            selectedHintEl.style.display = 'none';
            selectBtn.disabled = true;
        }
    }

    function renderRoots(roots) {
        if (!Array.isArray(roots) || !roots.length) {
            rootsEl.innerHTML = '';
            rootsEl.style.display = 'none';
            return;
        }

        rootsEl.innerHTML = roots.map(root => `
            <button type="button" class="btn btn-sm btn-outline-secondary folder-browser-root" data-path="${escHtml(root.path)}">
                ${escHtml(root.name)}
            </button>
        `).join('');
        rootsEl.style.display = '';

        rootsEl.querySelectorAll('.folder-browser-root').forEach(button => {
            button.addEventListener('click', () => {
                loadFolder(button.dataset.path || '');
            });
        });
    }

    async function loadFolder(path) {
        listEl.innerHTML = '<div class="d-flex justify-content-center align-items-center h-100 py-5 text-muted"><span><i class="fas fa-spinner fa-spin me-2"></i>Loading...</span></div>';
        setSelectedPath('');

        try {
            const url = path
                ? `/api/fs/browse?path=${encodeURIComponent(path)}`
                : '/api/fs/browse';
            const response = await fetch(url);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Could not load directory.');
            }

            state.currentPath = data.path || '';
            state.parentPath = data.parent || '';
            currentPathEl.textContent = state.currentPath;
            upBtn.disabled = !state.parentPath;
            renderRoots(data.roots || []);
            setSelectedPath(state.currentPath);

            if (Array.isArray(data.dirs) && data.dirs.length) {
                listEl.innerHTML = data.dirs.map(dir => `
                    <button type="button" class="list-group-item list-group-item-action d-flex align-items-center folder-browser-dir" data-path="${escHtml(dir.path)}">
                        <i class="fas fa-folder text-warning me-2"></i>
                        <span>${escHtml(dir.name)}</span>
                        <i class="fas fa-chevron-right ms-auto text-muted small"></i>
                    </button>
                `).join('');

                listEl.querySelectorAll('.folder-browser-dir').forEach(button => {
                    button.addEventListener('click', () => {
                        loadFolder(button.dataset.path || '');
                    });
                });
            } else {
                listEl.innerHTML = '<div class="text-muted px-3 py-3"><i class="fas fa-folder-open me-1"></i>No subfolders in this location.</div>';
            }
        } catch (error) {
            console.error('Folder browser error:', error);
            currentPathEl.textContent = '';
            state.currentPath = '';
            state.parentPath = '';
            upBtn.disabled = true;
            renderRoots([]);
            setSelectedPath('');
            listEl.innerHTML = `<div class="text-danger px-3 py-3"><i class="fas fa-exclamation-triangle me-1"></i>${escHtml(error.message || 'Could not load directory.')}</div>`;
        }
    }

    function resolveAndHide(path) {
        const resolve = state.resolve;
        state.resolve = null;
        if (resolve) {
            resolve(path || '');
        }
        state.modal.hide();
    }

    state.modal = window.bootstrap && typeof window.bootstrap.Modal === 'function'
        ? window.bootstrap.Modal.getOrCreateInstance(modalEl)
        : null;

    upBtn.addEventListener('click', () => {
        if (state.parentPath) {
            loadFolder(state.parentPath);
        }
    });

    selectBtn.addEventListener('click', () => {
        resolveAndHide(state.selectedPath || state.currentPath);
    });

    modalEl.addEventListener('hidden.bs.modal', () => {
        if (state.resolve) {
            const resolve = state.resolve;
            state.resolve = null;
            resolve('');
        }
    });

    window.PrismFolderBrowser = {
        async open(options = {}) {
            if (!state.modal) {
                return '';
            }

            const title = String(options.title || 'Select Folder').trim() || 'Select Folder';
            const confirmLabel = String(options.confirmLabel || 'Select Folder').trim() || 'Select Folder';
            const startPath = String(options.startPath || '').trim();

            titleEl.innerHTML = `<i class="fas fa-folder-open text-primary me-2"></i>${escHtml(title)}`;
            selectBtn.innerHTML = `<i class="fas fa-check me-1"></i>${escHtml(confirmLabel)}`;
            currentPathEl.textContent = '';
            renderRoots([]);

            const openPromise = new Promise(resolve => {
                state.resolve = resolve;
            });

            await loadFolder(startPath);
            state.modal.show();
            return openPromise;
        }
    };
})();