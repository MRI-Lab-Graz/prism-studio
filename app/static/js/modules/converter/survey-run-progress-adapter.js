export function createSurveyRunProgressAdapter({
    surveyWorkflowProgressController = null,
} = {}) {
    function setSurveyRunProgress(options) {
        surveyWorkflowProgressController?.setSurveyRunProgress(options);
    }

    function hideSurveyRunProgress() {
        surveyWorkflowProgressController?.hideSurveyRunProgress();
    }

    function startSurveyRunProgress(mode) {
        surveyWorkflowProgressController?.startSurveyRunProgress(mode);
    }

    function advanceSurveyRunProgress(mode, percent, label) {
        surveyWorkflowProgressController?.advanceSurveyRunProgress(mode, percent, label);
    }

    function pauseSurveyRunProgress(mode, label) {
        surveyWorkflowProgressController?.pauseSurveyRunProgress(mode, label);
    }

    function resumeSurveyRunProgress(mode, percent, label) {
        surveyWorkflowProgressController?.resumeSurveyRunProgress(mode, percent, label);
    }

    function finishSurveyRunProgress(mode, outcome) {
        surveyWorkflowProgressController?.finishSurveyRunProgress(mode, outcome);
    }

    return {
        setSurveyRunProgress,
        hideSurveyRunProgress,
        startSurveyRunProgress,
        advanceSurveyRunProgress,
        pauseSurveyRunProgress,
        resumeSurveyRunProgress,
        finishSurveyRunProgress,
    };
}
