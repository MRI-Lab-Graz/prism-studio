import { setButtonLoading } from './helpers.js';
import { fetchWithApiFallback } from '../../shared/api.js';
import { escapeHtml } from '../../shared/dom.js';

export async function loadGlobalSettings() {
    try {
        const response = await fetchWithApiFallback('/api/settings/global-library');
        const data = await response.json();
        if (data.success) {
            const libraryInput = document.getElementById('globalLibraryPath');
            libraryInput.value = data.global_template_library_path || '';
            if (data.default_library_path) {
                libraryInput.placeholder = `Default: ${data.default_library_path}`;
            }

            const recipesInput = document.getElementById('globalRecipesPath');
            recipesInput.value = data.global_recipes_path || '';

            const connectedToggle = document.getElementById('connectedToServerToggle');
            if (connectedToggle) {
                connectedToggle.checked = Boolean(data.connected_to_server);
            }

            if (window.PrismFileSystemMode && typeof window.PrismFileSystemMode.setConnectedToServer === 'function') {
                window.PrismFileSystemMode.setConnectedToServer(Boolean(data.connected_to_server));
            }

            updateLibraryInfoPanel(data.global_template_library_path || data.default_library_path, null);
        }
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

async function loadBackendMonitoringSetting() {
    const toggle = document.getElementById('backendMonitoringToggle');
    const verboseToggle = document.getElementById('backendMonitoringVerboseToggle');
    if (!toggle) return;

    try {
        const response = await fetchWithApiFallback('/api/settings/backend-monitoring');
        const data = await response.json();
        if (data && data.success) {
            const enabled = Boolean(data.backend_monitoring);
            const verboseEnabled = Boolean(data.backend_monitoring_verbose);

            toggle.checked = enabled;
            if (verboseToggle) {
                verboseToggle.checked = verboseEnabled;
                verboseToggle.disabled = !enabled;
                if (!enabled) {
                    verboseToggle.checked = false;
                }
            }
        }
    } catch (error) {
        console.error('Error loading backend monitoring setting:', error);
    }
}

async function saveBackendMonitoringSetting(payload) {
    const response = await fetchWithApiFallback('/api/settings/backend-monitoring', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    const data = await response.json();
    if (!response.ok || !data || !data.success) {
        throw new Error(data?.error || 'Failed to save backend monitoring setting');
    }

    return {
        backendMonitoring: Boolean(data.backend_monitoring),
        backendMonitoringVerbose: Boolean(data.backend_monitoring_verbose),
    };
}

async function loadDedicatedTerminalSetting() {
    const toggle = document.getElementById('dedicatedTerminalToggle');
    if (!toggle) return;

    try {
        const response = await fetchWithApiFallback('/api/settings/dedicated-terminal');
        const data = await response.json();
        if (data && data.success) {
            toggle.checked = Boolean(data.show_dedicated_terminal);
        }
    } catch (error) {
        console.error('Error loading dedicated terminal setting:', error);
    }
}

async function saveDedicatedTerminalSetting(enabled) {
    const response = await fetchWithApiFallback('/api/settings/dedicated-terminal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ show_dedicated_terminal: Boolean(enabled) })
    });

    const data = await response.json();
    if (!response.ok || !data || !data.success) {
        throw new Error(data?.error || 'Failed to save dedicated terminal setting');
    }

    return Boolean(data.show_dedicated_terminal);
}

export function initBackendMonitoringToggle() {
    const toggle = document.getElementById('backendMonitoringToggle');
    const verboseToggle = document.getElementById('backendMonitoringVerboseToggle');
    if (!toggle) return;

    loadBackendMonitoringSetting();

    toggle.addEventListener('change', async () => {
        const desired = Boolean(toggle.checked);
        toggle.disabled = true;
        if (verboseToggle) {
            verboseToggle.disabled = true;
        }

        try {
            const persisted = await saveBackendMonitoringSetting({
                backend_monitoring: desired,
                backend_monitoring_verbose: desired
                    ? Boolean(verboseToggle?.checked)
                    : false,
            });
            toggle.checked = persisted.backendMonitoring;
            if (verboseToggle) {
                verboseToggle.checked = persisted.backendMonitoringVerbose;
                verboseToggle.disabled = !persisted.backendMonitoring;
                if (!persisted.backendMonitoring) {
                    verboseToggle.checked = false;
                }
            }
        } catch (error) {
            console.error('Error saving backend monitoring setting:', error);
            toggle.checked = !desired;
            alert('Could not update backend monitoring setting.');
            if (verboseToggle) {
                verboseToggle.disabled = !toggle.checked;
            }
        } finally {
            toggle.disabled = false;
            if (verboseToggle) {
                verboseToggle.disabled = !toggle.checked;
            }
        }
    });

    if (verboseToggle) {
        verboseToggle.addEventListener('change', async () => {
            const desiredVerbose = Boolean(verboseToggle.checked);
            const baseEnabled = Boolean(toggle.checked);

            if (!baseEnabled) {
                verboseToggle.checked = false;
                return;
            }

            toggle.disabled = true;
            verboseToggle.disabled = true;
            try {
                const persisted = await saveBackendMonitoringSetting({
                    backend_monitoring_verbose: desiredVerbose,
                });
                toggle.checked = persisted.backendMonitoring;
                verboseToggle.checked = persisted.backendMonitoringVerbose;
                verboseToggle.disabled = !persisted.backendMonitoring;
            } catch (error) {
                console.error('Error saving backend monitoring verbose setting:', error);
                verboseToggle.checked = !desiredVerbose;
                alert('Could not update backend monitoring verbose setting.');
                verboseToggle.disabled = !toggle.checked;
            } finally {
                toggle.disabled = false;
                verboseToggle.disabled = !toggle.checked;
            }
        });
    }
}

export function initDedicatedTerminalToggle() {
    const toggle = document.getElementById('dedicatedTerminalToggle');
    if (!toggle) return;

    loadDedicatedTerminalSetting();

    toggle.addEventListener('change', async () => {
        const desired = Boolean(toggle.checked);
        toggle.disabled = true;

        try {
            const persisted = await saveDedicatedTerminalSetting(desired);
            toggle.checked = persisted;
        } catch (error) {
            console.error('Error saving dedicated terminal setting:', error);
            toggle.checked = !desired;
            alert('Could not update dedicated terminal setting.');
        } finally {
            toggle.disabled = false;
        }
    });
}

export async function loadLibraryInfo() {
    try {
        const response = await fetchWithApiFallback('/api/projects/library-path');
        const data = await response.json();

        const infoPanel = document.getElementById('libraryInfoPanel');
        infoPanel.style.display = 'block';

        const globalInfo = document.getElementById('globalLibraryInfo');
        if (data.global_library_path) {
            globalInfo.innerHTML = `<code class="small">${escapeHtml(data.global_library_path)}</code>`;
        } else {
            globalInfo.innerHTML = '<span class="text-muted">Not configured</span>';
        }

        const projectInfo = document.getElementById('projectLibraryInfo');
        if (data.success && data.project_library_path) {
            projectInfo.innerHTML = `<code class="small">${escapeHtml(data.project_library_path)}</code>`;
        } else if (data.project_path) {
            projectInfo.innerHTML = '<span class="text-warning"><i class="fas fa-exclamation-triangle me-1"></i>No library folder</span>';
        } else {
            projectInfo.innerHTML = '<span class="text-muted">Select a project</span>';
        }
    } catch (error) {
        console.error('Error loading library info:', error);
    }
}

export function updateLibraryInfoPanel(globalPath, projectPath) {
    const infoPanel = document.getElementById('libraryInfoPanel');
    infoPanel.style.display = 'block';

    const globalInfo = document.getElementById('globalLibraryInfo');
    if (globalPath) {
        globalInfo.innerHTML = `<code class="small">${escapeHtml(globalPath)}</code>`;
    } else {
        globalInfo.innerHTML = '<span class="text-muted">Not configured</span>';
    }
}

export function initProjectSettingsForm() {
    const globalSettingsForm = document.getElementById('globalSettingsForm');
    if (!globalSettingsForm || globalSettingsForm.dataset.bound === '1') {
        return;
    }
    globalSettingsForm.dataset.bound = '1';

    globalSettingsForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const btn = this.querySelector('button[type="submit"]');
        const originalText = setButtonLoading(btn, true, 'Saving...');

        const libraryPath = document.getElementById('globalLibraryPath').value.trim();
        const recipesPath = document.getElementById('globalRecipesPath').value.trim();
        const connectedToServer = Boolean(document.getElementById('connectedToServerToggle')?.checked);

        try {
            const response = await fetchWithApiFallback('/api/settings/global-library', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    global_template_library_path: libraryPath,
                    global_recipes_path: recipesPath,
                    connected_to_server: connectedToServer,
                })
            });
            const result = await response.json();

            const statusDiv = document.getElementById('libraryStatusMessage');
            if (result.success) {
                statusDiv.innerHTML = `
                    <div class="alert alert-success py-2">
                        <i class="fas fa-check-circle me-2"></i>Settings saved successfully!
                    </div>
                `;
                updateLibraryInfoPanel(result.global_template_library_path, null);
            } else {
                statusDiv.innerHTML = `
                    <div class="alert alert-danger py-2">
                        <i class="fas fa-exclamation-circle me-2"></i>${escapeHtml(result.error || 'Could not save settings.')}
                    </div>
                `;
            }

            if (result.success) {
                if (window.PrismFileSystemMode && typeof window.PrismFileSystemMode.setConnectedToServer === 'function') {
                    window.PrismFileSystemMode.setConnectedToServer(connectedToServer);
                }

                window.dispatchEvent(new CustomEvent('prism-library-settings-changed', {
                    detail: {
                        global_library_path: document.getElementById('globalLibraryPath').value,
                        connected_to_server: connectedToServer,
                    }
                }));
            }

            setTimeout(() => {
                if (result.success) {
                    statusDiv.innerHTML = '';
                }
            }, 3000);

        } catch (error) {
            document.getElementById('libraryStatusMessage').innerHTML = `
                <div class="alert alert-danger py-2">
                    <i class="fas fa-exclamation-circle me-2"></i>${escapeHtml(error.message || 'Could not save settings.')}
                </div>
            `;
        } finally {
            setButtonLoading(btn, false, null, originalText);
        }
    });
}

export async function useDefaultLibrary() {
    document.getElementById('globalRecipesPath').value = '';
    try {
        const response = await fetchWithApiFallback('/api/settings/global-library');
        const data = await response.json();
        if (data.default_library_path) {
            document.getElementById('globalLibraryPath').value = data.default_library_path;
            document.getElementById('libraryStatusMessage').innerHTML = `
                <div class="alert alert-info py-2">
                    <i class="fas fa-info-circle me-2"></i>Default path set. Click "Save Settings" to apply.
                </div>
            `;
        }
    } catch (error) {
        console.error('Error getting default path:', error);
    }
}

export async function clearGlobalLibrary() {
    if (!confirm('Clear the global template and recipe library paths?')) {
        return;
    }
    document.getElementById('globalRecipesPath').value = '';

    try {
        const response = await fetchWithApiFallback('/api/settings/global-library', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ global_template_library_path: '' })
        });
        const result = await response.json();

        if (result.success) {
            document.getElementById('globalLibraryPath').value = '';
            document.getElementById('libraryStatusMessage').innerHTML = `
                <div class="alert alert-info py-2">
                    <i class="fas fa-info-circle me-2"></i>Global library path cleared.
                </div>
            `;
            updateLibraryInfoPanel(null, null);

            window.dispatchEvent(new CustomEvent('prism-library-settings-changed', {
                detail: { global_library_path: null }
            }));

            setTimeout(() => {
                document.getElementById('libraryStatusMessage').innerHTML = '';
            }, 3000);
        }
    } catch (error) {
        console.error('Error clearing library:', error);
    }
}