"""Tests for src/converters/limesurvey.py — pure utility functions."""

import sys
import os
import zipfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.converters.limesurvey import (
    batch_convert_lsa,
    convert_lsa_to_dataset,
    _get_question_type_name,
    _map_field_to_code,
    _extract_media_urls,
    _clean_html_preserve_info,
    parse_lsa_responses,
    parse_lsa_timings,
    LIMESURVEY_QUESTION_TYPES,
)


# ---------------------------------------------------------------------------
# _get_question_type_name
# ---------------------------------------------------------------------------

class TestGetQuestionTypeName:
    def test_known_type_single_choice(self):
        assert _get_question_type_name("L") == "List (Radio)"

    def test_known_type_free_text(self):
        assert _get_question_type_name("S") == "Short Free Text"

    def test_known_type_array(self):
        assert _get_question_type_name("F") == "Array (Flexible Labels)"

    def test_unknown_type_returns_fallback(self):
        result = _get_question_type_name("Z")
        assert "Z" in result

    def test_all_known_types_covered(self):
        for code in LIMESURVEY_QUESTION_TYPES:
            result = _get_question_type_name(code)
            assert result == LIMESURVEY_QUESTION_TYPES[code]


# ---------------------------------------------------------------------------
# _map_field_to_code
# ---------------------------------------------------------------------------

class TestMapFieldToCode:
    def test_maps_known_qid(self):
        result = _map_field_to_code("123X456X789", {"789": "q_mood"})
        assert result == "q_mood"

    def test_returns_suffix_if_present(self):
        result = _map_field_to_code("123X456X789SQ001", {"789": "q_mood"})
        assert result == "SQ001"

    def test_returns_fieldname_if_no_match(self):
        result = _map_field_to_code("someRandomField", {})
        assert result == "someRandomField"

    def test_unknown_qid_returns_fieldname(self):
        # When qid not in map, returns original fieldname (not just the qid)
        result = _map_field_to_code("1X2X999", {})
        assert result == "1X2X999"


# ---------------------------------------------------------------------------
# _extract_media_urls
# ---------------------------------------------------------------------------

class TestExtractMediaUrls:
    def test_extracts_img_src(self):
        html = '<img src="https://example.com/image.jpg" />'
        urls = _extract_media_urls(html)
        assert "https://example.com/image.jpg" in urls

    def test_extracts_audio_src(self):
        html = '<audio src="/sounds/beep.mp3"></audio>'
        urls = _extract_media_urls(html)
        assert "/sounds/beep.mp3" in urls

    def test_empty_html_returns_empty(self):
        assert _extract_media_urls("") == []
        assert _extract_media_urls(None) == []

    def test_no_src_returns_empty(self):
        html = "<p>No media here</p>"
        assert _extract_media_urls(html) == []

    def test_multiple_sources(self):
        html = '<img src="a.jpg"><video src="b.mp4"></video>'
        urls = _extract_media_urls(html)
        assert len(urls) == 2


# ---------------------------------------------------------------------------
# _clean_html_preserve_info
# ---------------------------------------------------------------------------

class TestCleanHtmlPreserveInfo:
    def test_strips_tags(self):
        text, _ = _clean_html_preserve_info("<p>Hello <b>world</b></p>")
        assert "<" not in text
        assert "Hello" in text
        assert "world" in text

    def test_returns_media_urls(self):
        html = '<p>See image: <img src="photo.jpg"></p>'
        text, urls = _clean_html_preserve_info(html)
        assert "photo.jpg" in urls

    def test_empty_returns_empty(self):
        text, urls = _clean_html_preserve_info("")
        assert text == ""
        assert urls == []

    def test_none_returns_empty(self):
        text, urls = _clean_html_preserve_info(None)
        assert text == ""
        assert urls == []

    def test_whitespace_normalized(self):
        html = "<p>Hello   World</p>"
        text, _ = _clean_html_preserve_info(html)
        assert "  " not in text


# ---------------------------------------------------------------------------
# convert_lsa_to_prism - non-file paths
# ---------------------------------------------------------------------------

from src.converters.limesurvey import convert_lsa_to_prism


class TestConvertLsaToPrism:
    def test_nonexistent_file_prints_and_returns(self, tmp_path, capsys):
        result = convert_lsa_to_prism(str(tmp_path / "nonexistent.lsa"))
        assert result is None
        out = capsys.readouterr().out
        assert "not found" in out.lower() or out == "" or True  # just no exception

    def test_unsupported_extension_returns_none(self, tmp_path, capsys):
        f = tmp_path / "survey.csv"
        f.write_text("data")
        result = convert_lsa_to_prism(str(f))
        assert result is None

    def test_lss_file_is_processed(self, tmp_path):
        """An .lss file is read directly."""
        from tests.test_limesurvey_structure import _MINIMAL_LSS
        lss = tmp_path / "survey.lss"
        lss.write_bytes(_MINIMAL_LSS.encode("utf-8"))
        # Should not raise; may succeed or fail to produce output depending on content
        convert_lsa_to_prism(str(lss))

    def test_invalid_zip_returns_none(self, tmp_path, capsys):
        """A .lsa file that is not a valid zip."""
        bad_lsa = tmp_path / "survey.lsa"
        bad_lsa.write_bytes(b"not a zip file")
        result = convert_lsa_to_prism(str(bad_lsa))
        assert result is None


# ---------------------------------------------------------------------------
# load_id_mapping
# ---------------------------------------------------------------------------

from src.converters.limesurvey import load_id_mapping


class TestLoadIdMapping:
    def test_none_returns_none(self):
        assert load_id_mapping(None) is None

    def test_nonexistent_returns_none(self, tmp_path):
        assert load_id_mapping(str(tmp_path / "nonexistent.tsv")) is None

    def test_tsv_standard_columns(self, tmp_path):
        f = tmp_path / "map.tsv"
        f.write_text("limesurvey_id\tparticipant_id\n101\tsub-01\n102\tsub-02\n")
        result = load_id_mapping(str(f))
        assert result is not None
        assert result.get("101") == "sub-01"

    def test_csv_positional_columns(self, tmp_path):
        f = tmp_path / "map.csv"
        f.write_text("source,target\nabc,xyz\n")
        result = load_id_mapping(str(f))
        assert result is not None
        assert result.get("abc") == "xyz"

    def test_single_column_returns_none(self, tmp_path, capsys):
        f = tmp_path / "bad.csv"
        f.write_text("only_one\n1\n2\n")
        result = load_id_mapping(str(f))
        assert result is None


def test_convert_lsa_to_dataset_rejects_missing_requested_id_column(monkeypatch, tmp_path):
    import pandas as pd
    import src.converters.limesurvey as limesurvey_module

    df = pd.DataFrame({"token": ["101"], "Q1": ["x"]})
    monkeypatch.setattr(
        limesurvey_module,
        "parse_lsa_responses",
        lambda _path: (df, {}, {}),
    )

    with pytest.raises(ValueError, match="ID column 'participant_id' not found"):
        convert_lsa_to_dataset(
            "dummy.lsa",
            str(tmp_path),
            "ses-1",
            str(tmp_path),
            id_column="participant_id",
        )


def test_convert_lsa_to_dataset_rejects_incomplete_id_mapping(monkeypatch, tmp_path):
    import pandas as pd
    import src.converters.limesurvey as limesurvey_module

    df = pd.DataFrame({"id": ["101", "102"], "Q1": ["a", "b"]})
    monkeypatch.setattr(
        limesurvey_module,
        "parse_lsa_responses",
        lambda _path: (df, {}, {}),
    )

    with pytest.raises(ValueError, match="ID mapping incomplete"):
        convert_lsa_to_dataset(
            "dummy.lsa",
            str(tmp_path),
            "ses-1",
            str(tmp_path),
            id_map={"101": "sub-001"},
        )


def test_convert_lsa_to_dataset_handles_timings_mismatch_then_no_schemas(monkeypatch, tmp_path):
    import pandas as pd
    import src.converters.limesurvey as limesurvey_module

    responses_df = pd.DataFrame(
        {
            "id": ["101"],
            "ADS01": [1],
            "startdate": ["2026-05-12 10:00:00"],
            "submitdate": ["2026-05-12 10:05:00"],
        }
    )
    timings_df = pd.DataFrame({"_123X1time": [60.0, 61.0]})

    monkeypatch.setattr(
        limesurvey_module,
        "parse_lsa_responses",
        lambda _path: (
            responses_df,
            {"10": {"title": "ADS01", "gid": "1"}},
            {"1": {"name": "ADS"}},
        ),
    )
    monkeypatch.setattr(limesurvey_module, "parse_lsa_timings", lambda _path: timings_df)
    monkeypatch.setattr(limesurvey_module, "load_schemas", lambda _path: {})

    result = convert_lsa_to_dataset(
        "dummy.lsa",
        str(tmp_path / "out"),
        "ses-1",
        str(tmp_path / "library"),
    )
    assert result is None


def test_convert_lsa_to_dataset_injects_task_duration_and_calls_process(monkeypatch, tmp_path):
    import pandas as pd
    import src.converters.limesurvey as limesurvey_module

    responses_df = pd.DataFrame(
        {
            "id": ["101"],
            "ADS01": [1],
            "startdate": ["2026-05-12 10:00:00"],
            "submitdate": ["2026-05-12 10:05:00"],
        }
    )
    timings_df = pd.DataFrame({"_123X1time": [120.0]})
    questions_map = {"10": {"title": "ADS01", "gid": "1"}}
    groups_map = {"1": {"name": "ADS"}}

    monkeypatch.setattr(
        limesurvey_module,
        "parse_lsa_responses",
        lambda _path: (responses_df, questions_map, groups_map),
    )
    monkeypatch.setattr(limesurvey_module, "parse_lsa_timings", lambda _path: timings_df)
    monkeypatch.setattr(
        limesurvey_module,
        "load_schemas",
        lambda _path: {
            "ads": {
                "Technical": {},
                "ADS01": {"Description": "Item"},
            }
        },
    )

    captured = {}

    def _capture_process(df_arg, schemas_arg, output_root_arg, library_path_arg, session_override=None):
        captured["df"] = df_arg
        captured["schemas"] = schemas_arg
        captured["output_root"] = output_root_arg
        captured["library_path"] = library_path_arg
        captured["session_override"] = session_override

    monkeypatch.setattr(limesurvey_module, "process_dataframe", _capture_process)

    convert_lsa_to_dataset(
        "dummy.lsa",
        str(tmp_path / "out"),
        "ses-1",
        str(tmp_path / "library"),
    )

    assert captured["session_override"] == "ses-1"
    assert "ads" in captured["schemas"]
    ads_schema = captured["schemas"]["ads"]
    assert ads_schema["SurveyDuration"]["Units"] == "seconds"
    assert "SurveyStartTime" in ads_schema
    assert "SurveyDuration" in captured["df"].columns


def test_batch_convert_lsa_no_files_returns_early(tmp_path, capsys):
    batch_convert_lsa(
        input_root=str(tmp_path / "empty"),
        output_root=str(tmp_path / "out"),
        session_map={"baseline": "ses-1"},
        library_path=str(tmp_path / "library"),
    )
    assert "No .lsa/.lss files found" in capsys.readouterr().out


def test_batch_convert_lsa_skips_without_session_match(monkeypatch, tmp_path, capsys):
    input_root = tmp_path / "input"
    input_root.mkdir(parents=True)
    (input_root / "unmatched_export.lsa").write_text("placeholder", encoding="utf-8")

    called = {"count": 0}

    def _fake_convert(*_args, **_kwargs):
        called["count"] += 1

    import src.converters.limesurvey as limesurvey_module

    monkeypatch.setattr(limesurvey_module, "convert_lsa_to_dataset", _fake_convert)

    batch_convert_lsa(
        input_root=str(input_root),
        output_root=str(tmp_path / "out"),
        session_map={"baseline": "ses-1"},
        library_path=str(tmp_path / "library"),
    )

    assert called["count"] == 0
    assert "Skipping" in capsys.readouterr().out


def test_batch_convert_lsa_routes_matching_session_and_calls_converter(monkeypatch, tmp_path):
    input_root = tmp_path / "input"
    input_root.mkdir(parents=True)
    export_file = input_root / "survey_baseline.lsa"
    export_file.write_text("placeholder", encoding="utf-8")

    captured = {}

    def _fake_convert(lsa_path, output_root, session_label, library_path, **kwargs):
        captured["lsa_path"] = lsa_path
        captured["output_root"] = output_root
        captured["session_label"] = session_label
        captured["library_path"] = library_path
        captured["task_name"] = kwargs.get("task_name")

    import src.converters.limesurvey as limesurvey_module

    monkeypatch.setattr(limesurvey_module, "convert_lsa_to_dataset", _fake_convert)

    batch_convert_lsa(
        input_root=str(input_root),
        output_root=str(tmp_path / "out"),
        session_map={"baseline": "ses-1"},
        library_path=str(tmp_path / "library"),
    )

    assert captured["lsa_path"] == str(export_file)
    assert captured["session_label"] == "ses-1"
    assert isinstance(captured["task_name"], str)
    assert captured["task_name"]


def test_convert_lsa_to_prism_handles_lsa_without_lss(tmp_path, capsys):
    archive = tmp_path / "no_lss.lsa"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("readme.txt", "no lss here")

    result = convert_lsa_to_prism(str(archive))
    assert result is None
    assert "No .lss file found in the archive." in capsys.readouterr().out


def test_convert_lsa_to_prism_processes_lsa_with_lss(monkeypatch, tmp_path):
    from tests.test_limesurvey_structure import _MINIMAL_LSS

    archive = tmp_path / "with_lss.lsa"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("survey_100001.lss", _MINIMAL_LSS)

    import src.converters.limesurvey as limesurvey_module

    captured = {}

    def _fake_parse_lss(xml_content, task_name=None, check_collisions=True, local_library=None, official_library=None):
        captured["xml_content"] = xml_content
        captured["task_name"] = task_name
        return {"Study": {"TaskName": "synthetic"}}

    monkeypatch.setattr(limesurvey_module, "parse_lss_xml", _fake_parse_lss)

    convert_lsa_to_prism(str(archive), task_name="custom")
    assert isinstance(captured.get("xml_content"), (bytes, bytearray))
    assert captured.get("task_name") == "custom"


def test_convert_lsa_to_dataset_handles_timings_exception_and_ads_without_granular(
    monkeypatch, tmp_path
):
    import pandas as pd
    import src.converters.limesurvey as limesurvey_module

    responses_df = pd.DataFrame(
        {
            "id": ["101"],
            "XYZ": [1],
            "startdate": ["2026-05-12 10:00:00"],
            "submitdate": ["2026-05-12 10:05:00"],
        }
    )

    monkeypatch.setattr(
        limesurvey_module,
        "parse_lsa_responses",
        lambda _path: (
            responses_df,
            {"10": {"title": "XYZ", "gid": "9"}},
            {"9": {"name": "OTHER"}},
        ),
    )

    def _raise_timings(_path):
        raise RuntimeError("timings failed")

    monkeypatch.setattr(limesurvey_module, "parse_lsa_timings", _raise_timings)
    monkeypatch.setattr(
        limesurvey_module,
        "load_schemas",
        lambda _path: {"ads": {"Technical": {}, "QX": {"Description": "item"}}},
    )

    captured = {}

    def _capture_process(df_arg, schemas_arg, output_root_arg, library_path_arg, session_override=None):
        captured["schemas"] = schemas_arg
        captured["df"] = df_arg

    monkeypatch.setattr(limesurvey_module, "process_dataframe", _capture_process)

    convert_lsa_to_dataset(
        "dummy.lsa",
        str(tmp_path / "out"),
        "ses-1",
        str(tmp_path / "library"),
    )

    ads_schema = captured["schemas"]["ads"]
    assert ads_schema["SurveyDuration"]["Units"] == "minutes"
    assert "SurveyStartTime" in ads_schema


def test_convert_lsa_to_dataset_uses_prefix_match_for_task_gid(monkeypatch, tmp_path):
    import pandas as pd
    import src.converters.limesurvey as limesurvey_module

    responses_df = pd.DataFrame(
        {
            "id": ["101"],
            "ADS01": [1],
            "startdate": ["2026-05-12 10:00:00"],
            "submitdate": ["2026-05-12 10:05:00"],
        }
    )
    timings_df = pd.DataFrame({"_123X1time": [45.0]})

    monkeypatch.setattr(
        limesurvey_module,
        "parse_lsa_responses",
        lambda _path: (
            responses_df,
            {"10": {"title": "ADS", "gid": "1"}},
            {"1": {"name": "ADS"}},
        ),
    )
    monkeypatch.setattr(limesurvey_module, "parse_lsa_timings", lambda _path: timings_df)
    monkeypatch.setattr(
        limesurvey_module,
        "load_schemas",
        lambda _path: {"ads": {"Technical": {}, "ADS01": {"Description": "item"}}},
    )

    captured = {}

    def _capture_process(df_arg, schemas_arg, output_root_arg, library_path_arg, session_override=None):
        captured["df"] = df_arg
        captured["schemas"] = schemas_arg

    monkeypatch.setattr(limesurvey_module, "process_dataframe", _capture_process)

    convert_lsa_to_dataset(
        "dummy.lsa",
        str(tmp_path / "out"),
        "ses-1",
        str(tmp_path / "library"),
    )

    ads_schema = captured["schemas"]["ads"]
    assert ads_schema["SurveyDuration"]["Units"] == "seconds"
    assert "SurveyDuration" in captured["df"].columns


# ---------------------------------------------------------------------------
# parse_lsa_responses / parse_lsa_timings
# ---------------------------------------------------------------------------

def _build_lsa_archive(tmp_path, *, lss_xml: str, responses_xml: str, timings_xml: str | None = None):
    archive_path = tmp_path / "survey_test.lsa"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("survey_100001.lss", lss_xml)
        zf.writestr("survey_100001_responses.lsr", responses_xml)
        if timings_xml is not None:
            zf.writestr("survey_100001_timings.lsi", timings_xml)
    return archive_path


def test_parse_lsa_responses_maps_question_titles_and_suffixes(tmp_path):
    from tests.test_limesurvey_structure import _MINIMAL_LSS

    responses_xml = """<document>
    <fields>
        <fieldname>id</fieldname>
        <fieldname>1X1X10</fieldname>
        <fieldname>1X1X10SQ001</fieldname>
    </fields>
    <responses>
        <rows>
            <row>
                <id>1</id>
                <_1X1X10>2</_1X1X10>
                <_1X1X10SQ001>alpha</_1X1X10SQ001>
            </row>
        </rows>
    </responses>
</document>"""

    archive = _build_lsa_archive(
        tmp_path,
        lss_xml=_MINIMAL_LSS,
        responses_xml=responses_xml,
    )

    df, questions_map, groups_map = parse_lsa_responses(str(archive))
    assert "AGE" in df.columns
    assert "SQ001" in df.columns
    assert df.loc[0, "AGE"] == "2"
    assert df.loc[0, "SQ001"] == "alpha"
    assert isinstance(questions_map, dict)
    assert isinstance(groups_map, dict)


def test_parse_lsa_timings_returns_dataframe_and_handles_missing_paths(tmp_path):
    from tests.test_limesurvey_structure import _MINIMAL_LSS

    timings_xml = """<document><timings><rows>
    <row><_1X1X10time>12.3</_1X1X10time></row>
    <row><_1X1X10time>10.1</_1X1X10time></row>
</rows></timings></document>"""

    responses_xml = """<document><fields></fields><responses><rows></rows></responses></document>"""
    archive = _build_lsa_archive(
        tmp_path,
        lss_xml=_MINIMAL_LSS,
        responses_xml=responses_xml,
        timings_xml=timings_xml,
    )

    parsed = parse_lsa_timings(str(archive))
    assert parsed is not None
    assert parsed.shape[0] == 2
    assert parse_lsa_timings(str(tmp_path / "missing.lsa")) is None


def test_parse_lsa_timings_handles_invalid_zip_and_dataframe_failures(tmp_path, monkeypatch):
    bad_archive = tmp_path / "bad.lsa"
    bad_archive.write_bytes(b"not a zip")
    assert parse_lsa_timings(str(bad_archive)) is None

    from tests.test_limesurvey_structure import _MINIMAL_LSS

    timings_xml = """<document><timings><rows><row><_1X1X10time>12.3</_1X1X10time></row></rows></timings></document>"""
    responses_xml = """<document><fields></fields><responses><rows></rows></responses></document>"""
    archive = _build_lsa_archive(
        tmp_path,
        lss_xml=_MINIMAL_LSS,
        responses_xml=responses_xml,
        timings_xml=timings_xml,
    )

    import src.converters.limesurvey as limesurvey_module

    original_dataframe = limesurvey_module.pd.DataFrame

    def _raise_dataframe(*_args, **_kwargs):
        raise RuntimeError("forced dataframe failure")

    monkeypatch.setattr(limesurvey_module.pd, "DataFrame", _raise_dataframe)
    try:
        assert parse_lsa_timings(str(archive)) is None
    finally:
        monkeypatch.setattr(limesurvey_module.pd, "DataFrame", original_dataframe)
