"""LimeSurvey constants the importer and the exporters share (this module must stay free of
heavy imports such as pandas).

LS_ARRAY_TYPES: question types that are a matrix. LS_DESIGN_ATTRIBUTES: the question attributes
(design options) a template keeps and the exporters write back, LimeSurvey attribute name ->
the Survey Customizer's override name for it."""

LS_ARRAY_TYPES = {"F", "A", "B", "C", "E", "H", "1", ";", ":"}

LS_DESIGN_ATTRIBUTES = {
    "cssclass": "cssClass",
    "page_break": "pageBreak",
    "maximum_chars": "maximumChars",
    "numbers_only": "numbersOnly",
    "input_size": "inputSize",
    "prefix": "prefix",
    "suffix": "suffix",
    "placeholder": "placeholder",
    "display_columns": "displayColumns",
    "alphasort": "alphasort",
    "dropdown_size": "dropdownSize",
    "dropdown_prefix": "dropdownPrefix",
    "category_separator": "categorySeparator",
    "answer_width": "answerWidth",
    "repeat_headings": "repeatHeadings",
    "use_dropdown": "useDropdown",
}
