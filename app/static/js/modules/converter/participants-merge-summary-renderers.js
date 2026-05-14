import { escapeHtml } from '../../shared/dom.js';

function normalizeNonEmptyStrings(values) {
    return Array.isArray(values)
        ? values.map((value) => String(value || '').trim()).filter(Boolean)
        : [];
}

function buildSessionSplitGeneratedPreview(columnName, availableSessions, generatedColumns) {
    if (generatedColumns.length > 0) {
        return generatedColumns.join(', ');
    }

    if (availableSessions.length > 0) {
        return availableSessions.map((sessionValue) => `${columnName}@ses-${sessionValue}`).join(', ');
    }

    return 'session-specific columns';
}

export function buildParticipantsMergeConflictListHtml(conflicts, { maxVisible = 6 } = {}) {
    const safeConflicts = Array.isArray(conflicts) ? conflicts : [];
    if (safeConflicts.length === 0) {
        return '';
    }

    const visibleConflicts = safeConflicts.slice(0, maxVisible);
    const rows = visibleConflicts.map((conflict) => {
        const participantId = escapeHtml(String(conflict?.participant_id || ''));
        const columnName = escapeHtml(String(conflict?.column || ''));
        const existingValue = escapeHtml(String(conflict?.existing_value ?? ''));
        const incomingValue = escapeHtml(String(conflict?.incoming_value ?? ''));
        return `<li><code>${participantId}</code> · <code>${columnName}</code> already has <code>${existingValue}</code>, incoming file has <code>${incomingValue}</code>.</li>`;
    });

    if (safeConflicts.length > visibleConflicts.length) {
        rows.push(`<li>...and ${safeConflicts.length - visibleConflicts.length} more conflict(s).</li>`);
    }

    return rows.join('');
}

export function buildParticipantsMergeHarmonizationRowsHtml({
    harmonizationCandidates,
    harmonizationDecisionsByColumn,
}) {
    const safeCandidates = Array.isArray(harmonizationCandidates) ? harmonizationCandidates : [];
    const decisionsByColumn = (harmonizationDecisionsByColumn && typeof harmonizationDecisionsByColumn === 'object')
        ? harmonizationDecisionsByColumn
        : {};

    return safeCandidates.map((candidate, index) => {
        const columnName = String(candidate?.column || '').trim();
        if (!columnName) {
            return '';
        }

        const decision = decisionsByColumn[columnName] || { action: 'keep_existing', new_column: '' };
        const selectedAction = String(decision.action || 'keep_existing');
        const selectedNewColumn = String(
            decision.new_column || candidate.selected_new_column || candidate.default_new_column || ''
        ).trim();
        const mappingPairs = Array.isArray(candidate.mapping_pairs) ? candidate.mapping_pairs : [];
        const mappingText = mappingPairs.length > 0
            ? mappingPairs
                .map((pair) => `${escapeHtml(String(pair.incoming_value || ''))} -> ${escapeHtml(String(pair.existing_value || ''))}`)
                .join(', ')
            : 'Equivalent coding detected.';
        const matchedPairCount = Number(candidate.matched_pair_count || 0);
        const inputId = `participantsHarmonizationColumn_${index}`;

        return `
            <div class="border rounded p-2 mb-2" data-harmonization-column="${escapeHtml(columnName)}">
                <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
                    <div class="small"><strong>${escapeHtml(columnName)}</strong></div>
                    <span class="badge bg-light text-dark">${matchedPairCount} matched pair${matchedPairCount === 1 ? '' : 's'}</span>
                </div>
                <div class="small text-muted mt-1">Detected mapping: ${mappingText}</div>
                <div class="row g-2 mt-1">
                    <div class="col-md-5">
                        <label class="form-label form-label-sm mb-1">Action</label>
                        <select class="form-select form-select-sm participants-merge-harmonization-action">
                            <option value="keep_existing" ${selectedAction === 'keep_existing' ? 'selected' : ''}>Keep existing coding</option>
                            <option value="use_incoming" ${selectedAction === 'use_incoming' ? 'selected' : ''}>Use incoming coding</option>
                            <option value="keep_both" ${selectedAction === 'keep_both' ? 'selected' : ''}>Keep both (add column)</option>
                        </select>
                    </div>
                    <div class="col-md-7">
                        <label class="form-label form-label-sm mb-1">New column (for Keep both)</label>
                        <input
                            id="${escapeHtml(inputId)}"
                            class="form-control form-control-sm participants-merge-harmonization-column"
                            type="text"
                            value="${escapeHtml(selectedNewColumn)}"
                            placeholder="${escapeHtml(String(candidate.default_new_column || `${columnName}_incoming`))}"
                            ${selectedAction === 'keep_both' ? '' : 'disabled'}
                        >
                        <div class="invalid-feedback participants-merge-harmonization-feedback"></div>
                        <div class="form-text participants-merge-harmonization-column-hint"></div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

export function buildParticipantsMergeSessionResolutionRowsHtml({
    sessionResolutionCandidates,
    sessionResolutionDecisionsByColumn,
}) {
    const safeCandidates = Array.isArray(sessionResolutionCandidates)
        ? sessionResolutionCandidates
        : [];
    const decisionsByColumn = (sessionResolutionDecisionsByColumn && typeof sessionResolutionDecisionsByColumn === 'object')
        ? sessionResolutionDecisionsByColumn
        : {};

    return safeCandidates.map((candidate, index) => {
        const columnName = String(candidate?.column || '').trim();
        if (!columnName) {
            return '';
        }

        const decision = decisionsByColumn[columnName] || { action: '', session: '' };
        const selectedAction = String(decision.action || '').trim();
        const selectedSession = String(decision.session || '').trim();
        const availableSessions = normalizeNonEmptyStrings(candidate.available_sessions);
        const generatedColumns = normalizeNonEmptyStrings(candidate.generated_columns);
        const generatedPreview = buildSessionSplitGeneratedPreview(columnName, availableSessions, generatedColumns);
        const sessionSelectId = `participantsSessionResolution_${index}`;

        return `
            <div class="border rounded p-2 mb-2" data-session-resolution-column="${escapeHtml(columnName)}">
                <div class="small mb-1"><strong>${escapeHtml(columnName)}</strong></div>
                <div class="row g-2 align-items-end">
                    <div class="col-md-5">
                        <label class="form-label form-label-sm mb-1">Resolution</label>
                        <select class="form-select form-select-sm participants-session-resolution-action">
                            <option value="" ${selectedAction ? '' : 'selected'}>Choose...</option>
                            <option value="pick_session" ${selectedAction === 'pick_session' ? 'selected' : ''}>Take one session</option>
                            <option value="pick_latest_session" ${selectedAction === 'pick_latest_session' ? 'selected' : ''}>Take latest session</option>
                            <option value="split_sessions" ${selectedAction === 'split_sessions' ? 'selected' : ''}>Keep all sessions as columns</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label form-label-sm mb-1">Session (for Take one)</label>
                        <select id="${escapeHtml(sessionSelectId)}" class="form-select form-select-sm participants-session-resolution-session" ${selectedAction === 'pick_session' ? '' : 'disabled'}>
                            <option value="">Choose session...</option>
                            ${availableSessions.map((sessionValue) => `<option value="${escapeHtml(sessionValue)}" ${selectedSession === sessionValue ? 'selected' : ''}>${escapeHtml(sessionValue)}</option>`).join('')}
                        </select>
                    </div>
                    <div class="col-md-3">
                        <div class="small text-muted">${selectedAction === 'split_sessions' ? `Creates: ${escapeHtml(generatedPreview)}` : ''}</div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

export function buildParticipantsMergeSessionResolutionHintText({
    previewData,
    sessionResolutionCandidates,
}) {
    const safePreviewData = previewData && typeof previewData === 'object' ? previewData : {};
    const safeCandidates = Array.isArray(sessionResolutionCandidates)
        ? sessionResolutionCandidates
        : [];
    const sessionColumnName = String(
        safePreviewData.session_resolution_column || safeCandidates[0]?.session_column || 'session'
    ).trim();

    return `Columns vary across repeated participant rows. Choose how to resolve values by ${sessionColumnName || 'session'}.`;
}
