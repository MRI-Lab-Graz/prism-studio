"""End-to-end test: synthetic LimeSurvey .lsa → PRISM conversion with system variables."""

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

# ── Synthetic .lsa builder ──────────────────────────────────────────

LSS_XML = """\
<?xml version='1.0' encoding='UTF-8'?>
<document>
  <LimeSurveyDocType>Survey</LimeSurveyDocType>
  <DBVersion>415</DBVersion>
  <LimeSurveyVersion>6.0.0</LimeSurveyVersion>
  <languages>
    <language>en</language>
  </languages>
  <answers>
    <rows>
      <row><qid>201</qid><code>1</code><sortorder>1</sortorder><assessment_value>0</assessment_value><scale_id>0</scale_id></row>
      <row><qid>201</qid><code>2</code><sortorder>2</sortorder><assessment_value>0</assessment_value><scale_id>0</scale_id></row>
      <row><qid>201</qid><code>3</code><sortorder>3</sortorder><assessment_value>0</assessment_value><scale_id>0</scale_id></row>
      <row><qid>201</qid><code>4</code><sortorder>4</sortorder><assessment_value>0</assessment_value><scale_id>0</scale_id></row>
      <row><qid>201</qid><code>5</code><sortorder>5</sortorder><assessment_value>0</assessment_value><scale_id>0</scale_id></row>
    </rows>
  </answers>
  <questions>
    <rows>
      <row>
        <qid>201</qid><parent_qid>0</parent_qid><sid>999999</sid><gid>10</gid>
        <type>F</type><title>MTEST</title><other>N</other><mandatory>Y</mandatory>
        <question_order>1</question_order><scale_id>0</scale_id>
        <same_default>0</same_default><relevance>1</relevance>
      </row>
    </rows>
  </questions>
  <groups>
    <rows>
      <row><gid>10</gid><sid>999999</sid><group_order>1</group_order></row>
    </rows>
  </groups>
  <subquestions>
    <rows>
      <row><qid>301</qid><parent_qid>201</parent_qid><sid>999999</sid><gid>10</gid><type>T</type><title>SQ001</title><question_order>1</question_order><scale_id>0</scale_id><same_default>0</same_default><relevance>1</relevance></row>
      <row><qid>302</qid><parent_qid>201</parent_qid><sid>999999</sid><gid>10</gid><type>T</type><title>SQ002</title><question_order>2</question_order><scale_id>0</scale_id><same_default>0</same_default><relevance>1</relevance></row>
      <row><qid>303</qid><parent_qid>201</parent_qid><sid>999999</sid><gid>10</gid><type>T</type><title>SQ003</title><question_order>3</question_order><scale_id>0</scale_id><same_default>0</same_default><relevance>1</relevance></row>
    </rows>
  </subquestions>
  <answer_l10ns>
    <rows>
      <row><id>1</id><qid>201</qid><code>1</code><answer>Strongly disagree</answer><language>en</language></row>
      <row><id>2</id><qid>201</qid><code>2</code><answer>Disagree</answer><language>en</language></row>
      <row><id>3</id><qid>201</qid><code>3</code><answer>Neutral</answer><language>en</language></row>
      <row><id>4</id><qid>201</qid><code>4</code><answer>Agree</answer><language>en</language></row>
      <row><id>5</id><qid>201</qid><code>5</code><answer>Strongly agree</answer><language>en</language></row>
    </rows>
  </answer_l10ns>
  <question_l10ns>
    <rows>
      <row><id>10</id><qid>201</qid><question>Please rate:</question><help /><language>en</language></row>
      <row><id>11</id><qid>301</qid><question>I feel happy</question><help /><language>en</language></row>
      <row><id>12</id><qid>302</qid><question>I feel calm</question><help /><language>en</language></row>
      <row><id>13</id><qid>303</qid><question>I feel energetic</question><help /><language>en</language></row>
    </rows>
  </question_l10ns>
  <group_l10ns>
    <rows>
      <row><id>1</id><gid>10</gid><group_name>Wellbeing</group_name><description /><language>en</language></row>
    </rows>
  </group_l10ns>
  <surveys>
    <rows>
      <row>
        <sid>999999</sid><owner_id>1</owner_id><admin>Admin</admin>
        <active>Y</active><anonymized>N</anonymized><format>G</format>
        <savetimings>Y</savetimings><template>vanilla</template>
        <language>en</language><datestamp>Y</datestamp><ipaddr>Y</ipaddr>
      </row>
    </rows>
  </surveys>
  <surveys_languagesettings>
    <rows>
      <row>
        <surveyls_survey_id>999999</surveyls_survey_id>
        <surveyls_language>en</surveyls_language>
        <surveyls_title>E2E Test Survey</surveyls_title>
      </row>
    </rows>
  </surveys_languagesettings>
</document>
"""

# VV-style response data (TSV) with system columns
RESPONSES_TSV = (
    "id\tsubmitdate\tstartdate\tdatestamp\tlastpage\tstartlanguage\tseed\ttoken\tipaddr\trefurl\tinterviewtime\tcompleted\tMTESTSQ001\tMTESTSQ002\tMTESTSQ003\n"
    "1\t2026-03-15 10:30:00\t2026-03-15 10:00:00\t2026-03-15 10:30:00\t2\ten\t42\tabc123\t192.168.1.10\thttps://example.com\t1800\tY\t4\t3\t5\n"
    "2\t2026-03-15 11:15:00\t2026-03-15 11:00:00\t2026-03-15 11:15:00\t2\ten\t99\tdef456\t192.168.1.20\t\t900\tY\t2\t4\t3\n"
    "3\t\t2026-03-15 12:00:00\t2026-03-15 12:05:00\t1\ten\t77\tghi789\t10.0.0.1\t\t300\tN\t1\t\t\n"
)

# Timing data
TIMINGS_TSV = (
    "id\tinterviewtime\tgrouptime10\n1\t1800\t1800\n2\t900\t900\n3\t300\t300\n"
)


def _build_lsa(tmp_path: Path) -> Path:
    """Build a synthetic .lsa (ZIP) file with .lss, responses, and timings."""
    lsa_path = tmp_path / "test_survey.lsa"
    with zipfile.ZipFile(lsa_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("survey_999999.lss", LSS_XML)
        # .lsr is XML-wrapped responses, but our converter also handles TSV
        # For this test, we'll write the responses as a CSV that the converter can read
        zf.writestr("survey_999999_responses.csv", RESPONSES_TSV)
        zf.writestr("survey_999999_timings.csv", TIMINGS_TSV)
    return lsa_path


# ── Tests ────────────────────────────────────────────────────────────


def test_system_column_detection_on_realistic_data():
    """Verify all system columns from synthetic LS data are detected."""
    from src.converters.survey_processing import _extract_limesurvey_columns

    columns = RESPONSES_TSV.split("\n")[0].split("\t")
    ls_cols, other_cols = _extract_limesurvey_columns(columns)

    # System columns should be detected
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
    assert expected_system == set(ls_cols)

    # Question columns should NOT be detected as system
    assert "MTESTSQ001" in other_cols
    assert "MTESTSQ002" in other_cols
    assert "MTESTSQ003" in other_cols


def test_timing_columns_detected():
    """Verify grouptime and questiontime patterns are detected."""
    from src.converters.survey_processing import _extract_limesurvey_columns

    columns = [
        "id",
        "grouptime10",
        "grouptime20",
        "questiontime301",
        "questiontime302",
        "duration_total",
        "Q1",
        "Q2",
    ]
    ls_cols, other_cols = _extract_limesurvey_columns(columns)

    assert "grouptime10" in ls_cols
    assert "grouptime20" in ls_cols
    assert "questiontime301" in ls_cols
    assert "questiontime302" in ls_cols
    assert "duration_total" in ls_cols
    assert "Q1" in other_cols
    assert "Q2" in other_cols
