from src.runner import _check_survey_recipe_coverage


def test_recipe_coverage_uses_project_recipe_folder(tmp_path) -> None:
    validate_root = tmp_path / "rawdata_validate"
    survey_dir = validate_root / "sub-01" / "survey"
    survey_dir.mkdir(parents=True)
    (survey_dir / "sub-01_task-ads_survey.tsv").write_text("x\n1\n", encoding="utf-8")

    project_root = tmp_path / "project"
    recipe_dir = project_root / "code" / "recipes" / "survey"
    recipe_dir.mkdir(parents=True)
    (recipe_dir / "recipe-ads.json").write_text("{}", encoding="utf-8")

    issues = _check_survey_recipe_coverage(
        str(validate_root), project_path=str(project_root)
    )

    assert issues == []


def test_recipe_coverage_names_missing_task_ids(tmp_path) -> None:
    validate_root = tmp_path / "rawdata_validate"
    survey_dir = validate_root / "sub-01" / "survey"
    survey_dir.mkdir(parents=True)
    (survey_dir / "sub-01_task-missingalpha_survey.tsv").write_text(
        "x\n1\n", encoding="utf-8"
    )
    (survey_dir / "sub-01_task-missingbeta_survey.tsv").write_text(
        "x\n1\n", encoding="utf-8"
    )

    project_root = tmp_path / "project"
    issues = _check_survey_recipe_coverage(
        str(validate_root), project_path=str(project_root)
    )

    assert len(issues) == 1
    level, message, path = issues[0]
    assert level == "WARNING"
    assert "Survey recipe coverage in code/recipes/survey is incomplete" in message
    assert "Found: none" in message
    assert "Missing: missingalpha, missingbeta" in message
    assert path.endswith("code\\recipes\\survey") or path.endswith("code/recipes/survey")


def test_recipe_coverage_ignores_non_prefixed_json_files(tmp_path) -> None:
    validate_root = tmp_path / "rawdata_validate"
    survey_dir = validate_root / "sub-01" / "survey"
    survey_dir.mkdir(parents=True)
    (survey_dir / "sub-01_task-ads_survey.tsv").write_text("x\n1\n", encoding="utf-8")

    project_root = tmp_path / "project"
    recipe_dir = project_root / "code" / "recipes" / "survey"
    recipe_dir.mkdir(parents=True)
    (recipe_dir / "ads.json").write_text("{}", encoding="utf-8")

    issues = _check_survey_recipe_coverage(
        str(validate_root), project_path=str(project_root)
    )

    assert len(issues) == 1
    assert "Found: none" in issues[0][1]
    assert "Missing: ads" in issues[0][1]


def test_recipe_coverage_reports_found_and_missing_from_project_folder(tmp_path) -> None:
    validate_root = tmp_path / "rawdata_validate"
    survey_dir = validate_root / "sub-01" / "survey"
    survey_dir.mkdir(parents=True)
    (survey_dir / "sub-01_task-ads_survey.tsv").write_text("x\n1\n", encoding="utf-8")
    (survey_dir / "sub-01_task-phq9_survey.tsv").write_text("x\n1\n", encoding="utf-8")

    project_root = tmp_path / "project"
    recipe_dir = project_root / "code" / "recipes" / "survey"
    recipe_dir.mkdir(parents=True)
    (recipe_dir / "recipe-ads.json").write_text("{}", encoding="utf-8")

    issues = _check_survey_recipe_coverage(
        str(validate_root), project_path=str(project_root)
    )

    assert len(issues) == 1
    assert "Found: ads" in issues[0][1]
    assert "Missing: phq9" in issues[0][1]