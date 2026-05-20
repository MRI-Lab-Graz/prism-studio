export function initProjectSelectionController({
    fetchWithApiFallback,
    getCurrentProjectState,
    applyCurrentProject,
    hasUnsavedStudyMetadataChanges,
    isStudyMetadataBusy,
    clearCreateResult,
    resetCreateTargetStatusChecks,
    resetStudyMetadataForm,
    showStudyMetadataCard,
}) {
    function setCurrentProjectBannerVisibility(type) {
        const banner = document.getElementById('currentProjectBanner');
        if (!banner) return;
        banner.style.display = (type === 'create') ? 'none' : '';
    }

    function hasUnsavedNewProjectDraft() {
        const createForm = document.getElementById('createProjectForm');
        const metadataForm = document.getElementById('studyMetadataForm');

        const forms = [createForm, metadataForm].filter(Boolean);
        if (!forms.length) return false;

        for (const form of forms) {
            const fields = form.querySelectorAll('input, textarea, select');
            for (const field of fields) {
                if (field.type === 'hidden') {
                    continue;
                }

                if (field.tagName === 'SELECT') {
                    const options = Array.from(field.options || []);
                    if (options.some((option) => option.selected !== option.defaultSelected)) {
                        return true;
                    }
                    continue;
                }

                if (field.type === 'checkbox' || field.type === 'radio') {
                    if (field.checked !== field.defaultChecked) return true;
                    continue;
                }

                if ((field.value || '').trim() !== (field.defaultValue || '').trim()) {
                    return true;
                }
            }
        }

        const ethicsChoice = document.getElementById('metadataEthicsApproved')?.value || '';
        const fundingChoice = document.getElementById('metadataFundingDeclared')?.value || '';
        return Boolean(ethicsChoice || fundingChoice);
    }

    function confirmProjectContextChange(actionLabel = 'continue', targetPath = '') {
        const normalizedTargetPath = String(targetPath || '').trim();
        const normalizedCurrentPath = String(getCurrentProjectState().path || '').trim();

        if (normalizedTargetPath && normalizedCurrentPath && normalizedTargetPath === normalizedCurrentPath) {
            return true;
        }

        if (isStudyMetadataBusy()) {
            alert('Please wait until project metadata finishes loading or saving before switching projects.');
            return false;
        }

        if (normalizedCurrentPath && hasUnsavedStudyMetadataChanges()) {
            return confirm(
                '⚠️ Unsaved project metadata changes detected.\n\n' +
                `If you ${actionLabel}, the current changes will be lost.\n\n` +
                'Do you want to continue?'
            );
        }

        const createSection = document.getElementById('section-create');
        const createAlreadyActive = createSection && createSection.classList.contains('active');
        if (!normalizedCurrentPath && createAlreadyActive && hasUnsavedNewProjectDraft()) {
            return confirm(
                '⚠️ Unsaved New Project data detected.\n\n' +
                `If you ${actionLabel}, the current project and study metadata draft will be lost.\n\n` +
                'Do you want to continue?'
            );
        }

        return true;
    }

    function clearCurrentProjectForNewDraft() {
        applyCurrentProject({ path: '', name: '', icon: '' });

        // Keep backend session in sync to avoid accidental writes to a stale project.
        fetchWithApiFallback('/api/projects/current', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: '' })
        })
            .then(async (response) => {
                const data = await response.json().catch(() => ({}));
                if (!response.ok || !data || typeof data !== 'object') {
                    return;
                }

                const autosave = data.autosave_previous;
                if (!autosave || !autosave.attempted || autosave.success) {
                    return;
                }

                const detail = String(
                    autosave.error
                    || autosave.message
                    || 'DataLad auto-save failed while clearing the previous project.'
                ).trim();
                if (!detail) {
                    return;
                }

                window.setNavbarDataladFeedback?.(detail, 'danger', 'Auto-save failed');
            })
            .catch(() => {
                // UI state remains source of truth for this interaction.
            });
    }

    function selectProjectType(type) {
        const currentProjectPath = String(getCurrentProjectState().path || '').trim();

        if (type === 'create' && currentProjectPath) {
            const confirmSwitch = confirm(
                '⚠️ You are editing an existing project.\n\n' +
                'If you switch to "New Project" without saving, any changes will be lost.\n\n' +
                'Are you sure you want to continue?'
            );
            if (!confirmSwitch) {
                return;
            }

            clearCurrentProjectForNewDraft();
        }

        const createSection = document.getElementById('section-create');
        const createAlreadyActive = createSection && createSection.classList.contains('active');
        if (type === 'create' && !currentProjectPath && createAlreadyActive && hasUnsavedNewProjectDraft()) {
            const confirmReset = confirm(
                '⚠️ Unsaved New Project data detected.\n\n' +
                'Clicking "New Project" again will clear all currently entered project and study metadata fields.\n\n' +
                'Do you want to discard these unsaved changes?'
            );
            if (!confirmReset) {
                return;
            }
        }

        document.querySelectorAll('.project-card').forEach((card) => {
            card.classList.remove('active');
        });
        document.getElementById('card-' + type)?.classList.add('active');

        document.querySelectorAll('.form-section').forEach((section) => {
            section.classList.remove('active');
        });
        document.getElementById('section-' + type)?.classList.add('active');

        const createBtnContainer = document.getElementById('saveStudyMetadataSection');
        if (createBtnContainer) {
            createBtnContainer.style.display = (type === 'create') ? '' : 'none';
        }

        if (type === 'create') {
            clearCreateResult();
            resetCreateTargetStatusChecks();
            const projectNameInput = document.getElementById('projectName');
            if (projectNameInput) {
                projectNameInput.value = '';
                projectNameInput.classList.remove('is-invalid');
            }
            const projectPathInput = document.getElementById('projectPath');
            if (projectPathInput) {
                projectPathInput.value = '';
                projectPathInput.classList.remove('is-invalid');
            }
            const projectNameError = document.getElementById('projectNameError');
            if (projectNameError) projectNameError.textContent = '';
            resetStudyMetadataForm();

            if (window.resetAllBadges) {
                window.resetAllBadges();
            }
        }

        setCurrentProjectBannerVisibility(type);

        if (type === 'open') {
            const openProjectSection = document.getElementById('openProjectSection');
            if (openProjectSection) {
                if (window.bootstrap && typeof window.bootstrap.Collapse === 'function') {
                    const collapse = window.bootstrap.Collapse.getOrCreateInstance(openProjectSection, { toggle: false });
                    collapse.show();
                } else {
                    openProjectSection.classList.add('show');
                }
            }

            const existingPathInput = document.getElementById('existingPath');
            if (existingPathInput) {
                existingPathInput.focus();
                existingPathInput.select();
            }
        }

        if (type === 'create') {
            const projectNameField = document.getElementById('projectName');
            if (projectNameField) {
                projectNameField.focus();
            }
        }

        showStudyMetadataCard();
    }

    function bindProjectTypeCard(cardId, type) {
        const card = document.getElementById(cardId);
        if (!card) {
            return;
        }

        card.addEventListener('click', () => selectProjectType(type));
        card.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                selectProjectType(type);
            }
        });
    }

    function initProjectSelectionUi() {
        const createSection = document.getElementById('section-create');
        const openSection = document.getElementById('section-open');
        if (createSection?.classList.contains('active')) {
            setCurrentProjectBannerVisibility('create');
        } else if (openSection?.classList.contains('active')) {
            setCurrentProjectBannerVisibility('open');
        }

        bindProjectTypeCard('card-create', 'create');
        bindProjectTypeCard('card-open', 'open');
        bindProjectTypeCard('card-init-bids', 'init-bids');
    }

    return {
        confirmProjectContextChange,
        selectProjectType,
        initProjectSelectionUi,
    };
}