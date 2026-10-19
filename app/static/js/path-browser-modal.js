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
    const pathRowEl = document.getElementById('folderBrowserPathRow');
    const editPathBtn = document.getElementById('folderBrowserEditPath');
    const filterEl = document.getElementById('folderBrowserFilter');
    const headerEl = document.getElementById('folderBrowserHeader');

    const state = {
        currentPath: '',
        parentPath: '',
        selectedPath: '',
        selectionMode: 'folder',
        fileExtensions: '',
        sort: 'name',
        order: 'asc',
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

    function formatSize(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        const units = ['KB', 'MB', 'GB', 'TB'];
        let value = bytes;
        let i = -1;
        do { value /= 1024; i += 1; } while (value >= 1024 && i < units.length - 1);
        return `${value.toFixed(value < 10 ? 1 : 0)} ${units[i]}`;
    }

    function formatDate(epochSeconds) {
        return epochSeconds ? new Date(epochSeconds * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '';
    }

    function projectRoot() {
        const store = window.prismProjectStateStore;
        return (store && store.getState && store.getState().path) || window.currentProjectPath || '';
    }

    function renderPlaces(roots) {
        const places = [];
        if (projectRoot()) places.push({ name: 'Project', path: projectRoot(), icon: 'fa-folder-tree' });
        places.push({ name: 'Home', path: '', icon: 'fa-house' });
        (roots || []).forEach(root => places.push({ name: root.name, path: root.path, icon: 'fa-hard-drive' }));

        rootsEl.innerHTML = places.map(place => `
            <button type="button" class="btn btn-sm btn-light text-start folder-browser-root" data-path="${escHtml(place.path)}">
                <i class="fas ${place.icon} me-2 text-secondary"></i>${escHtml(place.name)}
            </button>
        `).join('');
        rootsEl.querySelectorAll('.folder-browser-root').forEach(button => {
            button.addEventListener('click', () => loadFolder(button.dataset.path || ''));
        });
    }

    function renderCrumbs(crumbs) {
        currentPathEl.innerHTML = (crumbs || []).map((crumb, i) => `
            ${i ? '<i class="fas fa-chevron-right text-muted mx-1" style="font-size:.6rem"></i>' : ''}<button type="button" class="btn btn-link btn-sm folder-browser-crumb" data-path="${escHtml(crumb.path)}">${escHtml(crumb.name)}</button>
        `).join('');
        currentPathEl.querySelectorAll('.folder-browser-crumb').forEach(button => {
            button.addEventListener('click', () => loadFolder(button.dataset.path || ''));
        });
    }

    function renderSortIndicators() {
        headerEl.querySelectorAll('button[data-sort]').forEach(button => {
            const active = button.dataset.sort === state.sort;
            const icon = button.querySelector('i');
            icon.className = `fas ms-1 ${active ? (state.order === 'asc' ? 'fa-sort-up' : 'fa-sort-down') : 'fa-sort text-muted'}`;
        });
    }

    function applyFilter() {
        const needle = filterEl.value.trim().toLowerCase();
        listEl.querySelectorAll('.fb-entry').forEach(row => {
            row.style.display = !needle || row.dataset.name.toLowerCase().includes(needle) ? '' : 'none';
        });
    }

    function entryRow(entry, isDir) {
        const icon = isDir ? 'fa-folder text-warning' : 'fa-file-lines text-secondary';
        return `
            <button type="button" class="fb-entry fb-row w-100 border-0 bg-transparent text-start ${isDir ? 'folder-browser-dir' : 'folder-browser-file'}" data-path="${escHtml(entry.path)}" data-name="${escHtml(entry.name)}">
                <span class="fb-name"><i class="fas ${icon} me-2"></i>${escHtml(entry.name)}</span>
                <span class="fb-modified text-muted small">${escHtml(formatDate(entry.modified))}</span>
                <span class="text-muted small text-end">${isDir ? '' : formatSize(Number(entry.size || 0))}</span>
            </button>
        `;
    }

    async function loadFolder(path) {
        listEl.innerHTML = '<div class="d-flex justify-content-center align-items-center h-100 py-5 text-muted"><span><i class="fas fa-spinner fa-spin me-2"></i>Loading...</span></div>';
        setSelectedPath('');
        filterEl.value = '';

        try {
            const query = new URLSearchParams({ sort: state.sort, order: state.order });
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
            renderCrumbs(data.crumbs);
            if (pathInputEl) pathInputEl.value = state.currentPath;
            upBtn.disabled = !state.parentPath;
            renderPlaces(data.roots);
            renderSortIndicators();
            if (state.selectionMode === 'folder') {
                setSelectedPath(state.currentPath);
            }

            const dirs = Array.isArray(data.dirs) ? data.dirs : [];
            const files = Array.isArray(data.files) ? data.files : [];

            const entries = dirs.map(dir => entryRow(dir, true));
            if (state.selectionMode === 'file') {
                files.forEach(file => entries.push(entryRow(file, false)));
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
                        listEl.querySelectorAll('.fb-entry.selected').forEach(row => row.classList.remove('selected'));
                        button.classList.add('selected');
                        setSelectedPath(button.dataset.path || '');
                    });
                    button.addEventListener('dblclick', () => resolveAndHide(button.dataset.path || ''));
                });
                applyFilter();
            } else {
                listEl.innerHTML = state.selectionMode === 'file'
                    ? '<div class="text-muted px-3 py-3"><i class="fas fa-folder-open me-1"></i>No matching entries in this location.</div>'
                    : '<div class="text-muted px-3 py-3"><i class="fas fa-folder-open me-1"></i>No subfolders in this location.</div>';
            }
        } catch (error) {
            console.error('Folder browser error:', error);
            currentPathEl.innerHTML = '';
            state.currentPath = '';
            state.parentPath = '';
            upBtn.disabled = true;
            renderPlaces([]);
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

    function showPathRow(show) {
        pathRowEl.classList.toggle('d-none', !show);
        pathRowEl.classList.toggle('d-flex', show);
        if (show) pathInputEl.focus();
    }
    editPathBtn.addEventListener('click', () => showPathRow(pathRowEl.classList.contains('d-none')));
    currentPathEl.addEventListener('click', (e) => { if (e.target === currentPathEl) showPathRow(true); });
    filterEl.addEventListener('input', applyFilter);
    headerEl.addEventListener('click', (e) => {
        const button = e.target.closest('button[data-sort]');
        if (!button) return;
        state.order = state.sort === button.dataset.sort && state.order === 'asc' ? 'desc' : 'asc';
        state.sort = button.dataset.sort;
        loadFolder(state.currentPath);
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
            currentPathEl.innerHTML = '';
            if (pathInputEl) pathInputEl.value = '';
            filterEl.value = '';
            showPathRow(false);
            renderPlaces([]);

            const openPromise = new Promise(resolve => {
                state.resolve = resolve;
            });

            await loadFolder(startPath);
            state.modal.show();
            return openPromise;
        }
    };
})();