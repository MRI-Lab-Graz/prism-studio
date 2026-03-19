/**
 * Environment Conversion Module
 * Handles upload → column detection → environment TSV generation
 */

export function initEnvironment(elements) {
    const {
        envDataFile,
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
        envError,
        envInfo,
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
    } = elements;

    // ── UI helpers ────────────────────────────────────────────────────────────

    function resetUI() {
        if (envColumnMapping) envColumnMapping.classList.add('d-none');
        if (envDataPreview) envDataPreview.classList.add('d-none');
        if (envLogContainer) envLogContainer.classList.add('d-none');
        if (envOutputPreview) envOutputPreview.classList.add('d-none');
        if (envError) { envError.classList.add('d-none'); envError.textContent = ''; }
        if (envInfo) { envInfo.classList.add('d-none'); envInfo.textContent = ''; }
        if (envCompatibilityInfo) envCompatibilityInfo.classList.add('d-none');
        if (envCompatibilityText) envCompatibilityText.textContent = '';
        if (envLog) envLog.innerHTML = '';
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
        const hasFile = envDataFile && envDataFile.files && envDataFile.files.length === 1;
        if (envPreviewBtn) envPreviewBtn.disabled = !hasFile;
        clearEnvDataFileBtn?.classList.toggle('d-none', !hasFile);

        const filename = hasFile ? (envDataFile.files[0].name || '').toLowerCase() : '';
        const showSeparator = filename.endsWith('.csv') || filename.endsWith('.tsv');
        envSeparatorGroup?.classList.toggle('d-none', !showSeparator);
    }

    function updateConvertBtn() {
        const hasTimestamp = envTimestampCol && envTimestampCol.value;
        const hasParticipant = (envParticipantCol && envParticipantCol.value)
            || (envParticipantOverride && envParticipantOverride.value.trim());
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

    // ── Event wiring ──────────────────────────────────────────────────────────

    if (envDataFile) {
        envDataFile.addEventListener('change', () => { resetUI(); updateFileBtn(); });
        updateFileBtn();
    }

    clearEnvDataFileBtn?.addEventListener('click', () => {
        if (envDataFile) { envDataFile.value = ''; }
        resetUI();
        updateFileBtn();
    });

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

        fetch(`/api/environment-location-search?q=${encodeURIComponent(query)}`)
            .then(r => r.json())
            .then(data => {
                if (data.error) throw new Error(data.error);
                if (!envLocationResults) return;
                envLocationResults.innerHTML = '<option value="">- no location selected -</option>';
                (data.results || []).forEach((item) => {
                    const opt = document.createElement('option');
                    opt.value = item.display_name || item.name;
                    opt.textContent = `${item.display_name} (${item.latitude.toFixed(4)}, ${item.longitude.toFixed(4)})`;
                    opt.dataset.lat = String(item.latitude);
                    opt.dataset.lon = String(item.longitude);
                    opt.dataset.label = item.display_name || item.name;
                    envLocationResults.appendChild(opt);
                });
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
        const file = envDataFile && envDataFile.files && envDataFile.files[0];
        if (!file) return;

        resetUI();
        envPreviewBtn.disabled = true;

        const fd = new FormData();
        fd.append('file', file);
        fd.append('separator', envSeparator ? envSeparator.value : 'auto');

        fetch('/api/environment-preview', { method: 'POST', body: fd })
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
        const file = envDataFile && envDataFile.files && envDataFile.files[0];
        if (!file) return;

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
        if (!participantCol && !participantOverride) {
            if (envError) {
                envError.textContent = 'Please select a participant ID column or set a manual participant ID.';
                envError.classList.remove('d-none');
            }
            return;
        }
        if (!sessionCol && !sessionOverride) {
            if (envError) {
                envError.textContent = 'Please select a session column or set a manual session value.';
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

        if (envError) envError.classList.add('d-none');
        if (envInfo) envInfo.classList.add('d-none');
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
        fd.append('file', file);
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

        fetch('/api/environment-convert-start', { method: 'POST', body: fd })
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
                if (startData.background) {
                    appendLog(
                        `🚀 Detached job started (PID ${startData.pid || 'n/a'})`,
                        'info',
                        envLog,
                    );
                }

                let cursor = 0;
                while (true) {
                    await new Promise(resolve => setTimeout(resolve, 500));

                    const statusResponse = await fetch(`/api/environment-convert-status/${encodeURIComponent(jobId)}?cursor=${cursor}`);
                    const statusData = await statusResponse.json().catch(() => ({}));
                    if (!statusResponse.ok) {
                        throw new Error(statusData.error || 'Failed to retrieve environment conversion status');
                    }

                    const newLogs = Array.isArray(statusData.logs) ? statusData.logs : [];
                    newLogs.forEach((entry) => appendLog(entry.message, entry.type || 'info', envLog));
                    cursor = Number.isInteger(statusData.next_cursor)
                        ? statusData.next_cursor
                        : cursor + newLogs.length;

                    if (!statusData.done) continue;
                    if (!statusData.success) {
                        throw new Error(statusData.error || 'Environment conversion failed');
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
                    appendLog(
                        `✅ Done — ${data.row_count} row(s) written, ${data.skipped || 0} skipped`,
                        'success',
                        envLog,
                    );
                    break;
                }
            })
            .catch(err => {
                appendLog(`❌ Error: ${err.message}`, 'error', envLog);
                if (envError) {
                    envError.textContent = err.message || 'Conversion failed';
                    envError.classList.remove('d-none');
                }
            })
            .finally(() => {
                envConvertBtn.disabled = false;
                if (envPilotRunBtn) envPilotRunBtn.disabled = false;
                updateConvertBtn();
            });
    };

    envConvertBtn?.addEventListener('click', () => startConversion(false));
    envPilotRunBtn?.addEventListener('click', () => startConversion(true));
}
