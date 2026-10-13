export function createSurveySessionAssignmentsController() {
    const DERIVED_HINT = 'Sessions are numbered 1, 2, … by startdate (completed responses only).';

    function applyMode() {
        const derived = document.getElementById('convertDuplicateHandling')?.value === 'sessions';
        const group = document.getElementById('convertSessionGroup');
        const select = document.getElementById('convertSessionSelect');
        const custom = document.getElementById('convertSessionCustom');
        const hint = document.getElementById('convertSessionHint');
        const badge = document.getElementById('convertSessionBadge');
        if (!group) return;
        group.classList.toggle('session-derived', derived);
        [select, custom].forEach((el) => {
            if (!el) return;
            el.disabled = derived;
            if (derived) el.value = '';
        });
        if (hint) {
            if (hint.dataset.original === undefined) hint.dataset.original = hint.firstChild?.textContent || '';
            if (hint.firstChild) hint.firstChild.textContent = derived ? DERIVED_HINT : hint.dataset.original;
        }
        if (badge) badge.textContent = derived ? 'FROM DATES' : 'REQUIRED';
    }

    function initialize() {
        document.getElementById('convertDuplicateHandling')?.addEventListener('change', applyMode);
        applyMode();
    }

    return { initialize, applyMode };
}
