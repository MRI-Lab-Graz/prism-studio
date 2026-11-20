import { fetchWithApiFallback } from '../../shared/api.js';

export function getSessionInputValue(selectEl, customEl) {
    const selectedValue = selectEl ? selectEl.value.trim() : '';
    const customValue = customEl ? customEl.value.trim() : '';
    return selectedValue || customValue;
}

/** Only what the user already picked comes back: a lone existing session is no reason to preselect it. */
export function sessionToRestore(previousValue, optionValues) {
    return previousValue && optionValues.includes(previousValue) ? previousValue : '';
}

export function createConverterSessionPickerController({
    resolveCurrentProjectPath,
}) {
    let sessionPickerRequestToken = 0;

    function populateSessionPickers(projectPath = resolveCurrentProjectPath()) {
        const convertSessionSelect = document.getElementById('convertSessionSelect');
        const biometricsSessionSelect = document.getElementById('biometricsSessionSelect');
        const selects = [convertSessionSelect, biometricsSessionSelect];
        const previousSelections = new Map(
            selects.filter(Boolean).map((selectEl) => [selectEl, selectEl.value])
        );

        selects.forEach((selectEl) => {
            if (!selectEl) {
                return;
            }
            while (selectEl.options.length > 1) {
                selectEl.remove(1);
            }
            selectEl.selectedIndex = 0;
        });

        // Biometrics conversion can auto-detect a session/ses/visit column per row,
        // so unlike survey it doesn't need a prior file-detection step to offer this.
        if (biometricsSessionSelect) {
            const allOpt = document.createElement('option');
            allOpt.value = 'all';
            allOpt.textContent = '✓ All sessions (auto-detect from file)';
            biometricsSessionSelect.appendChild(allOpt);
        }

        if (!projectPath) {
            return;
        }

        const requestToken = ++sessionPickerRequestToken;
        const requestUrl = `/api/projects/sessions/declared?project_path=${encodeURIComponent(projectPath)}`;

        fetchWithApiFallback(requestUrl)
            .then((response) => response.json())
            .then((data) => {
                if (requestToken !== sessionPickerRequestToken) {
                    return;
                }

                const sessions = data.sessions || [];
                selects.forEach((selectEl) => {
                    if (!selectEl) {
                        return;
                    }

                    sessions.forEach((session) => {
                        const option = document.createElement('option');
                        option.value = session.id.replace(/^ses-/, '');
                        option.textContent = session.label !== session.id
                            ? `${session.id} — ${session.label}`
                            : session.id;
                        selectEl.appendChild(option);
                    });

                    selectEl.value = sessionToRestore(
                        previousSelections.get(selectEl) || '',
                        Array.from(selectEl.options).map((option) => option.value)
                    );
                });
            })
            .catch(() => {});
    }

    return {
        populateSessionPickers,
    };
}