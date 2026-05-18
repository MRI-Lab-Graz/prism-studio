import {
    parseJsonResponse,
    summarizeServerResponseText,
} from './survey-workflow-response-utils.js';

export function createSurveyWorkflowResponseController() {
    return {
        parseJsonResponse,
        summarizeServerResponseText,
    };
}
