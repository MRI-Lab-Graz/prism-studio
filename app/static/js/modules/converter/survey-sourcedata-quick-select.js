export function createSurveySourcedataQuickSelectController({
    sourcedataQuickSelect,
    sourcedataFileSelect,
    convertExcelFile,
    convertError,
    resolveCurrentProjectPath,
    onProjectChanged,
}) {
    let requestToken = 0;
    let sourcedataQuickSelectEl = sourcedataQuickSelect || null;
    let sourcedataFileSelectEl = sourcedataFileSelect || null;

    function ensureElements() {
        if (sourcedataQuickSelectEl && sourcedataFileSelectEl) {
            return;
        }
        if (!convertExcelFile) {
            return;
        }

        const pickerContainer = convertExcelFile.closest('.studio-file-picker');
        if (pickerContainer) {
            sourcedataQuickSelectEl = sourcedataQuickSelectEl || pickerContainer.querySelector('#sourcedataQuickSelect');
            sourcedataFileSelectEl = sourcedataFileSelectEl || pickerContainer.querySelector('#sourcedataFileSelect');
        }

        if (sourcedataQuickSelectEl && sourcedataFileSelectEl) {
            return;
        }

        const inputGroup = convertExcelFile.closest('.input-group');
        if (!inputGroup || !inputGroup.parentElement) {
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.id = 'sourcedataQuickSelect';
        wrapper.className = 'd-none mb-2';
        wrapper.innerHTML = `
            <div class="input-group input-group-sm">
                <span class="input-group-text bg-light"><i class="fas fa-folder-open text-muted"></i></span>
                <select class="form-select form-select-sm" id="sourcedataFileSelect">
                    <option value="">Load from sourcedata/...</option>
                </select>
            </div>
        `;

        inputGroup.parentElement.insertBefore(wrapper, inputGroup);
        sourcedataQuickSelectEl = wrapper;
        sourcedataFileSelectEl = wrapper.querySelector('#sourcedataFileSelect');
    }

    function resetOptions() {
        ensureElements();
        if (!sourcedataFileSelectEl) {
            return;
        }
        sourcedataFileSelectEl.value = '';
        while (sourcedataFileSelectEl.options.length > 1) {
            sourcedataFileSelectEl.remove(1);
        }
    }

    function setPlaceholder(label, { disabled = true } = {}) {
        ensureElements();
        if (!sourcedataQuickSelectEl || !sourcedataFileSelectEl) {
            return;
        }

        sourcedataQuickSelectEl.classList.remove('d-none');
        resetOptions();

        let placeholderOption = sourcedataFileSelectEl.options[0];
        if (!placeholderOption) {
            placeholderOption = document.createElement('option');
            sourcedataFileSelectEl.appendChild(placeholderOption);
        }

        placeholderOption.value = '';
        placeholderOption.textContent = label;
        placeholderOption.disabled = disabled;
        sourcedataFileSelectEl.selectedIndex = 0;
        sourcedataFileSelectEl.disabled = disabled;
    }

    function refresh(projectPath = resolveCurrentProjectPath()) {
        ensureElements();
        if (!sourcedataQuickSelectEl || !sourcedataFileSelectEl) {
            return;
        }

        const previousValue = sourcedataFileSelectEl.value;
        const activeRequestToken = ++requestToken;
        setPlaceholder('Loading sourcedata files...', {
            disabled: true,
        });

        const effectiveProjectPath = String(projectPath || '').trim();
        const endpoint = effectiveProjectPath
            ? `/api/projects/sourcedata-files?project_path=${encodeURIComponent(effectiveProjectPath)}`
            : '/api/projects/sourcedata-files';

        fetch(endpoint)
            .then((response) => response.json())
            .then((data) => {
                if (activeRequestToken !== requestToken) {
                    return;
                }

                if (data.sourcedata_exists && data.files && data.files.length > 0) {
                    sourcedataQuickSelectEl.classList.remove('d-none');
                    resetOptions();
                    sourcedataFileSelectEl.disabled = false;

                    const placeholderOption = sourcedataFileSelectEl.options[0];
                    if (placeholderOption) {
                        placeholderOption.textContent = 'Load from sourcedata/...';
                        placeholderOption.disabled = false;
                    }

                    data.files.forEach((entry) => {
                        const option = document.createElement('option');
                        option.value = entry.name;
                        const sizeKB = (entry.size / 1024).toFixed(1);
                        option.textContent = `${entry.name} (${sizeKB} KB)`;
                        sourcedataFileSelectEl.appendChild(option);
                    });

                    if (previousValue && Array.from(sourcedataFileSelectEl.options).some((option) => option.value === previousValue)) {
                        sourcedataFileSelectEl.value = previousValue;
                    }
                } else if (data.sourcedata_exists) {
                    setPlaceholder('No survey files found in sourcedata/', {
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

    function clearSelectedFile() {
        ensureElements();
        if (!sourcedataFileSelectEl) {
            return;
        }
        sourcedataFileSelectEl.value = '';
    }

    function initialize() {
        ensureElements();
        if (!sourcedataQuickSelectEl || !sourcedataFileSelectEl) {
            return;
        }

        refresh();

        sourcedataFileSelectEl.addEventListener('change', async function handleSourcedataFileChange() {
            const filename = this.value;
            if (!filename) {
                return;
            }

            try {
                const currentProjectPath = resolveCurrentProjectPath();
                if (!currentProjectPath) {
                    throw new Error('No project selected');
                }

                const response = await fetch(`/api/projects/sourcedata-file?name=${encodeURIComponent(filename)}&project_path=${encodeURIComponent(currentProjectPath)}`);
                if (!response.ok) {
                    throw new Error('Failed to load file');
                }
                const blob = await response.blob();
                const file = new File([blob], filename, { type: blob.type });
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                convertExcelFile.files = dataTransfer.files;
                convertExcelFile.dispatchEvent(new Event('change', { bubbles: true }));
            } catch (error) {
                console.error('Failed to load sourcedata file:', error);
                convertError.textContent = `Failed to load ${filename} from sourcedata.`;
                convertError.classList.remove('d-none');
            }
        });

        window.addEventListener('prism-project-changed', function handleProjectChanged() {
            refresh();
            if (typeof onProjectChanged === 'function') {
                onProjectChanged();
            }
        });
    }

    return {
        initialize,
        refresh,
        clearSelectedFile,
    };
}
