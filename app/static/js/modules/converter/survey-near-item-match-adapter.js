export function createSurveyNearItemMatchAdapter({
    getSurveyNearItemMatchReviewController = () => null,
} = {}) {
    const getNearItemMatchReviewController = () => {
        const controller = getSurveyNearItemMatchReviewController();
        return controller && typeof controller === 'object' ? controller : null;
    };

    function collectNearMatchCandidates(payload) {
        const nearItemMatchReviewController = getNearItemMatchReviewController();
        if (!nearItemMatchReviewController) {
            return [];
        }
        return nearItemMatchReviewController.collectNearMatchCandidates(payload);
    }

    function buildNearMatchConfirmationMessage(payload, actionLabel) {
        const nearItemMatchReviewController = getNearItemMatchReviewController();
        if (!nearItemMatchReviewController) {
            return '';
        }
        return nearItemMatchReviewController.buildNearMatchConfirmationMessage(payload, actionLabel);
    }

    function promptNearMatchSelection(payload, actionLabel) {
        const nearItemMatchReviewController = getNearItemMatchReviewController();
        if (!nearItemMatchReviewController) {
            return Promise.resolve({ approved: false, selectedTasks: [], selectedCandidateCount: 0 });
        }
        return nearItemMatchReviewController.promptNearMatchSelection(payload, actionLabel);
    }

    return {
        collectNearMatchCandidates,
        buildNearMatchConfirmationMessage,
        promptNearMatchSelection,
    };
}
