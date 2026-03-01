document.addEventListener('DOMContentLoaded', () => {
    const storageKey = 'prism_beginner_help_mode';
    const globalToggleBtn = document.getElementById('globalBeginnerHelpToggle');
    const pageToggleCheckbox = document.getElementById('beginnerHelpModeToggle');

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
            controls.className = 'd-flex justify-content-end align-items-center mb-1 beginner-help-inline-controls';
            controls.innerHTML = `
                <button type="button" class="beginner-help-inline-toggle" id="${toggleId}" aria-expanded="true" title="Hide help">
                    <i class="fas fa-circle-xmark"></i>
                </button>
            `;

            block.parentNode?.insertBefore(controls, block);
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
