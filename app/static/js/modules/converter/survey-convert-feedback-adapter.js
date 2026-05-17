export function createSurveyConvertFeedbackAdapter({
    getSurveyConvertFeedbackController = () => null,
} = {}) {
    const getFeedbackController = () => {
        const controller = getSurveyConvertFeedbackController();
        return controller && typeof controller === 'object' ? controller : null;
    };

    function getProjectSaveSummary(data) {
        const feedbackController = getFeedbackController();
        if (!feedbackController) {
            return { target: 'the active project', countNote: '' };
        }
        return feedbackController.getProjectSaveSummary(data);
    }

    function openConverterTab(target) {
        const feedbackController = getFeedbackController();
        if (!feedbackController) {
            return false;
        }
        return feedbackController.openConverterTab(target);
    }

    function showConvertInfoMessage(message, options = {}) {
        const feedbackController = getFeedbackController();
        if (!feedbackController) {
            return;
        }
        feedbackController.showConvertInfoMessage(message, options);
    }

    function getParticipantRegistryWarning(payload) {
        const feedbackController = getFeedbackController();
        if (!feedbackController) {
            return null;
        }
        return feedbackController.getParticipantRegistryWarning(payload);
    }

    function showParticipantRegistryWarning(messagePrefix, warning) {
        const feedbackController = getFeedbackController();
        if (!feedbackController) {
            return;
        }
        feedbackController.showParticipantRegistryWarning(messagePrefix, warning);
    }

    return {
        getProjectSaveSummary,
        openConverterTab,
        showConvertInfoMessage,
        getParticipantRegistryWarning,
        showParticipantRegistryWarning,
    };
}
