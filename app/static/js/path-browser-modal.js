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
    const pathInputEl = document.getElementById('folderBrowserPathInput');
    const goBtnEl = document.getElementById('folderBrowserGoBtn');

    const state = {
        currentPath: '',
        parentPath: '',
        selectedPath: '',
        selectionMode: 'folder',
        fileExtensions: '',
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

    function setSelectionMode(mode) {
        state.selectionMode = mode === 'file' ? 'file' : 'folder';
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
            const query = new URLSearchParams();
            if (path) {
                query.set('path', path);
            }
            if (state.selectionMode === 'file') {
                query.set('include_files', '1');
                if (state.fileExtensions) {
                    query.set('extensions', state.fileExtensions);
                }
            }

            const url = `/api/fs/browse${query.toString() ? `?${query.toString()}` : ''}`;
            const response = await fetch(url);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Could not load directory.');
            }

            state.currentPath = data.path || '';
            state.parentPath = data.parent || '';
            currentPathEl.textContent = state.currentPath;
            if (pathInputEl) pathInputEl.value = state.currentPath;
            upBtn.disabled = !state.parentPath;
            renderRoots(data.roots || []);
            if (state.selectionMode === 'folder') {
                setSelectedPath(state.currentPath);
            }

            const dirs = Array.isArray(data.dirs) ? data.dirs : [];
            const files = Array.isArray(data.files) ? data.files : [];

            const entries = [];
            dirs.forEach((dir) => {
                entries.push(`
                    <button type="button" class="list-group-item list-group-item-action d-flex align-items-center folder-browser-dir" data-path="${escHtml(dir.path)}">
                        <i class="fas fa-folder text-warning me-2"></i>
                        <span>${escHtml(dir.name)}</span>
                        <i class="fas fa-chevron-right ms-auto text-muted small"></i>
                    </button>
                `);
            });

            if (state.selectionMode === 'file') {
                files.forEach((file) => {
                    entries.push(`
                        <button type="button" class="list-group-item list-group-item-action d-flex align-items-center folder-browser-file" data-path="${escHtml(file.path)}">
                            <i class="fas fa-file-lines text-secondary me-2"></i>
                            <span>${escHtml(file.name)}</span>
                            <small class="ms-auto text-muted">${Number(file.size || 0).toLocaleString()} B</small>
                        </button>
                    `);
                });
            }

            if (entries.length > 0) {
                listEl.innerHTML = entries.join('');

                listEl.querySelectorAll('.folder-browser-dir').forEach(button => {
                    button.addEventListener('click', () => {
                        loadFolder(button.dataset.path || '');
                    });
                });

                listEl.querySelectorAll('.folder-browser-file').forEach(button => {
                    button.addEventListener('click', () => {
                        setSelectedPath(button.dataset.path || '');
                    });
                });
            } else {
                listEl.innerHTML = state.selectionMode === 'file'
                    ? '<div class="text-muted px-3 py-3"><i class="fas fa-folder-open me-1"></i>No matching entries in this location.</div>'
                    : '<div class="text-muted px-3 py-3"><i class="fas fa-folder-open me-1"></i>No subfolders in this location.</div>';
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

    if (goBtnEl) {
        goBtnEl.addEventListener('click', () => {
            const typed = (pathInputEl ? pathInputEl.value : '').trim();
            if (typed) loadFolder(typed);
        });
    }
    if (pathInputEl) {
        pathInputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const typed = pathInputEl.value.trim();
                if (typed) loadFolder(typed);
            }
        });
    }

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
            const mode = String(options.mode || 'folder').trim().toLowerCase() === 'file' ? 'file' : 'folder';
            const defaultConfirm = mode === 'file' ? 'Select File' : 'Select Folder';
            const confirmLabel = String(options.confirmLabel || defaultConfirm).trim() || defaultConfirm;
            const startPath = String(options.startPath || '').trim();
            const extensions = String(options.extensions || '').trim();

            setSelectionMode(mode);
            state.fileExtensions = extensions;

            titleEl.innerHTML = `<i class="fas fa-folder-open text-primary me-2"></i>${escHtml(title)}`;
            selectBtn.innerHTML = `<i class="fas fa-check me-1"></i>${escHtml(confirmLabel)}`;
            currentPathEl.textContent = '';
            if (pathInputEl) pathInputEl.value = '';
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