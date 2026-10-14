import { browseFileWithFallback, isProjectJsonPath } from '../../shared/path-picker.js';

export function initProjectFileBrowser({ fetchWithApiFallback }) {
    const browseExistingPath = document.getElementById('browseExistingPath');
    if (!browseExistingPath) {
        return;
    }

    browseExistingPath.addEventListener('click', async function() {
        const existingInput = document.getElementById('existingPath');

        try {
            const pickedPath = await browseFileWithFallback(fetchWithApiFallback, {
                title: 'Select project.json',
                confirmLabel: 'Use This File',
                extensions: '.json',
                startPath: existingInput && existingInput.value ? existingInput.value : '',
            });
            if (!pickedPath) return;

            if (!isProjectJsonPath(pickedPath)) {
                alert('Please select a file named project.json.');
                return;
            }
            if (existingInput) {
                existingInput.value = pickedPath;
                existingInput.dispatchEvent(new Event('input', { bubbles: true }));
            }
        } catch (error) {
            console.error('Project file picker error:', error);
            alert('Failed to open project picker. Please enter path manually.');
        }
    });
}
