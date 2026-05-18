import { browseFolderWithFallback } from '../../shared/path-picker.js';

function bindFolderPickerButton({
    buttonId,
    inputId,
    title,
    confirmLabel,
    fetchWithApiFallback,
    onSelected,
}) {
    const button = document.getElementById(buttonId);
    if (!button) {
        return;
    }

    button.addEventListener('click', async function() {
        try {
            const input = document.getElementById(inputId);
            const selectedPath = await browseFolderWithFallback(fetchWithApiFallback, {
                title,
                confirmLabel,
                startPath: input?.value || ''
            });

            if (selectedPath) {
                if (input) {
                    input.value = selectedPath;
                }
                if (typeof onSelected === 'function') {
                    onSelected(selectedPath, input);
                }
            }
        } catch (error) {
            console.error('Browse error:', error);
            alert('Failed to open folder picker. Please enter path manually.');
        }
    });
}

export function initProjectPathPickers({ fetchWithApiFallback, validateProjectField, clearCreateResult }) {
    bindFolderPickerButton({
        buttonId: 'browseGlobalLibrary',
        inputId: 'globalLibraryPath',
        title: 'Select Global Survey Template Library',
        confirmLabel: 'Use This Folder',
        fetchWithApiFallback,
    });

    bindFolderPickerButton({
        buttonId: 'browseGlobalRecipes',
        inputId: 'globalRecipesPath',
        title: 'Select Global Recipe Library',
        confirmLabel: 'Use This Folder',
        fetchWithApiFallback,
    });

    bindFolderPickerButton({
        buttonId: 'browseProjectPath',
        inputId: 'projectPath',
        title: 'Select Project Location',
        confirmLabel: 'Use This Folder',
        fetchWithApiFallback,
        onSelected(_selectedPath, input) {
            if (!input) {
                return;
            }
            validateProjectField('projectPath');
            clearCreateResult();
            input.dispatchEvent(new Event('change', { bubbles: true }));
        }
    });

    bindFolderPickerButton({
        buttonId: 'browseInitBidsPath',
        inputId: 'initBidsPath',
        title: 'Select BIDS Dataset Root',
        confirmLabel: 'Use This Folder',
        fetchWithApiFallback,
    });
}