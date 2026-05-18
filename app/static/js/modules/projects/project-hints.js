import { escapeHtml } from '../../shared/dom.js';

const beginnerHelpModeKey = 'prism_beginner_help_mode';
const FORM_IDS = [
    'createProjectForm',
    'openProjectForm',
    'studyMetadataForm',
    'globalSettingsForm',
    'exportProjectForm'
];

function normalizeHintText(text) {
    return String(text || '').replace(/\s+/g, ' ').trim();
}

function getExistingFieldHelpTexts(field) {
    const container = field.closest('.form-check, [class*="col-"], .mb-3, .card-body') || field.parentElement;
    if (!container) return [];

    const texts = [];
    const nodes = container.querySelectorAll('small.text-muted, .form-text, small');
    nodes.forEach((node) => {
        if (node.classList.contains('field-hint-inline')) return;
        const text = normalizeHintText(node.textContent);
        if (text) texts.push(text);
    });
    return texts;
}

function isHintDuplicate(hintText, existingTexts) {
    const normalizedHint = normalizeHintText(hintText);
    if (!normalizedHint) return true;

    return (Array.isArray(existingTexts) ? existingTexts : []).some((existingText) => {
        const normalizedExisting = normalizeHintText(existingText);
        if (!normalizedExisting) return false;
        return normalizedExisting.includes(normalizedHint)
            || normalizedHint.includes(normalizedExisting);
    });
}

function isFieldEffectivelyEmpty(field) {
    if (field.type === 'checkbox' || field.type === 'radio') {
        return !field.checked;
    }
    if (field.tagName === 'SELECT' && field.multiple) {
        return Array.from(field.selectedOptions || []).length === 0;
    }
    return !String(field.value || '').trim();
}

function shouldShowBeginnerHint(field) {
    const isFocused = document.activeElement === field;
    const isInvalid = field.matches(':invalid') || field.classList.contains('is-invalid');
    return isFocused || isInvalid || isFieldEffectivelyEmpty(field);
}

function getFieldHintText(field) {
    const parts = [];

    const placeholder = normalizeHintText(field.getAttribute('placeholder'));
    if (placeholder) {
        parts.push(`Example: ${placeholder}`);
    }

    if (parts.length > 0) {
        return parts[0];
    }

    if (field.tagName === 'SELECT') {
        return 'Choose the option that best matches your study.';
    }
    if (field.type === 'checkbox' || field.type === 'radio') {
        return 'Enable this option if it applies to your project.';
    }
    return 'Fill out this field based on your study.';
}

function addHintIconToLabel(label, hintText) {
    if (!label || !hintText) return;
    if (label.querySelector('.field-hint-trigger')) return;

    const existingTooltipIcon = label.querySelector('[data-bs-toggle="tooltip"]');
    if (existingTooltipIcon) return;

    const hintButton = document.createElement('button');
    hintButton.type = 'button';
    hintButton.className = 'btn btn-link p-0 ms-1 align-baseline text-muted field-hint-trigger';
    hintButton.setAttribute('data-bs-toggle', 'tooltip');
    hintButton.setAttribute('data-bs-placement', 'top');
    hintButton.setAttribute('data-bs-title', hintText);
    hintButton.setAttribute('aria-label', 'Show field guidance');
    hintButton.innerHTML = '<i class="fas fa-info-circle"></i>';

    label.appendChild(hintButton);

    if (window.bootstrap?.Tooltip) {
        window.bootstrap.Tooltip.getOrCreateInstance(hintButton);
    }
}

function clearInlineFieldHints() {
    document.querySelectorAll('.field-hint-inline').forEach((node) => node.remove());
}

export function getBeginnerHelpModeEnabled() {
    try {
        const value = localStorage.getItem(beginnerHelpModeKey);
        if (value === null) return true;
        return value === '1';
    } catch (_) {
        return true;
    }
}

function setBeginnerHelpModeEnabled(enabled) {
    try {
        localStorage.setItem(beginnerHelpModeKey, enabled ? '1' : '0');
    } catch (_) {
        // ignore storage failures
    }
}

function renderInlineFieldHints() {
    clearInlineFieldHints();

    FORM_IDS.forEach((formId) => {
        const form = document.getElementById(formId);
        if (!form) return;

        const fields = form.querySelectorAll('input, select, textarea');
        fields.forEach((field) => {
            if (!field.id || field.type === 'hidden') return;
            if (!shouldShowBeginnerHint(field)) return;

            const hintText = getFieldHintText(field);
            if (!hintText) return;

            const existingHelpTexts = getExistingFieldHelpTexts(field);
            if (isHintDuplicate(hintText, existingHelpTexts)) return;

            const fieldGroup = field.closest('.form-check, .input-group, [class*="col-"]') || field.parentElement;
            if (!fieldGroup) return;

            if (fieldGroup.querySelector(`.field-hint-inline[data-for="${field.id}"]`)) {
                return;
            }

            const hint = document.createElement('div');
            hint.className = 'field-hint-inline form-text text-muted';
            hint.setAttribute('data-for', field.id);
            hint.innerHTML = `<i class="fas fa-info-circle me-1"></i>${escapeHtml(hintText)}`;

            if (fieldGroup.classList.contains('input-group')) {
                fieldGroup.insertAdjacentElement('afterend', hint);
            } else {
                fieldGroup.appendChild(hint);
            }
        });
    });
}

let beginnerHintRefreshBound = false;

function bindBeginnerHintRefreshEvents() {
    if (beginnerHintRefreshBound) return;

    const refreshIfEnabled = () => {
        if (!getBeginnerHelpModeEnabled()) return;
        renderInlineFieldHints();
    };

    ['focusin', 'focusout', 'input', 'change'].forEach((eventName) => {
        document.addEventListener(eventName, (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            if (!target.closest('#createProjectForm, #openProjectForm, #studyMetadataForm, #globalSettingsForm, #exportProjectForm')) return;
            if (!target.matches('input, select, textarea')) return;
            refreshIfEnabled();
        });
    });

    beginnerHintRefreshBound = true;
}

function applyBeginnerHelpMode(enabled) {
    if (enabled) {
        renderInlineFieldHints();
    } else {
        clearInlineFieldHints();
    }
}

export function initBeginnerHelpMode() {
    if (window.prismGlobalBeginnerHintsManaged === true) {
        return;
    }

    const toggle = document.getElementById('beginnerHelpModeToggle');
    const enabled = getBeginnerHelpModeEnabled();

    if (toggle) {
        toggle.checked = enabled;
        toggle.addEventListener('change', () => {
            const modeEnabled = Boolean(toggle.checked);
            setBeginnerHelpModeEnabled(modeEnabled);
            applyBeginnerHelpMode(modeEnabled);
        });
    }

    window.addEventListener('prism-beginner-help-changed', (event) => {
        const modeEnabled = Boolean(event?.detail?.enabled);
        if (toggle) {
            toggle.checked = modeEnabled;
        }
        setBeginnerHelpModeEnabled(modeEnabled);
        applyBeginnerHelpMode(modeEnabled);
    });

    applyBeginnerHelpMode(enabled);
    bindBeginnerHintRefreshEvents();
}

export function initProjectFieldHints() {
    FORM_IDS.forEach((formId) => {
        const form = document.getElementById(formId);
        if (!form) return;

        const fields = form.querySelectorAll('input, select, textarea');
        fields.forEach((field) => {
            if (!field.id || field.type === 'hidden') return;

            let label = form.querySelector(`label[for="${field.id}"]`);
            if (!label) {
                label = field.closest('.form-check')?.querySelector('.form-check-label') || null;
            }
            if (!label) return;

            const hintText = getFieldHintText(field);
            addHintIconToLabel(label, hintText);
        });
    });
}