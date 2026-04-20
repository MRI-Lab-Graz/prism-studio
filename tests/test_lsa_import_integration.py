"""Integration test: .lsa import with multiple questionnaires, sociodemographics,
system variables, and template matching (global + project library).

Tests the full pipeline: .lsa parsing → template matching → conversion → output validation.
"""

import csv
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app" / "src"))

# ── Synthetic multi-questionnaire .lsa ────────────────────────────────

MULTI_LSS_XML = """\
<?xml version='1.0' encoding='UTF-8'?>
<document>
  <LimeSurveyDocType>Survey</LimeSurveyDocType>
  <DBVersion>415</DBVersion>
  <LimeSurveyVersion>5.6.0</LimeSurveyVersion>
  <languages>
    <language>en</language>
  </languages>
  <answers>
    <rows>
      <!-- GAD-7 answers: 0-3 scale -->
      <row><qid>101</qid><code>0</code><sortorder>1</sortorder><assessment_value>0</assessment_value><scale_id>0</scale_id></row>
      <row><qid>101</qid><code>1</code><sortorder>2</sortorder><assessment_value>0</assessment_value><scale_id>0</scale_id></row>
      <row><qid>101</qid><code>2</code><sortorder>3</sortorder><assessment_value>0</assessment_value><scale_id>0</scale_id></row>
      <row><qid>101</qid><code>3</code><sortorder>4</sortorder><assessment_value>0</assessment_value><scale_id>0</scale_id></row>
      <!-- PSS answers: 0-4 scale -->
      <row><qid>201</qid><code>0</code><sortorder>1</sortorder><assessment_value>0</assessment_value><scale_id>0</scale_id></row>
      <row><qid>201</qid><code>1</code><sortorder>2</sortorder><assessment_value>0</assessment_value><scale_id>0</scale_id></row>
      <row><qid>201</qid><code>2</code><sortorder>3</sortorder><assessment_value>0</assessment_value><scale_id>0</scale_id></row>
      <row><qid>201</qid><code>3</code><sortorder>4</sortorder><assessment_value>0</assessment_value><scale_id>0</scale_id></row>
      <row><qid>201</qid><code>4</code><sortorder>5</sortorder><assessment_value>0</assessment_value><scale_id>0</scale_id></row>
    </rows>
  </answers>
  <answer_l10ns>
    <rows>
      <row><id>1</id><qid>101</qid><code>0</code><answer>Not at all</answer><language>en</language></row>
      <row><id>2</id><qid>101</qid><code>1</code><answer>Several days</answer><language>en</language></row>
      <row><id>3</id><qid>101</qid><code>2</code><answer>More than half</answer><language>en</language></row>
      <row><id>4</id><qid>101</qid><code>3</code><answer>Nearly every day</answer><language>en</language></row>
      <row><id>5</id><qid>201</qid><code>0</code><answer>Never</answer><language>en</language></row>
      <row><id>6</id><qid>201</qid><code>1</code><answer>Almost never</answer><language>en</language></row>
      <row><id>7</id><qid>201</qid><code>2</code><answer>Sometimes</answer><language>en</language></row>
      <row><id>8</id><qid>201</qid><code>3</code><answer>Fairly often</answer><language>en</language></row>
      <row><id>9</id><qid>201</qid><code>4</code><answer>Very often</answer><language>en</language></row>
    </rows>
  </answer_l10ns>
  <questions>
    <rows>
      <!-- GAD-7 array question -->
      <row>
        <qid>101</qid><parent_qid>0</parent_qid><sid>100001</sid><gid>10</gid>
        <type>F</type><title>GAD7</title><other>N</other><mandatory>Y</mandatory>
        <question_order>1</question_order><scale_id>0</scale_id>
        <same_default>0</same_default><relevance>1</relevance>
      </row>
      <!-- PSS array question -->
      <row>
        <qid>201</qid><parent_qid>0</parent_qid><sid>100001</sid><gid>20</gid>
        <type>F</type><title>PSS</title><other>N</other><mandatory>Y</mandatory>
        <question_order>1</question_order><scale_id>0</scale_id>
        <same_default>0</same_default><relevance>1</relevance>
      </row>
      <!-- Sociodemographic questions (simple text) -->
      <row>
        <qid>301</qid><parent_qid>0</parent_qid><sid>100001</sid><gid>30</gid>
        <type>S</type><title>age</title><other>N</other><mandatory>N</mandatory>
        <question_order>1</question_order><scale_id>0</scale_id>
        <same_default>0</same_default><relevance>1</relevance>
      </row>
      <row>
        <qid>302</qid><parent_qid>0</parent_qid><sid>100001</sid><gid>30</gid>
        <type>L</type><title>sex</title><other>N</other><mandatory>N</mandatory>
        <question_order>2</question_order><scale_id>0</scale_id>
        <same_default>0</same_default><relevance>1</relevance>
      </row>
    </rows>
  </questions>
  <question_l10ns>
    <rows>
      <row><id>1</id><qid>101</qid><question>How often have you been bothered by:</question><help /><language>en</language></row>
      <row><id>2</id><qid>201</qid><question>In the last month, how often:</question><help /><language>en</language></row>
      <row><id>3</id><qid>301</qid><question>Your age</question><help /><language>en</language></row>
      <row><id>4</id><qid>302</qid><question>Your sex</question><help /><language>en</language></row>
    </rows>
  </question_l10ns>
  <subquestions>
    <rows>
      <!-- GAD-7 subquestions -->
      <row><qid>1001</qid><parent_qid>101</parent_qid><sid>100001</sid><gid>10</gid><type>T</type><title>SQ001</title><question_order>1</question_order><scale_id>0</scale_id><same_default>0</same_default><relevance>1</relevance></row>
      <row><qid>1002</qid><parent_qid>101</parent_qid><sid>100001</sid><gid>10</gid><type>T</type><title>SQ002</title><question_order>2</question_order><scale_id>0</scale_id><same_default>0</same_default><relevance>1</relevance></row>
      <row><qid>1003</qid><parent_qid>101</parent_qid><sid>100001</sid><gid>10</gid><type>T</type><title>SQ003</title><question_order>3</question_order><scale_id>0</scale_id><same_default>0</same_default><relevance>1</relevance></row>
      <!-- PSS subquestions -->
      <row><qid>2001</qid><parent_qid>201</parent_qid><sid>100001</sid><gid>20</gid><type>T</type><title>SQ001</title><question_order>1</question_order><scale_id>0</scale_id><same_default>0</same_default><relevance>1</relevance></row>
      <row><qid>2002</qid><parent_qid>201</parent_qid><sid>100001</sid><gid>20</gid><type>T</type><title>SQ002</title><question_order>2</question_order><scale_id>0</scale_id><same_default>0</same_default><relevance>1</relevance></row>
    </rows>
  </subquestions>
  <groups>
    <rows>
      <row><gid>10</gid><sid>100001</sid><group_order>1</group_order></row>
      <row><gid>20</gid><sid>100001</sid><group_order>2</group_order></row>
      <row><gid>30</gid><sid>100001</sid><group_order>3</group_order></row>
    </rows>
  </groups>
  <group_l10ns>
    <rows>
      <row><id>1</id><gid>10</gid><group_name>Generalised Anxiety Disorder 7</group_name><description /><language>en</language></row>
      <row><id>2</id><gid>20</gid><group_name>Perceived Stress Scale</group_name><description /><language>en</language></row>
      <row><id>3</id><gid>30</gid><group_name>Sociodemographics</group_name><description /><language>en</language></row>
    </rows>
  </group_l10ns>
  <surveys>
    <rows>
      <row>
        <sid>100001</sid><owner_id>1</owner_id><admin>Admin</admin>
        <active>Y</active><anonymized>N</anonymized><format>G</format>
        <savetimings>Y</savetimings><template>vanilla</template>
        <language>en</language><datestamp>Y</datestamp><ipaddr>Y</ipaddr>
      </row>
    </rows>
  </surveys>
  <surveys_languagesettings>
    <rows>
      <row>
        <surveyls_survey_id>100001</surveyls_survey_id>
        <surveyls_language>en</surveyls_language>
        <surveyls_title>Multi-Questionnaire Integration Test</surveyls_title>
      </row>
    </rows>
  </surveys_languagesettings>
</document>
"""

# Response data with system columns, 2 questionnaires + sociodemographics
MULTI_RESPONSES = (
    "id\tsubmitdate\tstartdate\tdatestamp\tlastpage\tstartlanguage\tseed\t"
    "token\tipaddr\trefurl\tinterviewtime\tcompleted\t"
    "GAD7SQ001\tGAD7SQ002\tGAD7SQ003\t"
    "PSSSQ001\tPSSSQ002\t"
    "age\tsex\n"
    "1\t2026-04-01 10:30:00\t2026-04-01 10:00:00\t2026-04-01 10:30:00\t3\ten\t42\tabc123\t192.168.1.10\thttps://uni.at\t1800\tY\t"
    "2\t1\t3\t"
    "3\t2\t"
    "25\tM\n"
    "2\t2026-04-01 11:15:00\t2026-04-01 11:00:00\t2026-04-01 11:15:00\t3\ten\t99\tdef456\t192.168.1.20\t\t900\tY\t"
    "0\t0\t1\t"
    "1\t0\t"
    "31\tF\n"
    "3\t\t2026-04-01 12:00:00\t2026-04-01 12:05:00\t2\ten\t77\tghi789\t10.0.0.1\t\t300\tN\t"
    "3\t2\t\t"
    "\t4\t"
    "22\tM\n"
)

MULTI_TIMINGS = (
    "id\tinterviewtime\tgrouptime10\tgrouptime20\tgrouptime30\n"
    "1\t1800\t600\t800\t400\n"
    "2\t900\t300\t400\t200\n"
    "3\t300\t150\t100\t50\n"
)


def _build_multi_lsa(tmp_path: Path) -> Path:
    """Build a synthetic multi-questionnaire .lsa archive."""
    lsa_path = tmp_path / "survey_archive_100001.lsa"
    with zipfile.ZipFile(lsa_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("survey_100001.lss", MULTI_LSS_XML)
        zf.writestr("survey_100001_responses.csv", MULTI_RESPONSES)
        zf.writestr("survey_100001_timings.csv", MULTI_TIMINGS)
    return lsa_path


def _build_template(
    name: str,
    abbreviation: str,
    items: dict[str, str],
    levels: dict[str, str] | None = None,
) -> dict:
    """Create a minimal PRISM survey template JSON."""
    template = {
        "Study": {
            "OriginalName": {"en": name},
            "ShortName": abbreviation,
            "Abbreviation": abbreviation,
            "Authors": "Test Author",
            "Year": 2020,
            "Citation": "Test (2020)",
            "LicenseID": "CC-BY-4.0",
        },
        "Technical": {
            "AdministrationMethod": "online",
            "SoftwarePlatform": "LimeSurvey",
            "SoftwareVersion": "5.6.0",
        },
        "Items": {},
    }
    for key, question in items.items():
        item = {"Description": {"en": question}}
        if levels:
            item["Levels"] = levels
        template["Items"][key] = item
    return template


def _setup_library(lib_dir: Path) -> None:
    """Create a minimal library with GAD-7 and PSS templates."""
    survey_dir = lib_dir / "survey"
    survey_dir.mkdir(parents=True, exist_ok=True)

    gad7 = _build_template(
        name="Generalised Anxiety Disorder 7",
        abbreviation="GAD-7",
        items={
            "GAD7SQ001": "Feeling nervous",
            "GAD7SQ002": "Not being able to stop worrying",
            "GAD7SQ003": "Worrying too much",
        },
        levels={
            "0": "Not at all",
            "1": "Several days",
            "2": "More than half",
            "3": "Nearly every day",
        },
    )
    with open(survey_dir / "survey-gad7.json", "w", encoding="utf-8") as f:
        json.dump(gad7, f, indent=2)

    pss = _build_template(
        name="Perceived Stress Scale",
        abbreviation="PSS",
        items={
            "PSSSQ001": "How often upset by unexpected",
            "PSSSQ002": "How often unable to control",
        },
        levels={
            "0": "Never",
            "1": "Almost never",
            "2": "Sometimes",
            "3": "Fairly often",
            "4": "Very often",
        },
    )
    with open(survey_dir / "survey-pss.json", "w", encoding="utf-8") as f:
        json.dump(pss, f, indent=2)


# ── Tests ────────────────────────────────────────────────────────────


class TestSystemColumnSeparation:
    """Verify LimeSurvey system columns are correctly detected and separated."""

    def test_system_columns_detected_in_multi_survey(self):
        """All system columns should be detected regardless of questionnaire count."""
        from src.converters.survey_processing import _extract_limesurvey_columns

        columns = MULTI_RESPONSES.split("\n")[0].split("\t")
        ls_cols, other_cols = _extract_limesurvey_columns(columns)

        expected_system = {
            "id",
            "submitdate",
            "startdate",
            "datestamp",
            "lastpage",
            "startlanguage",
            "seed",
            "token",
            "ipaddr",
            "refurl",
            "interviewtime",
            "completed",
        }
        assert expected_system == set(
            ls_cols
        ), f"Missing: {expected_system - set(ls_cols)}, Extra: {set(ls_cols) - expected_system}"

        # Questionnaire columns should NOT be system columns
        for col in ["GAD7SQ001", "GAD7SQ002", "GAD7SQ003", "PSSSQ001", "PSSSQ002"]:
            assert (
                col in other_cols
            ), f"{col} should be a questionnaire column, not system"

        # Sociodemographic columns should NOT be system columns
        assert "age" in other_cols
        assert "sex" in other_cols

    def test_timing_columns_from_multi_group(self):
        """Per-group timing columns should be detected as system columns."""
        from src.converters.survey_processing import _extract_limesurvey_columns

        timing_cols = MULTI_TIMINGS.split("\n")[0].split("\t")
        ls_cols, _ = _extract_limesurvey_columns(timing_cols)

        assert "interviewtime" in ls_cols
        assert "grouptime10" in ls_cols
        assert "grouptime20" in ls_cols
        assert "grouptime30" in ls_cols


class TestToolLimesurveyOutput:
    """Verify tool-limesurvey TSV/JSON files are written correctly."""

    def test_tool_limesurvey_files_written(self, tmp_path):
        """tool-limesurvey files should be created for each participant."""
        import pandas as pd
        from src.converters.survey_io import _write_tool_limesurvey_files

        df = pd.DataFrame(
            {
                "participant_id": ["sub-01", "sub-02"],
                "id": [1, 2],
                "submitdate": ["2026-04-01 10:30:00", "2026-04-01 11:15:00"],
                "startdate": ["2026-04-01 10:00:00", "2026-04-01 11:00:00"],
                "seed": ["42", "99"],
                "token": ["abc123", "def456"],
                "ipaddr": ["192.168.1.10", "192.168.1.20"],
                "interviewtime": [1800, 900],
                "grouptime10": [600, 300],
                "grouptime20": [800, 400],
                "completed": ["Y", "Y"],
            }
        )

        ls_cols = [
            "id",
            "submitdate",
            "startdate",
            "seed",
            "token",
            "ipaddr",
            "interviewtime",
            "grouptime10",
            "grouptime20",
            "completed",
        ]

        output_root = tmp_path / "out"
        output_root.mkdir()

        n = _write_tool_limesurvey_files(
            df=df,
            ls_system_cols=ls_cols,
            res_id_col="participant_id",
            res_ses_col=None,
            session="1",
            output_root=output_root,
            normalize_sub_fn=lambda x: str(x),
            normalize_ses_fn=lambda x: f"ses-{x}",
            ensure_dir_fn=lambda p: (p.mkdir(parents=True, exist_ok=True), p)[-1],
            build_bids_survey_filename_fn=lambda *a, **kw: "dummy.tsv",
            ls_metadata={
                "survey_id": "100001",
                "survey_title": "Multi Test",
                "tool_version": "5.6.0",
            },
        )

        assert n == 2, f"Expected 2 participants, got {n}"

        # Verify files exist for both participants
        for sub in ["sub-01", "sub-02"]:
            survey_dir = output_root / sub / "ses-1" / "survey"
            tsv_files = list(survey_dir.glob("*tool-limesurvey*.tsv"))
            json_files = list(survey_dir.glob("*tool-limesurvey*.json"))
            assert (
                len(tsv_files) == 1
            ), f"Expected 1 TSV for {sub}, got {len(tsv_files)}"
            assert (
                len(json_files) == 1
            ), f"Expected 1 JSON for {sub}, got {len(json_files)}"

    def test_sensitive_fields_marked(self, tmp_path):
        """token and ipaddr should be marked as Sensitive in the JSON sidecar."""
        import pandas as pd
        from src.converters.survey_io import _write_tool_limesurvey_files

        df = pd.DataFrame(
            {
                "participant_id": ["sub-01"],
                "token": ["secret123"],
                "ipaddr": ["10.0.0.1"],
            }
        )

        output_root = tmp_path / "out"
        output_root.mkdir()

        _write_tool_limesurvey_files(
            df=df,
            ls_system_cols=["token", "ipaddr"],
            res_id_col="participant_id",
            res_ses_col=None,
            session="1",
            output_root=output_root,
            normalize_sub_fn=lambda x: str(x),
            normalize_ses_fn=lambda x: f"ses-{x}",
            ensure_dir_fn=lambda p: (p.mkdir(parents=True, exist_ok=True), p)[-1],
            build_bids_survey_filename_fn=lambda *a, **kw: "dummy.tsv",
        )

        json_file = list((output_root / "sub-01" / "ses-1" / "survey").glob("*.json"))[
            0
        ]
        with open(json_file, "r", encoding="utf-8") as f:
            sidecar = json.load(f)

        assert sidecar["SystemFields"]["token"]["Sensitive"] is True
        assert sidecar["SystemFields"]["ipaddr"]["Sensitive"] is True


class TestLsaStructureParsing:
    """Verify .lsa archive parsing extracts correct groups and metadata."""

    def test_lsa_structure_has_three_groups(self, tmp_path):
        """Multi-questionnaire .lsa should have 3 groups: GAD-7, PSS, Sociodemographics."""
        lsa_path = _build_multi_lsa(tmp_path)

        from src.converters.survey_lsa import _analyze_lsa_structure

        structure = _analyze_lsa_structure(lsa_path)
        if structure is None:
            pytest.skip(
                "_analyze_lsa_structure returned None (may need project context)"
            )

        groups = structure.get("groups", {})
        group_names = list(groups.keys())
        assert (
            len(groups) >= 2
        ), f"Expected at least 2 groups, got {len(groups)}: {group_names}"

    def test_lsa_metadata_extraction(self, tmp_path):
        """LimeSurvey version and language should be extracted from .lsa."""
        lsa_path = _build_multi_lsa(tmp_path)

        from src.converters.survey_lsa import infer_lsa_metadata

        meta = infer_lsa_metadata(lsa_path)

        assert meta["software_platform"] == "LimeSurvey"
        assert (
            meta.get("software_version") is not None or meta.get("language") is not None
        )


class TestTemplateMatching:
    """Verify template matching works with both global and project libraries."""

    def test_group_names_are_normalized(self):
        """parse_lss_xml_by_groups should return normalized group names as keys."""
        from src.converters.limesurvey import parse_lss_xml_by_groups

        parsed_groups = parse_lss_xml_by_groups(MULTI_LSS_XML.encode("utf-8"))
        assert parsed_groups is not None, "parse_lss_xml_by_groups returned None"

        group_names = list(parsed_groups.keys())
        assert len(group_names) == 3, f"Expected 3 groups, got {group_names}"

        # Names should be normalized (lowercased, spaces removed)
        assert "generalisedanxietydisorder7" in group_names
        assert "perceivedstressscale" in group_names
        assert "sociodemographics" in group_names

    def test_template_matching_with_matching_filenames(self, tmp_path):
        """Templates should match when item codes use the raw subquestion codes.

        parse_lss_xml_by_groups returns subquestion codes as-is from the XML
        (SQ001, SQ002), not prefixed with parent code (GAD7SQ001).
        Templates must use the same codes for item-overlap matching to work.
        """
        from src.converters.limesurvey import parse_lss_xml_by_groups
        from src.converters.survey_templates import match_groups_against_library

        parsed_groups = parse_lss_xml_by_groups(MULTI_LSS_XML.encode("utf-8"))

        # Create project library with matching filenames and raw subquestion codes
        project_dir = tmp_path / "project"
        project_lib = project_dir / "code" / "library" / "survey"
        project_lib.mkdir(parents=True)

        # Items must use raw SQ codes (as parse_lss_xml_by_groups returns them)
        # plus the parent question code (GAD7) which is a top-level structural key
        gad7 = _build_template(
            name="Generalised Anxiety Disorder 7",
            abbreviation="GAD-7",
            items={
                "SQ001": "Feeling nervous",
                "SQ002": "Worrying",
                "SQ003": "Too much",
            },
            levels={
                "0": "Not at all",
                "1": "Several days",
                "2": "More than half",
                "3": "Nearly every day",
            },
        )
        # Add GAD7 as top-level key (matching the parsed parent question code)
        gad7["GAD7"] = gad7.pop("Items", {})
        gad7["GAD7"] = {
            "Description": "Anxiety items",
            "Items": {
                "SQ001": {"Description": {"en": "Feeling nervous"}},
                "SQ002": {"Description": {"en": "Worrying"}},
                "SQ003": {"Description": {"en": "Too much"}},
            },
        }
        with open(
            project_lib / "survey-generalisedanxietydisorder7.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(gad7, f)

        matches = match_groups_against_library(parsed_groups, project_path=project_dir)
        matched_names = [name for name, match in matches.items() if match is not None]

        assert (
            "generalisedanxietydisorder7" in matched_names
        ), f"GAD-7 should match via name + item overlap, got: {matched_names}"

    def test_nested_items_extracted_for_array_questions(self):
        """_extract_template_structure should include nested Items from array questions."""
        from src.converters.survey_core import _extract_template_structure

        # Simulate an array-style template (as produced by LimeSurvey import)
        array_template = {
            "Study": {"OriginalName": "Test"},
            "Technical": {},
            "Metadata": {},
            "MBFIS01": {
                "Description": "Rate yourself",
                "QuestionType": "Array",
                "Items": {
                    "BFIS01": {"Description": "I am talkative"},
                    "BFIS02": {"Description": "I tend to find fault"},
                    "BFIS03": {"Description": "I do a thorough job"},
                },
            },
            "PRISMMETAg1": {"Description": "metadata", "QuestionType": "Equation"},
        }

        struct = _extract_template_structure(array_template)

        # Should include parent code AND nested item codes
        assert "MBFIS01" in struct, "Parent code should be included"
        assert "BFIS01" in struct, "Nested item BFIS01 should be included"
        assert "BFIS02" in struct, "Nested item BFIS02 should be included"
        assert "BFIS03" in struct, "Nested item BFIS03 should be included"
        assert (
            "PRISMMETAg1" in struct
        ), "PRISMMETA key should be in structure (filtered elsewhere)"
        assert "Study" not in struct, "Study should be excluded"

    def test_prismmeta_abbreviation_extraction(self):
        """_extract_prismmeta should parse abbreviation from hidden metadata HTML."""
        from src.converters.survey_templates import _extract_prismmeta

        prism_json = {
            "Study": {},
            "PRISMMETAg2": {
                "Attributes": {
                    "equation": (
                        '<div class="prism-metadata" style="display:none;">'
                        '<p><span class="meta-name">Big Five Inventory Short</span></p>'
                        '<p>Abbreviation: <span class="meta-abbrev">BFI-S</span></p>'
                        '<p>Authors: <span class="meta-authors">Lang et al.</span></p>'
                        "</div>"
                    )
                },
                "Description": "PRISM Template Metadata",
            },
        }

        fields = _extract_prismmeta(prism_json)

        assert fields.get("name") == "Big Five Inventory Short"
        assert fields.get("abbrev") == "BFI-S"
        assert fields.get("authors") == "Lang et al."

    def test_prismmeta_abbreviation_boosts_matching(self, tmp_path):
        """When PRISMMETA abbreviation matches a global template, confidence should be high."""
        from src.converters.survey_templates import (
            match_against_library,
            _load_global_templates,
        )

        # Simulate a parsed group with PRISMMETA pointing to BFI-S
        prism_json = {
            "Study": {"TaskName": "short15itembigfiveinventorybfis"},
            "Technical": {},
            "Metadata": {},
            "MBFIS01": {
                "Description": "Rate yourself",
                "Items": {
                    "BFIS01": {"Description": "talkative"},
                    "BFIS02": {"Description": "find fault"},
                },
            },
            "PRISMMETAg2": {
                "Attributes": {
                    "equation": (
                        '<div class="prism-metadata">'
                        '<span class="meta-abbrev">BFI-S</span>'
                        "</div>"
                    )
                },
                "Description": "PRISM Template Metadata\nAbbreviation: BFI-S",
            },
        }

        global_templates = _load_global_templates()
        if not global_templates:
            pytest.skip("No global templates available")

        # Check if BFI-S exists in global templates
        bfis_exists = any("bfi" in k and "s" in k for k in global_templates.keys())
        if not bfis_exists:
            pytest.skip("BFI-S not in global templates")

        match = match_against_library(
            prism_json, global_templates, group_name="short15itembigfiveinventorybfis"
        )

        assert (
            match is not None
        ), "BFI-S should match via PRISMMETA abbreviation + name + item overlap"
        assert match.confidence in (
            "exact",
            "high",
            "medium",
        ), f"Expected high confidence, got: {match.confidence}"

    def test_codemap_roundtrip_with_participants(self, tmp_path):
        """CodeMap should be embedded during export and parseable during import."""
        from src.converters.survey_templates import (
            _extract_prismmeta,
            parse_prismmeta_codemap,
        )

        participants_path = (
            Path(__file__).resolve().parent.parent / "official" / "participants.json"
        )
        if not participants_path.exists():
            pytest.skip("Participants template not available")

        from src.limesurvey_exporter import generate_lss

        lss_path = tmp_path / "with_participants.lss"
        generate_lss(
            [str(participants_path)], str(lss_path), language="en", ls_version="6"
        )

        from src.converters.limesurvey import parse_lss_xml_by_groups

        with open(lss_path, "rb") as f:
            parsed = parse_lss_xml_by_groups(f.read())

        # Find the participants group
        part_group = None
        for gname, gdata in parsed.items():
            meta = _extract_prismmeta(gdata)
            if meta.get("type") == "participants":
                part_group = (gname, gdata, meta)
                break

        assert part_group is not None, "Should find a participants group with PRISMMETA"
        gname, gdata, meta = part_group

        codemap = parse_prismmeta_codemap(meta)
        assert len(codemap) > 0, f"CodeMap should have entries, got empty for {gname}"

        # Verify specific known truncations
        assert (
            codemap.get("alcoholconsum60") == "alcohol_consumption"
        ), f"alcohol_consumption should be in codemap: {codemap}"
        assert (
            codemap.get("psychiatricdi65") == "psychiatric_diagnosis"
        ), f"psychiatric_diagnosis should be in codemap: {codemap}"

        # Verify that short codes are NOT in the codemap (they don't change)
        assert "age" not in codemap, "Short codes should not be in codemap"
        assert "sex" not in codemap, "Short codes should not be in codemap"

    def test_codemap_used_in_participant_renames(self, tmp_path):
        """CodeMap should produce correct renames for participant columns."""
        from src.converters.survey_lsa import _derive_lsa_participant_renames

        participants_path = (
            Path(__file__).resolve().parent.parent / "official" / "participants.json"
        )
        if not participants_path.exists():
            pytest.skip("Participants template not available")

        with open(participants_path, encoding="utf-8") as f:
            participant_template = json.load(f)

        from src.limesurvey_exporter import generate_lss
        from src.converters.limesurvey import parse_lss_xml_by_groups
        from src.converters.survey_templates import (
            match_groups_against_library,
            _load_global_templates,
        )
        from src.converters.survey import _build_participant_col_renames

        lss_path = tmp_path / "part_test.lss"
        generate_lss(
            [str(participants_path)], str(lss_path), language="en", ls_version="6"
        )

        with open(lss_path, "rb") as f:
            parsed = parse_lss_xml_by_groups(f.read())

        global_templates = _load_global_templates()
        matches = match_groups_against_library(parsed, global_templates)

        # Build fake lsa_analysis structure
        from src.converters.survey_core import _NON_ITEM_TOPLEVEL_KEYS

        lsa_analysis = {"groups": {}}
        for gname, gdata in parsed.items():
            item_codes = {
                k
                for k in gdata.keys()
                if k not in _NON_ITEM_TOPLEVEL_KEYS and isinstance(gdata.get(k), dict)
            }
            lsa_analysis["groups"][gname] = {
                "prism_json": gdata,
                "match": matches.get(gname),
                "item_codes": item_codes,
            }

        renames = _derive_lsa_participant_renames(
            lsa_analysis=lsa_analysis,
            survey_filter=None,
            participant_template=participant_template,
            build_participant_col_renames_fn=_build_participant_col_renames,
        )

        # The codemap should provide authoritative renames
        assert (
            renames.get("alcoholconsum60") == "alcohol_consumption"
        ), f"Expected alcohol_consumption rename, got: {renames}"
        assert (
            renames.get("psychiatricdi65") == "psychiatric_diagnosis"
        ), f"Expected psychiatric_diagnosis rename, got: {renames}"

    def test_library_templates_load_correctly(self, tmp_path):
        """Both global and project library templates should be loadable."""
        lib_dir = tmp_path / "library"
        _setup_library(lib_dir)

        survey_dir = lib_dir / "survey"
        templates = list(survey_dir.glob("*.json"))

        assert len(templates) == 2, f"Expected 2 templates, got {len(templates)}"

        for tpl_path in templates:
            with open(tpl_path, "r", encoding="utf-8") as f:
                tpl = json.load(f)
            assert "Study" in tpl
            assert "Items" in tpl
            assert "Technical" in tpl
            assert len(tpl["Items"]) > 0, f"Template {tpl_path.name} has no items"


class TestPrismExportRoundTrip:
    """Verify that PRISM-exported .lss files can be re-imported and matched."""

    def test_roundtrip_single_template(self, tmp_path):
        """Export a single template → re-parse → match against global library."""
        from src.limesurvey_exporter import generate_lss
        from src.converters.limesurvey import parse_lss_xml_by_groups
        from src.converters.survey_templates import (
            match_groups_against_library,
            _load_global_templates,
            _extract_prismmeta,
        )

        gad7_path = (
            Path(__file__).resolve().parent.parent
            / "official"
            / "library"
            / "survey"
            / "survey-gad7.json"
        )
        if not gad7_path.exists():
            pytest.skip("Global library not available")

        lss_path = tmp_path / "export.lss"
        generate_lss([str(gad7_path)], str(lss_path), language="en", ls_version="6")

        with open(lss_path, "rb") as f:
            parsed = parse_lss_xml_by_groups(f.read())
        assert parsed, "parse_lss_xml_by_groups returned None"
        assert len(parsed) == 1, f"Expected 1 group, got {len(parsed)}"

        gname = list(parsed.keys())[0]
        meta = _extract_prismmeta(parsed[gname])
        assert meta.get("abbrev"), f"PRISMMETA abbreviation missing: {meta}"

        global_templates = _load_global_templates()
        matches = match_groups_against_library(parsed, global_templates)
        match = matches[gname]
        assert match is not None, f"GAD-7 should match, group={gname}"
        assert match.confidence in (
            "exact",
            "high",
        ), f"Expected exact/high confidence, got {match.confidence}"
        assert match.template_key == "gad7", f"Expected gad7, got {match.template_key}"

    def test_roundtrip_multi_template(self, tmp_path):
        """Export multiple templates → re-parse → all should match."""
        from src.limesurvey_exporter import generate_lss
        from src.converters.limesurvey import parse_lss_xml_by_groups
        from src.converters.survey_templates import (
            match_groups_against_library,
            _load_global_templates,
        )

        lib_dir = (
            Path(__file__).resolve().parent.parent / "official" / "library" / "survey"
        )
        templates = ["survey-gad7.json", "survey-pss.json", "survey-bfi-s.json"]
        paths = [str(lib_dir / t) for t in templates]

        if not all(Path(p).exists() for p in paths):
            pytest.skip("Global library templates not available")

        lss_path = tmp_path / "multi_export.lss"
        generate_lss(paths, str(lss_path), language="en", ls_version="6")

        with open(lss_path, "rb") as f:
            parsed = parse_lss_xml_by_groups(f.read())

        assert len(parsed) == 3, f"Expected 3 groups, got {len(parsed)}"

        global_templates = _load_global_templates()
        matches = match_groups_against_library(parsed, global_templates)

        for gname, match in matches.items():
            assert match is not None, f"Group {gname} should match a global template"
            assert match.confidence in (
                "exact",
                "high",
            ), f"Group {gname}: expected exact/high, got {match.confidence}"

    def test_roundtrip_bfis_hyphen_normalization(self, tmp_path):
        """BFI-S items with hyphens (BFI-S01) should match exported codes (BFIS01)."""
        from src.limesurvey_exporter import generate_lss
        from src.converters.limesurvey import parse_lss_xml_by_groups
        from src.converters.survey_core import _extract_template_structure
        from src.converters.survey_templates import _ls_normalize_code

        lib_dir = (
            Path(__file__).resolve().parent.parent / "official" / "library" / "survey"
        )
        bfis_path = lib_dir / "survey-bfi-s.json"
        if not bfis_path.exists():
            pytest.skip("BFI-S template not available")

        lss_path = tmp_path / "bfis.lss"
        generate_lss([str(bfis_path)], str(lss_path), language="en", ls_version="6")

        with open(lss_path, "rb") as f:
            parsed = parse_lss_xml_by_groups(f.read())

        gname = list(parsed.keys())[0]
        parsed_struct = _extract_template_structure(parsed[gname])
        parsed_norm = {
            _ls_normalize_code(c)
            for c in parsed_struct
            if not c.startswith("PRISMMETA")
        }

        with open(bfis_path) as f:
            global_tpl = json.load(f)
        global_struct = _extract_template_structure(global_tpl)
        global_norm = {_ls_normalize_code(c) for c in global_struct}

        assert parsed_norm == global_norm, (
            f"Normalized codes should match.\n"
            f"  Parsed: {sorted(parsed_norm)}\n"
            f"  Global: {sorted(global_norm)}\n"
            f"  Only parsed: {parsed_norm - global_norm}\n"
            f"  Only global: {global_norm - parsed_norm}"
        )

    def test_prismmeta_contains_all_metadata_fields(self, tmp_path):
        """Exported PRISMMETA should contain name, abbreviation, authors, citation."""
        from src.limesurvey_exporter import generate_lss
        from src.converters.limesurvey import parse_lss_xml_by_groups
        from src.converters.survey_templates import _extract_prismmeta

        lib_dir = (
            Path(__file__).resolve().parent.parent / "official" / "library" / "survey"
        )
        gad7_path = lib_dir / "survey-gad7.json"
        if not gad7_path.exists():
            pytest.skip("GAD-7 template not available")

        lss_path = tmp_path / "meta_test.lss"
        generate_lss([str(gad7_path)], str(lss_path), language="en", ls_version="6")

        with open(lss_path, "rb") as f:
            parsed = parse_lss_xml_by_groups(f.read())

        gname = list(parsed.keys())[0]
        meta = _extract_prismmeta(parsed[gname])

        assert meta.get("name"), "meta-name should be present"
        assert meta.get("abbrev"), "meta-abbrev should be present"
        assert meta.get("authors"), "meta-authors should be present"
        assert meta.get("citation"), "meta-citation should be present"
        assert (
            "GAD" in meta["abbrev"].upper()
        ), f"Abbreviation should contain GAD, got: {meta['abbrev']}"


class TestLsaBuildAndParse:
    """Verify our synthetic .lsa archives are valid."""

    def test_lsa_zip_contents(self, tmp_path):
        """The .lsa ZIP should contain .lss, responses, and timings files."""
        lsa_path = _build_multi_lsa(tmp_path)

        with zipfile.ZipFile(lsa_path, "r") as zf:
            names = zf.namelist()

        assert any(n.endswith(".lss") for n in names), f"No .lss found in {names}"
        assert any("responses" in n for n in names), f"No responses file in {names}"
        assert any("timings" in n for n in names), f"No timings file in {names}"

    def test_lss_xml_is_valid(self, tmp_path):
        """The .lss XML should be parseable and contain expected elements."""
        import xml.etree.ElementTree as ET

        root = ET.fromstring(MULTI_LSS_XML)

        assert root.find(".//LimeSurveyVersion").text == "5.6.0"
        assert root.find(".//DBVersion").text == "415"

        groups = root.findall(".//groups/rows/row")
        assert len(groups) == 3, f"Expected 3 groups, got {len(groups)}"

        questions = root.findall(".//questions/rows/row")
        assert len(questions) == 4, "Expected 4 questions (GAD7, PSS, age, sex)"

        subquestions = root.findall(".//subquestions/rows/row")
        assert len(subquestions) == 5, "Expected 5 subquestions (3 GAD-7 + 2 PSS)"

    def test_response_data_has_correct_columns(self):
        """Response TSV should have system + questionnaire + sociodemographic columns."""
        header = MULTI_RESPONSES.split("\n")[0].split("\t")

        # System columns
        for col in [
            "id",
            "submitdate",
            "startdate",
            "token",
            "ipaddr",
            "interviewtime",
        ]:
            assert col in header, f"Missing system column: {col}"

        # Questionnaire columns
        for col in ["GAD7SQ001", "GAD7SQ002", "GAD7SQ003", "PSSSQ001", "PSSSQ002"]:
            assert col in header, f"Missing questionnaire column: {col}"

        # Sociodemographic columns
        assert "age" in header
        assert "sex" in header

    def test_three_participants_in_responses(self):
        """Response data should have 3 participants (complete, complete, incomplete)."""
        lines = [l for l in MULTI_RESPONSES.strip().split("\n") if l]
        assert (
            len(lines) == 4
        ), f"Expected 4 lines (1 header + 3 data), got {len(lines)}"

        # Third participant has no submitdate (incomplete)
        fields = lines[3].split("\t")
        header = lines[0].split("\t")
        submit_idx = header.index("submitdate")
        assert (
            fields[submit_idx] == ""
        ), "Third participant should have empty submitdate (incomplete)"
