/**
 * Environment Conversion Module
 * Handles upload → column detection → environment TSV generation
 */

import { fetchWithApiFallback } from '../../shared/api.js';
import { pollJobStatus } from '../../shared/job-polling.js';
import { resolveCurrentProjectPath } from '../../shared/project-state.js';
import { createPollingRunState, isPollingAbortError } from './polling-run-state.js';
import { createJobRunController } from './job-run-controller.js';

export function initEnvironment(elements) {
    const STATUS_POLL_INTERVAL_MS = 500;
    const STATUS_POLL_TIMEOUT_MS = 5 * 60 * 1000;
    const MAX_STATUS_POLL_ERRORS = 4;

    const {
        envDataFile,
        browseServerEnvFileBtn,
        clearEnvDataFileBtn,
        envPreviewBtn,
        envSeparatorGroup,
        envSeparator,
        envTimestampCol,
        envParticipantCol,
        envParticipantOverride,
        envSessionCol,
        envSessionOverride,
        envLocationCol,
        envLatCol,
        envLonCol,
        envLocationQuery,
        envLocationSearchBtn,
        envLocationResults,
        envLocationLabel,
        envLat,
        envLon,
        envConvertBackground,
        envPilotRunBtn,
        envConvertBtn,
        envCancelBtn,
        envError,
        envInfo,
        envProgressContainer,
        envProgressBar,
        envProgressText,
        envCompatibilityInfo,
        envCompatibilityText,
        envColumnMapping,
        envDataPreview,
        envPreviewHead,
        envPreviewBody,
        envLogContainer,
        envLog,
        envLogBody,
        envOutputPreview,
        envOutputPreviewHead,
        envOutputPreviewBody,
        toggleEnvLogBtn,
        appendLog,
        appendLogBatch,
    } = elements;

    let envServerFilePath = '';
    let envSourcedataRequestToken = 0;
    let envSourcedataQuickSelectEl = null;
    let envSourcedataFileSelectEl = null;

    let progressDisplayPct = 0;
    let progressTargetPct = 0;
    let progressAnimationTimer = null;
    const pollingRunState = createPollingRunState();
    const runController = createJobRunController();

    function prefersServerPicker() {
        return Boolean(
            window.PrismFileSystemMode
            && typeof window.PrismFileSystemMode.prefersServerPicker === 'function'
            && window.PrismFileSystemMode.prefersServerPicker()
        );
    }

    function getSelectedEnvFile() {
        return (envDataFile && envDataFile.files && envDataFile.files[0])
            ? envDataFile.files[0]
            : null;
    }

    function getSelectedEnvFilename() {
        const selectedFile = getSelectedEnvFile();
        if (selectedFile && selectedFile.name) {
            return selectedFile.name;
        }
        if (envServerFilePath) {
            const tokens = envServerFilePath.split('/');
            return tokens[tokens.length - 1] || envServerFilePath;
        }
        return '';
    }

    function hasSelectedEnvInput() {
        return Boolean(getSelectedEnvFile() || envServerFilePath);
    }

    function appendEnvInputToFormData(formData) {
        const selectedFile = getSelectedEnvFile();
        if (selectedFile) {
            formData.append('file', selectedFile);
            return selectedFile;
        }
        if (envServerFilePath) {
            formData.append('source_file_path', envServerFilePath);
        }
        return null;
    }

    async function pickServerEnvironmentFile() {
        if (!(window.PrismFileSystemMode && typeof window.PrismFileSystemMode.pickFile === 'function')) {
            return '';
        }

        return window.PrismFileSystemMode.pickFile({
            title: 'Select Environment File on Server',
            confirmLabel: 'Use This File',
            extensions: '.xlsx,.csv,.tsv,.sav,.rds,.rdata,.rda',
            startPath: envServerFilePath || ''
        });
    }

    function applyEnvironmentPickerUiState() {
        const connectedToServer = prefersServerPicker();

        if (browseServerEnvFileBtn) {
            browseServerEnvFileBtn.classList.toggle('d-none', !connectedToServer);
        }

        if (envDataFile) {
            envDataFile.disabled = connectedToServer;
            envDataFile.title = connectedToServer ? 'Connected-to-server mode: use Server picker.' : '';
            if (connectedToServer && envDataFile.files && envDataFile.files.length > 0) {
                envDataFile.value = '';
            }
        }

        if (!connectedToServer && envServerFilePath) {
            envServerFilePath = '';
            resetUI();
        }

        updateFileBtn();
    }

    function ensureEnvironmentSourcedataQuickSelectElements() {
        if (envSourcedataQuickSelectEl && envSourcedataFileSelectEl) {
            return;
        }
        if (!envDataFile) {
            return;
        }

        const pickerContainer = envDataFile.closest('.studio-file-picker');
        if (!pickerContainer) {
            return;
        }

        envSourcedataQuickSelectEl = pickerContainer.querySelector('#envSourcedataQuickSelect');
        envSourcedataFileSelectEl = pickerContainer.querySelector('#envSourcedataFileSelect');

        if (envSourcedataQuickSelectEl && envSourcedataFileSelectEl) {
            return;
        }

        const inputGroup = envDataFile.closest('.input-group');
        if (!inputGroup || !inputGroup.parentElement) {
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.id = 'envSourcedataQuickSelect';
        wrapper.className = 'd-none mb-2';
        wrapper.innerHTML = `
            <div class="input-group input-group-sm">
                <span class="input-group-text bg-light"><i class="fas fa-folder-open text-muted"></i></span>
                <select class="form-select form-select-sm" id="envSourcedataFileSelect">
                    <option value="">Loading sourcedata files...</option>
                </select>
            </div>
        `;

        inputGroup.parentElement.insertBefore(wrapper, inputGroup);
        envSourcedataQuickSelectEl = wrapper;
        envSourcedataFileSelectEl = wrapper.querySelector('#envSourcedataFileSelect');
    }

    function resetEnvironmentSourcedataQuickSelect() {
        ensureEnvironmentSourcedataQuickSelectElements();
        if (!envSourcedataFileSelectEl) {
            return;
        }

        envSourcedataFileSelectEl.value = '';
        while (envSourcedataFileSelectEl.options.length > 1) {
            envSourcedataFileSelectEl.remove(1);
        }
    }

    function setEnvironmentSourcedataPlaceholder(label, { disabled = true } = {}) {
        ensureEnvironmentSourcedataQuickSelectElements();
        if (!envSourcedataQuickSelectEl || !envSourcedataFileSelectEl) {
            return;
        }

        envSourcedataQuickSelectEl.classList.remove('d-none');
        resetEnvironmentSourcedataQuickSelect();

        let placeholderOption = envSourcedataFileSelectEl.options[0];
        if (!placeholderOption) {
            placeholderOption = document.createElement('option');
            envSourcedataFileSelectEl.appendChild(placeholderOption);
        }

        placeholderOption.value = '';
        placeholderOption.textContent = label;
        placeholderOption.disabled = disabled;
        envSourcedataFileSelectEl.selectedIndex = 0;
        envSourcedataFileSelectEl.disabled = disabled;
    }

    function refreshEnvironmentSourcedataQuickSelect(projectPath = resolveCurrentProjectPath()) {
        ensureEnvironmentSourcedataQuickSelectElements();
        if (!envSourcedataQuickSelectEl || !envSourcedataFileSelectEl) {
            return;
        }

        const previousValue = envSourcedataFileSelectEl.value;
        const requestToken = ++envSourcedataRequestToken;
        setEnvironmentSourcedataPlaceholder('Loading sourcedata files...', { disabled: true });

        const effectiveProjectPath = String(projectPath || '').trim();
        const endpoint = effectiveProjectPath
            ? `/api/projects/sourcedata-files?kind=environment&project_path=${encodeURIComponent(effectiveProjectPath)}`
            : '/api/projects/sourcedata-files?kind=environment';

        fetchWithApiFallback(endpoint)
            .then((response) => response.json())
            .then((data) => {
                if (requestToken !== envSourcedataRequestToken) {
                    return;
                }

                if (data.sourcedata_exists && Array.isArray(data.files) && data.files.length > 0) {
                    envSourcedataQuickSelectEl.classList.remove('d-none');
                    resetEnvironmentSourcedataQuickSelect();
                    envSourcedataFileSelectEl.disabled = false;

                    const placeholderOption = envSourcedataFileSelectEl.options[0];
                    if (placeholderOption) {
                        placeholderOption.textContent = 'Load from sourcedata/...';
                        placeholderOption.disabled = false;
                    }

                    data.files.forEach((entry) => {
                        const option = document.createElement('option');
                        option.value = entry.name;
                        const sizeKB = (entry.size / 1024).toFixed(1);
                        option.textContent = `${entry.name} (${sizeKB} KB)`;
                        envSourcedataFileSelectEl.appendChild(option);
                    });

                    if (previousValue && Array.from(envSourcedataFileSelectEl.options).some((option) => option.value === previousValue)) {
                        envSourcedataFileSelectEl.value = previousValue;
                    }
                } else if (data.sourcedata_exists) {
                    setEnvironmentSourcedataPlaceholder('No environment-compatible files found in sourcedata/', {
                        disabled: true,
                    });
                } else {
                    setEnvironmentSourcedataPlaceholder('No sourcedata folder found for the current project', {
                        disabled: true,
                    });
                }
            })
            .catch(() => {
                if (requestToken !== envSourcedataRequestToken) {
                    return;
                }
                setEnvironmentSourcedataPlaceholder('Could not load sourcedata files', {
                    disabled: true,
                });
            });
    }

    // ── UI helpers ────────────────────────────────────────────────────────────

    function resetUI() {
        if (envColumnMapping) envColumnMapping.classList.add('d-none');
        if (envDataPreview) envDataPreview.classList.add('d-none');
        if (envLogContainer) envLogContainer.classList.add('d-none');
        if (envOutputPreview) envOutputPreview.classList.add('d-none');
        if (envError) { envError.classList.add('d-none'); envError.textContent = ''; }
        if (envInfo) { envInfo.classList.add('d-none'); envInfo.textContent = ''; }
        if (envProgressContainer) envProgressContainer.classList.add('d-none');
        if (progressAnimationTimer) {
            window.clearInterval(progressAnimationTimer);
            progressAnimationTimer = null;
        }
        progressDisplayPct = 0;
        progressTargetPct = 0;
        if (envProgressBar) {
            envProgressBar.style.width = '0%';
            envProgressBar.setAttribute('aria-valuenow', '0');
        }
        if (envProgressText) envProgressText.textContent = '0%';
        if (envCompatibilityInfo) envCompatibilityInfo.classList.add('d-none');
        if (envCompatibilityText) envCompatibilityText.textContent = '';
        if (envLog) envLog.innerHTML = '';
        if (envCancelBtn) {
            envCancelBtn.classList.add('d-none');
            envCancelBtn.disabled = false;
            envCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Running Conversion';
            envCancelBtn.onclick = null;
        }
        if (envPreviewHead) envPreviewHead.innerHTML = '';
        if (envPreviewBody) envPreviewBody.innerHTML = '';
        if (envOutputPreviewHead) envOutputPreviewHead.innerHTML = '';
        if (envOutputPreviewBody) envOutputPreviewBody.innerHTML = '';
    }

    function renderOutputPreview(preview) {
        if (!envOutputPreview || !envOutputPreviewHead || !envOutputPreviewBody) return;
        if (!preview || !Array.isArray(preview.columns) || !Array.isArray(preview.rows) || preview.rows.length === 0) {
            envOutputPreview.classList.add('d-none');
            return;
        }

        envOutputPreviewHead.innerHTML = '';
        envOutputPreviewBody.innerHTML = '';

        const headRow = document.createElement('tr');
        preview.columns.forEach((col) => {
            const th = document.createElement('th');
            th.textContent = col;
            th.className = 'text-nowrap';
            headRow.appendChild(th);
        });
        envOutputPreviewHead.appendChild(headRow);

        preview.rows.forEach((row) => {
            const tr = document.createElement('tr');
            row.forEach((cell) => {
                const td = document.createElement('td');
                td.textContent = cell;
                td.className = 'text-nowrap small';
                tr.appendChild(td);
            });
            envOutputPreviewBody.appendChild(tr);
        });

        envOutputPreview.classList.remove('d-none');
    }

    function parseCoord(value) {
        const raw = String(value ?? '').trim();
        if (!raw) return Number.NaN;
        return Number(raw.replace(',', '.'));
    }

    function validLatLon(latText, lonText) {
        const lat = parseCoord(latText);
        const lon = parseCoord(lonText);
        if (Number.isNaN(lat) || Number.isNaN(lon)) return false;
        return lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
    }

    function renderCompatibility(compatibility) {
        if (!envCompatibilityInfo || !envCompatibilityText || !compatibility) return;
        const warnings = compatibility.warnings || [];
        const parsePct = compatibility.timestamp_parse_rate_pct;
        const parsePart = Number.isFinite(parsePct)
            ? `Timestamp parse rate: ${parsePct.toFixed(1)}%`
            : 'Timestamp parse rate: n/a';

        let text = `${compatibility.status.toUpperCase()} - ${parsePart}. `;
        if (warnings.length > 0) {
            text += `Warnings: ${warnings.join(' | ')}`;
        } else {
            text += 'No format issues detected.';
        }
        envCompatibilityText.textContent = text;
        envCompatibilityInfo.classList.remove('d-none');
        envCompatibilityInfo.classList.remove('alert-light', 'alert-warning', 'alert-danger', 'border');
        if (compatibility.status === 'compatible') {
            envCompatibilityInfo.classList.add('alert-light', 'border');
        } else if (compatibility.status === 'needs_attention') {
            envCompatibilityInfo.classList.add('alert-warning');
        } else {
            envCompatibilityInfo.classList.add('alert-danger');
        }
    }

    function populateSelect(selectEl, columns, selectedValue) {
        if (!selectEl) return;
        while (selectEl.options.length > 1) selectEl.remove(1);
        columns.forEach(col => {
            const opt = document.createElement('option');
            opt.value = col;
            opt.textContent = col;
            if (col === selectedValue) opt.selected = true;
            selectEl.appendChild(opt);
        });
    }

    function updateFileBtn() {
        const hasFile = hasSelectedEnvInput();
        if (envPreviewBtn) envPreviewBtn.disabled = !hasFile;
        clearEnvDataFileBtn?.classList.toggle('d-none', !hasFile);

        const filename = hasFile ? (getSelectedEnvFilename() || '').toLowerCase() : '';
        const showSeparator = filename.endsWith('.csv') || filename.endsWith('.tsv');
        envSeparatorGroup?.classList.toggle('d-none', !showSeparator);
    }

    function updateConvertBtn() {
        const hasTimestamp = envTimestampCol && envTimestampCol.value;
        const hasParticipant = envParticipantCol && envParticipantCol.value;
        const hasSession = (envSessionCol && envSessionCol.value)
            || (envSessionOverride && envSessionOverride.value.trim());
        const hasGlobalCoords = validLatLon(envLat?.value, envLon?.value);
        const hasCoordColumns = (envLatCol && envLatCol.value) && (envLonCol && envLonCol.value);
        const hasLocationSource = (envLocationCol && envLocationCol.value) || (envLocationLabel && envLocationLabel.value.trim());
        const hasGeoSource = hasGlobalCoords || hasCoordColumns || hasLocationSource;
        const ready = hasTimestamp && hasParticipant && hasSession && hasGeoSource;
        if (envConvertBtn) envConvertBtn.disabled = !ready;
        if (envPilotRunBtn) envPilotRunBtn.disabled = !ready;
    }

    function updateProgressUI(percent) {
        const normalized = Math.max(0, Math.min(100, Number(percent) || 0));
        const rounded = Math.round(normalized);
        progressDisplayPct = rounded;
        progressTargetPct = rounded;
        if (envProgressBar) {
            envProgressBar.style.width = `${rounded}%`;
            envProgressBar.setAttribute('aria-valuenow', String(rounded));
        }
        if (envProgressText) {
            envProgressText.textContent = `${rounded}%`;
        }
    }

    function animateProgressTo(percent) {
        const normalized = Math.max(0, Math.min(100, Number(percent) || 0));
        progressTargetPct = Math.round(normalized);

        if (progressAnimationTimer || progressDisplayPct >= progressTargetPct) return;

        progressAnimationTimer = window.setInterval(() => {
            if (progressDisplayPct >= progressTargetPct) {
                window.clearInterval(progressAnimationTimer);
                progressAnimationTimer = null;
                return;
            }

            const remaining = progressTargetPct - progressDisplayPct;
            const step = Math.max(1, Math.ceil(remaining * 0.25));
            progressDisplayPct = Math.min(progressTargetPct, progressDisplayPct + step);

            if (envProgressBar) {
                envProgressBar.style.width = `${progressDisplayPct}%`;
                envProgressBar.setAttribute('aria-valuenow', String(progressDisplayPct));
            }
            if (envProgressText) {
                envProgressText.textContent = `${progressDisplayPct}%`;
            }

            if (progressDisplayPct >= progressTargetPct) {
                window.clearInterval(progressAnimationTimer);
                progressAnimationTimer = null;
            }
        }, 120);
    }

    // ── Event wiring ──────────────────────────────────────────────────────────

    if (envDataFile) {
        envDataFile.addEventListener('change', () => {
            envServerFilePath = '';
            resetUI();
            updateFileBtn();
        });
        updateFileBtn();
    }

    browseServerEnvFileBtn?.addEventListener('click', async () => {
        const pickedPath = await pickServerEnvironmentFile();
        if (!pickedPath) return;

        envServerFilePath = pickedPath;
        if (envDataFile) {
            envDataFile.value = '';
        }
        resetUI();
        updateFileBtn();
    });

    clearEnvDataFileBtn?.addEventListener('click', () => {
        envServerFilePath = '';
        if (envDataFile) { envDataFile.value = ''; }
        resetUI();
        updateFileBtn();
    });

    window.addEventListener('prism-library-settings-changed', () => {
        applyEnvironmentPickerUiState();
    });

    window.addEventListener('prism-project-changed', () => {
        void runController.cancelActiveJob({
            buildCancelUrl: (jobId) => `/api/environment-convert-cancel/${encodeURIComponent(jobId)}`,
        }).catch(() => {});
        pollingRunState.abortActive('Environment polling aborted due to project change.');
        resetUI();
        updateFileBtn();
        refreshEnvironmentSourcedataQuickSelect();
    });

    if (window.PrismFileSystemMode && typeof window.PrismFileSystemMode.init === 'function') {
        window.PrismFileSystemMode.init().then(() => {
            applyEnvironmentPickerUiState();
        }).catch(() => {
            // Keep host picker behavior on init failure.
        });
    }

    applyEnvironmentPickerUiState();

    ensureEnvironmentSourcedataQuickSelectElements();
    if (envSourcedataQuickSelectEl && envSourcedataFileSelectEl) {
        refreshEnvironmentSourcedataQuickSelect();

        envSourcedataFileSelectEl.addEventListener('change', async function() {
            const filename = this.value;
            if (!filename) {
                return;
            }

            try {
                const currentProjectPath = resolveCurrentProjectPath();
                const endpoint = currentProjectPath
                    ? `/api/projects/sourcedata-file?name=${encodeURIComponent(filename)}&project_path=${encodeURIComponent(currentProjectPath)}`
                    : `/api/projects/sourcedata-file?name=${encodeURIComponent(filename)}`;

                const response = await fetchWithApiFallback(endpoint);
                if (!response.ok) {
                    throw new Error('Failed to load sourcedata file');
                }

                const blob = await response.blob();
                const file = new File([blob], filename, { type: blob.type });
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                envDataFile.files = dataTransfer.files;
                envDataFile.dispatchEvent(new Event('change', { bubbles: true }));
            } catch (_error) {
                if (envError) {
                    envError.textContent = `Failed to load ${filename} from sourcedata.`;
                    envError.classList.remove('d-none');
                }
            } finally {
                refreshEnvironmentSourcedataQuickSelect();
            }
        });
    }

    if (envTimestampCol) {
        envTimestampCol.addEventListener('change', updateConvertBtn);
    }
    envParticipantCol?.addEventListener('change', updateConvertBtn);
    envParticipantOverride?.addEventListener('input', updateConvertBtn);
    envSessionCol?.addEventListener('change', updateConvertBtn);
    envSessionOverride?.addEventListener('input', updateConvertBtn);
    envLocationCol?.addEventListener('change', updateConvertBtn);
    envLocationLabel?.addEventListener('input', updateConvertBtn);
    envLatCol?.addEventListener('change', updateConvertBtn);
    envLonCol?.addEventListener('change', updateConvertBtn);
    envLat?.addEventListener('input', updateConvertBtn);
    envLon?.addEventListener('input', updateConvertBtn);

    envLocationSearchBtn?.addEventListener('click', () => {
        const query = (envLocationQuery?.value || '').trim();
        if (!query || query.length < 2) {
            if (envError) {
                envError.textContent = 'Please enter at least 2 characters to search location.';
                envError.classList.remove('d-none');
            }
            return;
        }
        if (envError) envError.classList.add('d-none');

        fetchWithApiFallback(`/api/environment-location-search?q=${encodeURIComponent(query)}`)
            .then(r => r.json())
            .then(data => {
                if (data.error) throw new Error(data.error);
                if (!envLocationResults) return;
                envLocationResults.innerHTML = '';
                const results = data.results || [];
                if (results.length === 0) {
                    const noOpt = document.createElement('option');
                    noOpt.value = '';
                    noOpt.textContent = '— no results found —';
                    envLocationResults.appendChild(noOpt);
                    return;
                }
                results.forEach((item) => {
                    const opt = document.createElement('option');
                    opt.value = item.display_name || item.name;
                    opt.textContent = `${item.display_name} (${item.latitude.toFixed(4)}, ${item.longitude.toFixed(4)})`;
                    opt.dataset.lat = String(item.latitude);
                    opt.dataset.lon = String(item.longitude);
                    opt.dataset.label = item.display_name || item.name;
                    envLocationResults.appendChild(opt);
                });
                envLocationResults.selectedIndex = 0;
                envLocationResults.dispatchEvent(new Event('change'));
            })
            .catch(err => {
                if (envError) {
                    envError.textContent = err.message || 'Location lookup failed';
                    envError.classList.remove('d-none');
                }
            });
    });

    envLocationResults?.addEventListener('change', () => {
        const opt = envLocationResults.options[envLocationResults.selectedIndex];
        if (!opt || !opt.dataset.lat || !opt.dataset.lon) return;
        if (envLat) envLat.value = opt.dataset.lat;
        if (envLon) envLon.value = opt.dataset.lon;
        if (envLocationLabel && !envLocationLabel.value.trim()) {
            envLocationLabel.value = opt.dataset.label || opt.value;
        }
        updateConvertBtn();
    });

    // Toggle log collapse
    toggleEnvLogBtn?.addEventListener('click', () => {
        if (!envLogBody) return;
        const hidden = envLogBody.classList.toggle('d-none');
        const icon = toggleEnvLogBtn.querySelector('i');
        if (icon) {
            icon.classList.toggle('fa-chevron-down', !hidden);
            icon.classList.toggle('fa-chevron-right', hidden);
        }
    });

    // ── Preview (column detection) ────────────────────────────────────────────

    envPreviewBtn?.addEventListener('click', () => {
        if (!hasSelectedEnvInput()) return;

        resetUI();
        envPreviewBtn.disabled = true;

        const fd = new FormData();
        appendEnvInputToFormData(fd);
        fd.append('separator', envSeparator ? envSeparator.value : 'auto');

        fetchWithApiFallback('/api/environment-preview', { method: 'POST', body: fd })
            .then(r => r.json())
            .then(data => {
                if (data.error) throw new Error(data.error);

                const ad = data.auto_detected || {};
                populateSelect(envTimestampCol, data.columns, ad.timestamp);
                populateSelect(envParticipantCol, data.columns, ad.participant_id);
                populateSelect(envSessionCol, data.columns, ad.session);
                populateSelect(envLocationCol, data.columns, ad.location);
                populateSelect(envLatCol, data.columns, ad.lat);
                populateSelect(envLonCol, data.columns, ad.lon);

                if (envColumnMapping) envColumnMapping.classList.remove('d-none');
                renderCompatibility(data.compatibility || null);
                updateConvertBtn();

                // Build preview table
                if (data.sample && data.sample.length > 0 && envPreviewHead && envPreviewBody) {
                    const headRow = document.createElement('tr');
                    data.columns.forEach(col => {
                        const th = document.createElement('th');
                        th.textContent = col;
                        th.className = 'text-nowrap';
                        headRow.appendChild(th);
                    });
                    envPreviewHead.appendChild(headRow);

                    data.sample.forEach(row => {
                        const tr = document.createElement('tr');
                        row.forEach(cell => {
                            const td = document.createElement('td');
                            td.textContent = cell;
                            td.className = 'text-nowrap small';
                            tr.appendChild(td);
                        });
                        envPreviewBody.appendChild(tr);
                    });
                    if (envDataPreview) envDataPreview.classList.remove('d-none');
                }
            })
            .catch(err => {
                if (envError) {
                    envError.textContent = err.message || 'Failed to load file';
                    envError.classList.remove('d-none');
                }
            })
            .finally(() => {
                updateFileBtn();
            });
    });

    // ── Convert / Pilot run ──────────────────────────────────────────────────

    const startConversion = (pilotMode) => {
        if (!hasSelectedEnvInput()) return;

        const tsCol = envTimestampCol ? envTimestampCol.value : '';
        const participantCol = envParticipantCol ? envParticipantCol.value : '';
        const participantOverride = envParticipantOverride ? envParticipantOverride.value.trim() : '';
        const sessionCol = envSessionCol ? envSessionCol.value : '';
        const sessionOverride = envSessionOverride ? envSessionOverride.value.trim() : '';
        const latCol = envLatCol ? envLatCol.value : '';
        const lonCol = envLonCol ? envLonCol.value : '';
        if (!tsCol) {
            if (envError) {
                envError.textContent = 'Please select a timestamp column.';
                envError.classList.remove('d-none');
            }
            return;
        }
        if (!participantCol) {
            if (envError) {
                envError.textContent = 'Please select a participant ID column.';
                envError.classList.remove('d-none');
            }
            return;
        }
        if (!sessionCol && !sessionOverride) {
            if (envError) {
                envError.textContent = 'Please select a session column or enter a fixed session ID.';
                envError.classList.remove('d-none');
            }
            return;
        }
        const hasGlobalCoords = validLatLon(envLat?.value, envLon?.value);
        const hasCoordColumns = !!(latCol && lonCol);
        const hasLocationSource = !!((envLocationCol && envLocationCol.value) || (envLocationLabel && envLocationLabel.value.trim()));
        if (!hasGlobalCoords && !hasCoordColumns && !hasLocationSource) {
            if (envError) {
                envError.textContent = 'Please provide geolocation source: lat/lon columns, a location column/label, or global fallback coordinates.';
                envError.classList.remove('d-none');
            }
            return;
        }
        if ((latCol && !lonCol) || (!latCol && lonCol)) {
            if (envError) {
                envError.textContent = 'Please select both latitude and longitude columns, or neither.';
                envError.classList.remove('d-none');
            }
            return;
        }

        if (!runController.tryStartRun()) {
            return;
        }

        if (envError) envError.classList.add('d-none');
        if (envInfo) envInfo.classList.add('d-none');
        if (envProgressContainer) {
            if (pilotMode) {
                envProgressContainer.classList.add('d-none');
            } else {
                envProgressContainer.classList.remove('d-none');
                updateProgressUI(0);
            }
        }
        if (envLogContainer) envLogContainer.classList.remove('d-none');
        if (envLogBody) envLogBody.classList.remove('d-none');
        if (envLog) envLog.innerHTML = '';

        appendLog('🌍 Starting environment conversion…', 'info', envLog);
        if (pilotMode) {
            appendLog('🧪 Pilot mode enabled: processing one random subject', 'info', envLog);
        }
        if (envConvertBackground?.checked) {
            appendLog('📦 Detached background mode enabled', 'info', envLog);
        }

        const fd = new FormData();
        appendEnvInputToFormData(fd);
        fd.append('timestamp_col', tsCol);
        fd.append('separator', envSeparator ? envSeparator.value : 'auto');
        fd.append('participant_col', participantCol);
        fd.append('participant_override', participantOverride);
        fd.append('session_col', sessionCol);
        fd.append('session_override', sessionOverride);
        fd.append('location_col', envLocationCol ? (envLocationCol.value || '') : '');
        fd.append('lat_col', latCol);
        fd.append('lon_col', lonCol);
        fd.append('location_label', envLocationLabel ? envLocationLabel.value.trim() : '');
        fd.append('lat', envLat ? envLat.value.trim().replace(',', '.') : '');
        fd.append('lon', envLon ? envLon.value.trim().replace(',', '.') : '');
        fd.append('pilot_random_subject', pilotMode ? 'true' : 'false');
        fd.append('convert_in_background', envConvertBackground?.checked ? 'true' : 'false');
        fd.append('save_to_project', 'true');

        envConvertBtn.disabled = true;
        if (envPilotRunBtn) envPilotRunBtn.disabled = true;
        if (envCancelBtn) {
            envCancelBtn.classList.remove('d-none');
            envCancelBtn.disabled = false;
            envCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Running Conversion';
        }

        let activePollController = null;

        fetchWithApiFallback('/api/environment-convert-start', { method: 'POST', body: fd })
            .then(async (r) => {
                const data = await r.json().catch(() => ({}));
                if (!r.ok || data.error) {
                    throw new Error(data.error || 'Failed to start environment conversion');
                }
                return data;
            })
            .then(async (startData) => {
                const jobId = startData.job_id;
                if (!jobId) {
                    throw new Error('Environment conversion did not return a job id');
                }
                runController.setActiveJobId(jobId);

                const cancelHandler = async () => {
                    if (envCancelBtn) {
                        envCancelBtn.disabled = true;
                        envCancelBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Cancelling...';
                    }
                    try {
                        await runController.cancelActiveJob({
                            buildCancelUrl: (activeJobId) => `/api/environment-convert-cancel/${encodeURIComponent(activeJobId)}`,
                        });
                        appendLog('⏹️ Cancellation requested. Waiting for cleanup…', 'warning', envLog);
                    } catch (cancelError) {
                        if (envCancelBtn) {
                            envCancelBtn.disabled = false;
                            envCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Running Conversion';
                        }
                        throw cancelError;
                    }
                };

                if (envCancelBtn) {
                    envCancelBtn.onclick = () => {
                        cancelHandler().catch((cancelError) => {
                            appendLog(`❌ Error: ${cancelError.message}`, 'error', envLog);
                            if (envError) {
                                envError.textContent = cancelError.message || 'Cancellation failed';
                                envError.classList.remove('d-none');
                            }
                        });
                    };
                }

                if (startData.background) {
                    appendLog(
                        `🚀 Detached job started (PID ${startData.pid || 'n/a'})`,
                        'info',
                        envLog,
                    );
                }

                activePollController = pollingRunState.start();

                const statusData = await pollJobStatus({
                    fetchStatus: async (cursor) => {
                        const statusResponse = await fetchWithApiFallback(`/api/environment-convert-status/${encodeURIComponent(jobId)}?cursor=${cursor}`);
                        const statusPayload = await statusResponse.json().catch(() => ({}));
                        if (!statusResponse.ok) {
                            throw new Error(statusPayload.error || 'Failed to retrieve environment conversion status');
                        }
                        return statusPayload;
                    },
                    onLogs: (newLogs) => {
                        if (typeof appendLogBatch === 'function') {
                            appendLogBatch(newLogs, 'info', envLog);
                            return;
                        }
                        newLogs.forEach((entry) => appendLog(entry.message, entry.type || 'info', envLog));
                    },
                    onPollData: (nextStatusData) => {
                        if (!pilotMode && Number.isFinite(nextStatusData.progress_pct)) {
                            animateProgressTo(nextStatusData.progress_pct);
                        }
                    },
                    onRetryWarning: ({ attempt, maxAttempts, error }) => {
                        appendLog(
                            `⚠️ Status check failed (${attempt}/${maxAttempts}): ${error.message || error}`,
                            'warning',
                            envLog,
                        );
                    },
                    intervalMs: STATUS_POLL_INTERVAL_MS,
                    timeoutMs: STATUS_POLL_TIMEOUT_MS,
                    maxConsecutiveErrors: MAX_STATUS_POLL_ERRORS,
                    signal: activePollController.signal,
                    abortErrorMessage: 'Environment polling aborted due to project change.',
                    timeoutErrorMessage: 'Environment conversion status timed out after 5 minutes. Please check conversion logs and retry.',
                    statusFailureMessage: 'Failed to retrieve environment conversion status after multiple attempts.',
                    getFailureError: (nextStatusData) => nextStatusData.error || 'Environment conversion failed',
                });

                if (!pilotMode) {
                    updateProgressUI(100);
                }

                const data = statusData.result || {};
                if (envInfo) {
                    const paths = Array.isArray(data.project_environment_paths)
                        ? data.project_environment_paths
                        : [];
                    const target = data.project_environment_path || paths[0] || 'sub-*/ses-*/environment/*.tsv';
                    const pilotNote = data.pilot_mode
                        ? ` Pilot subject: ${data.pilot_subject || 'random'}.`
                        : '';
                    const estimate = Number.isFinite(data.estimated_total_seconds)
                        ? ` Estimated full run: ~${data.estimated_total_seconds}s.`
                        : '';
                    const filesNote = paths.length > 1
                        ? ` Saved ${paths.length} subject/session files.`
                        : '';
                    envInfo.textContent = `Converted and saved to project: ${target}.${filesNote}${pilotNote}${estimate}`;
                    envInfo.classList.remove('d-none');
                }
                renderOutputPreview(data.output_preview || null);
                const providerFailures = Array.isArray(data.provider_failures) ? data.provider_failures : [];
                const providerNote = providerFailures.length
                    ? ` ⚠️ Partial enrichment — API failures: ${providerFailures.join(', ')}.`
                    : '';
                appendLog(
                    `✅ Done — ${data.row_count} row(s) written, ${data.skipped || 0} skipped${providerNote}`,
                    providerFailures.length ? 'warning' : 'success',
                    envLog,
                );
            })
            .catch(err => {
                if (isPollingAbortError(err)) {
                    // Project-change listeners already reset the converter UI.
                } else if (err.message === 'Cancelled by user' || err.message === 'Conversion cancelled by user') {
                    appendLog('⏹️ Conversion cancelled. Partial project outputs were removed.', 'warning', envLog);
                    if (envInfo) {
                        envInfo.textContent = 'Environment conversion cancelled. Partial project outputs were removed.';
                        envInfo.classList.remove('d-none');
                    }
                    if (!pilotMode && envProgressContainer) {
                        envProgressContainer.classList.add('d-none');
                    }
                } else {
                    appendLog(`❌ Error: ${err.message}`, 'error', envLog);
                    if (envError) {
                        envError.textContent = err.message || 'Conversion failed';
                        envError.classList.remove('d-none');
                    }
                    if (!pilotMode && envProgressContainer) {
                        envProgressContainer.classList.add('d-none');
                    }
                }
            })
            .finally(() => {
                pollingRunState.clear(activePollController);
                runController.finishRun();
                envConvertBtn.disabled = false;
                if (envPilotRunBtn) envPilotRunBtn.disabled = false;
                if (envCancelBtn) {
                    envCancelBtn.classList.add('d-none');
                    envCancelBtn.disabled = false;
                    envCancelBtn.innerHTML = '<i class="fas fa-stop-circle me-2"></i>Cancel Running Conversion';
                    envCancelBtn.onclick = null;
                }
                updateConvertBtn();
            });
    };

    envConvertBtn?.addEventListener('click', () => startConversion(false));
    envPilotRunBtn?.addEventListener('click', () => startConversion(true));
}
