export function createSurveyTemplateRenderAdapter({
    getSurveyTemplateResultsController = () => null,
    getParticipantsMetadataController = () => null,
} = {}) {
    function displayTemplateSingle(data) {
        return getSurveyTemplateResultsController()?.displayTemplateSingle(data);
    }

    function displayTemplateGroups(data) {
        return getSurveyTemplateResultsController()?.displayTemplateGroups(data);
    }

    function displayTemplateQuestions(data) {
        return getSurveyTemplateResultsController()?.displayTemplateQuestions(data);
    }

    function displayParticipantMetadataSection(data) {
        return getParticipantsMetadataController()?.displayParticipantMetadataSection(data);
    }

    return {
        displayTemplateSingle,
        displayTemplateGroups,
        displayTemplateQuestions,
        displayParticipantMetadataSection,
    };
}
