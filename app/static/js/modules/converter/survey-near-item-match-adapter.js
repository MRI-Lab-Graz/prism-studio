export function createSurveyNearItemMatchAdapter({
    getSurveyNearItemMatchReviewController = () => null,
} = {}) {
    const getNearItemMatchReviewController = () => {
        const controller = getSurveyNearItemMatchReviewController();
        return controller && typeof controller === 'object' ? controller : null;
    };

    function promptNearMatchSelection(payload, actionLabel) {
        const nearItemMatchReviewController = getNearItemMatchReviewController();
        if (!nearItemMatchReviewController) {
            return Promise.resolve({ approved: false, selectedTasks: [], selectedCandidateCount: 0 });
        }
        return nearItemMatchReviewController.promptNearMatchSelection(payload, actionLabel);
    }

    return {
        promptNearMatchSelection,
    };
}
