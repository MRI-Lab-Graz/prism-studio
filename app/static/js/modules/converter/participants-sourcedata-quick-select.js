import { fetchWithApiFallback } from '../../shared/api.js';
import { resolveCurrentProjectPath } from '../../shared/project-state.js';

export function createParticipantsSourcedataQuickSelectController({
    getFileInput,
    clearServerFilePath,
    onClearSelectedFile,
    onResetPanelState,
    onUpdateButtonState,
    setErrorMessage,
}) {
    let requestToken = 0;
    let quickSelectEl = null;
    let fileSelectEl = null;

    function getCurrentFileInput() {
        return typeof getFileInput === 'function' ? getFileInput() : null;
    }

    function clearServerPath() {
        if (typeof clearServerFilePath === 'function') {
            clearServerFilePath();
        }
    }

    function clearSelectedFile() {
        if (fileSelectEl) {
            fileSelectEl.value = '';
        }
    }

    function resetPanelState() {
        if (typeof onResetPanelState === 'function') {
            onResetPanelState();
        }
    }

    function updateButtonState() {
        if (typeof onUpdateButtonState === 'function') {
            onUpdateButtonState();
        }
    }

    function reportLoadError(message) {
        if (typeof setErrorMessage === 'function') {
            setErrorMessage(message);
        }
    }

    function ensureElements() {
        if (quickSelectEl && fileSelectEl) {
            return true;
        }

        const fileInput = getCurrentFileInput();
        if (!fileInput) {
            return false;
        }

        const pickerContainer = fileInput.closest('.studio-file-picker');
        if (!pickerContainer) {
            return false;
        }

        quickSelectEl = pickerContainer.querySelector('#participantsSourcedataQuickSelect');
        fileSelectEl = pickerContainer.querySelector('#participantsSourcedataFileSelect');

        if (quickSelectEl && fileSelectEl) {
            return true;
        }

        const inputGroup = pickerContainer.querySelector('.input-group');
        if (!inputGroup || !inputGroup.parentElement) {
            return false;
        }

        const wrapper = document.createElement('div');
        wrapper.id = 'participantsSourcedataQuickSelect';
        wrapper.className = 'd-none mb-2';
        wrapper.innerHTML = `
            <div class="input-group input-group-sm">
                <span class="input-group-text bg-light"><i class="fas fa-folder-open text-muted"></i></span>
                <select class="form-select form-select-sm" id="participantsSourcedataFileSelect">
                    <option value="">Loading sourcedata files...</option>
                </select>
            </div>
        `;

        inputGroup.parentElement.insertBefore(wrapper, inputGroup);
        quickSelectEl = wrapper;
        fileSelectEl = wrapper.querySelector('#participantsSourcedataFileSelect');
        return Boolean(quickSelectEl && fileSelectEl);
    }

    function resetQuickSelectOptions() {
        if (!ensureElements() || !fileSelectEl) {
            return;
        }

        fileSelectEl.value = '';
        while (fileSelectEl.options.length > 1) {
            fileSelectEl.remove(1);
        }
    }

    function setPlaceholder(label, { disabled = true } = {}) {
        if (!ensureElements() || !quickSelectEl || !fileSelectEl) {
            return;
        }

        quickSelectEl.classList.remove('d-none');
        resetQuickSelectOptions();

        let placeholderOption = fileSelectEl.options[0];
        if (!placeholderOption) {
            placeholderOption = document.createElement('option');
            fileSelectEl.appendChild(placeholderOption);
        }

        placeholderOption.value = '';
        placeholderOption.textContent = label;
        placeholderOption.disabled = disabled;
        fileSelectEl.selectedIndex = 0;
        fileSelectEl.disabled = disabled;
    }

    function refresh(projectPath = resolveCurrentProjectPath()) {
        if (!ensureElements() || !quickSelectEl || !fileSelectEl) {
            return;
        }

        const previousValue = fileSelectEl.value;
        const activeRequestToken = ++requestToken;
        setPlaceholder('Loading sourcedata files...', { disabled: true });

        const effectiveProjectPath = String(projectPath || '').trim();
        const endpoint = effectiveProjectPath
            ? `/api/projects/sourcedata-files?kind=participants&project_path=${encodeURIComponent(effectiveProjectPath)}`
            : '/api/projects/sourcedata-files?kind=participants';

        fetchWithApiFallback(endpoint)
            .then((response) => response.json())
            .then((data) => {
                if (activeRequestToken !== requestToken) {
                    return;
                }

                if (data.sourcedata_exists && Array.isArray(data.files) && data.files.length > 0) {
                    quickSelectEl.classList.remove('d-none');
                    resetQuickSelectOptions();
                    fileSelectEl.disabled = false;

                    const placeholderOption = fileSelectEl.options[0];
                    if (placeholderOption) {
                        placeholderOption.textContent = 'Load from sourcedata/...';
                        placeholderOption.disabled = false;
                    }

                    data.files.forEach((entry) => {
                        const option = document.createElement('option');
                        option.value = entry.name;
                        const sizeKB = (entry.size / 1024).toFixed(1);
                        option.textContent = `${entry.name} (${sizeKB} KB)`;
                        fileSelectEl.appendChild(option);
                    });

                    if (previousValue && Array.from(fileSelectEl.options).some((option) => option.value === previousValue)) {
                        fileSelectEl.value = previousValue;
                    }
                } else if (data.sourcedata_exists) {
                    setPlaceholder('No participants-compatible files found in sourcedata/', {
                        disabled: true,
                    });
                } else {
                    setPlaceholder('No sourcedata folder found for the current project', {
                        disabled: true,
                    });
                }
            })
            .catch(() => {
                if (activeRequestToken !== requestToken) {
                    return;
                }
                setPlaceholder('Could not load sourcedata files', {
                    disabled: true,
                });
            });
    }

    async function handleSelectChange() {
        const filename = String(fileSelectEl?.value || '').trim();
        if (!filename) {
            if (typeof onClearSelectedFile === 'function') {
                onClearSelectedFile();
            }
            resetPanelState();
            updateButtonState();
            return;
        }

        try {
            const currentProjectPath = resolveCurrentProjectPath();
            const endpoint = currentProjectPath
                ? `/api/projects/sourcedata-file?name=${encodeURIComponent(filename)}&project_path=${encodeURIComponent(currentProjectPath)}`
                : `/api/projects/sourcedata-file?name=${encodeURIComponent(filename)}`;

            const response = await fetchWithApiFallback(endpoint);
            if (!response.ok) {
                throw new Error('Failed to load sourcedata file');
            }

            const blob = await response.blob();
            const file = new File([blob], filename, { type: blob.type });
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);

            clearServerPath();

            const fileInput = getCurrentFileInput();
            if (!fileInput) {
                throw new Error('Participants file input not available');
            }
            fileInput.files = dataTransfer.files;
            fileInput.dispatchEvent(new Event('change', { bubbles: true }));
        } catch (_error) {
            reportLoadError(`Failed to load ${filename} from sourcedata.`);
        } finally {
            refresh();
        }
    }

    function bindChangeHandler() {
        if (!ensureElements() || !fileSelectEl) {
            return;
        }

        if (fileSelectEl.dataset.participantsSourcedataBound === '1') {
            return;
        }
        fileSelectEl.dataset.participantsSourcedataBound = '1';
        fileSelectEl.addEventListener('change', () => {
            handleSelectChange();
        });
    }

    function initialize() {
        if (!ensureElements()) {
            return false;
        }

        bindChangeHandler();
        refresh();
        return true;
    }

    return {
        clearSelectedFile,
        refresh,
        initialize,
    };
}