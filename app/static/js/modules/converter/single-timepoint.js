/**
 * One-timepoint (cross-sectional) projects: every import is written as ses-1, so the session
 * controls are greyed out. The backend decides (project.json StudyDesign.Timepoints); this only
 * asks it and shows the result.
 */
import { fetchWithApiFallback } from '../../shared/api.js';
import { resolveCurrentProjectPath } from '../../shared/project-state.js';

export const SINGLE_BADGE = 'ONE TIMEPOINT';
export const SINGLE_HINT = 'This project has one timepoint (cross-sectional): every import is written as ses-1, whatever the file says.';

let single = false;

export const isSingleTimepoint = () => single;

/** Ask the backend about the current project and tell the pages (`prism-timepoints-changed`). */
export async function refreshTimepoints(projectPath = resolveCurrentProjectPath()) {
    let next = false;
    if (projectPath) {
        try {
            const response = await fetchWithApiFallback(`/api/session-map?project_path=${encodeURIComponent(projectPath)}`);
            next = (await response.json().catch(() => ({}))).timepoints === 'single';
        } catch {
            next = false; // unknown: leave the controls usable
        }
    }
    single = next;
    window.dispatchEvent(new CustomEvent('prism-timepoints-changed', { detail: { single } }));
    return single;
}

/**
 * Grey out (or restore) one page's session controls.
 * `controls` are disabled; `badge` and `hint` swap their text; `label` loses its red "required" colour.
 */
export function lockSessionControls({ controls = [], badge = null, hint = null, label = null }, locked) {
    controls.forEach((el) => { if (el) el.disabled = locked; });
    remember(badge, 'badge bg-secondary ms-1', locked, SINGLE_BADGE);
    remember(label, (label?.className || '').replace('text-danger', '').trim(), locked);
    if (hint) {
        const target = hint.firstChild?.nodeType === Node.TEXT_NODE ? hint.firstChild : hint;
        if (hint.dataset.original === undefined) hint.dataset.original = target.textContent;
        target.textContent = locked ? SINGLE_HINT : hint.dataset.original;
    }
}

/** Swap an element's classes (and text) while locked; restore what it had when unlocked. */
function remember(el, lockedClass, locked, lockedText) {
    if (!el) return;
    if (el.dataset.originalClass === undefined) {
        el.dataset.originalClass = el.className;
        el.dataset.originalText = el.textContent;
    }
    el.className = locked ? lockedClass : el.dataset.originalClass;
    if (lockedText !== undefined) el.textContent = locked ? lockedText : el.dataset.originalText;
}
