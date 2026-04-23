(function () {
    const MODE_STORAGE_KEY = 'prism.filePickerMode';

    const state = {
        initialized: false,
        mode: 'auto',
        connectedToServer: null,
        serverPlatform: 'unknown',
        clientPlatform: 'unknown',
        remoteDetected: false,
        initPromise: null,
    };

    function normalizePlatform(value) {
        const raw = String(value || '').toLowerCase();
        if (!raw) return 'unknown';
        if (raw.includes('mac') || raw.includes('darwin')) return 'macos';
        if (raw.includes('win')) return 'windows';
        if (raw.includes('linux') || raw.includes('x11')) return 'linux';
        return 'unknown';
    }

    function getClientPlatform() {
        const uaDataPlatform = (navigator.userAgentData && navigator.userAgentData.platform) || '';
        const platform = navigator.platform || '';
        return normalizePlatform(uaDataPlatform || platform);
    }

    function readStoredMode() {
        try {
            const value = (window.localStorage && window.localStorage.getItem(MODE_STORAGE_KEY)) || 'auto';
            if (value === 'host' || value === 'server' || value === 'auto') {
                return value;
            }
        } catch (_error) {
            // Ignore storage errors and keep auto mode.
        }
        return 'auto';
    }

    function writeStoredMode(value) {
        try {
            if (window.localStorage) {
                window.localStorage.setItem(MODE_STORAGE_KEY, value);
            }
        } catch (_error) {
            // Ignore storage write failures.
        }
    }

    function getEffectiveMode() {
        if (state.connectedToServer === true) {
            return 'server';
        }
        if (state.connectedToServer === false) {
            return 'host';
        }

        if (state.mode === 'host' || state.mode === 'server') {
            return state.mode;
        }
        return state.remoteDetected ? 'server' : 'host';
    }

    async function init() {
        if (state.initialized) {
            return state;
        }

        if (state.initPromise) {
            return state.initPromise;
        }

        state.initPromise = (async () => {
            state.mode = readStoredMode();
            state.clientPlatform = getClientPlatform();

            try {
                const settingsResponse = await fetch('/api/settings/global-library');
                const settingsPayload = await settingsResponse.json();
                if (settingsResponse.ok && settingsPayload && settingsPayload.success) {
                    if (typeof settingsPayload.connected_to_server === 'boolean') {
                        state.connectedToServer = settingsPayload.connected_to_server;
                    }
                }
            } catch (_error) {
                // Keep auto detection fallback when settings are unavailable.
            }

            try {
                const response = await fetch('/api/filesystem-context');
                const payload = await response.json();
                if (response.ok) {
                    state.serverPlatform = normalizePlatform(payload.server_platform || payload.server_system);
                }
            } catch (_error) {
                state.serverPlatform = 'unknown';
            }

            state.remoteDetected = (
                state.clientPlatform !== 'unknown' &&
                state.serverPlatform !== 'unknown' &&
                state.clientPlatform !== state.serverPlatform
            );

            state.initialized = true;
            return state;
        })();

        return state.initPromise;
    }

    async function pickFolder(options) {
        await init();
        if (!(window.PrismFolderBrowser && typeof window.PrismFolderBrowser.open === 'function')) {
            return '';
        }
        return window.PrismFolderBrowser.open(Object.assign({}, options || {}, { mode: 'folder' }));
    }

    async function pickFile(options) {
        await init();
        if (!(window.PrismFolderBrowser && typeof window.PrismFolderBrowser.open === 'function')) {
            return '';
        }
        return window.PrismFolderBrowser.open(Object.assign({}, options || {}, { mode: 'file' }));
    }

    window.PrismFileSystemMode = {
        init,
        getState: () => ({
            mode: state.mode,
            connectedToServer: state.connectedToServer,
            effectiveMode: getEffectiveMode(),
            serverPlatform: state.serverPlatform,
            clientPlatform: state.clientPlatform,
            remoteDetected: state.remoteDetected,
        }),
        getMode: () => state.mode,
        setMode: (value) => {
            const normalized = (value === 'host' || value === 'server') ? value : 'auto';
            state.mode = normalized;
            writeStoredMode(normalized);
        },
        setConnectedToServer: (value) => {
            if (value === null || value === undefined) {
                state.connectedToServer = null;
                return;
            }
            state.connectedToServer = Boolean(value);
        },
        getEffectiveMode,
        prefersServerPicker: () => getEffectiveMode() === 'server',
        pickFolder,
        pickFile,
    };

    window.PrismFileSystemMode.init();
})();
