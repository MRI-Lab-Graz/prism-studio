import { escapeHtml } from '../../shared/dom.js';
import {
    buildParticipantsMergeConflictListHtml,
    buildParticipantsMergeHarmonizationRowsHtml,
    buildParticipantsMergeSessionResolutionHintText,
    buildParticipantsMergeSessionResolutionRowsHtml,
} from './participants-merge-summary-renderers.js';

export function createParticipantsMergeSummaryController({
    assessMergeHarmonizationState,
    canApplyParticipantsConversion,
    scheduleMergePreviewRefresh,
    updateMergeApplyStatusBadge,
    isMergePreviewRefreshPending,
} = {}) {
    const resolveHarmonizationState = typeof assessMergeHarmonizationState === 'function'
        ? assessMergeHarmonizationState
        : (() => ({ hasInvalidKeepBoth: false, invalidByColumn: {}, keepBothCount: 0 }));
    const canApplyConversion = typeof canApplyParticipantsConversion === 'function'
        ? canApplyParticipantsConversion
        : (() => false);
    const schedulePreviewRefresh = typeof scheduleMergePreviewRefresh === 'function'
        ? scheduleMergePreviewRefresh
        : (() => {});
    const refreshApplyStatusBadge = typeof updateMergeApplyStatusBadge === 'function'
        ? updateMergeApplyStatusBadge
        : (() => {});
    const mergePreviewRefreshPending = typeof isMergePreviewRefreshPending === 'function'
        ? isMergePreviewRefreshPending
        : (() => false);

    function render(previewData) {
        const summary = document.getElementById('participantsMergeSummary');
        const title = document.getElementById('participantsMergeSummaryTitle');
        const matchedBadge = document.getElementById('participantsMergeMatchedCount');
        const newParticipantsBadge = document.getElementById('participantsMergeNewParticipantsCount');
        const fillBadge = document.getElementById('participantsMergeFillCount');
        const conflictBadge = document.getElementById('participantsMergeConflictCount');
        const summaryText = document.getElementById('participantsMergeSummaryText');
        const columnsText = document.getElementById('participantsMergeColumnsText');
        const conflictList = document.getElementById('participantsMergeConflictList');
        const conflictActions = document.getElementById('participantsMergeConflictActions');
        const downloadButton = document.getElementById('participantsDownloadMergeConflictsBtn');
        const harmonizationSection = document.getElementById('participantsMergeHarmonizationSection');
        const harmonizationHint = document.getElementById('participantsMergeHarmonizationHint');
        const harmonizationStatus = document.getElementById('participantsMergeHarmonizationStatus');
        const harmonizationList = document.getElementById('participantsMergeHarmonizationList');
        const sessionResolutionSection = document.getElementById('participantsMergeSessionResolutionSection');
        const sessionResolutionHint = document.getElementById('participantsMergeSessionResolutionHint');
        const sessionResolutionList = document.getElementById('participantsMergeSessionResolutionList');

        if (!summary || !title || !matchedBadge || !newParticipantsBadge || !fillBadge || !conflictBadge || !summaryText || !columnsText || !conflictList || !conflictActions || !downloadButton || !harmonizationSection || !harmonizationHint || !harmonizationStatus || !harmonizationList || !sessionResolutionSection || !sessionResolutionHint || !sessionResolutionList) {
            return;
        }

        if (!previewData || !previewData.merge_mode) {
            summary.classList.add('d-none');
            conflictActions.classList.add('d-none');
            harmonizationSection.classList.add('d-none');
            harmonizationStatus.classList.add('d-none');
            harmonizationStatus.textContent = '';
            harmonizationList.innerHTML = '';
            sessionResolutionSection.classList.add('d-none');
            sessionResolutionList.innerHTML = '';
            downloadButton.disabled = true;
            return;
        }

        const matchedCount = Number(previewData.matched_participant_count || 0);
        const newParticipantCount = Number(previewData.new_participant_count || 0);
        const fillCount = Number(previewData.fillable_value_count || 0);
        const conflictCount = Number(previewData.conflict_count || 0);
        const existingOnlyCount = Number(previewData.existing_only_participant_count || 0);
        const newColumns = Array.isArray(previewData.new_columns)
            ? previewData.new_columns.map((col) => String(col || '').trim()).filter(Boolean)
            : [];
        const conflicts = Array.isArray(previewData.conflicts) ? previewData.conflicts : [];
        const harmonizationCandidates = Array.isArray(previewData.harmonization_candidates)
            ? previewData.harmonization_candidates
            : [];
        const serverDecisions = (previewData.harmonization_decisions && typeof previewData.harmonization_decisions === 'object')
            ? previewData.harmonization_decisions
            : {};
        const sessionResolutionCandidates = Array.isArray(previewData.session_resolution_candidates)
            ? previewData.session_resolution_candidates
            : [];
        const sessionResolutionDecisions = (previewData.session_resolution_decisions && typeof previewData.session_resolution_decisions === 'object')
            ? previewData.session_resolution_decisions
            : {};
        const mergeQuality = (previewData.merge_quality && typeof previewData.merge_quality === 'object')
            ? previewData.merge_quality
            : {};
        const sessionResolutionRequired = Boolean(previewData.session_resolution_required);
        const canApply = Boolean(previewData.can_apply);

        matchedBadge.textContent = `${matchedCount} matched`;
        newParticipantsBadge.textContent = `${newParticipantCount} new participant${newParticipantCount === 1 ? '' : 's'}`;
        fillBadge.textContent = `${fillCount} filled value${fillCount === 1 ? '' : 's'}`;
        conflictBadge.textContent = `${conflictCount} conflict${conflictCount === 1 ? '' : 's'}`;

        summary.classList.remove('d-none', 'alert-success', 'alert-warning', 'alert-info');
        summary.classList.add(canApply ? 'alert-success' : 'alert-warning');
        title.textContent = canApply ? 'Merge Preview Ready' : 'Merge Preview Blocked';

        if (canApply) {
            summaryText.textContent = existingOnlyCount > 0
                ? `This merge can be applied safely. ${existingOnlyCount} existing participant${existingOnlyCount === 1 ? '' : 's'} will stay unchanged.`
                : 'This merge can be applied safely. All overlapping non-empty values agree.';

            const incomingTotalCells = Number(mergeQuality.incoming_new_participant_total_value_cells || 0);
            const incomingMissingCells = Number(mergeQuality.incoming_new_participant_missing_value_cells || 0);
            const incomingAllMissingRows = Number(mergeQuality.incoming_new_participants_all_missing_values || 0);
            if (newParticipantCount > 0 && incomingTotalCells > 0 && incomingMissingCells > 0) {
                const missingPercent = Math.round((incomingMissingCells / incomingTotalCells) * 100);
                const allMissingNote = incomingAllMissingRows > 0
                    ? ` ${incomingAllMissingRows} new participant row${incomingAllMissingRows === 1 ? ' is' : 's are'} fully empty in the imported file.`
                    : '';
                summaryText.textContent += ` Imported values for new participants are sparse (${incomingMissingCells}/${incomingTotalCells} missing cells, ${missingPercent}%).${allMissingNote}`;
            }
        } else if (sessionResolutionRequired && conflictCount === 0) {
            summaryText.textContent = 'This merge is blocked until session resolution is chosen for columns that vary across repeated participant rows.';
        } else {
            summaryText.textContent = 'This merge is blocked because conflicting non-empty values were found. Existing participants.tsv remains authoritative until conflicts are resolved.';
        }

        if (newColumns.length > 0) {
            columnsText.textContent = `New columns from the import: ${newColumns.join(', ')}`;
            columnsText.classList.remove('d-none');
        } else {
            columnsText.textContent = '';
            columnsText.classList.add('d-none');
        }

        if (conflicts.length > 0) {
            conflictList.innerHTML = buildParticipantsMergeConflictListHtml(conflicts);
            conflictList.classList.remove('d-none');
        } else {
            conflictList.innerHTML = '';
            conflictList.classList.add('d-none');
        }

        if (conflictCount > 0) {
            conflictActions.classList.remove('d-none');
            downloadButton.disabled = false;
        } else {
            conflictActions.classList.add('d-none');
            downloadButton.disabled = true;
        }

        if (!(window.participantsMergeSessionResolutionDecisions && typeof window.participantsMergeSessionResolutionDecisions === 'object')) {
            window.participantsMergeSessionResolutionDecisions = {};
        }

        if (sessionResolutionCandidates.length > 0) {
            sessionResolutionCandidates.forEach((candidate) => {
                const columnName = String(candidate && candidate.column ? candidate.column : '').trim();
                if (!columnName) {
                    return;
                }

                const serverEntry = sessionResolutionDecisions[columnName];
                const selectedAction = String(serverEntry?.action || candidate.selected_action || '').trim();
                const selectedSession = String(serverEntry?.session || candidate.selected_session || '').trim();
                const sessionColumn = String(candidate.session_column || '').trim();
                window.participantsMergeSessionResolutionDecisions[columnName] = {
                    action: selectedAction,
                    session: selectedSession,
                    session_column: sessionColumn,
                };
            });

            sessionResolutionHint.textContent = buildParticipantsMergeSessionResolutionHintText({
                previewData,
                sessionResolutionCandidates,
            });

            sessionResolutionList.innerHTML = buildParticipantsMergeSessionResolutionRowsHtml({
                sessionResolutionCandidates,
                sessionResolutionDecisionsByColumn: window.participantsMergeSessionResolutionDecisions,
            });

            sessionResolutionSection.classList.remove('d-none');

            sessionResolutionList.querySelectorAll('.participants-session-resolution-action').forEach((selectEl) => {
                selectEl.addEventListener('change', () => {
                    const row = selectEl.closest('[data-session-resolution-column]');
                    if (!row) {
                        return;
                    }

                    const columnName = String(row.getAttribute('data-session-resolution-column') || '').trim();
                    if (!columnName) {
                        return;
                    }

                    const sessionSelect = row.querySelector('.participants-session-resolution-session');
                    const action = String(selectEl.value || '').trim();
                    const sessionValue = sessionSelect ? String(sessionSelect.value || '').trim() : '';
                    if (sessionSelect) {
                        sessionSelect.disabled = action !== 'pick_session';
                    }

                    window.participantsMergeSessionResolutionDecisions[columnName] = {
                        action,
                        session: action === 'pick_session' ? sessionValue : '',
                        session_column: String(previewData.session_resolution_column || '').trim(),
                    };

                    schedulePreviewRefresh();
                });
            });

            sessionResolutionList.querySelectorAll('.participants-session-resolution-session').forEach((sessionEl) => {
                sessionEl.addEventListener('change', () => {
                    const row = sessionEl.closest('[data-session-resolution-column]');
                    if (!row) {
                        return;
                    }

                    const columnName = String(row.getAttribute('data-session-resolution-column') || '').trim();
                    if (!columnName) {
                        return;
                    }

                    const actionSelect = row.querySelector('.participants-session-resolution-action');
                    const action = actionSelect ? String(actionSelect.value || '').trim() : '';
                    if (action !== 'pick_session') {
                        return;
                    }

                    window.participantsMergeSessionResolutionDecisions[columnName] = {
                        action,
                        session: String(sessionEl.value || '').trim(),
                        session_column: String(previewData.session_resolution_column || '').trim(),
                    };

                    schedulePreviewRefresh();
                });
            });
        } else {
            sessionResolutionSection.classList.add('d-none');
            sessionResolutionList.innerHTML = '';
        }

        if (!(window.participantsMergeHarmonizationDecisions && typeof window.participantsMergeHarmonizationDecisions === 'object')) {
            window.participantsMergeHarmonizationDecisions = {};
        }

        if (harmonizationCandidates.length === 0) {
            harmonizationSection.classList.add('d-none');
            harmonizationStatus.classList.add('d-none');
            harmonizationStatus.textContent = '';
            harmonizationList.innerHTML = '';

            const convertBtn = document.getElementById('participantsConvertBtn');
            const convertHint = document.getElementById('convertBtnHint');
            const canConvert = canApplyConversion();
            if (convertBtn) {
                convertBtn.disabled = !canConvert;
                convertBtn.classList.remove('btn-outline-secondary', 'btn-success');
                convertBtn.classList.add(canConvert ? 'btn-success' : 'btn-outline-secondary');
            }
            if (convertHint) {
                if (sessionResolutionRequired && conflictCount === 0) {
                    convertHint.textContent = 'Choose session resolution before applying merge';
                } else {
                    convertHint.textContent = canConvert
                        ? 'Ready to apply conflict-free merge'
                        : 'Resolve merge conflicts first';
                }
            }
            refreshApplyStatusBadge(previewData);
            return;
        }

        harmonizationCandidates.forEach((candidate) => {
            const columnName = String(candidate && candidate.column ? candidate.column : '').trim();
            if (!columnName) {
                return;
            }

            const serverEntry = serverDecisions[columnName];
            const fallbackAction = String(candidate.selected_action || 'keep_existing').trim().toLowerCase();
            const fallbackNewColumn = String(candidate.selected_new_column || candidate.default_new_column || '').trim();

            let selectedAction = fallbackAction;
            let selectedNewColumn = fallbackNewColumn;

            if (serverEntry && typeof serverEntry === 'object') {
                selectedAction = String(serverEntry.action || fallbackAction).trim().toLowerCase();
                selectedNewColumn = String(serverEntry.new_column || fallbackNewColumn).trim();
            }

            if (!['keep_existing', 'use_incoming', 'keep_both'].includes(selectedAction)) {
                selectedAction = 'keep_existing';
            }

            window.participantsMergeHarmonizationDecisions[columnName] = {
                action: selectedAction,
                new_column: selectedAction === 'keep_both' ? selectedNewColumn : '',
            };
        });

        harmonizationHint.textContent = `Equivalent coding detected in ${harmonizationCandidates.length} column(s). Choose how merge should harmonize these values.`;

        harmonizationList.innerHTML = buildParticipantsMergeHarmonizationRowsHtml({
            harmonizationCandidates,
            harmonizationDecisionsByColumn: window.participantsMergeHarmonizationDecisions,
        });

        harmonizationSection.classList.remove('d-none');

        const refreshHarmonizationUiState = () => {
            const harmonizationState = resolveHarmonizationState(previewData);
            const invalidByColumn = harmonizationState.invalidByColumn || {};

            harmonizationList.querySelectorAll('[data-harmonization-column]').forEach((row) => {
                const columnName = String(row.getAttribute('data-harmonization-column') || '').trim();
                const inputEl = row.querySelector('.participants-merge-harmonization-column');
                const actionEl = row.querySelector('.participants-merge-harmonization-action');
                const feedbackEl = row.querySelector('.participants-merge-harmonization-feedback');
                const hintEl = row.querySelector('.participants-merge-harmonization-column-hint');

                if (!inputEl || !actionEl || !feedbackEl || !hintEl) {
                    return;
                }

                const action = String(actionEl.value || 'keep_existing').trim();
                if (action !== 'keep_both') {
                    inputEl.classList.remove('is-invalid');
                    feedbackEl.textContent = '';
                    hintEl.textContent = 'No extra column will be created for this field.';
                    return;
                }

                const errorText = String(invalidByColumn[columnName] || '').trim();
                if (errorText) {
                    inputEl.classList.add('is-invalid');
                    feedbackEl.textContent = errorText;
                    hintEl.textContent = '';
                } else {
                    inputEl.classList.remove('is-invalid');
                    feedbackEl.textContent = '';
                    const targetName = String(inputEl.value || '').trim();
                    hintEl.textContent = targetName
                        ? `Incoming coding will be written to ${targetName}.`
                        : 'Enter the new incoming-coded column name.';
                }
            });

            harmonizationStatus.classList.remove('d-none', 'text-danger', 'text-warning', 'text-muted', 'text-success');
            if (harmonizationState.hasInvalidKeepBoth) {
                harmonizationStatus.classList.add('text-danger');
                harmonizationStatus.textContent = 'Fix Keep both column names before applying merge.';
            } else if (mergePreviewRefreshPending()) {
                harmonizationStatus.textContent = 'Refreshing merge preview with updated harmonization settings...';
                harmonizationStatus.classList.add('text-muted');
            } else if (conflictCount > 0) {
                harmonizationStatus.classList.add('text-warning');
                harmonizationStatus.textContent = 'Harmonization can resolve equivalent coding only. Remaining conflicts must be fixed in source data.';
            } else {
                harmonizationStatus.classList.add('text-success');
                harmonizationStatus.textContent = 'Merge is conflict-free. Confirm harmonization choices, then apply merge.';
            }

            const convertBtn = document.getElementById('participantsConvertBtn');
            const convertHint = document.getElementById('convertBtnHint');
            const canConvert = canApplyConversion();
            if (convertBtn) {
                convertBtn.disabled = !canConvert;
                convertBtn.classList.remove('btn-outline-secondary', 'btn-success');
                convertBtn.classList.add(canConvert ? 'btn-success' : 'btn-outline-secondary');
            }
            if (convertHint) {
                if (harmonizationState.hasInvalidKeepBoth) {
                    convertHint.textContent = 'Fix Keep both column names before applying merge';
                } else if (sessionResolutionRequired && conflictCount === 0) {
                    convertHint.textContent = 'Choose session resolution before applying merge';
                } else {
                    convertHint.textContent = canConvert
                        ? 'Ready to apply conflict-free merge'
                        : 'Resolve merge conflicts first';
                }
            }

            refreshApplyStatusBadge(previewData);
        };

        harmonizationList.querySelectorAll('.participants-merge-harmonization-action').forEach((selectEl) => {
            selectEl.addEventListener('change', () => {
                const row = selectEl.closest('[data-harmonization-column]');
                if (!row) {
                    return;
                }

                const columnName = String(row.getAttribute('data-harmonization-column') || '').trim();
                if (!columnName) {
                    return;
                }

                const inputEl = row.querySelector('.participants-merge-harmonization-column');
                const action = String(selectEl.value || 'keep_existing').trim();
                const newColumn = inputEl ? String(inputEl.value || '').trim() : '';

                if (inputEl) {
                    inputEl.disabled = action !== 'keep_both';
                }

                window.participantsMergeHarmonizationDecisions[columnName] = {
                    action,
                    new_column: action === 'keep_both' ? newColumn : '',
                };

                refreshHarmonizationUiState();
                schedulePreviewRefresh();
            });
        });

        harmonizationList.querySelectorAll('.participants-merge-harmonization-column').forEach((inputEl) => {
            inputEl.addEventListener('input', () => {
                const row = inputEl.closest('[data-harmonization-column]');
                if (!row) {
                    return;
                }

                const columnName = String(row.getAttribute('data-harmonization-column') || '').trim();
                if (!columnName) {
                    return;
                }

                const actionEl = row.querySelector('.participants-merge-harmonization-action');
                const action = actionEl ? String(actionEl.value || 'keep_existing').trim() : 'keep_existing';
                if (action !== 'keep_both') {
                    return;
                }

                window.participantsMergeHarmonizationDecisions[columnName] = {
                    action,
                    new_column: String(inputEl.value || '').trim(),
                };

                refreshHarmonizationUiState();
            });

            inputEl.addEventListener('change', () => {
                const row = inputEl.closest('[data-harmonization-column]');
                if (!row) {
                    return;
                }

                const columnName = String(row.getAttribute('data-harmonization-column') || '').trim();
                if (!columnName) {
                    return;
                }

                const actionEl = row.querySelector('.participants-merge-harmonization-action');
                const action = actionEl ? String(actionEl.value || 'keep_existing').trim() : 'keep_existing';
                if (action !== 'keep_both') {
                    return;
                }

                window.participantsMergeHarmonizationDecisions[columnName] = {
                    action,
                    new_column: String(inputEl.value || '').trim(),
                };

                refreshHarmonizationUiState();
                schedulePreviewRefresh();
            });
        });

        refreshHarmonizationUiState();
    }

    return {
        render,
    };
}
