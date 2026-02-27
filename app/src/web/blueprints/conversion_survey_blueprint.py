from flask import Blueprint

from .conversion_survey_handlers import (
    api_survey_languages,
    api_survey_convert_preview,
    api_survey_convert,
    api_survey_convert_validate,
    api_save_unmatched_template,
)

conversion_survey_bp = Blueprint("conversion_survey", __name__)

conversion_survey_bp.add_url_rule(
    "/api/survey-languages",
    view_func=api_survey_languages,
    methods=["GET"],
)
conversion_survey_bp.add_url_rule(
    "/api/survey-convert-preview",
    view_func=api_survey_convert_preview,
    methods=["POST"],
)
conversion_survey_bp.add_url_rule(
    "/api/survey-convert",
    view_func=api_survey_convert,
    methods=["POST"],
)
conversion_survey_bp.add_url_rule(
    "/api/survey-convert-validate",
    view_func=api_survey_convert_validate,
    methods=["POST"],
)
conversion_survey_bp.add_url_rule(
    "/api/save-unmatched-template",
    view_func=api_save_unmatched_template,
    methods=["POST"],
)
