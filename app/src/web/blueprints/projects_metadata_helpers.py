import json
from pathlib import Path


def _get_bids_file_path(project_path: Path, filename: str) -> Path:
    return project_path / filename


def _read_project_json(project_path: Path) -> dict:
    """Read and return project.json content from a project directory."""
    pj = project_path / "project.json"
    if not pj.exists():
        return {}
    with open(pj, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_project_json(project_path: Path, data: dict):
    """Write project.json to disk, updating LastModified metadata if present."""
    from src.cross_platform import CrossPlatformFile

    pj = project_path / "project.json"
    CrossPlatformFile.write_text(
        str(pj), json.dumps(data, indent=2, ensure_ascii=False)
    )


_NA_VALUES = {"na", "n/a", "nan", "", "none", "null", "missing", "n.a."}


def _read_participants_schema(project_path: Path) -> dict:
    """Read participants.json schema if it exists."""
    for candidate in [
        project_path / "rawdata" / "participants.json",
        project_path / "participants.json",
    ]:
        if candidate.exists():
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def _resolve_level_label(value: str, levels: dict, lang: str = "en") -> str | None:
    """Map a coded value to its human-readable label using Levels dict."""
    from src.reporting import get_i18n_text

    if str(value).strip().lower() in _NA_VALUES:
        return None
    label_obj = levels.get(str(value))
    if label_obj is None:
        return str(value)
    return get_i18n_text(label_obj, lang) or str(value)


def _compute_participant_stats(project_path: Path, lang: str = "en") -> dict | None:
    """Read participants.tsv and compute demographic summary statistics."""
    tsv_path = _get_bids_file_path(project_path, "participants.tsv")
    if not tsv_path.exists():
        return None

    try:
        import pandas as pd

        df = pd.read_csv(tsv_path, sep="\t")
        if df.empty:
            return None

        schema = _read_participants_schema(project_path)
        stats: dict = {"n": len(df)}

        age_col = None
        for candidate in ["age", "Age", "AGE"]:
            if candidate in df.columns:
                age_col = candidate
                break
        if age_col:
            ages = pd.to_numeric(df[age_col], errors="coerce").dropna()
            if len(ages) > 0:
                stats["age_mean"] = round(float(ages.mean()), 2)
                stats["age_sd"] = (
                    round(float(ages.std(ddof=1)), 2) if len(ages) > 1 else None
                )
                stats["age_min"] = int(ages.min())
                stats["age_max"] = int(ages.max())

        sex_col = None
        for candidate in ["sex", "Sex", "SEX", "gender", "Gender"]:
            if candidate in df.columns:
                sex_col = candidate
                break
        if sex_col:
            series = df[sex_col].astype(str)
            mask = ~series.str.strip().str.lower().isin(_NA_VALUES)
            series = series[mask]
            counts = series.value_counts()

            sex_schema = schema.get(sex_col) or schema.get(sex_col.lower()) or {}
            sex_levels = sex_schema.get("Levels") or {}

            if sex_levels:
                mapped: dict[str, int] = {}
                for val, cnt in counts.items():
                    label = _resolve_level_label(val, sex_levels, lang)
                    if label is None:
                        continue
                    mapped[label] = mapped.get(label, 0) + int(cnt)
            else:
                label_map = {
                    "M": "male",
                    "m": "male",
                    "1": "male",
                    "F": "female",
                    "f": "female",
                    "2": "female",
                    "O": "other",
                    "o": "other",
                }
                mapped = {}
                for val, cnt in counts.items():
                    sv = str(val).strip()
                    if sv.lower() in _NA_VALUES:
                        continue
                    label = label_map.get(sv, sv)
                    mapped[label] = mapped.get(label, 0) + int(cnt)

            stats["sex_counts"] = dict(sorted(mapped.items(), key=lambda x: -x[1]))

        skip_cols = {
            "participant_id",
            "age",
            "sex",
            "gender",
            "session",
            "session_date",
            "group",
        }
        from src.reporting import get_i18n_text

        additional: list[dict] = []
        for col in df.columns:
            if col.lower() in skip_cols:
                continue
            col_schema = schema.get(col) or {}
            col_levels = col_schema.get("Levels") or {}
            if not col_levels:
                continue
            col_desc = col_schema.get("Description")
            col_label = (
                get_i18n_text(col_desc, lang) if col_desc else col.replace("_", " ")
            )

            series = df[col].astype(str)
            mask = ~series.str.strip().str.lower().isin(_NA_VALUES)
            series = series[mask]
            if series.empty:
                continue
            counts = series.value_counts()
            distribution: dict[str, int] = {}
            for val, cnt in counts.items():
                label = _resolve_level_label(val, col_levels, lang)
                if label is None:
                    continue
                distribution[label] = distribution.get(label, 0) + int(cnt)
            if distribution:
                additional.append({"name": col_label, "distribution": distribution})

        stats["additional_columns"] = additional[:5]
        return stats
    except Exception:
        return None


_EXPERIMENTAL_TYPES = {
    "randomized-controlled-trial",
    "quasi-experimental",
    "case-control",
}

_EDITABLE_SECTIONS = (
    "Basics",
    "Overview",
    "StudyDesign",
    "Recruitment",
    "Eligibility",
    "DataCollection",
    "Procedure",
    "MissingData",
    "References",
    "Conditions",
)


def _compute_methods_completeness(
    project_data: dict, dataset_desc: dict | None
) -> dict:
    """Compute weighted completeness score across fields feeding methods generation."""
    sd = project_data.get("StudyDesign") or {}
    rec = project_data.get("Recruitment") or {}
    elig = project_data.get("Eligibility") or {}
    proc = project_data.get("Procedure") or {}
    cond = project_data.get("Conditions") or {}
    sessions = project_data.get("Sessions") or []
    task_defs = project_data.get("TaskDefinitions") or {}
    dd = dataset_desc or {}

    is_experimental = sd.get("Type", "") in _EXPERIMENTAL_TYPES

    def _filled(val) -> bool:
        if val is None:
            return False
        if isinstance(val, str):
            return bool(val.strip())
        if isinstance(val, (list, dict)):
            return len(val) > 0
        if isinstance(val, (int, float)):
            return True
        return bool(val)

    def _obj_filled(obj, key):
        if not isinstance(obj, dict):
            return False
        return _filled(obj.get(key))

    fields: list[tuple[str, str, int, str, bool]] = [
        ("StudyDesign", "Type", 3, "Select the study design type", _filled(sd.get("Type"))),
        ("StudyDesign", "ConditionType", 2, "Condition type", _filled(cond.get("Type"))),
        (
            "StudyDesign",
            "TypeDescription",
            2,
            "Describe the design in detail",
            _filled(sd.get("TypeDescription")),
        ),
        (
            "Recruitment",
            "Method",
            3,
            "How were participants recruited?",
            _filled(rec.get("Method")),
        ),
        (
            "Recruitment",
            "Location",
            3,
            "Where were participants recruited?",
            _filled(rec.get("Location")),
        ),
        (
            "Recruitment",
            "Period.Start",
            3,
            "When did recruitment begin?",
            _obj_filled(rec.get("Period"), "Start"),
        ),
        (
            "Recruitment",
            "Period.End",
            2,
            "When did recruitment end?",
            _obj_filled(rec.get("Period"), "End"),
        ),
        (
            "Recruitment",
            "Compensation",
            2,
            "Participant compensation",
            _filled(rec.get("Compensation")),
        ),
        (
            "Eligibility",
            "InclusionCriteria",
            3,
            "List inclusion criteria",
            _filled(elig.get("InclusionCriteria")),
        ),
        (
            "Eligibility",
            "ExclusionCriteria",
            3,
            "List exclusion criteria",
            _filled(elig.get("ExclusionCriteria")),
        ),
        (
            "Eligibility",
            "TargetSampleSize",
            1,
            "Planned sample size",
            _filled(elig.get("TargetSampleSize")),
        ),
        (
            "Eligibility",
            "PowerAnalysis",
            1,
            "Power analysis description",
            _filled(elig.get("PowerAnalysis")),
        ),
        (
            "Procedure",
            "Overview",
            3,
            "Narrative procedure overview",
            _filled(proc.get("Overview")),
        ),
        (
            "Procedure",
            "InformedConsent",
            2,
            "Informed consent procedure",
            _filled(proc.get("InformedConsent")),
        ),
        (
            "Procedure",
            "QualityControl",
            2,
            "Quality control measures",
            _filled(proc.get("QualityControl")),
        ),
        (
            "Procedure",
            "MissingDataHandling",
            1,
            "Missing data handling",
            _filled(proc.get("MissingDataHandling")),
        ),
        (
            "Procedure",
            "Debriefing",
            1,
            "Debriefing procedure",
            _filled(proc.get("Debriefing")),
        ),
        (
            "Basics",
            "Name",
            3,
            "Dataset name (dataset_description.json)",
            _filled(dd.get("Name")),
        ),
        (
            "Basics",
            "Authors",
            3,
            "Authors (dataset_description.json)",
            _filled(dd.get("Authors")),
        ),
        (
            "Basics",
            "Description",
            2,
            "Dataset overview text",
            _filled((project_data.get("Overview") or {}).get("Main") or dd.get("Description")),
        ),
        ("Basics", "EthicsApprovals", 2, "Ethics approvals", _filled(dd.get("EthicsApprovals"))),
        ("Basics", "License", 2, "Data license", _filled(dd.get("License"))),
        ("Basics", "Keywords", 1, "Keywords for discoverability", _filled(dd.get("Keywords"))),
        ("Basics", "Acknowledgements", 1, "Acknowledgements", _filled(dd.get("Acknowledgements"))),
        ("Basics", "DatasetDOI", 1, "Dataset DOI", _filled(dd.get("DatasetDOI"))),
        ("Basics", "DatasetType", 1, "Dataset type", _filled(dd.get("DatasetType"))),
        ("Basics", "HEDVersion", 1, "HED version", _filled(dd.get("HEDVersion"))),
        ("Basics", "Funding", 1, "Funding", _filled(dd.get("Funding"))),
        ("Basics", "HowToAcknowledge", 1, "How to acknowledge", _filled(dd.get("HowToAcknowledge"))),
        ("Basics", "ReferencesAndLinks", 1, "References and links", _filled(dd.get("ReferencesAndLinks"))),
        (
            "Overview",
            "Main",
            3,
            "Dataset overview",
            _filled((project_data.get("Overview") or {}).get("Main")),
        ),
        (
            "Overview",
            "IndependentVariables",
            1,
            "Independent variables",
            _filled((project_data.get("Overview") or {}).get("IndependentVariables")),
        ),
        (
            "Overview",
            "DependentVariables",
            1,
            "Dependent variables",
            _filled((project_data.get("Overview") or {}).get("DependentVariables")),
        ),
        (
            "Overview",
            "ControlVariables",
            1,
            "Control variables",
            _filled((project_data.get("Overview") or {}).get("ControlVariables")),
        ),
        (
            "Overview",
            "QualityAssessment",
            1,
            "Quality assessment",
            _filled((project_data.get("Overview") or {}).get("QualityAssessment")),
        ),
        (
            "SessionsTasks",
            "Sessions",
            3,
            "Define at least one session",
            len(sessions) > 0,
        ),
        (
            "SessionsTasks",
            "TaskDefinitions",
            3,
            "Define at least one task",
            len(task_defs) > 0,
        ),
    ]

    if is_experimental:
        fields.extend(
            [
                (
                    "StudyDesign",
                    "Blinding",
                    1,
                    "Blinding procedure (experimental studies)",
                    _filled(sd.get("Blinding")),
                ),
                (
                    "StudyDesign",
                    "Randomization",
                    1,
                    "Randomization method",
                    _filled(sd.get("Randomization")),
                ),
                (
                    "StudyDesign",
                    "ControlCondition",
                    1,
                    "Control condition",
                    _filled(sd.get("ControlCondition")),
                ),
            ]
        )

    required_fields = {
        "Basics": {"Name"},
        "Overview": {"Main"},
        "StudyDesign": {"Type"},
        "Recruitment": {
            "Method",
            "Location",
            "Period.Start",
            "Period.End",
            "Compensation",
        },
        "Eligibility": {"InclusionCriteria", "ExclusionCriteria"},
        "Procedure": {"Overview"},
    }

    sections_map: dict[str, dict] = {}
    total_weight = 0
    filled_weight = 0
    total_fields = 0
    filled_fields = 0

    for section_key, field_name, priority, hint, is_filled in fields:
        is_required = field_name in required_fields.get(section_key, set())
        if section_key not in sections_map:
            sections_map[section_key] = {
                "fields": [],
                "filled": 0,
                "total": 0,
                "weight_filled": 0,
                "weight_total": 0,
                "required_filled": 0,
                "required_total": 0,
                "optional_filled": 0,
                "optional_total": 0,
                "read_only": section_key in ("SessionsTasks",),
            }
        sec = sections_map[section_key]
        sec["fields"].append(
            {
                "name": field_name,
                "filled": is_filled,
                "priority": priority,
                "hint": hint,
                "required": is_required,
            }
        )
        sec["total"] += 1
        sec["weight_total"] += priority
        if is_required:
            sec["required_total"] += 1
        else:
            sec["optional_total"] += 1
        total_weight += priority
        total_fields += 1
        if is_filled:
            sec["filled"] += 1
            sec["weight_filled"] += priority
            if is_required:
                sec["required_filled"] += 1
            else:
                sec["optional_filled"] += 1
            filled_weight += priority
            filled_fields += 1

    score = round(filled_weight / total_weight * 100) if total_weight else 0

    return {
        "score": score,
        "filled_fields": filled_fields,
        "total_fields": total_fields,
        "sections": sections_map,
    }


def _auto_detect_study_hints(project_path: Path, project_data: dict) -> dict:
    """Scan project files to auto-detect study metadata from existing data."""
    hints: dict[str, dict] = {}
    dataset_root = project_path

    platforms: list[str] = []
    versions: list[str] = []
    methods: list[str] = []

    if dataset_root.is_dir():
        for sidecar in dataset_root.glob("task-*_survey.json"):
            try:
                with open(sidecar, "r", encoding="utf-8") as f:
                    sc = json.load(f)
                tech = sc.get("Technical") or {}
                if tech.get("SoftwarePlatform"):
                    platforms.append(tech["SoftwarePlatform"])
                if tech.get("SoftwareVersion"):
                    versions.append(tech["SoftwareVersion"])
                method = (
                    tech.get("CollectionMethod")
                    or tech.get("AdministrationMethod")
                    or ""
                )
                if method:
                    methods.append(method)
            except Exception:
                pass
        for sidecar in dataset_root.glob("tool-*_survey.json"):
            try:
                with open(sidecar, "r", encoding="utf-8") as f:
                    sc = json.load(f)
                tech = sc.get("Technical") or {}
                if tech.get("SoftwarePlatform"):
                    platforms.append(tech["SoftwarePlatform"])
                if tech.get("SoftwareVersion"):
                    versions.append(tech["SoftwareVersion"])
            except Exception:
                pass

    if platforms:
        from collections import Counter

        top_platform = Counter(platforms).most_common(1)[0][0]
        hints["DataCollection.Platform"] = {
            "value": top_platform,
            "source": "task sidecar",
        }
    if versions:
        from collections import Counter

        top_version = Counter(versions).most_common(1)[0][0]
        hints["DataCollection.PlatformVersion"] = {
            "value": top_version,
            "source": "task sidecar",
        }
    if methods:
        from collections import Counter

        top_method = Counter(methods).most_common(1)[0][0]
        hints["DataCollection.Method"] = {
            "value": top_method,
            "source": "task sidecar",
        }

    if "DataCollection.Method" not in hints and platforms:
        online_platforms = {
            "limesurvey",
            "qualtrics",
            "redcap",
            "surveymonkey",
            "prolific",
            "mturk",
            "gorilla",
            "pavlovia",
            "formr",
            "sosci",
            "soscisurvey",
            "unipark",
        }
        if any(p.lower().replace(" ", "") in online_platforms for p in platforms):
            hints["DataCollection.Method"] = {
                "value": "online",
                "source": "inferred from platform",
            }

    if "DataCollection.Platform" not in hints:
        converter_platforms = {
            "survey-lsa": "LimeSurvey",
        }
        sessions = project_data.get("Sessions") or []
        for s in sessions:
            for t in s.get("tasks") or []:
                src = t.get("source") or {}
                conv = src.get("converter", "")
                if conv in converter_platforms:
                    hints["DataCollection.Platform"] = {
                        "value": converter_platforms[conv],
                        "source": "conversion provenance",
                    }
                    if not hints.get("DataCollection.Method"):
                        hints["DataCollection.Method"] = {
                            "value": "online",
                            "source": "inferred from converter",
                        }
                    break
            if "DataCollection.Platform" in hints:
                break

    if dataset_root.is_dir():
        sub_dirs = [
            d
            for d in dataset_root.iterdir()
            if d.is_dir() and d.name.startswith("sub-")
        ]
        if sub_dirs:
            hints["Eligibility.ActualSampleSize"] = {
                "value": len(sub_dirs),
                "source": "dataset root sub-* folders",
            }

    tsv_path = _get_bids_file_path(project_path, "participants.tsv")
    if tsv_path.exists():
        try:
            import pandas as pd

            df = pd.read_csv(tsv_path, sep="\t")
            hints["Eligibility.ActualSampleSize"] = {
                "value": len(df),
                "source": "participants.tsv",
            }
            for col in ["group", "Group", "GROUP"]:
                if col in df.columns:
                    groups = df[col].dropna().unique().tolist()
                    if len(groups) > 1:
                        hints["Conditions.Groups"] = {
                            "value": [
                                {
                                    "id": str(g).lower().replace(" ", "_"),
                                    "label": str(g),
                                    "description": "",
                                }
                                for g in sorted(groups)
                            ],
                            "source": "participants.tsv group column",
                        }
                        hints["Conditions.Type"] = {
                            "value": "between-subjects",
                            "source": "inferred from group column",
                        }
                    break
        except Exception:
            pass

    earliest_date = None
    latest_date = None
    sessions = project_data.get("Sessions") or []
    for s in sessions:
        for t in s.get("tasks") or []:
            src = t.get("source") or {}
            conv_date = src.get("convertedAt", "")
            if conv_date:
                if earliest_date is None or conv_date < earliest_date:
                    earliest_date = conv_date
                if latest_date is None or conv_date > latest_date:
                    latest_date = conv_date
    if earliest_date:
        hints["Recruitment.Period.Start"] = {
            "value": earliest_date[:7],
            "source": "earliest conversion date",
        }
    if latest_date:
        hints["Recruitment.Period.End"] = {
            "value": latest_date[:7],
            "source": "latest conversion date",
        }

    if len(sessions) > 1:
        hints["StudyDesign.Type"] = {
            "value": "longitudinal",
            "source": f"{len(sessions)} sessions detected",
        }
    elif len(sessions) == 1:
        hints["StudyDesign.Type"] = {
            "value": "cross-sectional",
            "source": "single session detected",
        }

    return hints