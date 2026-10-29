"""An .lsa with no responses says so, instead of the page later reporting "No columns found"."""

import pytest

from src.converters.limesurvey import parse_lsa_responses
from tests.lsa_fixtures import make_lsa


def test_an_archive_without_responses_says_so(tmp_path):
    with pytest.raises(ValueError, match="no responses"):
        parse_lsa_responses(str(make_lsa(tmp_path, rows=[])))
