export function createSurveyValueOffsetEditorAdapter({
    surveyValueOffsetEditorController,
} = {}) {
    function applyAdvancedOptionsState() {
        return surveyValueOffsetEditorController.applyAdvancedOptionsState();
    }

    function createTaskValueOffsetRow(task = '', offset = null) {
        return surveyValueOffsetEditorController.createTaskValueOffsetRow(task, offset);
    }

    function getAvailableSurveyTasksForValueOffsets() {
        return surveyValueOffsetEditorController.getAvailableSurveyTasksForValueOffsets();
    }

    function getTaskValueOffsetMapFromEditorState() {
        return surveyValueOffsetEditorController.getTaskValueOffsetMapFromEditorState();
    }

    function getCurrentTaskValueOffsetSelectionSignature() {
        return surveyValueOffsetEditorController.getCurrentTaskValueOffsetSelectionSignature();
    }

    function hasManualTaskValueOffsets() {
        return surveyValueOffsetEditorController.hasManualTaskValueOffsets();
    }

    function hasIncompleteTaskValueOffsetRows() {
        return surveyValueOffsetEditorController.hasIncompleteTaskValueOffsetRows();
    }

    function hasAppliedTaskValueOffsetSelections() {
        return surveyValueOffsetEditorController.hasAppliedTaskValueOffsetSelections();
    }

    function updateTaskValueOffsetApplyState() {
        return surveyValueOffsetEditorController.updateTaskValueOffsetApplyState();
    }

    function getPreferredTaskValueOffsetTask() {
        return surveyValueOffsetEditorController.getPreferredTaskValueOffsetTask();
    }

    function syncTaskValueOffsetTextFromState() {
        return surveyValueOffsetEditorController.syncTaskValueOffsetTextFromState();
    }

    function setTaskValueOffsetEditorStateFromText(rawText) {
        return surveyValueOffsetEditorController.setTaskValueOffsetEditorStateFromText(rawText);
    }

    function clearTaskValueOffsetEditorState() {
        return surveyValueOffsetEditorController.clearTaskValueOffsetEditorState();
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

    function handleTaskValueOffsetEditorChanged() {
        return surveyValueOffsetEditorController.handleTaskValueOffsetEditorChanged();
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
        createTaskValueOffsetRow,
        getAvailableSurveyTasksForValueOffsets,
        getTaskValueOffsetMapFromEditorState,
        getCurrentTaskValueOffsetSelectionSignature,
        hasManualTaskValueOffsets,
        hasIncompleteTaskValueOffsetRows,
        hasAppliedTaskValueOffsetSelections,
        updateTaskValueOffsetApplyState,
        getPreferredTaskValueOffsetTask,
        syncTaskValueOffsetTextFromState,
        setTaskValueOffsetEditorStateFromText,
        clearTaskValueOffsetEditorState,
        ensureTaskValueOffsetEditorRow,
        focusTaskValueOffsetEditor,
        renderTaskValueOffsetEditor,
        handleTaskValueOffsetEditorChanged,
        clearManualValueOffsetAdvice,
        handleApplyTaskValueOffsetsClick,
        getManualTaskValueOffsets,
    };
}
