document.addEventListener('DOMContentLoaded', () => {
    const storageKey = 'prism_beginner_help_mode';
    const globalToggleBtn = document.getElementById('globalBeginnerHelpToggle');
    const pageToggleCheckbox = document.getElementById('beginnerHelpModeToggle');
    let inlineHintsBound = false;

    // Expose that global-help-mode owns inline beginner hints across pages.
    window.prismGlobalBeginnerHintsManaged = true;

    function normalizeHintText(text) {
        return String(text || '').replace(/\s+/g, ' ').trim();
    }

    function isFieldSupported(field) {
        if (!(field instanceof HTMLElement)) return false;
        if (!field.matches('input, select, textarea')) return false;

        const type = String(field.getAttribute('type') || '').toLowerCase();
        if (['hidden', 'button', 'submit', 'reset'].includes(type)) return false;
        if (field.hasAttribute('disabled')) return false;
        return true;
    }

    function isFieldEffectivelyEmpty(field) {
        if (field instanceof HTMLInputElement && (field.type === 'checkbox' || field.type === 'radio')) {
            return !field.checked;
        }

        if (field instanceof HTMLSelectElement && field.multiple) {
            return Array.from(field.selectedOptions || []).length === 0;
        }

        return !String(field.value || '').trim();
    }

    function shouldShowInlineHint(field) {
        const isFocused = document.activeElement === field;
        const isInvalid = field.matches(':invalid') || field.classList.contains('is-invalid');
        return isFocused || isInvalid || isFieldEffectivelyEmpty(field);
    }

    function getFieldHintText(field) {
        const placeholder = normalizeHintText(field.getAttribute('placeholder'));
        if (placeholder) {
            return `Example: ${placeholder}`;
        }

        if (field.tagName === 'SELECT') {
            return 'Choose the option that best matches your data.';
        }

        if (field instanceof HTMLInputElement && (field.type === 'checkbox' || field.type === 'radio')) {
            return 'Enable this option if it applies to your project.';
        }

        return 'Fill this field to continue.';
    }

    function getExistingHelpTexts(field) {
        const container = field.closest('.form-check, .input-group, [class*="col-"], .mb-3, .card-body, .accordion-body') || field.parentElement;
        if (!container) return [];

        const texts = [];
        container.querySelectorAll('small.text-muted, .form-text, small, .field-hint-inline').forEach(node => {
            const text = normalizeHintText(node.textContent);
            if (text) texts.push(text);
        });
        return texts;
    }

    function isHintDuplicate(hintText, existingTexts) {
        const normalizedHint = normalizeHintText(hintText).toLowerCase();
        if (!normalizedHint) return true;

        return existingTexts.some(existing => {
            const normalizedExisting = normalizeHintText(existing).toLowerCase();
            if (!normalizedExisting) return false;
            return normalizedExisting === normalizedHint
                || normalizedExisting.includes(normalizedHint)
                || normalizedHint.includes(normalizedExisting);
        });
    }

    function clearInlineFieldHints() {
        document.querySelectorAll('.field-hint-inline[data-beginner-inline-hint="true"]').forEach(node => node.remove());
    }

    function renderInlineFieldHints() {
        clearInlineFieldHints();

        document.querySelectorAll('form').forEach(form => {
            form.querySelectorAll('input, select, textarea').forEach(field => {
                if (!isFieldSupported(field)) return;
                if (!field.id) return;
                if (!shouldShowInlineHint(field)) return;

                const hintText = getFieldHintText(field);
                if (!hintText) return;

                const existingHelpTexts = getExistingHelpTexts(field);
                if (isHintDuplicate(hintText, existingHelpTexts)) return;

                const fieldGroup = field.closest('.form-check, .input-group, [class*="col-"]') || field.parentElement;
                if (!fieldGroup) return;

                const hint = document.createElement('div');
                hint.className = 'field-hint-inline form-text text-muted';
                hint.setAttribute('data-for', field.id);
                hint.setAttribute('data-beginner-inline-hint', 'true');
                hint.innerHTML = '<i class="fas fa-info-circle me-1"></i>' + hintText;

                if (fieldGroup.classList.contains('input-group')) {
                    fieldGroup.insertAdjacentElement('afterend', hint);
                } else {
                    fieldGroup.appendChild(hint);
                }
            });
        });
    }

    function bindInlineHintRefresh() {
        if (inlineHintsBound) return;

        const refreshIfEnabled = () => {
            if (!window.prismBeginnerHelpMode) return;
            renderInlineFieldHints();
        };

        ['focusin', 'focusout', 'input', 'change'].forEach(eventName => {
            document.addEventListener(eventName, (event) => {
                const target = event.target;
                if (!(target instanceof HTMLElement)) return;
                if (!target.closest('form')) return;
                if (!isFieldSupported(target)) return;
                refreshIfEnabled();
            });
        });

        inlineHintsBound = true;
    }

    function readMode() {
        try {
            const value = localStorage.getItem(storageKey);
            if (value === null) return true;
            return value === '1';
        } catch (_) {
            return true;
        }
    }

    function writeMode(enabled) {
        try {
            localStorage.setItem(storageKey, enabled ? '1' : '0');
        } catch (_) {
            // ignore storage failures
        }
    }

    function setButtonState(enabled) {
        if (!globalToggleBtn) return;
        globalToggleBtn.setAttribute('aria-pressed', enabled ? 'true' : 'false');
        globalToggleBtn.classList.toggle('btn-outline-info', enabled);
        globalToggleBtn.classList.toggle('btn-outline-secondary', !enabled);
        globalToggleBtn.title = enabled ? 'Beginner help is ON' : 'Beginner help is OFF';
        const label = globalToggleBtn.querySelector('.help-label');
        if (label) {
            label.textContent = enabled ? 'Beginner Help On' : 'Beginner Help Off';
        }
    }

    function setPageCheckboxState(enabled) {
        if (!pageToggleCheckbox) return;
        pageToggleCheckbox.checked = enabled;
    }

    function setPanelExpanded(panel, expanded) {
        const content = panel.querySelector('[data-help-content]');
        const toggle = panel.querySelector('[data-help-toggle]');
        if (content) {
            content.classList.toggle('d-none', !expanded);
        }
        if (toggle) {
            toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            toggle.setAttribute('title', expanded ? 'Hide help' : 'Show help');
            const icon = toggle.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-circle-info', !expanded);
                icon.classList.toggle('fa-circle-xmark', expanded);
            }
        }
        panel.dataset.helpExpanded = expanded ? 'true' : 'false';
    }

    function setLegacyHelpBlockExpanded(block, expanded) {
        const toggleId = block.dataset.helpToggleId;
        const toggle = toggleId ? document.getElementById(toggleId) : null;

        block.classList.toggle('d-none', !expanded);
        block.dataset.helpExpanded = expanded ? 'true' : 'false';

        if (toggle) {
            toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            toggle.title = expanded ? 'Hide help' : 'Show help';
            const icon = toggle.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-circle-info', !expanded);
                icon.classList.toggle('fa-circle-xmark', expanded);
            }
        }
    }

    function ensureLegacyHelpBlockToggles() {
        document.querySelectorAll('.beginner-help-block').forEach((block, index) => {
            if (block.dataset.helpEnhanced === 'true') {
                return;
            }

            const toggleId = `beginnerHelpToggle-${index + 1}`;
            const controls = document.createElement('div');
            controls.className = 'beginner-help-inline-controls';
            controls.innerHTML = `
                <button type="button" class="beginner-help-inline-toggle" id="${toggleId}" aria-expanded="true" title="Hide help">
                    <i class="fas fa-circle-xmark"></i>
                </button>
            `;

            block.insertBefore(controls, block.firstChild);
            block.dataset.helpEnhanced = 'true';
            block.dataset.helpToggleId = toggleId;

            const toggle = document.getElementById(toggleId);
            if (toggle) {
                toggle.addEventListener('click', () => {
                    const isExpanded = block.dataset.helpExpanded === 'true';
                    setLegacyHelpBlockExpanded(block, !isExpanded);
                });
            }
        });
    }

    function applyLegacyHelpBlocks(enabled) {
        ensureLegacyHelpBlockToggles();
        document.querySelectorAll('.beginner-help-block').forEach(block => {
            const explicit = block.dataset.helpExpanded;
            const expanded = explicit === 'true' || (explicit !== 'false' && enabled);
            setLegacyHelpBlockExpanded(block, expanded);
        });
    }

    function applyHelpPanels(enabled) {
        document.querySelectorAll('[data-help-panel]').forEach(panel => {
            const explicit = panel.dataset.helpExpanded;
            const expanded = explicit === 'true' || (explicit !== 'false' && enabled);
            setPanelExpanded(panel, expanded);
        });
    }

    function applyMode(enabled, persist = true) {
        if (persist) {
            writeMode(enabled);
        }
        document.documentElement.setAttribute('data-beginner-help-mode', enabled ? 'on' : 'off');
        window.prismBeginnerHelpMode = enabled;
        setButtonState(enabled);
        setPageCheckboxState(enabled);
        applyHelpPanels(enabled);
        applyLegacyHelpBlocks(enabled);
        if (enabled) {
            renderInlineFieldHints();
        } else {
            clearInlineFieldHints();
        }

        window.dispatchEvent(new CustomEvent('prism-beginner-help-changed', {
            detail: { enabled }
        }));
    }

    document.querySelectorAll('[data-help-panel] [data-help-toggle]').forEach(toggle => {
        toggle.addEventListener('click', () => {
            const panel = toggle.closest('[data-help-panel]');
            if (!panel) return;
            const isExpanded = panel.dataset.helpExpanded === 'true';
            setPanelExpanded(panel, !isExpanded);
        });
    });

    ensureLegacyHelpBlockToggles();
    bindInlineHintRefresh();

    if (globalToggleBtn) {
        globalToggleBtn.addEventListener('click', () => {
            const enabled = !(window.prismBeginnerHelpMode === true);
            applyMode(enabled, true);
        });
    }

    if (pageToggleCheckbox) {
        pageToggleCheckbox.addEventListener('change', () => {
            applyMode(Boolean(pageToggleCheckbox.checked), true);
        });
    }

    applyMode(readMode(), false);
});
