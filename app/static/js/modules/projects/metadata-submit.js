export function createStudyMetadataSubmitController({
    getCurrentProjectPath,
    getSubmitInFlight,
}) {
    function requestStudyMetadataSubmit(submitIntent = 'standard') {
        const form = document.getElementById('studyMetadataForm');
        if (!form) return;

        const preferredSubmitter = document.getElementById('createProjectSubmitBtn');
        form.dataset.submitIntent = submitIntent;

        const active = document.activeElement;
        if (active instanceof HTMLElement && form.contains(active) && typeof active.blur === 'function') {
            active.blur();
        }

        window.requestAnimationFrame(() => {
            if (getSubmitInFlight()) {
                return;
            }
            if (typeof form.requestSubmit === 'function' && preferredSubmitter) {
                form.requestSubmit(preferredSubmitter);
                return;
            }

            form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        });
    }

    function requestMetadataRepairSave() {
        requestStudyMetadataSubmit('standard');
    }

    function bindProjectBoxSubmitBridge(button, submitIntent) {
        if (!button || button.dataset.bound === '1') {
            return;
        }

        button.dataset.bound = '1';
        let pointerTriggeredSubmit = false;

        const triggerSubmit = () => {
            requestStudyMetadataSubmit(submitIntent);
        };

        button.addEventListener('pointerdown', (event) => {
            if (event.button !== 0) return;
            event.preventDefault();
            pointerTriggeredSubmit = true;
            triggerSubmit();
        });

        button.addEventListener('click', (event) => {
            event.preventDefault();
            if (pointerTriggeredSubmit) {
                pointerTriggeredSubmit = false;
                return;
            }
            triggerSubmit();
        });
    }

    function bindProjectBoxActionButtons() {
        const projectBoxSaveBtn = document.getElementById('projectBoxSaveBtn');
        bindProjectBoxSubmitBridge(projectBoxSaveBtn, 'standard');

        const projectBoxPreliminarySaveBtn = document.getElementById('projectBoxPreliminarySaveBtn');
        bindProjectBoxSubmitBridge(projectBoxPreliminarySaveBtn, 'preliminary');
    }

    function shouldSubmitStudyMetadataFromPrimaryButton() {
        const createSection = document.getElementById('section-create');
        const createActive = Boolean(createSection && createSection.classList.contains('active'));
        return !createActive && Boolean(getCurrentProjectPath());
    }

    function initPrimaryStudyMetadataSubmitButton() {
        const studyMetadataForm = document.getElementById('studyMetadataForm');
        const createProjectSubmitBtn = document.getElementById('createProjectSubmitBtn');
        if (!studyMetadataForm || !createProjectSubmitBtn) {
            return;
        }

        if (createProjectSubmitBtn.dataset.submitBridgeBound === '1') {
            return;
        }
        createProjectSubmitBtn.dataset.submitBridgeBound = '1';

        let pointerTriggeredSubmit = false;

        const triggerSubmit = () => {
            if (!shouldSubmitStudyMetadataFromPrimaryButton()) {
                return;
            }
            if (getSubmitInFlight()) return;

            const active = document.activeElement;
            const activeInsideForm =
                active instanceof HTMLElement
                && active !== createProjectSubmitBtn
                && studyMetadataForm.contains(active);

            if (activeInsideForm && typeof active.blur === 'function') {
                active.blur();
            }

            window.requestAnimationFrame(() => {
                if (getSubmitInFlight()) return;
                if (typeof studyMetadataForm.requestSubmit === 'function') {
                    studyMetadataForm.requestSubmit(createProjectSubmitBtn);
                    return;
                }

                studyMetadataForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            });
        };

        createProjectSubmitBtn.addEventListener('pointerdown', (event) => {
            if (event.button !== 0) return;
            if (!shouldSubmitStudyMetadataFromPrimaryButton()) {
                return;
            }
            event.preventDefault();
            pointerTriggeredSubmit = true;
            triggerSubmit();
        });

        createProjectSubmitBtn.addEventListener('click', (event) => {
            if (!shouldSubmitStudyMetadataFromPrimaryButton()) {
                return;
            }
            event.preventDefault();
            if (pointerTriggeredSubmit) {
                pointerTriggeredSubmit = false;
                return;
            }
            triggerSubmit();
        });
    }

    return {
        bindProjectBoxActionButtons,
        initPrimaryStudyMetadataSubmitButton,
        requestMetadataRepairSave,
    };
}