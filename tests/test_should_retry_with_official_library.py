"""Which converter errors mean "try the official template library instead"."""

import pytest

from src.web.blueprints.conversion_utils import should_retry_with_official_library


@pytest.mark.parametrize(
    "message",
    [
        "No survey item columns matched any template",
        "Unknown surveys: brs",
        # raised when the project library holds no template at all
        "No survey templates were found in /p/code/library/survey. PRISM needs a JSON template",
    ],
)
def test_template_lookup_failures_retry_with_the_official_library(message):
    assert should_retry_with_official_library(ValueError(message))


@pytest.mark.parametrize(
    "error",
    [
        ValueError("id_column_required"),
        ValueError("Unsupported file type"),
        RuntimeError("No survey templates were found"),  # only ValueErrors are lookup failures
    ],
)
def test_other_errors_do_not_retry(error):
    assert not should_retry_with_official_library(error)
