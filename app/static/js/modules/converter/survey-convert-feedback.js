import { activateConverterTab } from './tab-activation.js';

export function createSurveyConvertFeedbackController({
    convertInfo,
    appendLog,
}) {
    function showConvertInfoMessage(message, options = {}) {
        if (!convertInfo) {
            return;
        }

        const {
            variant = 'info',
            iconClass = 'fas fa-info-circle',
            action = null,
        } = options;

        convertInfo.classList.remove('d-none', 'alert-info', 'alert-success', 'alert-warning', 'alert-danger');
        convertInfo.classList.add('alert', `alert-${variant}`);
        convertInfo.innerHTML = '';

        const wrapper = document.createElement('div');
        if (action && action.type === 'open_converter_tab') {
            wrapper.className = 'd-flex flex-column flex-md-row align-items-md-center justify-content-between gap-2';
        }

        const messageContainer = document.createElement('div');
        const icon = document.createElement('i');
        icon.className = `${iconClass} me-2`;
        messageContainer.appendChild(icon);

        const messageText = document.createElement('span');
        messageText.textContent = String(message || '');
        messageContainer.appendChild(messageText);
        wrapper.appendChild(messageContainer);

        if (action && action.type === 'open_converter_tab') {
            const actionButton = document.createElement('button');
            actionButton.type = 'button';
            actionButton.className = 'btn btn-sm btn-outline-dark align-self-start align-self-md-center';

            const buttonIcon = document.createElement('i');
            buttonIcon.className = 'fas fa-users me-1';
            actionButton.appendChild(buttonIcon);
            actionButton.appendChild(document.createTextNode(String(action.label || 'Open')));
            actionButton.addEventListener('click', () => {
                if (!activateConverterTab(action.target, { focus: true })) {
                    appendLog('Could not open the requested converter tab.', 'warning');
                }
            });
            wrapper.appendChild(actionButton);
        }

        convertInfo.appendChild(wrapper);
        convertInfo.classList.remove('d-none');
    }

    function getProjectSaveSummary(data) {
        const outputPaths = Array.isArray(data && data.project_output_paths)
            ? data.project_output_paths.filter((value) => typeof value === 'string' && value.trim())
            : [];
        const target = (data && (data.project_output_path || outputPaths[0] || data.project_output_root)) || 'the active project';
        const outputCount = Number.isFinite(data && data.project_output_count)
            ? data.project_output_count
            : outputPaths.length;
        const countNote = outputCount > 1 ? ` (${outputCount} files)` : '';

        return { target, countNote };
    }

    function getParticipantRegistryWarning(payload) {
        if (payload && typeof payload.participant_registry_warning === 'object' && payload.participant_registry_warning) {
            return payload.participant_registry_warning;
        }

        if (payload && payload.conversion_summary && typeof payload.conversion_summary.participant_registry_warning === 'object') {
            return payload.conversion_summary.participant_registry_warning;
        }

        if (payload && payload.preview && typeof payload.preview.participant_registry_warning === 'object') {
            return payload.preview.participant_registry_warning;
        }

        const previewIssues = payload && payload.preview && Array.isArray(payload.preview.data_issues)
            ? payload.preview.data_issues
            : [];
        return previewIssues.find((issue) => issue && issue.type === 'missing_from_participants_tsv') || null;
    }

    function showParticipantRegistryWarning(messagePrefix, warning) {
        if (!warning) {
            return;
        }

        const parts = [messagePrefix, warning.message, warning.details].filter((value) => typeof value === 'string' && value.trim());
        showConvertInfoMessage(parts.join(' '), {
            variant: 'warning',
            iconClass: 'fas fa-exclamation-triangle',
            action: warning.action || null,
        });
    }

    return {
        getProjectSaveSummary,
        getParticipantRegistryWarning,
        showParticipantRegistryWarning,
    };
}
