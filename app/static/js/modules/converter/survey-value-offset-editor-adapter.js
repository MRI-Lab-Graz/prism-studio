export function createSurveyValueOffsetEditorAdapter({
    surveyValueOffsetEditorController,
} = {}) {
    function applyAdvancedOptionsState() {
        return surveyValueOffsetEditorController.applyAdvancedOptionsState();
    }

    function hasManualTaskValueOffsets() {
        return surveyValueOffsetEditorController.hasManualTaskValueOffsets();
    }

    function hasAppliedTaskValueOffsetSelections() {
        return surveyValueOffsetEditorController.hasAppliedTaskValueOffsetSelections();
    }

    function updateTaskValueOffsetApplyState() {
        return surveyValueOffsetEditorController.updateTaskValueOffsetApplyState();
    }

    function ensureTaskValueOffsetEditorRow(task = '') {
        return surveyValueOffsetEditorController.ensureTaskValueOffsetEditorRow(task);
    }

    function focusTaskValueOffsetEditor(rowId = null) {
        return surveyValueOffsetEditorController.focusTaskValueOffsetEditor(rowId);
    }

    function renderTaskValueOffsetEditor() {
        return surveyValueOffsetEditorController.renderTaskValueOffsetEditor();
    }

    function clearManualValueOffsetAdvice() {
        return surveyValueOffsetEditorController.clearManualValueOffsetAdvice();
    }

    function handleApplyTaskValueOffsetsClick() {
        return surveyValueOffsetEditorController.handleApplyTaskValueOffsetsClick();
    }

    function getManualTaskValueOffsets() {
        return surveyValueOffsetEditorController.getManualTaskValueOffsets();
    }

    return {
        applyAdvancedOptionsState,
        hasManualTaskValueOffsets,
        hasAppliedTaskValueOffsetSelections,
        updateTaskValueOffsetApplyState,
        ensureTaskValueOffsetEditorRow,
        focusTaskValueOffsetEditor,
        renderTaskValueOffsetEditor,
        clearManualValueOffsetAdvice,
        handleApplyTaskValueOffsetsClick,
        getManualTaskValueOffsets,
    };
}
