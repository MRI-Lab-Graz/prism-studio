export function getParticipantsMergeHarmonizationDecisions(rawDecisionsInput) {
    const rawDecisions = (rawDecisionsInput && typeof rawDecisionsInput === 'object')
        ? rawDecisionsInput
        : {};

    const normalizedDecisions = {};
    Object.entries(rawDecisions).forEach(([columnName, rawEntry]) => {
        const cleanedColumn = String(columnName || '').trim();
        if (!cleanedColumn) {
            return;
        }

        let action = 'keep_existing';
        let newColumn = '';

        if (typeof rawEntry === 'string') {
            action = String(rawEntry || '').trim().toLowerCase();
        } else if (rawEntry && typeof rawEntry === 'object') {
            action = String(rawEntry.action || '').trim().toLowerCase();
            newColumn = String(rawEntry.new_column || '').trim();
        }

        if (!['keep_existing', 'use_incoming', 'keep_both'].includes(action)) {
            action = 'keep_existing';
        }

        normalizedDecisions[cleanedColumn] = {
            action,
            new_column: action === 'keep_both' ? newColumn : '',
        };
    });

    return normalizedDecisions;
}

export function appendParticipantsMergeHarmonizationDecisions(formData, rawDecisionsInput) {
    const decisions = getParticipantsMergeHarmonizationDecisions(rawDecisionsInput);
    if (Object.keys(decisions).length > 0) {
        formData.append('harmonization_decisions', JSON.stringify(decisions));
    }
}

export function getParticipantsMergeSessionResolutionDecisions(rawDecisionsInput) {
    const rawDecisions = (rawDecisionsInput && typeof rawDecisionsInput === 'object')
        ? rawDecisionsInput
        : {};

    const normalizedDecisions = {};
    Object.entries(rawDecisions).forEach(([columnName, rawEntry]) => {
        const cleanedColumn = String(columnName || '').trim();
        if (!cleanedColumn || !rawEntry || typeof rawEntry !== 'object') {
            return;
        }

        const action = String(rawEntry.action || '').trim().toLowerCase();
        if (!['pick_session', 'pick_latest_session', 'split_sessions'].includes(action)) {
            return;
        }

        const decision = { action };
        if (action === 'pick_session') {
            const sessionValue = String(rawEntry.session || '').trim();
            decision.session = sessionValue;
        }

        const sessionColumn = String(rawEntry.session_column || '').trim();
        if (sessionColumn) {
            decision.session_column = sessionColumn;
        }

        normalizedDecisions[cleanedColumn] = decision;
    });

    return normalizedDecisions;
}

export function appendParticipantsMergeSessionResolutionDecisions(formData, rawDecisionsInput) {
    const decisions = getParticipantsMergeSessionResolutionDecisions(rawDecisionsInput);
    if (Object.keys(decisions).length > 0) {
        formData.append('session_resolution_decisions', JSON.stringify(decisions));
    }
}
