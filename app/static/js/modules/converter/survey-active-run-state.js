export function createSurveyActiveRunState() {
    let activeRunAbortController = null;
    let activeRunMode = null;
    let activeRunCancelledByUser = false;

    function setActiveSurveyRun(mode, controller) {
        activeRunMode = mode;
        activeRunAbortController = controller;
        activeRunCancelledByUser = false;
    }

    function clearActiveSurveyRun(mode = null) {
        if (mode && activeRunMode && activeRunMode !== mode) {
            return;
        }
        activeRunMode = null;
        activeRunAbortController = null;
        activeRunCancelledByUser = false;
    }

    function cancelActiveSurveyRun() {
        if (!activeRunAbortController) {
            return false;
        }
        activeRunCancelledByUser = true;
        activeRunAbortController.abort();
        return true;
    }

    function getActiveRunAbortController() {
        return activeRunAbortController;
    }

    function getActiveRunMode() {
        return activeRunMode;
    }

    function getActiveRunCancelledByUser() {
        return activeRunCancelledByUser;
    }

    return {
        setActiveSurveyRun,
        clearActiveSurveyRun,
        cancelActiveSurveyRun,
        getActiveRunAbortController,
        getActiveRunMode,
        getActiveRunCancelledByUser,
    };
}
