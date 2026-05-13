import { fetchWithApiFallback } from '../../shared/api.js';

export function createSurveyTemplateGenerationController({
    convertBtn,
    convertDatasetName,
    convertError,
    convertInfo,
    conversionLog,
    conversionLogContainer,
    appendLog,
    setCurrentTemplateData,
    showTemplateResultsContainer,
    displayTemplateSingle,
    displayTemplateGroups,
    displayTemplateQuestions,
    displayParticipantMetadataSection,
    updateConvertBtn,
}) {
    async function handleTemplateGeneration(file) {
        const exportMode = document.getElementById('convertTemplateExport')?.value || 'groups';
        const taskName = document.getElementById('convertDatasetName')?.value.trim() || '';

        convertBtn.disabled = true;
        convertError.classList.add('d-none');
        convertInfo.classList.add('d-none');

        if (conversionLogContainer) {
            conversionLogContainer.classList.remove('d-none');
        }
        if (conversionLog) {
            conversionLog.innerHTML = '';
        }

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('mode', exportMode);
            if (taskName) {
                formData.append('task_name', taskName);
            }

            const response = await fetchWithApiFallback('/api/survey-generate-templates', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (data.log && Array.isArray(data.log)) {
                data.log.forEach((entry) => {
                    appendLog(entry.message, entry.type, conversionLog);
                });
            }

            if (!response.ok || data.error) {
                throw new Error(data.error || 'Template generation failed');
            }

            setCurrentTemplateData(data);
            showTemplateResultsContainer();

            if (data.mode === 'combined') {
                displayTemplateSingle(data);
            } else if (data.mode === 'groups') {
                displayTemplateGroups(data);
            } else if (data.mode === 'questions') {
                displayTemplateQuestions(data);
            }

            displayParticipantMetadataSection(data);

            convertInfo.textContent = 'Template generation complete!';
            convertInfo.classList.remove('d-none');
        } catch (err) {
            convertError.textContent = err.message;
            convertError.classList.remove('d-none');
            appendLog(`Error: ${err.message}`, 'error', conversionLog);
        } finally {
            updateConvertBtn();
        }
    }

    return {
        handleTemplateGeneration,
    };
}
