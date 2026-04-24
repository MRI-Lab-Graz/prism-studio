document.addEventListener('DOMContentLoaded', () => {
    if (window.bootstrap && typeof window.bootstrap.Tooltip === 'function') {
        const tooltipTriggers = Array.from(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggers.forEach((el) => {
            new window.bootstrap.Tooltip(el);
        });
    }

    function getFallbackApiOrigin() {
        const configuredOrigin = (window.PRISM_API_ORIGIN || '').trim();
        if (configuredOrigin) {
            return configuredOrigin.replace(/\/$/, '');
        }
        return 'http://127.0.0.1:5001';
    }

    function canRetryApiWithFallback(url) {
        const protocol = (window.location && window.location.protocol) ? window.location.protocol : '';
        const isRelativeApiRequest = typeof url === 'string' && url.startsWith('/api/');
        return isRelativeApiRequest && protocol !== 'http:' && protocol !== 'https:';
    }

    async function fetchWithApiFallback(
        url,
        options = {},
        fallbackMessage = 'Cannot reach PRISM backend API. Please restart PRISM Studio and try again.'
    ) {
        try {
            return await fetch(url, options);
        } catch (primaryError) {
            if (!canRetryApiWithFallback(url)) {
                throw primaryError;
            }

            const fallbackUrl = `${getFallbackApiOrigin()}${url}`;
            try {
                return await fetch(fallbackUrl, options);
            } catch (_fallbackError) {
                throw new Error(fallbackMessage);
            }
        }
    }

    function getCurrentProjectPath() {
        if (typeof window.resolveCurrentProjectPath === 'function') {
            return String(window.resolveCurrentProjectPath() || '').trim();
        }
        return String(window.currentProjectPath || '').trim();
    }

    // Shared helpers
    function downloadBase64Zip(base64Data, filename) {
        const binaryString = window.atob(base64Data);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        const blob = new Blob([bytes], { type: 'application/zip' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    }

    // --------------------
    // Wide to Long
    // --------------------
    const wideLongFile = document.getElementById('wideLongFile');
    const wideLongPickFileBtn = document.getElementById('wideLongPickFileBtn');
    const wideLongBrowseServerFileBtn = document.getElementById('wideLongBrowseServerFileBtn');
    const wideLongFileName = document.getElementById('wideLongFileName');
    const wideLongClearBtn = document.getElementById('wideLongClearBtn');
    const wideLongSessionColumn = null; // fixed to 'session'
    const wideLongIndicators = document.getElementById('wideLongIndicators');
    const wideLongRunColumn = null; // fixed to 'run'
    const wideLongRunIndicators = document.getElementById('wideLongRunIndicators');
    const wideLongDataPreviewBtn = document.getElementById('wideLongDataPreviewBtn');
    const wideLongConvertBtn = document.getElementById('wideLongConvertBtn');
    const wideLongError = document.getElementById('wideLongError');
    const wideLongInfo = document.getElementById('wideLongInfo');
    const wideLongProgress = document.getElementById('wideLongProgress');
    const wideLongPreview = document.getElementById('wideLongPreview');
    const wideLongTablePreview = document.getElementById('wideLongTablePreview');
    const wideLongTableMeta = document.getElementById('wideLongTableMeta');
    const wideLongColumnPreviewSection = document.getElementById('wideLongColumnPreviewSection');
    const wideLongColumnPreviewList = document.getElementById('wideLongColumnPreviewList');
    const wideLongAmbiguityWarning = document.getElementById('wideLongAmbiguityWarning');
    const wideLongTableHead = document.getElementById('wideLongTableHead');
    const wideLongTableBody = document.getElementById('wideLongTableBody');
    const wideLongRawPeek = document.getElementById('wideLongRawPeek');
    const wideLongRawMeta = document.getElementById('wideLongRawMeta');
    const wideLongRawPeekBody = document.getElementById('wideLongRawPeekBody');
    const wideLongRawPeekToggle = document.getElementById('wideLongRawPeekToggle');
    const wideLongRawColumns = document.getElementById('wideLongRawColumns');
    const wideLongRawTableHead = document.getElementById('wideLongRawTableHead');
    const wideLongRawTableBody = document.getElementById('wideLongRawTableBody');
    let wideLongServerFilePath = '';
    let organizeServerFolderPath = '';
    let organizeServerFilePaths = [];
    let renamerServerFolderPath = '';
    let renamerServerEntries = [];

    function getParentDirectory(pathValue) {
        const rawPath = String(pathValue || '').trim();
        if (!rawPath) {
            return '';
        }

        const normalized = rawPath.replace(/\\/g, '/');
        const sepIndex = normalized.lastIndexOf('/');
        if (sepIndex <= 0) {
            return '';
        }

        const parent = normalized.slice(0, sepIndex);
        if (/^[A-Za-z]:$/.test(parent)) {
            return `${parent}/`;
        }
        return parent;
    }

    function updateOrganizeServerFilesHint() {
        const organizeFilesServerHint = document.getElementById('organizeFilesServerPathHint');
        const organizeClearServerFilesBtn = document.getElementById('organizeClearServerFilesBtn');
        if (!organizeFilesServerHint || !organizeClearServerFilesBtn) {
            return;
        }

        if (organizeServerFilePaths.length === 0) {
            organizeFilesServerHint.textContent = '';
            organizeFilesServerHint.classList.add('d-none');
            organizeClearServerFilesBtn.classList.add('d-none');
            return;
        }

        const lastPath = organizeServerFilePaths[organizeServerFilePaths.length - 1];
        if (organizeServerFilePaths.length === 1) {
            organizeFilesServerHint.textContent = `Server file: ${lastPath}`;
        } else {
            organizeFilesServerHint.textContent = `Server files: ${organizeServerFilePaths.length} selected (last: ${lastPath})`;
        }
        organizeFilesServerHint.classList.remove('d-none');
        organizeClearServerFilesBtn.classList.remove('d-none');
    }

    function updateRenamerServerHints() {
        const renamerServerFolderHint = document.getElementById('renamerServerFolderHint');
        const renamerServerFileHint = document.getElementById('renamerServerFileHint');
        const renamerClearServerSelectionBtn = document.getElementById('renamerClearServerSelectionBtn');

        if (!renamerServerFolderHint || !renamerServerFileHint || !renamerClearServerSelectionBtn) {
            return;
        }

        if (renamerServerFolderPath) {
            renamerServerFolderHint.textContent = `Server folder: ${renamerServerFolderPath} (${renamerServerEntries.length} files)`;
            renamerServerFolderHint.classList.remove('d-none');
            renamerServerFileHint.textContent = '';
            renamerServerFileHint.classList.add('d-none');
            renamerClearServerSelectionBtn.classList.remove('d-none');
            return;
        }

        if (renamerServerEntries.length > 0) {
            const lastEntry = renamerServerEntries[renamerServerEntries.length - 1] || {};
            const lastPath = String(lastEntry.path || lastEntry.relative_path || lastEntry.name || '').trim();
            if (renamerServerEntries.length === 1) {
                renamerServerFileHint.textContent = `Server file: ${lastPath}`;
            } else {
                renamerServerFileHint.textContent = `Server files: ${renamerServerEntries.length} selected (last: ${lastPath})`;
            }
            renamerServerFileHint.classList.remove('d-none');
            renamerServerFolderHint.textContent = '';
            renamerServerFolderHint.classList.add('d-none');
            renamerClearServerSelectionBtn.classList.remove('d-none');
            return;
        }

        renamerServerFolderHint.textContent = '';
        renamerServerFolderHint.classList.add('d-none');
        renamerServerFileHint.textContent = '';
        renamerServerFileHint.classList.add('d-none');
        renamerClearServerSelectionBtn.classList.add('d-none');
    }

    function prefersServerPicker() {
        return Boolean(
            window.PrismFileSystemMode
            && typeof window.PrismFileSystemMode.prefersServerPicker === 'function'
            && window.PrismFileSystemMode.prefersServerPicker()
        );
    }

    function applyRemotePickerUiState() {
        const connectedToServer = prefersServerPicker();

        const renamerInput = document.getElementById('renamerFiles');
        const renamerLocalUploadGroup = document.getElementById('renamerLocalUploadGroup');
        const organizeFilesInput = document.getElementById('organizeFiles');
        const organizeFilesPickerCol = document.getElementById('organizeFilesPickerCol');
        const organizeFolderInput = document.getElementById('organizeFolder');
        const organizeFolderPickerCol = document.getElementById('organizeFolderPickerCol');
        const organizeFolderLocalUploadGroup = document.getElementById('organizeFolderLocalUploadGroup');
        const organizeFolderLabel = document.getElementById('organizeFolderLabel');
        const wideLongInput = document.getElementById('wideLongFile');
        const wideLongServerBtn = document.getElementById('wideLongBrowseServerFileBtn');
        const renamerServerFileBtn = document.getElementById('renamerBrowseServerFileBtn');
        const renamerServerFolderBtn = document.getElementById('renamerBrowseServerFolderBtn');
        const organizeServerFileBtn = document.getElementById('organizeBrowseServerFileBtn');
        const organizeServerFolderBtn = document.getElementById('organizeFolderServerBrowseBtn');
        const renamerServerFolderHint = document.getElementById('renamerServerFolderHint');
        const renamerServerFileHint = document.getElementById('renamerServerFileHint');
        const organizeFilesServerHint = document.getElementById('organizeFilesServerPathHint');
        const organizeServerHint = document.getElementById('organizeFolderServerPathHint');

        if (renamerLocalUploadGroup) {
            renamerLocalUploadGroup.classList.remove('d-none');
        }
        if (organizeFilesPickerCol) {
            organizeFilesPickerCol.classList.remove('d-none');
        }
        if (organizeFolderPickerCol) {
            organizeFolderPickerCol.classList.remove('col-md-12');
            organizeFolderPickerCol.classList.add('col-md-6');
        }
        if (organizeFolderLocalUploadGroup) {
            organizeFolderLocalUploadGroup.classList.remove('d-none');
        }
        if (organizeFolderLabel) {
            organizeFolderLabel.textContent = 'Or Select a Folder';
        }

        if (renamerInput) {
            renamerInput.disabled = false;
            renamerInput.title = '';
        }
        if (organizeFilesInput) {
            organizeFilesInput.disabled = false;
            organizeFilesInput.title = '';
        }
        if (organizeFolderInput) {
            organizeFolderInput.disabled = false;
            organizeFolderInput.title = '';
        }
        if (wideLongInput) {
            wideLongInput.disabled = false;
            wideLongInput.title = '';
        }
        if (wideLongServerBtn) {
            wideLongServerBtn.classList.toggle('d-none', !connectedToServer);
        }
        if (renamerServerFileBtn) {
            renamerServerFileBtn.classList.toggle('d-none', !connectedToServer);
        }
        if (renamerServerFolderBtn) {
            renamerServerFolderBtn.classList.toggle('d-none', !connectedToServer);
        }
        if (organizeServerFileBtn) {
            organizeServerFileBtn.classList.toggle('d-none', !connectedToServer);
        }
        if (organizeServerFolderBtn) {
            organizeServerFolderBtn.classList.toggle('d-none', !connectedToServer);
        }

        if (!connectedToServer) {
            renamerServerFolderPath = '';
            renamerServerEntries = [];
            organizeServerFolderPath = '';
            organizeServerFilePaths = [];

            if (renamerServerFolderHint) {
                renamerServerFolderHint.textContent = '';
                renamerServerFolderHint.classList.add('d-none');
            }
            if (renamerServerFileHint) {
                renamerServerFileHint.textContent = '';
                renamerServerFileHint.classList.add('d-none');
            }
            if (organizeFilesServerHint) {
                organizeFilesServerHint.textContent = '';
                organizeFilesServerHint.classList.add('d-none');
            }
            if (organizeServerHint) {
                organizeServerHint.textContent = '';
                organizeServerHint.classList.add('d-none');
            }
        }

        updateRenamerServerHints();
        updateOrganizeServerFilesHint();

        updateOrganizeBtn();
        updateRenamerBtn();
    }

    function hideRawPeek() {
        if (wideLongRawPeek) wideLongRawPeek.classList.add('d-none');
        if (wideLongRawColumns) wideLongRawColumns.innerHTML = '';
        if (wideLongRawTableHead) wideLongRawTableHead.innerHTML = '';
        if (wideLongRawTableBody) wideLongRawTableBody.innerHTML = '';
        if (wideLongRawMeta) wideLongRawMeta.textContent = '';
    }

    async function fetchRawPeek(file, sourcePath = '') {
        hideRawPeek();
        const formData = new FormData();
        if (file) {
            formData.append('data', file);
        } else if (sourcePath) {
            formData.append('source_file_path', sourcePath);
        }
        try {
            const response = await fetchWithApiFallback('/api/file-management/raw-peek', { method: 'POST', body: formData });
            if (!response.ok) return;
            const data = await response.json();
            if (!data.columns || !data.columns.length) return;

            // Column chips
            if (wideLongRawColumns) {
                wideLongRawColumns.innerHTML = data.columns.map(col =>
                    `<span class="badge bg-light text-dark border font-monospace" style="font-size:0.75rem;">${escapeHtml(col)}</span>`
                ).join('');
            }

            // Raw data table
            if (wideLongRawTableHead && wideLongRawTableBody) {
                wideLongRawTableHead.innerHTML = `<tr>${data.columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr>`;
                wideLongRawTableBody.innerHTML = (data.rows || []).map(row =>
                    `<tr>${data.columns.map(c => `<td>${escapeHtml(row[c] ?? '')}</td>`).join('')}</tr>`
                ).join('');
            }

            if (wideLongRawMeta) {
                wideLongRawMeta.textContent = `(${data.total_columns} columns, ${data.total_rows} rows — showing first ${(data.rows || []).length})`;
            }

            if (wideLongRawPeek) wideLongRawPeek.classList.remove('d-none');
        } catch (_) {
            // Non-fatal — peek is optional
        }
    }

    function parseCombined(raw) {
        return (raw || '').replace(/;/g, ',').split(',')
            .map((e) => e.trim()).filter(Boolean)
            .map((e) => e.includes(':') ? e.split(':', 2).map((s) => s.trim()) : [e, e]);
    }

    function escapeHtml(value) {
        return String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    }

    function updateWideLongPreview() {
        if (!wideLongPreview) return;

        const file = (wideLongFile && wideLongFile.files && wideLongFile.files[0]) ? wideLongFile.files[0].name : '<file>';
        const indicatorsRaw = ((wideLongIndicators && wideLongIndicators.value) || '').trim();
        const runIndicatorsRaw = ((wideLongRunIndicators && wideLongRunIndicators.value) || '').trim();

        const sessionPairs = parseCombined(indicatorsRaw);
        const runPairs = parseCombined(runIndicatorsRaw);

        const lines = [];
        lines.push(`$ prism wide-to-long --input ${file}`);
        if (indicatorsRaw) {
            lines.push(`  --session-indicators ${indicatorsRaw}`);
        } else {
            lines.push('  --session-indicators <auto-detect-prefixes>');
        }
        if (runIndicatorsRaw) {
            lines.push(`  --run-column run`);
            lines.push(`  --run-indicators ${runIndicatorsRaw}`);
        }

        if (sessionPairs.length) {
            lines.push('');
            lines.push('Session mapping preview:');
            sessionPairs.forEach(([src, tgt]) => lines.push(`  ${src} -> ${tgt}`));
        } else {
            lines.push('');
            lines.push('Session mapping preview:');
            lines.push('  Waiting for indicators...');
        }

        if (runPairs.length) {
            lines.push('');
            lines.push('Run mapping preview:');
            runPairs.forEach(([src, tgt]) => lines.push(`  ${src} -> ${tgt}`));
        }

        wideLongPreview.textContent = lines.join('\n');
    }

    function setWideLongIdleState() {
        if (wideLongProgress) wideLongProgress.classList.add('d-none');
        const hasFile = !!(
            (wideLongFile && wideLongFile.files && wideLongFile.files.length > 0)
            || wideLongServerFilePath
        );
        const hasCurrentProject = Boolean(getCurrentProjectPath());
        if (wideLongConvertBtn) wideLongConvertBtn.disabled = !hasFile || !hasCurrentProject;
        if (wideLongDataPreviewBtn) wideLongDataPreviewBtn.disabled = !hasFile;
    }

    function hideWideLongTablePreview() {
        if (wideLongTablePreview) wideLongTablePreview.classList.add('d-none');
        if (wideLongTableMeta) wideLongTableMeta.textContent = '';
        if (wideLongColumnPreviewSection) wideLongColumnPreviewSection.classList.add('d-none');
        if (wideLongColumnPreviewList) wideLongColumnPreviewList.innerHTML = '';
        if (wideLongAmbiguityWarning) {
            wideLongAmbiguityWarning.classList.add('d-none');
            wideLongAmbiguityWarning.innerHTML = '';
        }
        if (wideLongTableHead) wideLongTableHead.innerHTML = '';
        if (wideLongTableBody) wideLongTableBody.innerHTML = '';
    }

    function formatWideLongAmbiguity(item) {
        const column = escapeHtml(item.column || '');
        const details = Array.isArray(item.details) ? item.details : [];

        if (item.reason === 'indicator-occurs-multiple-times') {
            const detailText = details
                .map((detail) => `${escapeHtml(detail.indicator || '')} × ${escapeHtml(detail.match_count || '')}`)
                .join(', ');
            return `<li><strong>${column}</strong>: indicator appears multiple times (${detailText}). Use a more specific token.</li>`;
        }

        const detailText = details
            .map((detail) => escapeHtml(detail.indicator || ''))
            .join(', ');
        return `<li><strong>${column}</strong>: multiple indicators match (${detailText}). Use a more specific token.</li>`;
    }

    function renderWideLongTablePreview(payload) {
        if (!wideLongTablePreview || !wideLongTableHead || !wideLongTableBody) return;

        const columns = Array.isArray(payload.columns) ? payload.columns : [];
        const rows = Array.isArray(payload.rows) ? payload.rows : [];
        const shown = Number(payload.rows_shown || rows.length || 0);
        const total = Number(payload.rows_total || shown);
        const indicators = Array.isArray(payload.detected_indicators)
            ? payload.detected_indicators
            : (Array.isArray(payload.detected_prefixes) ? payload.detected_prefixes : []);
        const renamePreview = Array.isArray(payload.column_rename_preview) ? payload.column_rename_preview : [];
        const ambiguousColumns = Array.isArray(payload.ambiguous_columns) ? payload.ambiguous_columns : [];
        const canConvert = payload.can_convert !== false;

        if (wideLongColumnPreviewSection && wideLongColumnPreviewList) {
            if (renamePreview.length) {
                wideLongColumnPreviewList.innerHTML = renamePreview.map((item) => {
                    const column = escapeHtml(item.column || '');
                    const outputColumn = escapeHtml(item.output_column || '');
                    const indicator = escapeHtml(item.indicator || '');
                    return `<div class="mb-1"><code>${column}</code> -> <code>${outputColumn}</code> <span class="text-muted">(${indicator})</span></div>`;
                }).join('');
                wideLongColumnPreviewSection.classList.remove('d-none');
            } else {
                wideLongColumnPreviewSection.classList.add('d-none');
                wideLongColumnPreviewList.innerHTML = '';
            }
        }

        if (wideLongAmbiguityWarning) {
            if (ambiguousColumns.length) {
                wideLongAmbiguityWarning.innerHTML = [
                    '<div class="fw-bold mb-1">Conversion blocked until the indicator is specific enough.</div>',
                    '<ul class="mb-0 ps-3">',
                    ambiguousColumns.map((item) => formatWideLongAmbiguity(item)).join(''),
                    '</ul>'
                ].join('');
                wideLongAmbiguityWarning.classList.remove('d-none');
            } else {
                wideLongAmbiguityWarning.classList.add('d-none');
                wideLongAmbiguityWarning.innerHTML = '';
            }
        }

        const headCells = columns.map((col) => `<th>${escapeHtml(col)}</th>`).join('');
        wideLongTableHead.innerHTML = columns.length ? `<tr>${headCells}</tr>` : '';

        wideLongTableBody.innerHTML = rows.map((row) => {
            const cells = columns.map((col) => `<td>${escapeHtml(row[col] ?? '')}</td>`).join('');
            return `<tr>${cells}</tr>`;
        }).join('');

        if (wideLongTableMeta) {
            const indicatorText = indicators.length ? indicators.join(', ') : 'auto-detect';
            if (canConvert) {
                wideLongTableMeta.textContent = `Showing ${shown} of ${total} converted rows. Matched session indicators: ${indicatorText}`;
            } else {
                wideLongTableMeta.textContent = `Matched session indicators: ${indicatorText}. Row preview is hidden until ambiguous columns are resolved.`;
            }
        }

        wideLongTablePreview.classList.remove('d-none');
    }

    function clearWideLongForm() {
        if (wideLongFile) {
            wideLongFile.value = '';
        }
        wideLongServerFilePath = '';
        if (wideLongFileName) {
            wideLongFileName.value = 'No file selected';
        }
        // session column is fixed to 'session'
        if (wideLongIndicators) {
            wideLongIndicators.value = '';
        }
        // run column is fixed to 'run'
        if (wideLongRunIndicators) {
            wideLongRunIndicators.value = '';
        }
        hideRawPeek();
        if (wideLongError) {
            wideLongError.classList.add('d-none');
            wideLongError.textContent = '';
        }
        if (wideLongInfo) {
            wideLongInfo.classList.add('d-none');
            wideLongInfo.textContent = '';
        }
        hideWideLongTablePreview();

        setWideLongIdleState();
        updateWideLongPreview();
    }

    if (wideLongPickFileBtn && wideLongFile) {
        wideLongPickFileBtn.addEventListener('click', async () => {
            wideLongFile.click();
        });
    }

    if (wideLongBrowseServerFileBtn) {
        wideLongBrowseServerFileBtn.addEventListener('click', async () => {
            if (!(window.PrismFileSystemMode && typeof window.PrismFileSystemMode.pickFile === 'function')) {
                return;
            }

            const pickedPath = await window.PrismFileSystemMode.pickFile({
                title: 'Select Wide Table on Server',
                confirmLabel: 'Use This File',
                extensions: '.csv,.tsv,.xlsx',
            });
            if (!pickedPath) {
                return;
            }

            wideLongServerFilePath = pickedPath;
            if (wideLongFile) {
                wideLongFile.value = '';
            }
            if (wideLongFileName) {
                wideLongFileName.value = pickedPath.split('/').pop() || pickedPath;
            }
            hideWideLongTablePreview();
            setWideLongIdleState();
            updateWideLongPreview();
            fetchRawPeek(null, pickedPath);
        });
    }

    if (wideLongClearBtn) {
        wideLongClearBtn.addEventListener('click', clearWideLongForm);
    }

    if (wideLongFile) {
        wideLongFile.addEventListener('change', () => {
            wideLongServerFilePath = '';
            if (wideLongError) wideLongError.classList.add('d-none');
            if (wideLongInfo) wideLongInfo.classList.add('d-none');
            if (wideLongFileName) {
                const selected = wideLongFile.files && wideLongFile.files[0] ? wideLongFile.files[0].name : 'No file selected';
                wideLongFileName.value = selected;
            }
            hideWideLongTablePreview();
            setWideLongIdleState();
            updateWideLongPreview();
            if (wideLongFile.files && wideLongFile.files[0]) {
                fetchRawPeek(wideLongFile.files[0], '');
            }
        });
        if (wideLongFileName) {
            wideLongFileName.value = 'No file selected';
        }
        setWideLongIdleState();
    }

    if (wideLongRawPeekToggle && wideLongRawPeekBody) {
        wideLongRawPeekToggle.addEventListener('click', () => {
            const hidden = wideLongRawPeekBody.classList.toggle('d-none');
            const icon = wideLongRawPeekToggle.querySelector('i');
            if (hidden) {
                if (icon) { icon.className = 'fas fa-chevron-down'; }
                wideLongRawPeekToggle.childNodes[wideLongRawPeekToggle.childNodes.length - 1].textContent = ' show';
            } else {
                if (icon) { icon.className = 'fas fa-chevron-up'; }
                wideLongRawPeekToggle.childNodes[wideLongRawPeekToggle.childNodes.length - 1].textContent = ' hide';
            }
        });
    }


    if (wideLongIndicators) {
        wideLongIndicators.addEventListener('input', () => {
            hideWideLongTablePreview();
            updateWideLongPreview();
        });
    }

    if (wideLongRunIndicators) {
        wideLongRunIndicators.addEventListener('input', () => {
            hideWideLongTablePreview();
            updateWideLongPreview();
        });
    }
    updateWideLongPreview();

    if (wideLongDataPreviewBtn) {
        wideLongDataPreviewBtn.addEventListener('click', async () => {
            const selectedWideLongFile = (wideLongFile && wideLongFile.files && wideLongFile.files[0])
                ? wideLongFile.files[0]
                : null;
            if (!selectedWideLongFile && !wideLongServerFilePath) {
                return;
            }

            if (wideLongError) wideLongError.classList.add('d-none');
            if (wideLongInfo) wideLongInfo.classList.add('d-none');
            if (wideLongProgress) wideLongProgress.classList.remove('d-none');
            wideLongDataPreviewBtn.disabled = true;
            if (wideLongConvertBtn) wideLongConvertBtn.disabled = true;

            const formData = new FormData();
            if (selectedWideLongFile) {
                formData.append('data', selectedWideLongFile);
            } else if (wideLongServerFilePath) {
                formData.append('source_file_path', wideLongServerFilePath);
            }
            formData.append('session_column', 'session');
            formData.append('session_indicators', (wideLongIndicators && wideLongIndicators.value || '').trim());
            formData.append('run_column', (wideLongRunIndicators && wideLongRunIndicators.value || '').trim() ? 'run' : '');
            formData.append('run_indicators', (wideLongRunIndicators && wideLongRunIndicators.value || '').trim());
            formData.append('preview_limit', '8');

            try {
                const response = await fetchWithApiFallback('/api/file-management/wide-to-long-preview', {
                    method: 'POST',
                    body: formData,
                });

                if (!response.ok) {
                    let message = 'Output preview failed.';
                    try {
                        const payload = await response.json();
                        if (payload && payload.error) {
                            message = payload.error;
                        }
                    } catch (_) {
                        // Keep fallback message when response is not JSON.
                    }
                    throw new Error(message);
                }

                const payload = await response.json();
                renderWideLongTablePreview(payload);
            } catch (err) {
                hideWideLongTablePreview();
                if (wideLongError) {
                    wideLongError.textContent = err.message || 'Output preview failed.';
                    wideLongError.classList.remove('d-none');
                }
            } finally {
                setWideLongIdleState();
            }
        });
    }

    if (wideLongConvertBtn) {
        wideLongConvertBtn.addEventListener('click', async () => {
            const selectedWideLongFile = (wideLongFile && wideLongFile.files && wideLongFile.files[0])
                ? wideLongFile.files[0]
                : null;
            if (!selectedWideLongFile && !wideLongServerFilePath) {
                return;
            }
            const currentProjectPath = getCurrentProjectPath();
            if (!currentProjectPath) {
                if (wideLongError) {
                    wideLongError.textContent = 'No active project selected. Open a project before saving converted files.';
                    wideLongError.classList.remove('d-none');
                }
                return;
            }

            if (wideLongError) wideLongError.classList.add('d-none');
            if (wideLongInfo) wideLongInfo.classList.add('d-none');
            if (wideLongProgress) wideLongProgress.classList.remove('d-none');
            wideLongConvertBtn.disabled = true;

            const formData = new FormData();
            if (selectedWideLongFile) {
                formData.append('data', selectedWideLongFile);
            } else if (wideLongServerFilePath) {
                formData.append('source_file_path', wideLongServerFilePath);
            }
            formData.append('session_column', 'session');
            formData.append('session_indicators', (wideLongIndicators && wideLongIndicators.value || '').trim());
            formData.append('run_column', (wideLongRunIndicators && wideLongRunIndicators.value || '').trim() ? 'run' : '');
            formData.append('run_indicators', (wideLongRunIndicators && wideLongRunIndicators.value || '').trim());
            formData.append('project_path', currentProjectPath);

            try {
                const response = await fetchWithApiFallback('/api/file-management/wide-to-long', {
                    method: 'POST',
                    body: formData,
                });

                if (!response.ok) {
                    let message = 'Wide-to-long conversion failed.';
                    try {
                        const payload = await response.json();
                        if (payload && payload.error) {
                            message = payload.error;
                        }
                    } catch (_) {
                        // Keep fallback message when response is not JSON.
                    }
                    throw new Error(message);
                }

                const result = await response.json();

                if (wideLongInfo) {
                    wideLongInfo.innerHTML = `<i class="fas fa-check-circle me-1"></i>Saved to <code>${result.saved_to}</code>`;
                    wideLongInfo.classList.remove('d-none');
                }
            } catch (err) {
                if (wideLongError) {
                    wideLongError.textContent = err.message || 'Wide-to-long conversion failed.';
                    wideLongError.classList.remove('d-none');
                }
            } finally {
                setWideLongIdleState();
            }
        });
    }

    // --------------------
    // Batch Organizer
    // --------------------
    const organizeFiles = document.getElementById('organizeFiles');
    const organizeModality = document.getElementById('organizeModality');
    const organizeDryRunBtn = document.getElementById('organizeDryRunBtn');
    const organizeCopyBtn = document.getElementById('organizeCopyBtn');
    const organizeError = document.getElementById('organizeError');
    const organizeInfo = document.getElementById('organizeInfo');
    const organizeProgress = document.getElementById('organizeProgress');
    const organizeLogContainer = document.getElementById('organizeLogContainer');
    const organizeLog = document.getElementById('organizeLog');
    const organizeLogClearBtn = document.getElementById('organizeLogClearBtn');
    const organizeFolder = document.getElementById('organizeFolder');
    const organizeBrowseServerFileBtn = document.getElementById('organizeBrowseServerFileBtn');
    const organizeClearServerFilesBtn = document.getElementById('organizeClearServerFilesBtn');
    const organizeFilesServerPathHint = document.getElementById('organizeFilesServerPathHint');
    const organizeFolderServerBrowseBtn = document.getElementById('organizeFolderServerBrowseBtn');
    const organizeFolderServerPathHint = document.getElementById('organizeFolderServerPathHint');
    const organizeFlatStructure = document.getElementById('organizeFlatStructure');
    const organizeTargetPrism = document.getElementById('organizeTargetPrism');
    const organizeTargetRaw = document.getElementById('organizeTargetRaw');
    const organizeTargetSource = document.getElementById('organizeTargetSource');
    const flatStructureHint = document.getElementById('flatStructureHint');
    const repoSubjectRewriteBtn = document.getElementById('repoSubjectRewriteBtn');
    const repoSubjectRewritePreviewBtn = document.getElementById('repoSubjectRewritePreviewBtn');
    const repoSubjectRewriteExample = document.getElementById('repoSubjectRewriteExample');
    const repoSubjectRewriteKeep = document.getElementById('repoSubjectRewriteKeep');
    const repoSubjectRewriteResult = document.getElementById('repoSubjectRewriteResult');
    let repoSubjectExamples = [];
    let repoSubjectPreviewReady = false;
    
    const organizeTargetRoot = () => {
        const checked = document.querySelector('input[name="organizeTargetRoot"]:checked');
        return checked ? checked.value : 'prism';
    };

    // Update flat structure hint and auto-suggest based on destination
    function updateFlatStructureHint() {
        const targetRoot = organizeTargetRoot();
        const isSourcedata = targetRoot === 'sourcedata';
        const isRawdata = targetRoot === 'rawdata';
        const isPrismRoot = targetRoot === 'prism';

        if (organizeFlatStructure) {
            if (isPrismRoot) {
                organizeFlatStructure.checked = false;
                organizeFlatStructure.disabled = true;
            } else {
                organizeFlatStructure.disabled = false;
            }
        }

        if (flatStructureHint) {
            if (isPrismRoot) {
                flatStructureHint.textContent = 'Project root keeps PRISM folders; use rawdata or sourcedata for flat copies.';
                flatStructureHint.className = 'text-muted';
            } else if (isSourcedata) {
                flatStructureHint.textContent = 'Recommended for sourcedata';
                flatStructureHint.className = 'text-success';
            } else if (isRawdata) {
                flatStructureHint.textContent = 'Optional for rawdata; flat copies go to rawdata/<modality>/';
                flatStructureHint.className = 'text-muted';
            }
        }
        // Auto-enable flat for sourcedata (but allow user to override)
        if (organizeFlatStructure && isSourcedata && !organizeFlatStructure.checked) {
            organizeFlatStructure.checked = true;
        }
    }

    if (organizeTargetPrism) {
        organizeTargetPrism.addEventListener('change', updateFlatStructureHint);
    }
    if (organizeTargetRaw) {
        organizeTargetRaw.addEventListener('change', updateFlatStructureHint);
    }
    if (organizeTargetSource) {
        organizeTargetSource.addEventListener('change', updateFlatStructureHint);
    }
    updateFlatStructureHint();

    function getOrganizeFiles() {
        const fileList = [];
        if (organizeFiles && organizeFiles.files) {
            fileList.push(...Array.from(organizeFiles.files));
        }
        if (organizeFolder && organizeFolder.files) {
            fileList.push(...Array.from(organizeFolder.files));
        }
        return fileList;
    }

    function clearOrganizerServerFolderSelection() {
        organizeServerFolderPath = '';
        if (organizeFolderServerPathHint) {
            organizeFolderServerPathHint.textContent = '';
            organizeFolderServerPathHint.classList.add('d-none');
        }
    }

    function clearOrganizerServerFileSelection() {
        organizeServerFilePaths = [];
        if (organizeFilesServerPathHint) {
            organizeFilesServerPathHint.textContent = '';
            organizeFilesServerPathHint.classList.add('d-none');
        }
        updateOrganizeServerFilesHint();
    }

    function hasOrganizerInput() {
        return getOrganizeFiles().length > 0 || Boolean(organizeServerFolderPath) || organizeServerFilePaths.length > 0;
    }

    function updateOrganizeBtn() {
        const hasFiles = hasOrganizerInput();
        const hasCurrentProject = Boolean(getCurrentProjectPath());
        if (organizeDryRunBtn) organizeDryRunBtn.disabled = !hasFiles;
        if (organizeCopyBtn) organizeCopyBtn.disabled = !hasFiles || !hasCurrentProject;
    }

    if (organizeFiles) {
        organizeFiles.addEventListener('change', () => {
            if (organizeFiles.files && organizeFiles.files.length > 0) {
                clearOrganizerServerFolderSelection();
                clearOrganizerServerFileSelection();
            }
            updateOrganizeBtn();
        });
        updateOrganizeBtn();
    }

    if (organizeFolder) {
        organizeFolder.addEventListener('change', () => {
            if (organizeFolder.files && organizeFolder.files.length > 0) {
                clearOrganizerServerFolderSelection();
                clearOrganizerServerFileSelection();
            }
            updateOrganizeBtn();
        });
        updateOrganizeBtn();
    }

    if (organizeClearServerFilesBtn) {
        organizeClearServerFilesBtn.addEventListener('click', () => {
            clearOrganizerServerFileSelection();
            updateOrganizeBtn();
        });
    }

    if (organizeBrowseServerFileBtn) {
        organizeBrowseServerFileBtn.addEventListener('click', async () => {
            if (!(window.PrismFileSystemMode && typeof window.PrismFileSystemMode.pickFile === 'function')) {
                return;
            }
            try {
                const startPath = organizeServerFilePaths.length > 0
                    ? getParentDirectory(organizeServerFilePaths[organizeServerFilePaths.length - 1])
                    : '';
                const picked = await window.PrismFileSystemMode.pickFile({
                    title: 'Select File to Organize (Server)',
                    confirmLabel: 'Add This File',
                    startPath,
                });

                if (!picked) {
                    return;
                }

                if (!organizeServerFilePaths.includes(picked)) {
                    organizeServerFilePaths.push(picked);
                }
                clearOrganizerServerFolderSelection();
                if (organizeFiles) {
                    organizeFiles.value = '';
                }
                if (organizeFolder) {
                    organizeFolder.value = '';
                }
                updateOrganizeServerFilesHint();
                updateOrganizeBtn();
            } catch (error) {
                if (organizeError) {
                    organizeError.textContent = error.message || 'Failed to browse server file.';
                    organizeError.classList.remove('d-none');
                }
            }
        });
    }

    if (organizeLogClearBtn) {
        organizeLogClearBtn.addEventListener('click', () => {
            if (organizeLog) organizeLog.textContent = '';
        });
    }

    function appendOrganizerLog(message, level = 'info') {
        if (!organizeLog) return;
        const levelClasses = {
            info: 'ansi-blue',
            success: 'ansi-green',
            warning: 'ansi-yellow',
            error: 'ansi-red',
            progress: 'ansi-cyan',
            preview: 'ansi-cyan'
        };
        const line = document.createElement('div');
        line.className = levelClasses[level] || 'ansi-reset';
        line.textContent = message;
        organizeLog.appendChild(line);
        organizeLog.scrollTop = organizeLog.scrollHeight;
    }

    function getProjectSaveSummary(result) {
        const outputPaths = Array.isArray(result && result.project_output_paths)
            ? result.project_output_paths.filter((value) => typeof value === 'string' && value.trim())
            : [];
        const target = (result && (result.project_output_path || outputPaths[0] || result.project_output_root)) || 'the active project';
        const outputCount = Number.isFinite(result && result.project_output_count)
            ? result.project_output_count
            : outputPaths.length;
        const countNote = outputCount > 1 ? ` (${outputCount} files)` : '';

        return { target, countNote };
    }

    async function runOrganizer(opts = {}) {
        const saveToProject = opts.saveToProject === true;
        const skipDownload = opts.skipDownload === true;
        const dryRun = opts.dryRun === true;
        if (!organizeFiles) return;
        const currentProjectPath = getCurrentProjectPath();
        if (saveToProject && !currentProjectPath) {
            if (organizeError) {
                organizeError.textContent = 'No active project selected. Open a project before copying files.';
                organizeError.classList.remove('d-none');
            }
            return;
        }
        if (organizeError) organizeError.classList.add('d-none');
        if (organizeInfo) organizeInfo.classList.add('d-none');
        if (organizeProgress) organizeProgress.classList.remove('d-none');
        if (organizeLogContainer) organizeLogContainer.classList.remove('d-none');
        if (organizeLog) organizeLog.textContent = '';
        if (organizeDryRunBtn) organizeDryRunBtn.disabled = true;
        if (organizeCopyBtn) organizeCopyBtn.disabled = true;

        const files = getOrganizeFiles();
        const usingServerFolderPath = files.length === 0 && Boolean(organizeServerFolderPath);
        const usingServerFilePaths = files.length === 0 && organizeServerFilePaths.length > 0;
        const modality = organizeModality ? organizeModality.value : 'anat';
        const destRoot = organizeTargetRoot();
        const flatStructure = document.getElementById('organizeFlatStructure')?.checked || false;
        const datasetName = 'Organized Dataset';

        const sourceLabel = usingServerFolderPath
            ? `folder ${organizeServerFolderPath}`
            : (usingServerFilePaths
                ? `${organizeServerFilePaths.length} server file${organizeServerFilePaths.length === 1 ? '' : 's'}`
                : `${files.length} files`);
        appendOrganizerLog(`Starting ${dryRun ? 'dry run' : 'copy'} for ${sourceLabel}...`, 'progress');
        appendOrganizerLog(`Mode: ${dryRun ? 'preview' : 'execute'} | Modality: ${modality} | Destination: ${destRoot}${flatStructure ? ' (flat)' : ''}`, 'info');

        const formData = new FormData();
        if (usingServerFolderPath) {
            formData.append('folder_path', organizeServerFolderPath);
        } else if (files.length > 0) {
            files.forEach(f => formData.append('files', f));
        }
        organizeServerFilePaths.forEach((serverFilePath) => {
            formData.append('server_file_paths', serverFilePath);
        });
        formData.append('dataset_name', datasetName);
        formData.append('modality', modality);
        formData.append('save_to_project', saveToProject);
        formData.append('dest_root', destRoot);
        formData.append('flat_structure', flatStructure);
        formData.append('dry_run', dryRun);
        if (saveToProject && currentProjectPath) {
            formData.append('project_path', currentProjectPath);
        }

        try {
            const response = await fetchWithApiFallback('/api/batch-convert', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const data = await response.json().catch(() => null);
                throw new Error(data && data.error ? data.error : 'Organization failed');
            }

            const result = await response.json();

            // Display logs with colors based on level
            if (result.logs && organizeLog) {
                result.logs.forEach((entry) => {
                    const level = entry && entry.level ? entry.level : 'info';
                    const message = entry && entry.message ? entry.message : '';
                    if (message) {
                        appendOrganizerLog(message, level);
                    }
                });
            }

            if (result.dry_run) {
                if (organizeInfo) {
                    const newCount = result.new_files || 0;
                    const existingCount = result.existing_files || 0;
                    organizeInfo.innerHTML = `<i class="fas fa-check-circle me-2 text-success"></i>Dry run complete: ${result.converted || 0} files would be organized.<br>📄 <strong>New:</strong> ${newCount} · 📋 <strong>Existing (will overwrite):</strong> ${existingCount}<br>Review the log above, then click "Copy to Project" to execute.`;
                    organizeInfo.classList.remove('d-none');
                }
                appendOrganizerLog(`Dry run complete: ${result.converted || 0} files would be organized.`, 'success');
            } else {
                const warnings = result.warnings || [];
                if (warnings.length && organizeError) {
                    organizeError.innerHTML = warnings.map(w => `<div><i class="fas fa-exclamation-triangle me-2"></i>${escapeHtml(w)}</div>`).join('');
                    organizeError.classList.remove('d-none');
                }

                warnings.forEach((warningMsg) => {
                    appendOrganizerLog(`⚠ ${warningMsg}`, 'warning');
                });

                if (organizeInfo) {
                    const saveSummary = result.project_saved ? getProjectSaveSummary(result) : null;
                    const savedText = saveSummary ? ` Saved to project: ${saveSummary.target}${saveSummary.countNote}.` : '';
                    const zipText = skipDownload ? '' : ' ZIP download started.';
                    organizeInfo.textContent = `Organized ${result.converted || 0} files. ${result.errors || 0} errors.${savedText}${zipText}`.trim();
                    organizeInfo.classList.remove('d-none');
                }
                if (result.project_saved) {
                    const saveSummary = getProjectSaveSummary(result);
                    appendOrganizerLog(`Saved to project: ${saveSummary.target}${saveSummary.countNote}`, 'success');
                }
                appendOrganizerLog(`Finished: ${result.converted || 0} organized, ${result.errors || 0} errors.`, result.errors ? 'warning' : 'success');
            }
        } catch (err) {
            if (organizeError) {
                organizeError.textContent = err.message;
                organizeError.classList.remove('d-none');
            }
            appendOrganizerLog(`✗ ${err.message}`, 'error');
        } finally {
            if (organizeProgress) organizeProgress.classList.add('d-none');
            updateOrganizeBtn();
        }
    }

    if (organizeDryRunBtn) {
        organizeDryRunBtn.addEventListener('click', () => runOrganizer({ dryRun: true }));
    }

    if (organizeCopyBtn) {
        organizeCopyBtn.addEventListener('click', () => runOrganizer({ saveToProject: true, skipDownload: true }));
    }

    function resetRepoSubjectPreviewState() {
        repoSubjectPreviewReady = false;
        if (repoSubjectRewriteBtn) {
            repoSubjectRewriteBtn.disabled = true;
        }
    }

    function setRepoSubjectRewriteBusy(isBusy) {
        if (repoSubjectRewritePreviewBtn) {
            repoSubjectRewritePreviewBtn.disabled = isBusy;
        }
        if (repoSubjectRewriteBtn) {
            repoSubjectRewriteBtn.disabled = isBusy || !repoSubjectPreviewReady;
        }
        if (repoSubjectRewriteExample) {
            repoSubjectRewriteExample.disabled = isBusy || repoSubjectExamples.length === 0;
        }
        if (repoSubjectRewriteKeep) {
            repoSubjectRewriteKeep.disabled = isBusy || repoSubjectExamples.length === 0;
        }
    }

    function suggestKeepFragment(exampleSubject) {
        const rawLabel = String(exampleSubject || '').replace(/^sub-/, '');
        if (!rawLabel) {
            return '';
        }
        const digits = rawLabel.replace(/\D/g, '');
        if (digits.length >= 3) {
            return digits.slice(-3);
        }
        if (rawLabel.length <= 3) {
            return rawLabel;
        }
        return rawLabel.slice(-3);
    }

    function applyRepoSubjectExampleSelection({ suggestKeep = false } = {}) {
        if (!repoSubjectRewriteExample || repoSubjectExamples.length === 0) {
            return;
        }
        const selectedValue = String(repoSubjectRewriteExample.value || '').trim();
        if (!selectedValue || !repoSubjectExamples.includes(selectedValue)) {
            repoSubjectRewriteExample.value = repoSubjectExamples[0];
        }
        if (suggestKeep && repoSubjectRewriteKeep) {
            repoSubjectRewriteKeep.value = suggestKeepFragment(repoSubjectRewriteExample.value);
        }
    }

    async function loadRepoSubjectExamples() {
        const currentProjectPath = getCurrentProjectPath();
        if (!currentProjectPath) {
            repoSubjectExamples = [];
            if (repoSubjectRewriteExample) {
                repoSubjectRewriteExample.innerHTML = '<option value="">No active project</option>';
            }
            if (repoSubjectRewriteResult) {
                repoSubjectRewriteResult.innerHTML = '<div class="alert alert-warning py-2 mb-0">No active project selected. Open a project first.</div>';
            }
            resetRepoSubjectPreviewState();
            setRepoSubjectRewriteBusy(false);
            return;
        }

        setRepoSubjectRewriteBusy(true);
        if (repoSubjectRewriteResult) {
            repoSubjectRewriteResult.innerHTML = '<div class="alert alert-info py-2 mb-0">Loading subject ID examples...</div>';
        }

        try {
            const response = await fetchWithApiFallback('/api/file-management/subject-rewrite', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: 'examples',
                    mode: 'last3',
                    project_path: currentProjectPath,
                }),
            });

            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload.error || 'Failed to load subject ID examples.');
            }

            repoSubjectExamples = Array.isArray(payload.subject_examples)
                ? payload.subject_examples.filter((value) => typeof value === 'string' && value.startsWith('sub-'))
                : [];

            if (repoSubjectRewriteExample) {
                if (repoSubjectExamples.length === 0) {
                    repoSubjectRewriteExample.innerHTML = '<option value="">No subject IDs found</option>';
                } else {
                    repoSubjectRewriteExample.innerHTML = repoSubjectExamples
                        .map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`)
                        .join('');
                }
            }

            if (repoSubjectExamples.length > 0) {
                applyRepoSubjectExampleSelection({ suggestKeep: true });
                if (repoSubjectRewriteResult) {
                    repoSubjectRewriteResult.innerHTML = '<div class="alert alert-secondary py-2 mb-0">Choose an example and click Preview to see the full mapping before applying.</div>';
                }
            } else if (repoSubjectRewriteResult) {
                repoSubjectRewriteResult.innerHTML = '<div class="alert alert-secondary py-2 mb-0">No subject IDs found in the current project.</div>';
            }
            resetRepoSubjectPreviewState();
        } catch (error) {
            repoSubjectExamples = [];
            if (repoSubjectRewriteExample) {
                repoSubjectRewriteExample.innerHTML = '<option value="">Failed to load examples</option>';
            }
            if (repoSubjectRewriteResult) {
                repoSubjectRewriteResult.innerHTML = `<div class="alert alert-danger py-2 mb-0">${escapeHtml(error.message || 'Failed to load subject ID examples.')}</div>`;
            }
            resetRepoSubjectPreviewState();
        } finally {
            setRepoSubjectRewriteBusy(false);
        }
    }

    function renderRepoSubjectRewriteResult(payload, actionLabel) {
        if (!repoSubjectRewriteResult) return;

        const hasConflicts = Array.isArray(payload.conflicts) && payload.conflicts.length > 0;
        const mappingEntries = Object.entries(payload.mapping || {});
        const mappingPreviewLimit = 20;
        const mappingTotal = mappingEntries.length;
        const mappingHeader = mappingTotal > mappingPreviewLimit
            ? `<div class="small mb-1 text-muted"><strong>Mapping:</strong> showing first ${mappingPreviewLimit} of ${mappingTotal} entries.</div>`
            : '<div class="small mb-1"><strong>Mapping:</strong> full mapping.</div>';
        const mappingHtml = mappingEntries.length
            ? `${mappingHeader}<div class="small">${mappingEntries.slice(0, mappingPreviewLimit).map(([oldCode, newCode]) => `${escapeHtml(oldCode)} -> ${escapeHtml(newCode)}`).join(' | ')}</div>`
            : '<div class="small text-muted">No subject IDs require rewriting.</div>';

        const rule = payload.rule || {};
        const strategy = rule.strategy ? String(rule.strategy) : '';
        const keepFragment = rule.keep_fragment ? String(rule.keep_fragment) : '';
        const exampleSubject = rule.example_subject ? String(rule.example_subject) : '';

        let ruleText = '';
        if (strategy && keepFragment && exampleSubject) {
            if (strategy === 'suffix') {
                ruleText = `Keep suffix '${escapeHtml(keepFragment)}' from each subject ID (based on ${escapeHtml(exampleSubject)}).`;
            } else if (strategy === 'prefix') {
                ruleText = `Keep prefix '${escapeHtml(keepFragment)}' from each subject ID (based on ${escapeHtml(exampleSubject)}).`;
            } else if (strategy === 'slice') {
                ruleText = `Keep the selected internal segment '${escapeHtml(keepFragment)}' from each subject ID (based on ${escapeHtml(exampleSubject)}).`;
            } else if (strategy === 'full') {
                ruleText = `Rule keeps the full ID from ${escapeHtml(exampleSubject)} (no shortening for this example).`;
            }
        }

        const ruleHtml = ruleText
            ? `<div class="small mb-1"><strong>Rule:</strong> ${ruleText}</div>`
            : '';

        let conflictSourcesHtml = '';
        const tokenSources = payload.subject_token_sources && typeof payload.subject_token_sources === 'object'
            ? payload.subject_token_sources
            : {};
        if (hasConflicts) {
            const conflictSourceLines = [];
            const seenConflictTokens = new Set();
            payload.conflicts.forEach((line) => {
                const tokens = String(line).match(/sub-[A-Za-z0-9]+/g) || [];
                tokens.forEach((token) => {
                    if (seenConflictTokens.has(token)) {
                        return;
                    }
                    seenConflictTokens.add(token);
                    const sources = Array.isArray(tokenSources[token]) ? tokenSources[token] : [];
                    if (sources.length > 0) {
                        conflictSourceLines.push(`<div><strong>${escapeHtml(token)}</strong>: ${sources.slice(0, 3).map((value) => escapeHtml(value)).join(' | ')}</div>`);
                    }
                });
            });
            if (conflictSourceLines.length > 0) {
                conflictSourcesHtml = `<div class="small mt-2"><strong>Conflict sources (sample paths):</strong>${conflictSourceLines.join('')}</div>`;
            }
        }

        const conflictHtml = hasConflicts
            ? `<div class="alert alert-danger py-2 mb-2">${payload.conflicts.map((msg) => `<div>${escapeHtml(msg)}</div>`).join('')}${conflictSourcesHtml}</div>`
            : '';

        const infoClass = hasConflicts ? 'alert-warning' : (actionLabel === 'Preview' ? 'alert-info' : 'alert-success');
        repoSubjectRewriteResult.innerHTML = `
            ${conflictHtml}
            <div class="alert ${infoClass} py-2 mb-0">
                <div><strong>${actionLabel}</strong>: ${payload.mapping_count || 0} subject mapping(s), ${payload.directory_rename_count || 0} folder rename(s), ${payload.file_rename_count || 0} filename rename(s), ${payload.text_update_count || 0} metadata text update(s).</div>
                ${ruleHtml}
                ${mappingHtml}
            </div>
        `;
    }

    async function runRepoSubjectRewrite(action) {
        const currentProjectPath = getCurrentProjectPath();
        if (!currentProjectPath) {
            if (repoSubjectRewriteResult) {
                repoSubjectRewriteResult.innerHTML = '<div class="alert alert-danger py-2 mb-0">No active project selected. Open a project first.</div>';
            }
            return;
        }

        if (!repoSubjectRewriteExample || !repoSubjectRewriteKeep) {
            return;
        }

        const selectedExample = String(repoSubjectRewriteExample.value || '').trim();
        const keepFragment = String(repoSubjectRewriteKeep.value || '').trim();
        if (!selectedExample) {
            if (repoSubjectRewriteResult) {
                repoSubjectRewriteResult.innerHTML = '<div class="alert alert-danger py-2 mb-0">Select an example subject ID first.</div>';
            }
            return;
        }
        if (!keepFragment) {
            if (repoSubjectRewriteResult) {
                repoSubjectRewriteResult.innerHTML = '<div class="alert alert-danger py-2 mb-0">Enter the part that should stay from the example subject ID.</div>';
            }
            return;
        }

        if (action === 'apply') {
            if (!repoSubjectPreviewReady) {
                if (repoSubjectRewriteResult) {
                    repoSubjectRewriteResult.innerHTML = '<div class="alert alert-warning py-2 mb-0">Run Preview first, then apply.</div>';
                }
                return;
            }

            const confirmed = window.confirm('Apply this subject ID rewrite mapping to the current project and update internal metadata links?');
            if (!confirmed) {
                return;
            }
        }

        setRepoSubjectRewriteBusy(true);

        if (repoSubjectRewriteResult) {
            repoSubjectRewriteResult.innerHTML = `<div class="alert alert-info py-2 mb-0">${action === 'apply' ? 'Applying rewrite...' : 'Previewing rewrite mapping...'}</div>`;
        }

        try {
            const response = await fetchWithApiFallback('/api/file-management/subject-rewrite', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action,
                    mode: 'example_keep',
                    example_subject: selectedExample,
                    keep_fragment: keepFragment,
                    project_path: currentProjectPath,
                }),
            });

            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload.error || 'Subject rewrite request failed.');
            }

            renderRepoSubjectRewriteResult(payload, action === 'apply' ? 'Applied' : 'Preview');
            if (action === 'preview') {
                repoSubjectPreviewReady = !Array.isArray(payload.conflicts) || payload.conflicts.length === 0;
            } else {
                repoSubjectPreviewReady = false;
                window.dispatchEvent(new Event('prism-project-changed'));
                await loadRepoSubjectExamples();
            }
        } catch (error) {
            if (repoSubjectRewriteResult) {
                repoSubjectRewriteResult.innerHTML = `<div class="alert alert-danger py-2 mb-0">${escapeHtml(error.message || 'Subject rewrite request failed.')}</div>`;
            }
            repoSubjectPreviewReady = false;
        } finally {
            setRepoSubjectRewriteBusy(false);
        }
    }

    if (repoSubjectRewritePreviewBtn) {
        repoSubjectRewritePreviewBtn.addEventListener('click', () => runRepoSubjectRewrite('preview'));
    }

    if (repoSubjectRewriteBtn) {
        repoSubjectRewriteBtn.addEventListener('click', () => runRepoSubjectRewrite('apply'));
    }

    if (repoSubjectRewriteExample) {
        repoSubjectRewriteExample.addEventListener('change', () => {
            resetRepoSubjectPreviewState();
            applyRepoSubjectExampleSelection({ suggestKeep: true });
            if (repoSubjectRewriteResult) {
                repoSubjectRewriteResult.innerHTML = '<div class="alert alert-secondary py-2 mb-0">Example changed. Click Preview to regenerate mapping.</div>';
            }
            setRepoSubjectRewriteBusy(false);
        });
    }

    if (repoSubjectRewriteKeep) {
        repoSubjectRewriteKeep.addEventListener('input', () => {
            resetRepoSubjectPreviewState();
            if (repoSubjectRewriteResult) {
                repoSubjectRewriteResult.innerHTML = '<div class="alert alert-secondary py-2 mb-0">Rule changed. Click Preview to regenerate mapping.</div>';
            }
            setRepoSubjectRewriteBusy(false);
        });
    }

    if (organizeFolder && organizeFolder.parentElement) {
        let serverFolderButton = organizeFolderServerBrowseBtn || document.getElementById('organizeFolderServerBrowseBtn');
        if (!serverFolderButton) {
            serverFolderButton = document.createElement('button');
            serverFolderButton.type = 'button';
            serverFolderButton.className = 'btn btn-outline-secondary btn-sm mt-2 d-none';
            serverFolderButton.id = 'organizeFolderServerBrowseBtn';
            serverFolderButton.innerHTML = '<i class="fas fa-server me-1"></i>Server Folder';
            organizeFolder.parentElement.appendChild(serverFolderButton);
        }

        let serverFolderHint = organizeFolderServerPathHint || document.getElementById('organizeFolderServerPathHint');
        if (!serverFolderHint) {
            serverFolderHint = document.createElement('div');
            serverFolderHint.className = 'form-text d-none';
            serverFolderHint.id = 'organizeFolderServerPathHint';
            organizeFolder.parentElement.appendChild(serverFolderHint);
        }

        serverFolderButton.addEventListener('click', async () => {
            if (!(window.PrismFileSystemMode && typeof window.PrismFileSystemMode.pickFolder === 'function')) {
                return;
            }
            const picked = await window.PrismFileSystemMode.pickFolder({
                title: 'Select Folder to Organize (Server)',
                confirmLabel: 'Use This Folder',
                startPath: organizeServerFolderPath || ''
            });
            if (!picked) return;

            organizeServerFolderPath = picked;
            clearOrganizerServerFileSelection();
            if (organizeFiles) {
                organizeFiles.value = '';
            }
            if (organizeFolder) {
                organizeFolder.value = '';
            }
            if (serverFolderHint) {
                serverFolderHint.textContent = `Server folder: ${picked}`;
                serverFolderHint.classList.remove('d-none');
            }
            updateOrganizeBtn();
        });

        if (organizeFolder) {
            organizeFolder.addEventListener('change', () => {
                if (organizeFolder.files && organizeFolder.files.length > 0) {
                    clearOrganizerServerFolderSelection();
                }
            });
        }

        if (window.PrismFileSystemMode && typeof window.PrismFileSystemMode.init === 'function') {
            window.PrismFileSystemMode.init().then(() => {
                applyRemotePickerUiState();
            }).catch(() => {
                // Keep default host picker behavior on init failures.
            });
        }

    }

    // --------------------
    // Renamer Helper
    // --------------------
    const renamerFiles = document.getElementById('renamerFiles');
    const renamerPattern = document.getElementById('renamerPattern');
    const renamerReplacement = document.getElementById('renamerReplacement');
    const renamerNewExample = document.getElementById('renamerNewExample');
    const renamerTask = document.getElementById('renamerTask');
    const renamerExtension = document.getElementById('renamerExtension');
    const renamerModality = document.getElementById('renamerModality');
    const renamerRecording = document.getElementById('renamerRecording');
    const renamerRecordingContainer = document.getElementById('renamerRecordingContainer');
    const renamerExampleContainer = document.getElementById('renamerExampleContainer');
    const renamerOriginalExample = document.getElementById('renamerOriginalExample');
    const renamerOriginalPathHint = document.getElementById('renamerOriginalPathHint');
    const renamerPreview = document.getElementById('renamerPreview');
    const renamerPreviewBody = document.getElementById('renamerPreviewBody');
    const renamerFilterAll = document.getElementById('renamerFilterAll');
    const renamerFilterUnmatched = document.getElementById('renamerFilterUnmatched');
    const renamerError = document.getElementById('renamerError');
    const renamerInfo = document.getElementById('renamerInfo');
    const renamerProgress = document.getElementById('renamerProgress');
    const renamerProgressBar = document.getElementById('renamerProgressBar');
    const renamerLogContainer = document.getElementById('renamerLogContainer');
    const renamerLog = document.getElementById('renamerLog');
    const renamerLogClearBtn = document.getElementById('renamerLogClearBtn');
    const renamerBrowseServerFileBtn = document.getElementById('renamerBrowseServerFileBtn');
    const renamerBrowseServerFolderBtn = document.getElementById('renamerBrowseServerFolderBtn');
    const renamerClearServerSelectionBtn = document.getElementById('renamerClearServerSelectionBtn');
    const renamerServerFileHint = document.getElementById('renamerServerFileHint');
    const renamerServerFolderHint = document.getElementById('renamerServerFolderHint');
    const renamerOrganize = document.getElementById('renamerOrganize');
    const renamerResetBtn = document.getElementById('renamerResetBtn');
    const renamerDryRunBtn = document.getElementById('renamerDryRunBtn');
    const renamerDownloadBtn = document.getElementById('renamerDownloadBtn');
    const renamerCopyBtn = document.getElementById('renamerCopyBtn');
    const renamerUseMapping = document.getElementById('renamerUseMapping');
    const renamerMappingFields = document.getElementById('renamerMappingFields');
    const renamerSubjectValue = document.getElementById('renamerSubjectValue');
    const renamerSessionValue = document.getElementById('renamerSessionValue');
    const renamerMappingPreview = document.getElementById('renamerMappingPreview');
    const renamerFolderMappingFields = document.getElementById('renamerFolderMappingFields');
    const renamerFolderSubjectLevel = document.getElementById('renamerFolderSubjectLevel');
    const renamerFolderSessionLevel = document.getElementById('renamerFolderSessionLevel');
    const renamerTargetRaw = document.getElementById('renamerTargetRaw');
    const renamerTargetPrism = document.getElementById('renamerTargetPrism');
    const renamerTargetSource = document.getElementById('renamerTargetSource');
    const renamerStructureHint = document.getElementById('renamerStructureHint');
    const renamerIdFromFilename = document.getElementById('renamerIdFromFilename');
    const renamerIdFromFolder = document.getElementById('renamerIdFromFolder');

    const renamerTargetRoot = () => {
        const checked = document.querySelector('input[name="renamerTargetRoot"]:checked');
        return checked ? checked.value : 'prism';
    };

    const renamerIdSource = () => {
        const checked = document.querySelector('input[name="renamerIdSource"]:checked');
        return checked ? checked.value : 'filename';
    };

    function renamerCanCopyToProject() {
        return !(renamerTargetRoot() === 'prism' && renamerOrganize && !renamerOrganize.checked);
    }

    // Update structure hint based on destination
    function updateRenamerStructureHint() {
        const targetRoot = renamerTargetRoot();
        const isSourcedata = targetRoot === 'sourcedata';
        const isRawdata = targetRoot === 'rawdata';
        if (renamerStructureHint) {
            if (renamerOrganize && !renamerOrganize.checked && targetRoot === 'prism') {
                renamerStructureHint.textContent = 'Flat output can be downloaded or copied to rawdata/sourcedata. Enable folders to copy into the PRISM root.';
                renamerStructureHint.className = 'text-danger';
            } else if (renamerOrganize && !renamerOrganize.checked) {
                renamerStructureHint.textContent = isSourcedata
                    ? 'Flat structure (recommended for sourcedata)'
                    : (isRawdata ? 'Flat structure (copied to rawdata/<modality>/)' : 'Flat structure');
                renamerStructureHint.className = isSourcedata ? 'text-success' : 'text-muted';
            } else {
                renamerStructureHint.textContent = 'Creates sub-XX/ses-YY/modality/ folders';
                renamerStructureHint.className = 'text-muted';
            }
        }
    }

    let currentExampleFile = null;
    let renamerTemplateManuallyEdited = false;

    function updateRecordingVisibility() {
        if (!renamerModality || !renamerRecordingContainer) return;
        const showRecording = renamerModality.value === 'physio';
        renamerRecordingContainer.style.display = showRecording ? 'block' : 'none';
    }

    function updateRenamerBtn() {
        const hasFiles = (renamerFiles && renamerFiles.files && renamerFiles.files.length > 0) || renamerServerEntries.length > 0;
        const hasNewName = renamerNewExample && renamerNewExample.value.trim().length > 0;
        const hasTask = !!getValidatedTaskLabel();
        const hasCurrentProject = Boolean(getCurrentProjectPath());
        const disabled = !hasFiles || !hasNewName || !hasTask;
        if (renamerDownloadBtn) renamerDownloadBtn.disabled = disabled;
        if (renamerCopyBtn) renamerCopyBtn.disabled = disabled || !renamerCanCopyToProject() || !hasCurrentProject;
        if (renamerDryRunBtn) renamerDryRunBtn.disabled = disabled;
    }

    function updateMappingVisibility() {
        if (!renamerMappingFields || !renamerUseMapping) return;
        const isFolderMode = renamerIdSource() === 'folder';
        renamerMappingFields.classList.toggle('d-none', !renamerUseMapping.checked);
        if (renamerFolderMappingFields) {
            renamerFolderMappingFields.classList.toggle('d-none', !(renamerUseMapping.checked && isFolderMode));
        }
        if (renamerMappingPreview && !renamerUseMapping.checked) {
            renamerMappingPreview.textContent = '';
            renamerMappingPreview.classList.remove('text-danger');
            renamerMappingPreview.classList.add('text-muted');
        }
        if (isFolderMode && renamerMappingPreview) {
            const subjectLevel = getFolderLevelValue(renamerFolderSubjectLevel, 2);
            const sessionLevel = getFolderLevelValue(renamerFolderSessionLevel, 1);
            const subjectValue = sanitizeLiteral(renamerSubjectValue && renamerSubjectValue.value || '');
            const sessionValue = sanitizeLiteral(renamerSessionValue && renamerSessionValue.value || '');
            const suffix = sessionValue
                ? `, using example subject '${subjectValue}' and session '${sessionValue}'`
                : `, using example subject '${subjectValue}' (session optional)`;
            renamerMappingPreview.textContent = `Folder mode: subject from level ${subjectLevel} and session from level ${sessionLevel} (counted from end)${suffix}.`;
            renamerMappingPreview.classList.remove('text-danger');
            renamerMappingPreview.classList.add('text-muted');
        }
    }

    function getFolderLevelValue(inputEl, fallback) {
        if (!inputEl || !inputEl.value) return fallback;
        const parsed = Number.parseInt(inputEl.value, 10);
        if (!Number.isFinite(parsed) || parsed < 1) return fallback;
        return parsed;
    }

    function getClientRelativePath(file) {
        if (!file) return '';
        if (file.webkitRelativePath && file.webkitRelativePath.length > 0) {
            return file.webkitRelativePath;
        }
        return file.name || '';
    }

    function getRenamerEntries() {
        if (renamerFiles && renamerFiles.files && renamerFiles.files.length > 0) {
            return Array.from(renamerFiles.files).map((file) => ({
                file,
                name: file.name,
                sourcePath: getClientRelativePath(file),
                isServer: false,
            }));
        }

        if (renamerServerEntries.length > 0) {
            return renamerServerEntries.map((entry) => ({
                file: null,
                name: entry.name,
                sourcePath: entry.relative_path || entry.path || entry.name,
                isServer: true,
            }));
        }

        return [];
    }

    function updateOriginalExampleDisplay() {
        if (!currentExampleFile || !renamerOriginalExample) return;
        const sourcePath = getClientRelativePath(currentExampleFile);
        const isFolderMode = renamerIdSource() === 'folder';

        renamerOriginalExample.textContent = isFolderMode ? sourcePath : currentExampleFile.name;

        if (renamerOriginalPathHint) {
            const span = renamerOriginalPathHint.querySelector('span');
            if (span) span.textContent = sourcePath;
            renamerOriginalPathHint.classList.toggle('d-none', !isFolderMode);
        }
    }

    function sanitizeLiteral(value) {
        if (!value) return '';
        let cleaned = value.trim();
        // Remove wrapper brackets/parentheses
        if ((cleaned.startsWith('{') && cleaned.endsWith('}')) || (cleaned.startsWith('(') && cleaned.endsWith(')'))) {
            cleaned = cleaned.slice(1, -1).trim();
        }
        // Remove zero-width characters, non-breaking spaces, and other invisible Unicode characters
        cleaned = cleaned
            .replace(/[\u200B\u200C\u200D\uFEFF]/g, '') // Zero-width characters
            .replace(/[\u00A0]/g, ' ') // Non-breaking space to regular space
            .replace(/[\u200E\u200F]/g, '') // Directional marks
            .replace(/[\u202A-\u202E]/g, '') // Bidirectional formatting
            .trim();
        return cleaned;
    }

    function splitFilenameAndExt(filename) {
        if (!filename) return { base: '', ext: '' };
        const match = filename.match(/^(.*?)(\.[^.]+(?:\.[^.]+)*)$/);
        if (!match) return { base: filename, ext: '' };
        return { base: match[1], ext: match[2] };
    }

    function ensureExampleExtension(filename) {
        if (!currentExampleFile || !currentExampleFile.name) return filename;
        const currentParts = splitFilenameAndExt(filename);
        if (currentParts.ext) return filename;

        const exampleParts = splitFilenameAndExt(currentExampleFile.name);
        if (!exampleParts.ext) return filename;

        return `${filename}${exampleParts.ext}`;
    }

    function normalizeMappingPlaceholders(name, hasSessionValue) {
        let tokenCount = 0;
        let normalized = (name || '').replace(/\{\}/g, () => {
            tokenCount += 1;
            if (tokenCount === 1) return '{subject}';
            if (tokenCount === 2) return hasSessionValue ? '{session}' : '';
            return '{}';
        });

        if (!hasSessionValue) {
            normalized = normalized
                .replace(/_ses-(?=_|$)/g, '')
                .replace(/__+/g, '_')
                .replace(/(^_|_$)/g, '');
        }

        return normalized;
    }

    function sanitizeTaskLabel(value) {
        if (!value) return '';
        return value
            .trim()
            .toLowerCase()
            .replace(/\s+/g, '-')
            .replace(/[^a-z0-9-]/g, '');
    }

    function getValidatedTaskLabel() {
        return sanitizeTaskLabel(renamerTask && renamerTask.value ? renamerTask.value : '');
    }

    function syncTemplateWithTaskAndRecording(templateValue) {
        const task = getValidatedTaskLabel();
        const modality = renamerModality ? renamerModality.value : 'physio';
        const recording = (modality === 'physio' && renamerRecording && renamerRecording.value)
            ? renamerRecording.value
            : '';

        if (!templateValue) return templateValue;

        let updated = templateValue;
        if (task) {
            updated = updated.replace(/task-[^_\.]+/g, `task-${task}`);
        }

        if (modality === 'physio') {
            if (recording) {
                if (/_recording-[^_]+_physio/.test(updated)) {
                    updated = updated.replace(/_recording-[^_]+_physio/g, `_recording-${recording}_physio`);
                } else {
                    updated = updated.replace(/_physio(\.[^.]+(?:\.[^.]+)*)?$/i, `_recording-${recording}_physio$1`);
                }
            } else {
                updated = updated.replace(/_recording-[^_]+_physio/g, '_physio');
            }
        }

        return updated;
    }

    function foldForLooseMatch(value) {
        if (!value) return '';
        return value
            .normalize('NFD')
            .replace(/\p{M}/gu, '')
            .toLowerCase();
    }

    function findLiteralSpan(haystack, literal) {
        if (!haystack || !literal) return null;

        const directIndex = haystack.indexOf(literal);
        if (directIndex >= 0) {
            return {
                index: directIndex,
                value: literal,
                length: literal.length
            };
        }

        const literalNfc = literal.normalize('NFC');
        const literalNfd = literal.normalize('NFD');
        const nfcIndex = haystack.indexOf(literalNfc);
        if (nfcIndex >= 0) {
            return {
                index: nfcIndex,
                value: literalNfc,
                length: literalNfc.length
            };
        }
        const nfdIndex = haystack.indexOf(literalNfd);
        if (nfdIndex >= 0) {
            return {
                index: nfdIndex,
                value: literalNfd,
                length: literalNfd.length
            };
        }

        const foldedLiteral = foldForLooseMatch(literal);
        if (!foldedLiteral) return null;

        const maxExtraChars = 6;
        for (let start = 0; start < haystack.length; start += 1) {
            const maxEnd = Math.min(haystack.length, start + literal.length + maxExtraChars);
            for (let end = start + 1; end <= maxEnd; end += 1) {
                const candidate = haystack.slice(start, end);
                if (foldForLooseMatch(candidate) === foldedLiteral) {
                    return {
                        index: start,
                        value: candidate,
                        length: end - start
                    };
                }
            }
        }

        return null;
    }

    function spansOverlap(a, b) {
        if (!a || !b) return false;
        const aStart = a.index;
        const aEnd = a.index + a.length;
        const bStart = b.index;
        const bEnd = b.index + b.length;
        return aStart < bEnd && bStart < aEnd;
    }

    function findNonOverlappingLiteralSpan(haystack, literal, blockedSpan) {
        if (!haystack || !literal) return null;
        if (!blockedSpan) return findLiteralSpan(haystack, literal);

        const blockedStart = blockedSpan.index;
        const blockedEnd = blockedSpan.index + blockedSpan.length;

        const candidates = [];

        // Prefer exact direct matches and collect all of them.
        let from = 0;
        while (from <= haystack.length) {
            const idx = haystack.indexOf(literal, from);
            if (idx < 0) break;
            candidates.push({ index: idx, value: literal, length: literal.length });
            from = idx + 1;
        }

        // If no direct matches were found, fall back to the existing fuzzy matcher.
        if (candidates.length === 0) {
            const fuzzy = findLiteralSpan(haystack, literal);
            if (fuzzy && !spansOverlap(fuzzy, blockedSpan)) {
                return fuzzy;
            }
            return null;
        }

        // Prefer a candidate after the blocked span (common case like 001-t1 with subject=001, session=1).
        const after = candidates.find(c => c.index >= blockedEnd && !spansOverlap(c, blockedSpan));
        if (after) return after;

        // Otherwise return any non-overlapping candidate.
        const any = candidates.find(c => !spansOverlap(c, blockedSpan));
        if (any) return any;

        // As last resort keep old behavior.
        const fallback = candidates[0];
        if (fallback && !spansOverlap(fallback, blockedSpan)) {
            return fallback;
        }
        if (fallback && (fallback.index + fallback.length <= blockedStart || fallback.index >= blockedEnd)) {
            return fallback;
        }
        return null;
    }

    function buildAutoRenamerFilename(force = false) {
        if (!renamerNewExample) return;
        if (renamerTemplateManuallyEdited && !force) return;

        const modality = renamerModality ? renamerModality.value : 'physio';
        const task = getValidatedTaskLabel();
        const idSource = renamerIdSource();
        const sessionValue = sanitizeLiteral(renamerSessionValue && renamerSessionValue.value || '');
        const hasSession = idSource === 'folder' ? true : !!sessionValue;
        const recording = (modality === 'physio' && renamerRecording && renamerRecording.value)
            ? renamerRecording.value
            : '';

        const sourceExt = currentExampleFile && currentExampleFile.name
            ? (splitFilenameAndExt(currentExampleFile.name).ext || '')
            : '';

        if (renamerExtension) {
            renamerExtension.value = sourceExt || '(none)';
        }

        if (!task) {
            renamerNewExample.value = '';
            return;
        }

        const entities = ['sub-{subject}'];
        if (hasSession) entities.push('ses-{session}');
        entities.push(`task-${task}`);

        let suffix = modality;
        if (modality === 'physio' && recording) {
            suffix = `recording-${recording}_physio`;
        }

        let generatedName = `${entities.join('_')}_${suffix}`;
        if (sourceExt) generatedName += sourceExt;

        renamerNewExample.value = generatedName;
    }

    function pickExampleFile() {
        const entries = getRenamerEntries();
        if (entries.length === 0) return;
        const selected = entries[Math.floor(Math.random() * entries.length)];
        currentExampleFile = selected.file || {
            name: selected.name,
            webkitRelativePath: selected.sourcePath,
        };
        renamerTemplateManuallyEdited = false;
        updateOriginalExampleDisplay();
        if (renamerExampleContainer) renamerExampleContainer.classList.remove('d-none');
        if (renamerNewExample) {
            buildAutoRenamerFilename(true);
        }
        updateRenamerBtn();
        if (renamerPreview) renamerPreview.classList.add('d-none');
        inferPattern();
    }

    function filterRenamerTable(showOnlyUnmatched) {
        if (!renamerPreviewBody) return;
        const rows = renamerPreviewBody.querySelectorAll('tr');
        rows.forEach(row => {
            const isMatch = row.getAttribute('data-match') === 'true';
            if (showOnlyUnmatched) {
                row.classList.toggle('d-none', isMatch);
            } else {
                row.classList.remove('d-none');
            }
        });
        if (renamerFilterAll) renamerFilterAll.classList.toggle('active', !showOnlyUnmatched);
        if (renamerFilterUnmatched) renamerFilterUnmatched.classList.toggle('active', showOnlyUnmatched);
    }

    function appendRenamerLog(message, level = 'info') {
        if (!renamerLog) return;
        const levelColors = {
            info: '#9ca3af',
            success: '#22c55e',
            warning: '#f59e0b',
            error: '#ef4444',
            progress: '#60a5fa'
        };
        const line = document.createElement('div');
        line.style.color = levelColors[level] || levelColors.info;
        line.textContent = message;
        renamerLog.appendChild(line);
        renamerLog.scrollTop = renamerLog.scrollHeight;
    }

    function updateRenamerProgress(current, total, label) {
        if (!renamerProgress || !renamerProgressBar) return;
        const pct = total > 0 ? Math.round((current / total) * 100) : 0;
        renamerProgress.classList.remove('d-none');
        renamerProgressBar.style.width = `${pct}%`;
        renamerProgressBar.textContent = label || `${current}/${total}`;
    }

    function buildRenamerFormData(opts = {}) {
        const saveToProject = opts.saveToProject === true;
        const isDryRun = opts.isDryRun === true;
        const skipZip = opts.skipZip === true;
        const files = opts.files || [];
        const entries = opts.entries || [];
        const serverEntries = entries.filter((entry) => entry && entry.isServer);
        const folderPath = String(opts.folderPath || '').trim();
        const currentProjectPath = String(opts.projectPath || getCurrentProjectPath()).trim();
        const formData = new FormData();
        formData.append('pattern', renamerPattern.value);
        formData.append('replacement', renamerReplacement.value);
        formData.append('dry_run', isDryRun);
        if (renamerOrganize) formData.append('organize', renamerOrganize.checked);
        formData.append('save_to_project', saveToProject);
        formData.append('skip_zip', skipZip);
        if (renamerModality) formData.append('modality', renamerModality.value);
        formData.append('dest_root', renamerTargetRoot());
        formData.append('flat_structure', renamerOrganize ? !renamerOrganize.checked : false);
        formData.append('id_source', renamerIdSource());
        formData.append('folder_subject_level', getFolderLevelValue(renamerFolderSubjectLevel, 2));
        formData.append('folder_session_level', getFolderLevelValue(renamerFolderSessionLevel, 1));
        formData.append('folder_subject_value', sanitizeLiteral(renamerSubjectValue && renamerSubjectValue.value || ''));
        formData.append('folder_session_value', sanitizeLiteral(renamerSessionValue && renamerSessionValue.value || ''));
        formData.append('folder_example_path', currentExampleFile ? getClientRelativePath(currentExampleFile) : '');
        if (folderPath) {
            formData.append('folder_path', folderPath);
        }
        if (saveToProject && currentProjectPath) {
            formData.append('project_path', currentProjectPath);
        }

        if (isDryRun) {
            entries.forEach(entry => {
                formData.append('filenames', entry.name);
                formData.append('source_paths', entry.sourcePath);
            });
        } else {
            files.forEach(f => {
                formData.append('files', f);
                formData.append('source_paths', getClientRelativePath(f));
            });
            if (!folderPath) {
                serverEntries.forEach((entry) => {
                    formData.append('server_file_paths', entry.sourcePath);
                });
            }
        }
        return formData;
    }

    async function runRenamerSequentialCopy(files) {
        const entries = getRenamerEntries();
        if (files.length === 0 && renamerServerFolderPath) {
            await runRenamer(false, { saveToProject: true, skipDownload: true, silent: false });
            return;
        }

        const copyProjectPath = getCurrentProjectPath();
        if (!copyProjectPath) {
            if (renamerError) {
                renamerError.textContent = 'No active project selected. Open a project before copying renamed files.';
                renamerError.classList.remove('d-none');
            }
            return;
        }
        if (renamerError) renamerError.classList.add('d-none');
        if (renamerInfo) renamerInfo.classList.add('d-none');
        if (renamerLogContainer) renamerLogContainer.classList.remove('d-none');
        if (renamerLog) renamerLog.textContent = '';
        appendRenamerLog(`Starting Copy to Project for ${entries.length} files...`, 'progress');

        let successCount = 0;
        let errorCount = 0;
        const warningMessages = [];
        const savedTargets = [];

        for (let idx = 0; idx < files.length; idx += 1) {
            const file = files[idx];
            updateRenamerProgress(idx + 1, files.length, `Copying ${idx + 1}/${files.length}`);
            appendRenamerLog(`→ [${idx + 1}/${files.length}] ${getClientRelativePath(file)}`, 'info');

            const formData = buildRenamerFormData({
                saveToProject: true,
                isDryRun: false,
                skipZip: true,
                projectPath: copyProjectPath,
                files: [file]
            });

            try {
                const response = await fetchWithApiFallback('/api/physio-rename', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const data = await response.json().catch(() => null);
                    const msg = (data && data.error) ? data.error : `HTTP ${response.status}`;
                    throw new Error(msg);
                }

                const result = await response.json();
                const results = Array.isArray(result.results) ? result.results : [];
                const currentSuccess = results.filter(r => r && r.success).length;
                const currentErrors = results.length - currentSuccess;

                successCount += currentSuccess;
                errorCount += Math.max(0, currentErrors);

                if (currentSuccess > 0) {
                    appendRenamerLog(`✓ Copied: ${file.name}`, 'success');
                }
                if (currentErrors > 0) {
                    appendRenamerLog(`✗ Failed: ${file.name}`, 'error');
                }

                if (result.project_saved) {
                    const saveSummary = getProjectSaveSummary(result);
                    savedTargets.push(`${saveSummary.target}${saveSummary.countNote}`);
                    appendRenamerLog(`📁 Saved to project: ${saveSummary.target}${saveSummary.countNote}`, 'success');
                }

                const warnings = Array.isArray(result.warnings) ? result.warnings : [];
                warnings.forEach(w => {
                    warningMessages.push(w);
                    appendRenamerLog(`⚠ ${w}`, 'warning');
                });
            } catch (err) {
                errorCount += 1;
                appendRenamerLog(`✗ Error for ${file.name}: ${err.message}`, 'error');
            }
        }

        updateRenamerProgress(files.length, files.length, `Done (${successCount} ok, ${errorCount} failed)`);
        appendRenamerLog('Copy to Project finished.', 'progress');

        if (renamerInfo) {
            const uniqueTargets = Array.from(new Set(savedTargets));
            const savedText = uniqueTargets.length > 0
                ? ` First saved path: ${uniqueTargets[0]}.`
                : '';
            renamerInfo.textContent = `Copy finished: ${successCount} files copied, ${errorCount} failed.${savedText}`;
            renamerInfo.classList.remove('d-none');
        }
        if (warningMessages.length > 0 && renamerError) {
            renamerError.innerHTML = warningMessages.map(w => `<div><i class="fas fa-exclamation-triangle me-2"></i>${escapeHtml(w)}</div>`).join('');
            renamerError.classList.remove('d-none');
        }
    }

    function inferPattern() {
        if (!currentExampleFile || !renamerNewExample) return;
        const task = getValidatedTaskLabel();
        if (!task) {
            if (renamerPattern) renamerPattern.value = '';
            if (renamerReplacement) renamerReplacement.value = '';
            if (renamerPreview) renamerPreview.classList.add('d-none');
            if (renamerError) {
                renamerError.textContent = 'Task is required. Please enter a task label (e.g. rest).';
                renamerError.classList.remove('d-none');
            }
            updateRenamerBtn();
            return;
        }
        if (renamerError) renamerError.classList.add('d-none');
        const oldName = currentExampleFile.name;
        const rawInputName = renamerNewExample.value.trim();
        if (!rawInputName) {
            if (renamerPreview) renamerPreview.classList.add('d-none');
            return;
        }

        const rawInputParts = splitFilenameAndExt(rawInputName);
        const userProvidedExt = !!rawInputParts.ext;
        let newName = ensureExampleExtension(rawInputName);

        if (renamerUseMapping && renamerUseMapping.checked) {
            const idSource = renamerIdSource();
            if (renamerError) renamerError.classList.add('d-none');
            const subjectValue = sanitizeLiteral(renamerSubjectValue && renamerSubjectValue.value || '');
            const sessionValue = sanitizeLiteral(renamerSessionValue && renamerSessionValue.value || '');

            const allowSessionPlaceholder = idSource === 'folder' ? true : !!sessionValue;
            newName = normalizeMappingPlaceholders(newName, allowSessionPlaceholder);
            newName = ensureExampleExtension(newName);
            if (renamerNewExample.value !== newName) {
                renamerNewExample.value = newName;
            }

            if (idSource === 'folder') {
                if (!subjectValue) {
                    if (renamerError) {
                        renamerError.textContent = 'Subject string is required in folder mode. Enter the subject part from the example path.';
                        renamerError.classList.remove('d-none');
                    }
                    if (renamerMappingPreview) {
                        renamerMappingPreview.textContent = 'Enter the exact subject string from the example path (for example: 135).';
                        renamerMappingPreview.classList.add('text-danger');
                        renamerMappingPreview.classList.remove('text-muted');
                    }
                    return;
                }

                if (!newName.includes('{subject}')) {
                    if (renamerError) {
                        renamerError.textContent = 'Use {subject} in the New PRISM Filename when folder mode is enabled.';
                        renamerError.classList.remove('d-none');
                    }
                    if (renamerMappingPreview) {
                        renamerMappingPreview.textContent = 'Add {subject} to the New PRISM Filename (folder mode).';
                        renamerMappingPreview.classList.add('text-danger');
                        renamerMappingPreview.classList.remove('text-muted');
                    }
                    return;
                }

                if (renamerPattern) renamerPattern.value = '^(.*)$';
                if (renamerReplacement) renamerReplacement.value = newName;
                if (renamerMappingPreview) {
                    const oldPath = getClientRelativePath(currentExampleFile);
                    const subjectLevel = getFolderLevelValue(renamerFolderSubjectLevel, 2);
                    const sessionLevel = getFolderLevelValue(renamerFolderSessionLevel, 1);
                    const subjectValue = sanitizeLiteral(renamerSubjectValue && renamerSubjectValue.value || '');
                    const sessionValue = sanitizeLiteral(renamerSessionValue && renamerSessionValue.value || '');
                    const suffix = sessionValue
                        ? `, subject example '${subjectValue}', session example '${sessionValue}'`
                        : `, subject example '${subjectValue}', session omitted`;
                    renamerMappingPreview.textContent = `Folder mode preview (subject level ${subjectLevel}, session level ${sessionLevel}${suffix}): ${oldPath} → ${newName}`;
                    renamerMappingPreview.classList.remove('text-danger');
                    renamerMappingPreview.classList.add('text-muted');
                }
                runRenamer(true, { silent: true });
                return;
            }

            if (!subjectValue) {
                if (renamerError) {
                    renamerError.textContent = 'Subject string is required when subject/session mapping is enabled.';
                    renamerError.classList.remove('d-none');
                }
                if (renamerMappingPreview) {
                    renamerMappingPreview.textContent = 'Enter the subject string from the example filename.';
                    renamerMappingPreview.classList.add('text-danger');
                    renamerMappingPreview.classList.remove('text-muted');
                }
                return;
            }

            if (!newName.includes('{subject}')) {
                if (renamerError) {
                    renamerError.textContent = 'Use {subject} in the New PRISM Filename when subject/session mapping is enabled.';
                    renamerError.classList.remove('d-none');
                }
                if (renamerMappingPreview) {
                    renamerMappingPreview.textContent = 'Add {subject} to the New PRISM Filename to insert the subject string.';
                    renamerMappingPreview.classList.add('text-danger');
                    renamerMappingPreview.classList.remove('text-muted');
                }
                return;
            }

            if (!sessionValue && newName.includes('{session}')) {
                if (renamerError) {
                    renamerError.textContent = 'Remove {session} from the New PRISM Filename or provide a session string.';
                    renamerError.classList.remove('d-none');
                }
                if (renamerMappingPreview) {
                    renamerMappingPreview.textContent = 'Either enter a session string or remove {session} from the new filename.';
                    renamerMappingPreview.classList.add('text-danger');
                    renamerMappingPreview.classList.remove('text-muted');
                }
                return;
            }

            const escapeRegex = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const oldParts = splitFilenameAndExt(oldName);
            const oldStem = oldParts.base;
            const subjectSpan = findLiteralSpan(oldStem, subjectValue);
            const sessionSpan = sessionValue
                ? findNonOverlappingLiteralSpan(oldStem, sessionValue, subjectSpan)
                : null;
            const subjectIdx = subjectSpan ? subjectSpan.index : -1;
            const sessionIdx = sessionSpan ? sessionSpan.index : -1;

            if (subjectIdx < 0) {
                // Try to be helpful - maybe there's a copy-paste issue
                const debugMsg = `"${subjectValue}" (${[...subjectValue].map(c => c.charCodeAt(0)).join(',')}) not in "${oldName}"`;
                if (renamerError) {
                    renamerError.textContent = `Subject string not found. Try manually selecting it from the filename, or clear and retype it.`;
                    renamerError.classList.remove('d-none');
                    renamerError.title = debugMsg; // Hover shows debug info
                }
                if (renamerMappingPreview) {
                    renamerMappingPreview.textContent = `Subject string not found in the example filename.`;
                    renamerMappingPreview.classList.add('text-danger');
                    renamerMappingPreview.classList.remove('text-muted');
                    renamerMappingPreview.title = debugMsg;
                }
                return;
            }

            if (sessionValue && subjectSpan && sessionSpan && sessionIdx === subjectIdx) {
                if (renamerError) {
                    renamerError.textContent = 'Subject and session strings overlap in the example filename.';
                    renamerError.classList.remove('d-none');
                }
                if (renamerMappingPreview) {
                    renamerMappingPreview.textContent = 'Subject and session strings overlap in the example filename.';
                    renamerMappingPreview.classList.add('text-danger');
                    renamerMappingPreview.classList.remove('text-muted');
                }
                return;
            }

            // Build markers with positions
            const markers = [];
            if (sessionValue && sessionSpan) markers.push({ key: 'session', value: sessionSpan.value, index: sessionIdx, length: sessionSpan.length });
            if (subjectSpan) markers.push({ key: 'subject', value: subjectSpan.value, index: subjectIdx, length: subjectSpan.length });
            markers.sort((a, b) => a.index - b.index);

            // Create pattern by replacing each marker with capture groups
            // Use lookahead to constrain non-greedy matches when followed by another known marker
            let pattern = '^';
            let cursor = 0;
            markers.forEach((marker, idx) => {
                // Add literal text before this marker
                pattern += escapeRegex(oldStem.slice(cursor, marker.index));
                
                // For the capture group: if there's another marker after this one,
                // use boundary text (if present) or fixed-width capture when adjacent.
                if (idx < markers.length - 1) {
                    const nextMarker = markers[idx + 1];
                    const boundaryLiteral = oldStem.slice(marker.index + marker.length, nextMarker.index);
                    if (boundaryLiteral) {
                        const boundaryEscaped = escapeRegex(boundaryLiteral);
                        pattern += `(.+?)(?=${boundaryEscaped})`;
                    } else {
                        // Adjacent markers with no separator: preserve observed width from example.
                        pattern += `(.{${marker.length}})`;
                    }
                } else {
                    // Last marker - non-greedy so extension capture can work.
                    pattern += '(.+?)';
                }
                cursor = marker.index + marker.length;
            });
            // Add literal text after last marker (before extension)
            const remaining = oldStem.slice(cursor);
            if (remaining) {
                pattern += escapeRegex(remaining);
            }
            pattern += '(\\.[^.]+(?:\\.[^.]+)*)?$';

            // Map marker keys to their capture group indices (1-based)
            const subjectGroupIndex = markers.findIndex(m => m.key === 'subject') + 1;
            const sessionMarkerIndex = markers.findIndex(m => m.key === 'session');
            const hasSessionCapture = sessionMarkerIndex >= 0;
            const sessionGroupIndex = hasSessionCapture ? (sessionMarkerIndex + 1) : 0;
            const extensionGroupIndex = markers.length + 1;

            let replacement = newName.replace(/\{subject\}/g, `\\${subjectGroupIndex}`);
            if (sessionValue) {
                if (hasSessionCapture) {
                    replacement = replacement.replace(/\{session\}/g, `\\${sessionGroupIndex}`);
                } else {
                    replacement = replacement.replace(/\{session\}/g, sessionValue);
                }
            }

            if (!userProvidedExt) {
                const replacementParts = splitFilenameAndExt(replacement);
                replacement = `${replacementParts.base}\\${extensionGroupIndex}`;
            }

            if (renamerPattern) renamerPattern.value = pattern;
            if (renamerReplacement) renamerReplacement.value = replacement;
            if (renamerMappingPreview) {
                try {
                    const re = new RegExp(pattern);
                    const jsReplacement = replacement.replace(/\\(\d+)/g, (_, groupIdx) => `$${groupIdx}`);
                    const previewName = oldName.replace(re, jsReplacement);
                    const sessionNote = sessionValue && !hasSessionCapture
                        ? ` (session '${sessionValue}' will be added)`
                        : '';
                    renamerMappingPreview.textContent = `Preview: ${oldName} → ${previewName}${sessionNote}`;
                    renamerMappingPreview.classList.remove('text-danger');
                    renamerMappingPreview.classList.add('text-muted');
                } catch {
                    renamerMappingPreview.textContent = 'Mapping pattern could not be created for this example.';
                    renamerMappingPreview.classList.add('text-danger');
                    renamerMappingPreview.classList.remove('text-muted');
                }
            }
            runRenamer(true, { silent: true });
            return;
        }

        if (renamerNewExample.value !== newName) {
            renamerNewExample.value = newName;
        }

        const digitRegex = /\d+/g;
        const matches = [];
        let match;
        while ((match = digitRegex.exec(oldName)) !== null) {
            matches.push({ value: match[0], index: match.index });
        }

        let finalPattern = '';
        let lastIndex = 0;
        matches.forEach(m => {
            finalPattern += oldName.substring(lastIndex, m.index).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            finalPattern += '(\\d+)';
            lastIndex = m.index + m.value.length;
        });
        finalPattern += oldName.substring(lastIndex).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

        let replacement = newName;
        if (matches.length > 0) {
            const uniqueValues = [...new Set(matches.map(m => m.value))].sort((a, b) => b.length - a.length);
            const valueToGroup = {};
            matches.forEach((m, i) => {
                if (!(m.value in valueToGroup)) {
                    valueToGroup[m.value] = i + 1;
                }
            });
            const combinedRegex = new RegExp(uniqueValues.map(v => v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'g');
            replacement = replacement.replace(combinedRegex, matched => `\\${valueToGroup[matched]}`);
        }

        if (renamerPattern) renamerPattern.value = finalPattern;
        if (renamerReplacement) renamerReplacement.value = replacement;
        runRenamer(true, { silent: true });
    }

    async function runRenamer(isDryRun, opts = {}) {
        const saveToProject = opts.saveToProject === true;
        const skipDownload = opts.skipDownload === true;
        const silent = opts.silent === true;
        const currentProjectPath = getCurrentProjectPath();
        if (!renamerPattern || !renamerReplacement || !renamerPattern.value) return;
        if (!isDryRun && saveToProject && !currentProjectPath) {
            if (renamerError) {
                renamerError.textContent = 'No active project selected. Open a project before copying renamed files.';
                renamerError.classList.remove('d-none');
            }
            return;
        }

        if (renamerError) renamerError.classList.add('d-none');
        if (renamerInfo) renamerInfo.classList.add('d-none');
        if (renamerProgress) renamerProgress.classList.add('d-none');

        if (!silent) {
            if (renamerLogContainer) renamerLogContainer.classList.remove('d-none');
            if (renamerLog) renamerLog.textContent = '';
            const modeLabel = isDryRun ? 'preview renames' : (saveToProject ? 'copy to project' : 'rename and download');
            appendRenamerLog(`Starting ${modeLabel}...`, 'progress');
        }

        const entries = getRenamerEntries();
        const files = entries.filter((entry) => entry.file).map((entry) => entry.file);
        const hasServerEntries = entries.some((entry) => entry.isServer);
        if (entries.length === 0 && !isDryRun) return;

        if (!silent) {
            appendRenamerLog(`Files selected: ${entries.length}`, 'info');
        }

        if (!isDryRun && saveToProject && skipDownload && !hasServerEntries) {
            await runRenamerSequentialCopy(files);
            updateRenamerBtn();
            return;
        }

        const formData = buildRenamerFormData({
            saveToProject,
            isDryRun,
            skipZip: skipDownload,
            projectPath: currentProjectPath,
            files,
            entries,
            folderPath: renamerServerFolderPath
        });

        try {
            const response = await fetchWithApiFallback('/api/physio-rename', {
                method: 'POST',
                body: formData
            });
            if (!response.ok) {
                const data = await response.json().catch(() => null);
                if (data && data.error) {
                    throw new Error(data.error);
                }
                if (response.status === 413) {
                    throw new Error('Renaming failed: upload too large for a single request. Use Copy to Project (no ZIP) or fewer files per batch.');
                }
                throw new Error(`Renaming failed (HTTP ${response.status})`);
            }
            const result = await response.json();

            if (isDryRun) {
                if (!renamerPreviewBody) return;
                renamerPreviewBody.innerHTML = '';
                let matchCount = 0;
                const selectedModality = renamerModality ? renamerModality.value : 'physio';

                result.results.forEach(res => {
                    const isMatch = res.old !== res.new;
                    let isValidBids = true;
                    let bidsError = '';

                    if (isMatch) {
                        if (!res.new.startsWith('sub-')) {
                            isValidBids = false;
                            bidsError = 'Missing sub- prefix';
                        } else if (!res.new.includes('_')) {
                            isValidBids = false;
                            bidsError = 'Missing entities/suffix';
                        } else {
                            const lastDot = res.new.lastIndexOf('.');
                            const stem = lastDot > -1 ? res.new.slice(0, lastDot) : res.new;
                            const suffix = stem.split('_').pop();
                            const expectedSuffixes = {
                                physio: 'physio',
                                biometrics: 'biometrics',
                                events: 'events',
                                survey: 'survey'
                            };
                            if (expectedSuffixes[selectedModality] && suffix !== expectedSuffixes[selectedModality]) {
                                isValidBids = false;
                                bidsError = `Expected _${expectedSuffixes[selectedModality]} suffix`;
                            }
                        }
                    }

                    if (isMatch && isValidBids) {
                        matchCount++;
                    }

                    const tr = document.createElement('tr');
                    tr.setAttribute('data-match', isMatch && isValidBids);

                    const displayPath = (res.path && res.path !== res.new)
                        ? `<span class="text-muted">${escapeHtml(res.path.substring(0, res.path.lastIndexOf('/') + 1))}</span>${escapeHtml(res.new)}`
                        : escapeHtml(res.new);

                    tr.innerHTML = `
                        <td class="font-monospace small">${escapeHtml(res.old)}</td>
                        <td><i class="fas fa-arrow-right text-muted"></i></td>
                        <td class="font-monospace small ${isMatch ? (isValidBids ? 'text-success' : 'text-danger') : 'text-muted'}">
                            ${displayPath}
                            ${!isValidBids && isMatch ? `<br><small class="text-danger"><i class="fas fa-times-circle me-1"></i>${escapeHtml(bidsError)}</small>` : ''}
                        </td>
                        <td class="text-center">
                            ${(isMatch && isValidBids) ? '<i class="fas fa-check-circle text-success"></i>' : (!isMatch ? '<i class="fas fa-exclamation-triangle text-warning" title="No match found - file will not be renamed"></i>' : '<i class="fas fa-times-circle text-danger" title="Invalid BIDS/PRISM format"></i>')}
                        </td>
                    `;
                    renamerPreviewBody.appendChild(tr);
                });
                if (renamerPreview) renamerPreview.classList.remove('d-none');

                if (result.results && matchCount < result.results.length && result.results.length > 0 && renamerError) {
                    const unmatchedCount = result.results.length - matchCount;
                    renamerError.innerHTML = `
                        <div class="d-flex align-items-center">
                            <i class="fas fa-exclamation-triangle me-3 fa-2x"></i>
                            <div>
                                <strong>Warning: ${unmatchedCount} files are either unmatched or invalid.</strong><br>
                                Only files with a green checkmark will be renamed correctly. Check the "New PRISM Filename" column for errors.
                                <div class="mt-2">
                                    <button type="button" class="btn btn-sm btn-outline-danger" id="renamerShowIssues">
                                        <i class="fas fa-search me-1"></i>Show Incompatible Files
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                    renamerError.classList.remove('d-none');
                    const showIssuesBtn = document.getElementById('renamerShowIssues');
                    if (showIssuesBtn && renamerFilterUnmatched) {
                        showIssuesBtn.addEventListener('click', () => renamerFilterUnmatched.click());
                    }
                }
                filterRenamerTable(false);
                if (!silent) {
                    const totalCount = Array.isArray(result.results) ? result.results.length : 0;
                    appendRenamerLog(`Preview complete: ${matchCount}/${totalCount} files match BIDS/PRISM naming.`, matchCount === totalCount ? 'success' : 'warning');
                }
            } else {
                const warnings = result.warnings || [];
                const saved = result.project_saved === true;

                if (!skipDownload && result.zip) {
                    downloadBase64Zip(result.zip, 'renamed_files.zip');
                }

                if (renamerInfo) {
                    const warnText = warnings.length ? ` Warnings: ${warnings.join(' ')}` : '';
                    const saveSummary = saved ? getProjectSaveSummary(result) : null;
                    const savedText = saveSummary ? ` Saved to project: ${saveSummary.target}${saveSummary.countNote}.` : '';
                    const zipText = skipDownload ? '' : ' ZIP download started.';
                    renamerInfo.textContent = `Successfully renamed ${result.results.length} files.${savedText}${zipText}${warnText}`.trim();
                    renamerInfo.classList.remove('d-none');
                }

                if (warnings.length && renamerError) {
                    renamerError.innerHTML = warnings.map(w => `<div><i class="fas fa-exclamation-triangle me-2"></i>${escapeHtml(w)}</div>`).join('');
                    renamerError.classList.remove('d-none');
                }

                if (!silent) {
                    if (saved) {
                        const saveSummary = getProjectSaveSummary(result);
                        appendRenamerLog(`Saved to project: ${saveSummary.target}${saveSummary.countNote}`, 'success');
                    }
                    appendRenamerLog(`Rename complete: ${result.results.length} files processed.${skipDownload ? '' : ' ZIP generated.'}`, 'success');
                    warnings.forEach((warningMsg) => appendRenamerLog(`⚠ ${warningMsg}`, 'warning'));
                }
            }
        } catch (err) {
            if (renamerError) {
                renamerError.textContent = err.message;
                renamerError.classList.remove('d-none');
            }
            if (!silent) {
                appendRenamerLog(`✗ ${err.message}`, 'error');
            }
        }
    }

    if (renamerLogClearBtn) {
        renamerLogClearBtn.addEventListener('click', () => {
            if (renamerLog) renamerLog.textContent = '';
        });
    }

    // Event wiring
    if (renamerFiles) {
        renamerFiles.addEventListener('change', () => {
            renamerServerFolderPath = '';
            renamerServerEntries = [];
            updateRenamerServerHints();
            pickExampleFile();
            updateRenamerBtn();
        });
    }

    if (renamerFiles && renamerFiles.parentElement) {
        let browseServerRenamerFolderBtn = renamerBrowseServerFolderBtn || document.getElementById('renamerBrowseServerFolderBtn');
        if (!browseServerRenamerFolderBtn) {
            browseServerRenamerFolderBtn = document.createElement('button');
            browseServerRenamerFolderBtn.type = 'button';
            browseServerRenamerFolderBtn.className = 'btn btn-outline-secondary btn-sm d-none';
            browseServerRenamerFolderBtn.id = 'renamerBrowseServerFolderBtn';
            browseServerRenamerFolderBtn.innerHTML = '<i class="fas fa-server me-1"></i>Server Folder';
            renamerFiles.parentElement.appendChild(browseServerRenamerFolderBtn);
        }

        let browseServerRenamerFileBtn = renamerBrowseServerFileBtn || document.getElementById('renamerBrowseServerFileBtn');
        if (!browseServerRenamerFileBtn) {
            browseServerRenamerFileBtn = document.createElement('button');
            browseServerRenamerFileBtn.type = 'button';
            browseServerRenamerFileBtn.className = 'btn btn-outline-secondary btn-sm d-none';
            browseServerRenamerFileBtn.id = 'renamerBrowseServerFileBtn';
            browseServerRenamerFileBtn.innerHTML = '<i class="fas fa-server me-1"></i>Server File';
            renamerFiles.parentElement.appendChild(browseServerRenamerFileBtn);
        }

        let clearServerRenamerSelectionBtn = renamerClearServerSelectionBtn || document.getElementById('renamerClearServerSelectionBtn');
        if (!clearServerRenamerSelectionBtn) {
            clearServerRenamerSelectionBtn = document.createElement('button');
            clearServerRenamerSelectionBtn.type = 'button';
            clearServerRenamerSelectionBtn.className = 'btn btn-outline-danger btn-sm d-none';
            clearServerRenamerSelectionBtn.id = 'renamerClearServerSelectionBtn';
            clearServerRenamerSelectionBtn.innerHTML = '<i class="fas fa-xmark me-1"></i>Clear Server Selection';
            renamerFiles.parentElement.appendChild(clearServerRenamerSelectionBtn);
        }

        if (!(renamerServerFolderHint || document.getElementById('renamerServerFolderHint'))) {
            const createdFolderHint = document.createElement('div');
            createdFolderHint.className = 'form-text d-none';
            createdFolderHint.id = 'renamerServerFolderHint';
            renamerFiles.parentElement.appendChild(createdFolderHint);
        }

        if (!(renamerServerFileHint || document.getElementById('renamerServerFileHint'))) {
            const createdFileHint = document.createElement('div');
            createdFileHint.className = 'form-text d-none';
            createdFileHint.id = 'renamerServerFileHint';
            renamerFiles.parentElement.appendChild(createdFileHint);
        }

        const loadServerFolderEntries = async (folderPath) => {
            const response = await fetchWithApiFallback(`/api/fs/list-files?path=${encodeURIComponent(folderPath)}&recursive=1`);
            const payload = await response.json();
            if (!response.ok || payload.error) {
                throw new Error(payload.error || 'Could not list files in folder');
            }
            renamerServerEntries = Array.isArray(payload.files) ? payload.files : [];
        };

        browseServerRenamerFolderBtn.addEventListener('click', async () => {
            if (!(window.PrismFileSystemMode && typeof window.PrismFileSystemMode.pickFolder === 'function')) {
                return;
            }
            try {
                const picked = await window.PrismFileSystemMode.pickFolder({
                    title: 'Select Folder to Rename (Server)',
                    confirmLabel: 'Use This Folder',
                    startPath: renamerServerFolderPath || ''
                });
                if (!picked) return;

                await loadServerFolderEntries(picked);
                renamerServerFolderPath = picked;
                if (renamerFiles) {
                    renamerFiles.value = '';
                }
                updateRenamerServerHints();
                pickExampleFile();
                updateRenamerBtn();
            } catch (error) {
                if (renamerError) {
                    renamerError.textContent = error.message || 'Failed to browse server folder.';
                    renamerError.classList.remove('d-none');
                }
            }
        });

        browseServerRenamerFileBtn.addEventListener('click', async () => {
            if (!(window.PrismFileSystemMode && typeof window.PrismFileSystemMode.pickFile === 'function')) {
                return;
            }
            try {
                const startPath = renamerServerEntries.length > 0
                    ? getParentDirectory(renamerServerEntries[renamerServerEntries.length - 1].path || '')
                    : '';
                const picked = await window.PrismFileSystemMode.pickFile({
                    title: 'Select File to Rename (Server)',
                    confirmLabel: 'Add This File',
                    startPath,
                });
                if (!picked) return;

                renamerServerFolderPath = '';
                if (renamerFiles) {
                    renamerFiles.value = '';
                }

                const fileName = picked.split(/[\\/]/).pop() || picked;
                const exists = renamerServerEntries.some((entry) => String(entry.path || '') === picked);
                if (!exists) {
                    renamerServerEntries.push({
                        name: fileName,
                        relative_path: picked,
                        path: picked,
                        size: 0,
                    });
                }

                updateRenamerServerHints();
                pickExampleFile();
                updateRenamerBtn();
            } catch (error) {
                if (renamerError) {
                    renamerError.textContent = error.message || 'Failed to browse server file.';
                    renamerError.classList.remove('d-none');
                }
            }
        });

        clearServerRenamerSelectionBtn.addEventListener('click', () => {
            renamerServerFolderPath = '';
            renamerServerEntries = [];
            currentExampleFile = null;
            updateRenamerServerHints();
            if (renamerExampleContainer) {
                renamerExampleContainer.classList.add('d-none');
            }
            if (renamerPreview) {
                renamerPreview.classList.add('d-none');
            }
            updateRenamerBtn();
        });

        if (window.PrismFileSystemMode && typeof window.PrismFileSystemMode.init === 'function') {
            window.PrismFileSystemMode.init().then(() => {
                applyRemotePickerUiState();
            }).catch(() => {
                // Keep host picker as fallback.
            });
        }

        window.addEventListener('prism-library-settings-changed', () => {
            applyRemotePickerUiState();
        });
    }

    if (renamerResetBtn) {
        renamerResetBtn.addEventListener('click', pickExampleFile);
    }

    if (renamerNewExample) {
        renamerNewExample.addEventListener('input', () => {
            renamerTemplateManuallyEdited = true;
            inferPattern();
            updateRenamerBtn();
        });
    }

    // renamerUseMapping is permanently enabled (checkbox is checked+disabled in template)
    // so change events never fire — no listener needed here

    if (renamerSubjectValue) {
        renamerSubjectValue.addEventListener('input', () => {
            buildAutoRenamerFilename();
            inferPattern();
        });
    }

    if (renamerSessionValue) {
        renamerSessionValue.addEventListener('input', () => {
            buildAutoRenamerFilename();
            inferPattern();
        });
    }

    if (renamerTask) {
        renamerTask.addEventListener('input', () => {
            if (renamerTemplateManuallyEdited && renamerNewExample) {
                renamerNewExample.value = syncTemplateWithTaskAndRecording(renamerNewExample.value);
            } else {
                buildAutoRenamerFilename();
            }
            inferPattern();
            updateRenamerBtn();
        });
    }

    if (renamerModality) {
        renamerModality.addEventListener('change', () => {
            updateRecordingVisibility();
            buildAutoRenamerFilename();
            inferPattern();
        });
    }

    if (renamerRecording) {
        renamerRecording.addEventListener('change', () => {
            if (renamerTemplateManuallyEdited && renamerNewExample) {
                renamerNewExample.value = syncTemplateWithTaskAndRecording(renamerNewExample.value);
            } else {
                buildAutoRenamerFilename();
            }
            inferPattern();
        });
    }

    if (renamerOrganize) {
        renamerOrganize.addEventListener('change', () => {
            updateRenamerStructureHint();
            updateRenamerBtn();
            runRenamer(true, { silent: true });
        });
    }

    if (renamerTargetPrism) {
        renamerTargetPrism.addEventListener('change', () => {
            updateRenamerStructureHint();
            updateRenamerBtn();
        });
    }
    if (renamerTargetRaw) {
        renamerTargetRaw.addEventListener('change', () => {
            updateRenamerStructureHint();
            updateRenamerBtn();
        });
    }
    if (renamerTargetSource) {
        renamerTargetSource.addEventListener('change', () => {
            updateRenamerStructureHint();
            updateRenamerBtn();
        });
    }
    if (renamerIdFromFilename) {
        renamerIdFromFilename.addEventListener('change', () => {
            updateOriginalExampleDisplay();
            updateMappingVisibility();
            buildAutoRenamerFilename();
            inferPattern();
        });
    }
    if (renamerIdFromFolder) {
        renamerIdFromFolder.addEventListener('change', () => {
            updateOriginalExampleDisplay();
            updateMappingVisibility();
            buildAutoRenamerFilename();
            inferPattern();
        });
    }
    if (renamerFolderSubjectLevel) {
        renamerFolderSubjectLevel.addEventListener('input', () => {
            updateMappingVisibility();
            inferPattern();
        });
    }
    if (renamerFolderSessionLevel) {
        renamerFolderSessionLevel.addEventListener('input', () => {
            updateMappingVisibility();
            inferPattern();
        });
    }

    if (renamerFilterAll) {
        renamerFilterAll.addEventListener('click', () => filterRenamerTable(false));
    }

    if (renamerFilterUnmatched) {
        renamerFilterUnmatched.addEventListener('click', () => filterRenamerTable(true));
    }

    if (renamerDryRunBtn) {
        renamerDryRunBtn.addEventListener('click', () => runRenamer(true));
    }

    if (renamerDownloadBtn) {
        renamerDownloadBtn.addEventListener('click', () => runRenamer(false));
    }

    if (renamerCopyBtn) {
        renamerCopyBtn.addEventListener('click', () => runRenamer(false, { saveToProject: true, skipDownload: true }));
    }

    window.addEventListener('prism-project-changed', () => {
        setWideLongIdleState();
        updateOrganizeBtn();
        updateRenamerBtn();
        loadRepoSubjectExamples();
    });

    // Initial state
    updateRecordingVisibility();
    updateMappingVisibility();
    buildAutoRenamerFilename();
    updateRenamerBtn();
    updateRenamerStructureHint();
    applyRemotePickerUiState();
    loadRepoSubjectExamples();
});
