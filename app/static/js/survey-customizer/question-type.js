// The LimeSurvey question type of a customizer question: the user's override for this export, else the
// type the backend derived from the template (limesurvey_exporter.ls_question_type). No derivation here.

export function detectQuestionType(question) {
    return (question.toolOverrides || {}).questionType || question.questionType;
}
