import os
import sys
import importlib

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

generate_full_methods = importlib.import_module("src.reporting").generate_full_methods


def test_generate_full_methods_normalizes_markdownish_dataset_description():
    project_data = {}
    dataset_desc = {
        "Name": "PRISM Survey Dataset",
        "Description": '"Krea"-Rohdaten beinhalten\n\n# sex\n\n# age\n\n# handedness\n\nauf Einzeltitem-Basis.',
    }

    md_text, _ = generate_full_methods(
        project_data=project_data,
        dataset_desc=dataset_desc,
        template_data={},
        lang="en",
        detail_level="standard",
        continuous=True,
    )

    assert "# sex" not in md_text
    assert "sex, age, and handedness" in md_text
    assert "auf Einzeltitem-Basis" in md_text


def test_generate_full_methods_enriches_survey_details_from_template():
    project_data = {
        "TaskDefinitions": {
            "ads": {
                "modality": "survey",
            }
        }
    }
    template_data = {
        "ads": {
            "Study": {
                "TaskName": {"en": "Affective Distress Scale"},
                "Description": {"en": "Measures distress symptoms."},
                "References": [
                    {"Type": "primary", "Citation": "Smith et al. (2020)"},
                    {"Type": "validation", "Citation": "Doe et al. (2021)"},
                ],
            },
            "q1": {
                "Levels": {
                    "1": {"en": "not at all"},
                    "2": {"en": "somewhat"},
                    "3": {"en": "very much"},
                }
            },
            "q2": {
                "Levels": {
                    "1": {"en": "not at all"},
                    "2": {"en": "somewhat"},
                    "3": {"en": "very much"},
                }
            },
        }
    }

    md_text, _ = generate_full_methods(
        project_data=project_data,
        dataset_desc=None,
        template_data=template_data,
        lang="en",
        detail_level="detailed",
        continuous=True,
    )

    assert "Affective Distress Scale" in md_text
    assert "comprises 2 items and a 3-point Likert scale" in md_text
    assert "Smith et al. (2020)" in md_text
    assert "Validation evidence: Doe et al. (2021)." in md_text


def test_generate_full_methods_uses_clean_fallback_for_short_task_codes():
    project_data = {
        "TaskDefinitions": {
            "ads": {
                "modality": "survey",
                "description": "ads",
            }
        }
    }

    md_text, _ = generate_full_methods(
        project_data=project_data,
        dataset_desc=None,
        template_data={},
        lang="en",
        detail_level="standard",
        continuous=True,
    )

    assert "The ADS was administered." in md_text
    assert "The ads." not in md_text


def test_generate_full_methods_skips_instruction_like_descriptions():
    project_data = {
        "TaskDefinitions": {
            "ribs": {
                "modality": "survey",
            }
        }
    }
    template_data = {
        "ribs": {
            "Study": {
                "TaskName": {"de": "Runco Ideational Behavior Scale"},
                "Description": {
                    "de": (
                        "Dieser Fragebogen umfasst Aussagen, welche sich zur Beschreibung "
                        "Ihrer Kreativität eignen könnten. Lesen Sie bitte jede dieser Aussagen "
                        "aufmerksam durch und entscheiden Sie, wie sehr die jeweilige Aussage "
                        "auf Sie zutrifft."
                    )
                },
            },
            "item_01": {
                "Levels": {
                    "1": {"de": "Trifft nicht zu"},
                    "2": {"de": "Trifft völlig zu"},
                }
            },
        }
    }

    md_text, _ = generate_full_methods(
        project_data=project_data,
        dataset_desc=None,
        template_data=template_data,
        lang="de",
        detail_level="standard",
        continuous=True,
    )

    assert "Lesen Sie bitte" not in md_text
    assert "entscheiden Sie" not in md_text


def test_generate_full_methods_does_not_fallback_to_other_i18n_language():
    project_data = {
        "TaskDefinitions": {
            "ribs": {
                "modality": "survey",
            }
        }
    }
    template_data = {
        "ribs": {
            "Study": {
                "TaskName": {"de": "Runco Ideational Behavior Scale"},
                "Description": {"de": "Nur deutsch verfuegbar."},
            },
            "item_01": {
                "Levels": {
                    "1": {"de": "Trifft nicht zu"},
                    "2": {"de": "Trifft voellig zu"},
                }
            },
        }
    }

    md_text, _ = generate_full_methods(
        project_data=project_data,
        dataset_desc=None,
        template_data=template_data,
        lang="en",
        detail_level="standard",
        continuous=True,
    )

    # No German fallback labels in English output when only German i18n entries exist.
    assert "Trifft nicht zu" not in md_text
    assert "Trifft voellig zu" not in md_text


# ---- Task 6: journal order, short boilerplate, warnings ---------------------

_FULL_PROJECT = {
    "StudyDesign": {"Type": "cross-sectional"},
    "Recruitment": {"Method": "flyers"},
    "Sessions": [{"id": "ses-1", "label": "Baseline", "tasks": [{"task": "ads"}]}],
    "TaskDefinitions": {"ads": {"modality": "survey"}},
}
_FULL_DD = {"Funding": ["DFG"], "License": "CC0", "EthicsApprovals": ["Ethics board X"]}


def _full(detail="standard", dd=_FULL_DD):
    return generate_full_methods(
        project_data=_FULL_PROJECT,
        dataset_desc=dd,
        template_data={},
        lang="en",
        detail_level=detail,
    )


def test_section_order():
    _, used = _full()
    order = ["Participants", "StudyDesign", "Procedure", "Measures", "Ethics", "DataAvailability", "Funding"]
    order = [k if k != "Ethics" else "EthicsStatement" for k in order]
    idx = [used.index(k) for k in order]
    assert idx == sorted(idx)


def test_boilerplate_is_short():
    md, used = _full()
    assert "enforcing standardized filename patterns" not in md
    assert "PRISM Studio v" in md
    assert "DataStandardization" in used
    assert "Data Standardization and Validation" not in md


def test_brief_has_no_standardization_or_new_sections():
    md, used = _full("brief")
    assert "PRISM Studio v" not in md
    assert "DataStandardization" not in used


def test_standardization_sentence_sits_in_data_availability():
    md, _ = _full()
    avail = md.split("## Data Availability")[1].split("## ")[0]
    assert "PRISM Studio v" in avail


def test_warnings_missing_n():
    from src.reporting import methods_warnings

    w = methods_warnings({}, None, {})
    assert any("sample size" in x for x in w)
    assert methods_warnings({"Eligibility": {"TargetSampleSize": 40}}, None, {}) == []
    assert methods_warnings({}, {"n": 12}, {}) == []


def test_warnings_instrument_without_citation():
    from src.reporting import methods_warnings

    project = {"TaskDefinitions": {"ads": {"modality": "survey"}}}
    w = methods_warnings(project, {"n": 5}, {"ads": {"Study": {"TaskName": {"en": "ADS"}}}})
    assert len(w) == 1 and "ads" in w[0]


def test_no_warnings_complete_project():
    from src.reporting import methods_warnings

    project = {"TaskDefinitions": {"ads": {"modality": "survey"}}}
    tpl = {"ads": {"Study": {"References": [{"Type": "primary", "Citation": "Smith (2020)"}]}}}
    assert methods_warnings(project, {"n": 5}, tpl) == []


# ---- Task 7: acquisition section ---------------------------------------------

_ACQ = {
    "modalities": {
        "func": {
            "n_subjects": 2,
            "sessions": {"1": 1, "01": 1},
            "params": {
                "RepetitionTime": [2.0],
                "EchoTime": [0.03],
                "FlipAngle": [90],
                "MagneticFieldStrength": [3],
                "Manufacturer": ["Siemens"],
                "ManufacturersModelName": ["Prisma"],
            },
        }
    }
}


def _acq(detail="standard", lang="en", acq=_ACQ):
    return generate_full_methods(
        project_data={},
        dataset_desc=None,
        template_data={},
        lang=lang,
        detail_level=detail,
        continuous=True,
        acquisition=acq,
    )


def test_acquisition_section_has_parameters_and_verbatim_sessions():
    md, used = _acq()
    assert "TR = 2000 ms" in md and "TE = 30 ms" in md and "3 T Siemens Prisma" in md
    assert "N = 2" not in md and "2 participants" in md
    assert "1 (*n* = 1)" in md and "01 (*n* = 1)" in md
    assert "DataAcquisition" in used


def test_acquisition_section_brief_and_empty():
    assert "TR =" not in _acq("brief")[0]
    assert "DataAcquisition" not in _acq(acq={"modalities": {}})[1]


def test_acquisition_section_de_is_not_mixed_language():
    md, _ = _acq(lang="de")
    assert "TR = 2000 ms" in md
    assert "were acquired" not in md and "participants" not in md


# ---- Task 8: processing section -----------------------------------------------

_PROC = {
    "recipes": [{"task": "dass21", "scores": ["Depression", "Anxiety"]}],
    "software": {"prism_version": "9.9.9", "modality_schemas": {"survey": "1.2.0"}},
}


def _proc(detail="standard", lang="en", proc=_PROC):
    return generate_full_methods(
        project_data={},
        dataset_desc=None,
        template_data={},
        lang=lang,
        detail_level=detail,
        continuous=True,
        processing=proc,
    )


def test_processing_names_task_scores_and_software():
    md, used = _proc()
    assert "dass21" in md and "Depression, Anxiety" in md
    assert "PRISM Studio v9.9.9" in md and "survey 1.2.0" in md
    assert "DataProcessing" in used


def test_processing_without_recipes_or_exclusions_adds_nothing():
    md, used = _proc(proc={"recipes": [], "software": _PROC["software"]})
    assert "processed with" not in md and "DataProcessing" not in used


def test_processing_brief_is_empty():
    assert "9.9.9" not in _proc("brief")[0]


def test_processing_has_no_exclusion_sentence_without_count():
    assert "did not meet" not in _proc()[0]
    md, _ = _proc(proc={**_PROC, "eligibility_flags": 3})
    assert "3 participants did not meet" in md


def test_processing_de_is_not_mixed_language():
    md, _ = _proc(lang="de")
    assert "Depression, Anxiety" in md
    assert "were scored" not in md and "Software" in md


# ---- Task 9: richer participants / procedure / measures ------------------------

_TPL9 = {
    "ads": {
        "Study": {
            "TaskName": {"en": "Affective Distress Scale"},
            "Subscales": ["Worry", "Tension"],
            "AdministrationTime": {"min": 5, "max": 10},
            "License": "CC BY 4.0",
        }
    }
}


def _measures(detail="standard", tpl=_TPL9):
    return generate_full_methods(
        project_data={"TaskDefinitions": {"ads": {"modality": "survey"}}},
        dataset_desc=None,
        template_data=tpl,
        lang="en",
        detail_level=detail,
        continuous=True,
    )[0]


def test_standard_measures_state_subscales_time_and_license():
    md = _measures()
    assert "subscales: Worry, Tension" in md
    assert "approximately 5-10 minutes" in md
    assert "License: CC BY 4.0." in md


def test_brief_measures_skip_the_new_details():
    md = _measures("brief")
    assert "Worry" not in md and "License" not in md


def test_unverified_license_is_not_published():
    tpl = {"ads": {"Study": {"License": "NOT VERIFIED: the upstream page states nothing"}}}
    assert "NOT VERIFIED" not in _measures(tpl=tpl)


def test_procedure_keeps_session_labels_verbatim():
    md, _ = generate_full_methods(
        project_data={
            "Sessions": [
                {"id": "ses-1", "label": "1", "tasks": []},
                {"id": "ses-01", "label": "01", "tasks": []},
            ]
        },
        dataset_desc=None,
        template_data={},
        continuous=True,
    )
    assert '("1")' in md and '("01")' in md


def test_participants_state_per_session_n_when_counts_differ():
    acq = {"modalities": {"func": {"n_subjects": 40, "sessions": {"1": 40, "01": 35}, "params": {}}}}
    md, _ = generate_full_methods(
        project_data={"Recruitment": {"Method": "flyers"}},
        dataset_desc=None,
        template_data={},
        continuous=True,
        acquisition=acq,
    )
    assert "*N* = 40 at 1, *N* = 35 at 01" in md


def test_participants_no_per_session_n_when_counts_equal():
    acq = {"modalities": {"func": {"n_subjects": 5, "sessions": {"1": 5, "2": 5}, "params": {}}}}
    md, _ = generate_full_methods(
        project_data={"Recruitment": {"Method": "flyers"}},
        dataset_desc=None,
        template_data={},
        continuous=True,
        acquisition=acq,
    )
    assert " at 1," not in md


def test_session_id_label_is_shown_exactly_without_ses_prefix():
    md, _ = generate_full_methods(
        project_data={"Sessions": [{"id": "ses-pre", "tasks": []}, {"id": "ses-01", "tasks": []}]},
        dataset_desc=None,
        template_data={},
        continuous=True,
    )
    assert '("pre")' in md and '("01")' in md


# ---- review fixes -------------------------------------------------------------

_DIFF_ACQ = {"modalities": {"func": {"n_subjects": 3, "sessions": {"1": 3, "01": 2}, "params": {}}}}


def test_brief_has_no_per_session_n_sentence():
    md, _ = generate_full_methods(
        project_data={"Recruitment": {"Method": "flyers"}},
        dataset_desc=None,
        template_data={},
        detail_level="brief",
        continuous=True,
        acquisition=_DIFF_ACQ,
    )
    assert "differed between sessions" not in md


def test_de_omits_new_english_only_sentences():
    md, _ = generate_full_methods(
        project_data={
            "Recruitment": {"Method": "flyers"},
            "TaskDefinitions": {"ads": {"modality": "survey"}},
            "Sessions": [{"id": "ses-1", "tasks": []}, {"id": "ses-2", "tasks": []}],
        },
        dataset_desc=None,
        template_data=_TPL9,
        lang="de",
        continuous=True,
        acquisition=_DIFF_ACQ,
    )
    for english in ("differed between sessions", "has the subscales", "License:", "Administration takes", "took place", "followed."):
        assert english not in md


def test_device_line_skips_non_numeric_field_strength():
    acq = {"modalities": {"func": {"n_subjects": 1, "sessions": {}, "params": {"MagneticFieldStrength": ["3T"], "Manufacturer": ["Siemens"]}}}}
    md, _ = _acq(acq=acq)
    assert "  T" not in md and " T Siemens" not in md
