import {
    buildParticipantsMergeConflictListHtml,
    buildParticipantsMergeHarmonizationRowsHtml,
    buildParticipantsMergeSessionResolutionHintText,
    buildParticipantsMergeSessionResolutionRowsHtml,
    isParticipantsMergeSessionResolutionSessionEnabled,
} from './participants-merge-summary-renderers.js';
import {
    getParticipantsMergeHarmonizationDecisionPayload,
    getParticipantsMergeHarmonizationDecisionUpdates,
    getParticipantsMergeSessionResolutionDecisionPayload,
    getParticipantsMergeSessionResolutionDecisionUpdates,
} from './participants-merge-summary-decisions.js';
import {
    getParticipantsMergeBadgeTexts,
    getParticipantsMergeConflictActionsView,
    getParticipantsMergeConflictListView,
    getParticipantsMergeConvertButtonView,
    getParticipantsMergeConvertHintText,
    getParticipantsMergeHarmonizationFieldView,
    getParticipantsMergeNewColumnsView,
    getParticipantsMergeSummaryView,
    getParticipantsMergeHarmonizationStatusView,
} from './participants-merge-summary-status.js';

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

        const applyVisibilityClass = (element, isVisible) => {
            element.classList.toggle('d-none', !Boolean(isVisible));
        };

        const applyTextVisibilityView = (element, view) => {
            element.textContent = String(view?.text || '');
            applyVisibilityClass(element, view?.isVisible);
        };

        const applyHtmlVisibilityView = (element, view) => {
            element.innerHTML = String(view?.html || '');
            applyVisibilityClass(element, view?.isVisible);
        };

        const applyConflictActionsView = (view) => {
            applyVisibilityClass(conflictActions, view?.showActions);
            downloadButton.disabled = !Boolean(view?.isDownloadEnabled);
        };

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

        const badgeTexts = getParticipantsMergeBadgeTexts({
            matchedCount,
            newParticipantCount,
            fillCount,
            conflictCount,
        });
        matchedBadge.textContent = badgeTexts.matchedText;
        newParticipantsBadge.textContent = badgeTexts.newParticipantsText;
        fillBadge.textContent = badgeTexts.fillText;
        conflictBadge.textContent = badgeTexts.conflictText;

        const summaryView = getParticipantsMergeSummaryView({
            canApply,
            existingOnlyCount,
            newParticipantCount,
            mergeQuality,
            sessionResolutionRequired,
            conflictCount,
        });
        summary.classList.remove('d-none', 'alert-success', 'alert-warning', 'alert-info');
        summary.classList.add(summaryView.alertToneClass);
        title.textContent = summaryView.titleText;
        summaryText.textContent = summaryView.summaryText;

        const newColumnsView = getParticipantsMergeNewColumnsView({ newColumns });
        applyTextVisibilityView(columnsText, newColumnsView);

        const conflictListView = getParticipantsMergeConflictListView({
            conflicts,
            buildConflictListHtml: buildParticipantsMergeConflictListHtml,
        });
        applyHtmlVisibilityView(conflictList, conflictListView);

        const conflictActionsView = getParticipantsMergeConflictActionsView({
            conflictCount,
        });
        applyConflictActionsView(conflictActionsView);

        if (!(window.participantsMergeSessionResolutionDecisions && typeof window.participantsMergeSessionResolutionDecisions === 'object')) {
            window.participantsMergeSessionResolutionDecisions = {};
        }

        if (sessionResolutionCandidates.length > 0) {
            Object.assign(
                window.participantsMergeSessionResolutionDecisions,
                getParticipantsMergeSessionResolutionDecisionUpdates({
                    sessionResolutionCandidates,
                    sessionResolutionDecisions,
                }),
            );

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
                        sessionSelect.disabled = !isParticipantsMergeSessionResolutionSessionEnabled(action);
                    }

                    window.participantsMergeSessionResolutionDecisions[columnName] = getParticipantsMergeSessionResolutionDecisionPayload({
                        action,
                        session: sessionValue,
                        sessionColumn: previewData.session_resolution_column,
                        clearSessionWhenNotPickSession: true,
                    });

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
                    if (!isParticipantsMergeSessionResolutionSessionEnabled(action)) {
                        return;
                    }

                    window.participantsMergeSessionResolutionDecisions[columnName] = getParticipantsMergeSessionResolutionDecisionPayload({
                        action,
                        session: sessionEl.value,
                        sessionColumn: previewData.session_resolution_column,
                        clearSessionWhenNotPickSession: true,
                    });

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

        const updateConvertButtonVisualState = (canConvert) => {
            const convertBtn = document.getElementById('participantsConvertBtn');
            if (!convertBtn) {
                return;
            }

            const convertButtonView = getParticipantsMergeConvertButtonView({ canConvert });
            convertBtn.disabled = !convertButtonView.isEnabled;
            convertBtn.classList.remove('btn-outline-secondary', 'btn-success');
            convertBtn.classList.add(convertButtonView.toneClass);
        };

        if (harmonizationCandidates.length === 0) {
            harmonizationSection.classList.add('d-none');
            harmonizationStatus.classList.add('d-none');
            harmonizationStatus.textContent = '';
            harmonizationList.innerHTML = '';

            const convertHint = document.getElementById('convertBtnHint');
            const canConvert = canApplyConversion();
            updateConvertButtonVisualState(canConvert);
            if (convertHint) {
                convertHint.textContent = getParticipantsMergeConvertHintText({
                    hasInvalidKeepBoth: false,
                    sessionResolutionRequired,
                    conflictCount,
                    canConvert,
                });
            }
            refreshApplyStatusBadge(previewData);
            return;
        }

        Object.assign(
            window.participantsMergeHarmonizationDecisions,
            getParticipantsMergeHarmonizationDecisionUpdates({
                harmonizationCandidates,
                harmonizationDecisions: serverDecisions,
            }),
        );

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
                const fieldView = getParticipantsMergeHarmonizationFieldView({
                    action,
                    errorText: invalidByColumn[columnName],
                    targetName: inputEl.value,
                });
                if (fieldView.isInvalid) {
                    inputEl.classList.add('is-invalid');
                } else {
                    inputEl.classList.remove('is-invalid');
                }
                feedbackEl.textContent = fieldView.feedbackText;
                hintEl.textContent = fieldView.hintText;
            });

            harmonizationStatus.classList.remove('d-none', 'text-danger', 'text-warning', 'text-muted', 'text-success');
            const statusView = getParticipantsMergeHarmonizationStatusView({
                harmonizationState,
                isRefreshPending: mergePreviewRefreshPending(),
                conflictCount,
            });
            harmonizationStatus.classList.add(statusView.toneClass);
            harmonizationStatus.textContent = statusView.text;

            const convertHint = document.getElementById('convertBtnHint');
            const canConvert = canApplyConversion();
            updateConvertButtonVisualState(canConvert);
            if (convertHint) {
                convertHint.textContent = getParticipantsMergeConvertHintText({
                    hasInvalidKeepBoth: harmonizationState.hasInvalidKeepBoth,
                    sessionResolutionRequired,
                    conflictCount,
                    canConvert,
                });
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

                window.participantsMergeHarmonizationDecisions[columnName] = getParticipantsMergeHarmonizationDecisionPayload({
                    action,
                    newColumn,
                });

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

                window.participantsMergeHarmonizationDecisions[columnName] = getParticipantsMergeHarmonizationDecisionPayload({
                    action,
                    newColumn: inputEl.value,
                });

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

                window.participantsMergeHarmonizationDecisions[columnName] = getParticipantsMergeHarmonizationDecisionPayload({
                    action,
                    newColumn: inputEl.value,
                });

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
