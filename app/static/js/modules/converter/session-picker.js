import { fetchWithApiFallback } from '../../shared/api.js';

const CUSTOM_INPUT_IDS_BY_SELECT_ID = {
    convertSessionSelect: 'convertSessionCustom',
    biometricsSessionSelect: 'biometricsSessionCustom',
};

export function getSessionInputValue(selectEl, customEl) {
    const selectedValue = selectEl ? selectEl.value.trim() : '';
    const customValue = customEl ? customEl.value.trim() : '';
    return selectedValue || customValue;
}

export function createConverterSessionPickerController({
    resolveCurrentProjectPath,
}) {
    let sessionPickerRequestToken = 0;

    function hasManualCustomValue(selectEl) {
        if (!selectEl) {
            return false;
        }

        const customInputId = CUSTOM_INPUT_IDS_BY_SELECT_ID[selectEl.id] || '';
        if (!customInputId) {
            return false;
        }

        const customInput = document.getElementById(customInputId);
        return Boolean(customInput && String(customInput.value || '').trim());
    }

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

                    const previousValue = previousSelections.get(selectEl) || '';
                    const restoredPrevious = previousValue
                        && Array.from(selectEl.options).some((option) => option.value === previousValue);
                    if (restoredPrevious) {
                        selectEl.value = previousValue;
                        return;
                    }

                    if (sessions.length === 1 && !hasManualCustomValue(selectEl)) {
                        const onlySessionValue = String((sessions[0] && sessions[0].id) || '').replace(/^ses-/, '');
                        if (onlySessionValue && Array.from(selectEl.options).some((option) => option.value === onlySessionValue)) {
                            selectEl.value = onlySessionValue;
                        }
                    }
                });
            })
            .catch(() => {});
    }

    return {
        populateSessionPickers,
    };
}