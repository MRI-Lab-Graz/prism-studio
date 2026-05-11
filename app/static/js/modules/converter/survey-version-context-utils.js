export function normalizeVersionSelectionSession(session) {
    const value = String(session || '').trim();
    if (!value) return null;
    const label = value.replace(/^ses-/i, '').replace(/[^a-zA-Z0-9]+/g, '');
    if (!label) return null;
    return `ses-${label}`;
}

export function normalizeVersionSelectionRun(run) {
    if (run === null || run === undefined || run === '') return null;
    const value = String(run || '').trim();
    if (!value) return null;
    const label = value.replace(/^run-/i, '').replace(/[^a-zA-Z0-9]+/g, '');
    if (!label) return null;
    return `run-${label}`;
}

export function buildVersionSelectionKey({ task, session = null, run = null }) {
    const normalizedTask = String(task || '').trim().toLowerCase();
    const normalizedSession = normalizeVersionSelectionSession(session) || 'base';
    const normalizedRunValue = normalizeVersionSelectionRun(run);
    const normalizedRun = normalizedRunValue === null ? 'base' : normalizedRunValue;
    return `${normalizedTask}::${normalizedSession}::${normalizedRun}`;
}

export function getTimelineRunSortMeta(value) {
    const normalizedValue = normalizeVersionSelectionRun(value);
    if (!normalizedValue) {
        return { group: 2, order: Number.MAX_SAFE_INTEGER, token: '' };
    }

    const token = normalizedValue.replace(/^run-/i, '');
    const numericMatch = token.match(/^0*(\d+)$/);
    if (numericMatch) {
        return { group: 0, order: Number(numericMatch[1]), token };
    }

    return { group: 1, order: Number.MAX_SAFE_INTEGER, token: token.toLowerCase() };
}

export function normalizeTimelineSessionToken(value) {
    return String(value || '')
        .trim()
        .replace(/^ses-/, '')
        .replace(/[_\s]+/g, '-');
}

export function getTimelineSessionSortMeta(value) {
    const token = normalizeTimelineSessionToken(value);
    if (!token) {
        return { group: 2, order: Number.MAX_SAFE_INTEGER, token: '' };
    }

    const aliasOrder = [
        'screening',
        'baseline',
        'base',
        'pre',
        'pretest',
        'before',
        'start',
        'mid',
        'during',
        'post',
        'posttest',
        'after',
        'followup',
        'follow-up',
        'fu',
        'end'
    ];
    const aliasIndex = aliasOrder.indexOf(token.toLowerCase());
    if (aliasIndex >= 0) {
        return { group: 0, order: aliasIndex, token };
    }

    return { group: 1, order: Number.MAX_SAFE_INTEGER, token };
}

export function compareTimelineSessions(left, right) {
    const leftMeta = getTimelineSessionSortMeta(left);
    const rightMeta = getTimelineSessionSortMeta(right);
    if (leftMeta.group !== rightMeta.group) {
        return leftMeta.group - rightMeta.group;
    }
    if (leftMeta.order !== rightMeta.order) {
        return leftMeta.order - rightMeta.order;
    }
    return String(left || '').localeCompare(String(right || ''));
}

export function compareTimelineContexts(left, right) {
    const sessionCompare = compareTimelineSessions(left?.session, right?.session);
    if (sessionCompare !== 0) {
        return sessionCompare;
    }
    const leftMeta = getTimelineRunSortMeta(left?.run);
    const rightMeta = getTimelineRunSortMeta(right?.run);
    if (leftMeta.group !== rightMeta.group) {
        return leftMeta.group - rightMeta.group;
    }
    if (leftMeta.order !== rightMeta.order) {
        return leftMeta.order - rightMeta.order;
    }
    return leftMeta.token.localeCompare(rightMeta.token);
}

export function deriveDetectedContexts(taskRuns, previewParticipants, detectedSessions = []) {
    const participants = Array.isArray(previewParticipants) ? previewParticipants : [];
    const fallbackSessions = [...new Set((Array.isArray(detectedSessions) ? detectedSessions : []).map((value) => String(value || '').trim()).filter(Boolean))].sort(compareTimelineSessions);
    const sessions = [...new Set(participants.map((item) => String(item?.session_id || '').trim()).filter(Boolean))].sort(compareTimelineSessions);
    const effectiveSessions = sessions.length > 0 ? sessions : fallbackSessions;
    const runs = [...new Set(participants.map((item) => normalizeVersionSelectionRun(item && item.run_id)).filter(Boolean))].sort((left, right) => compareTimelineContexts({ session: null, run: left }, { session: null, run: right }));
    const maxRun = Math.max(
        0,
        ...Object.values(taskRuns || {}).map((value) => (Number.isInteger(value) && value > 1 ? value : 0))
    );
    const hasSessionContexts = effectiveSessions.length > 1;
    const hasRunContexts = runs.length > 1 || maxRun > 1;

    if (!hasSessionContexts && !hasRunContexts) {
        return [{ session: null, run: null }];
    }

    const observedContexts = [...new Set(
        participants.map((item) => JSON.stringify({
            session: hasSessionContexts ? String(item?.session_id || '').trim() || null : null,
            run: hasRunContexts ? normalizeVersionSelectionRun(item?.run_id) : null
        }))
    )]
        .map((value) => {
            try {
                return JSON.parse(value);
            } catch (_error) {
                return null;
            }
        })
        .filter((value) => value && (value.session !== null || value.run !== null));

    if (observedContexts.length > 0) {
        return observedContexts.sort(compareTimelineContexts);
    }

    const runValues = hasRunContexts
        ? (runs.length > 0 ? runs : Array.from({ length: maxRun }, (_, index) => `run-${index + 1}`))
        : [null];
    const sessionValues = hasSessionContexts ? effectiveSessions : [null];
    const fallbackContexts = [];
    sessionValues.forEach((sessionValue) => {
        runValues.forEach((runValue) => {
            fallbackContexts.push({ session: sessionValue, run: runValue });
        });
    });
    return fallbackContexts;
}
