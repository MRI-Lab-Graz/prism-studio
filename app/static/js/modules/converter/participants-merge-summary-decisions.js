export function getParticipantsMergeSessionResolutionDecisionUpdates({
    sessionResolutionCandidates,
    sessionResolutionDecisions,
}) {
    const safeCandidates = Array.isArray(sessionResolutionCandidates)
        ? sessionResolutionCandidates
        : [];
    const safeServerDecisions = (sessionResolutionDecisions && typeof sessionResolutionDecisions === 'object')
        ? sessionResolutionDecisions
        : {};
    const updates = {};

    safeCandidates.forEach((candidate) => {
        const columnName = String(candidate && candidate.column ? candidate.column : '').trim();
        if (!columnName) {
            return;
        }

        const serverEntry = safeServerDecisions[columnName];
        const selectedAction = String(serverEntry?.action || candidate.selected_action || '').trim();
        const selectedSession = String(serverEntry?.session || candidate.selected_session || '').trim();
        const sessionColumn = String(candidate.session_column || '').trim();

        updates[columnName] = getParticipantsMergeSessionResolutionDecisionPayload({
            action: selectedAction,
            session: selectedSession,
            sessionColumn,
        });
    });

    return updates;
}

export function getParticipantsMergeSessionResolutionDecisionPayload({
    action,
    session,
    sessionColumn,
    clearSessionWhenNotPickSession = false,
}) {
    const normalizedAction = String(action || '').trim();
    const normalizedSession = String(session || '').trim();
    const normalizedSessionColumn = String(sessionColumn || '').trim();

    return {
        action: normalizedAction,
        session: clearSessionWhenNotPickSession && normalizedAction !== 'pick_session'
            ? ''
            : normalizedSession,
        session_column: normalizedSessionColumn,
    };
}

export function getParticipantsMergeHarmonizationDecisionPayload({
    action,
    newColumn,
}) {
    const normalizedAction = String(action || 'keep_existing').trim();
    const normalizedNewColumn = String(newColumn || '').trim();

    return {
        action: normalizedAction,
        new_column: normalizedAction === 'keep_both' ? normalizedNewColumn : '',
    };
}

export function getParticipantsMergeHarmonizationDecisionUpdates({
    harmonizationCandidates,
    harmonizationDecisions,
}) {
    const safeCandidates = Array.isArray(harmonizationCandidates)
        ? harmonizationCandidates
        : [];
    const safeServerDecisions = (harmonizationDecisions && typeof harmonizationDecisions === 'object')
        ? harmonizationDecisions
        : {};
    const updates = {};

    safeCandidates.forEach((candidate) => {
        const columnName = String(candidate && candidate.column ? candidate.column : '').trim();
        if (!columnName) {
            return;
        }

        const serverEntry = safeServerDecisions[columnName];
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

        updates[columnName] = getParticipantsMergeHarmonizationDecisionPayload({
            action: selectedAction,
            newColumn: selectedNewColumn,
        });
    });

    return updates;
}
