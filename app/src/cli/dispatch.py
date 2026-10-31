"""Command dispatch utilities for prism_tools CLI.

This module provides a central dispatch function. Command registration is
introduced incrementally as handlers are extracted from app/prism_tools.py.
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Callable, Mapping

from src.project_ready import ProjectNotReadyError, require_project_ready

CommandHandler = Callable[[Namespace], None]

# Commands that must keep working on an unfinished project (they fix or inspect it).
GATE_EXEMPT_COMMANDS = {
    "settings",  # app settings, not a project
    "session-map",
    "environment",
    "demo",
    "save-gate",
    "preregistration",  # a draft is prepared before the project is complete
    "methods",  # like the GUI routes: gaps are reported as warnings, not blocked
}


def project_path_from_args(args: Namespace) -> str | None:
    for name in ("project", "dataset", "output", "prism"):
        value = getattr(args, name, None)
        if not value:
            continue
        path = Path(str(value)).expanduser()
        if path.name == "project.json" and path.is_file():
            return str(value)
        if (path / "project.json").is_file():
            return str(value)
    return None


def dispatch_prism_tools(
    args: Namespace,
    parsers: Mapping[str, ArgumentParser],
    handlers: Mapping[str, CommandHandler],
) -> None:
    """Dispatch prism_tools commands with compatibility-preserving fallback help output."""
    root_parser = parsers["root"]

    diagnostic = args.command == "datalad" and getattr(args, "action", None) == "doctor"
    if args.command not in GATE_EXEMPT_COMMANDS and not diagnostic:
        project = project_path_from_args(args)
        if project:
            try:
                require_project_ready(project)
            except ProjectNotReadyError as exc:
                print(f"Error: {exc}")
                print(
                    "In project.json set Basics.Name, Basics.Authors, Basics.Keywords and "
                    "StudyDesign.Timepoints (single or multiple)."
                )
                sys.exit(2)

    if args.command == "anonymize":
        handlers["anonymize"](args)
    elif args.command == "template-export":
        handlers["template_export"](args)
    elif args.command == "modality":
        if args.action == "propose":
            handlers["modality_propose"](args)
        else:
            parsers["modality"].print_help()
    elif args.command == "spec":
        if args.action == "local" and getattr(args, "local_action", None) in ("list", "add-term", "remove", "add-values", "remove-values"):
            handlers[f"spec_local_{args.local_action.replace('-', '_')}"](args)
        elif args.action == "propose":
            handlers["spec_propose"](args)
        elif args.action == "catalog":
            handlers["spec_catalog"](args)
        elif args.action == "example":
            handlers["spec_example"](args)
        elif args.action == "propose-values":
            handlers["spec_propose_values"](args)
        elif args.action == "propose-metric":
            handlers["spec_propose_metric"](args)
        elif args.action == "propose-new-kind":
            handlers["spec_propose_new_kind"](args)
        elif args.action == "check-kind-name":
            handlers["spec_check_kind_name"](args)
        else:
            parsers["spec"].print_help()
    elif args.command == "terms":
        if args.action in ("list", "show", "suggest", "propose"):
            handlers[f"terms_{args.action}"](args)
        else:
            parsers["terms"].print_help()
    elif args.command == "modality-version":
        if args.action in ("status", "list", "pin", "update", "freeze"):
            handlers[f"modality_version_{args.action}"](args)
        else:
            parsers["modality-version"].print_help()
    elif args.command == "convert" and args.modality == "physio":
        handlers["convert_physio"](args)
    elif args.command == "wide-to-long":
        handlers["wide_to_long"](args)
    elif args.command == "participants":
        if args.action == "detect-id":
            handlers["participants_detect_id"](args)
        elif args.action == "preview":
            handlers["participants_preview"](args)
        elif args.action == "convert":
            handlers["participants_convert"](args)
        elif args.action == "merge":
            handlers["participants_merge"](args)
        elif args.action == "save-mapping":
            handlers["participants_save_mapping"](args)
        elif args.action == "neurobagel-schema":
            handlers["participants_neurobagel_schema"](args)
        elif args.action == "save-schema":
            handlers["participants_save_schema"](args)
        elif args.action == "fix-bids":
            handlers["participants_fix_bids"](args)
        else:
            parsers["participants"].print_help()
    elif args.command == "export":
        if args.action in ("project", "folder", "git-lfs", "annex-availability", "structure", "deface-report", "deface-preflight", "deface", "anc", "openminds", "openminds-tasks"):
            handlers[f"export_{args.action.replace('-', '_')}"](args)
        else:
            parsers["export"].print_help()
    elif args.command == "settings":
        if args.action in ("show", "set"):
            handlers[f"settings_{args.action}"](args)
        else:
            parsers["settings"].print_help()
    elif args.command == "session-map":
        if args.action == "show":
            handlers["session_map_show"](args)
        elif args.action == "set":
            handlers["session_map_set"](args)
        elif args.action == "suggest":
            handlers["session_map_suggest"](args)
        elif args.action == "unset":
            handlers["session_map_unset"](args)
        else:
            parsers["session-map"].print_help()
    elif args.command == "preregistration":
        if args.action == "draft":
            handlers["preregistration_draft"](args)
        else:
            parsers["preregistration"].print_help()
    elif args.command == "project":
        if args.action in ("generate-readme", "regenerate-citation", "fixable", "fix", "delete", "set-schema-version"):
            handlers[f"project_{args.action.replace('-', '_')}"](args)
        else:
            parsers["project"].print_help()
    elif args.command == "rsync":
        if args.action in ("config", "sync"):
            handlers[f"rsync_{args.action}"](args)
        else:
            parsers["rsync"].print_help()
    elif args.command == "methods":
        if args.action == "generate":
            handlers["methods_generate"](args)
        else:
            parsers["methods"].print_help()
    elif args.command == "sessions":
        if args.action in ("review", "set", "unset"):
            handlers[f"sessions_{args.action}"](args)
        else:
            parsers["sessions"].print_help()
    elif args.command == "merge-versions":
        handlers["merge_versions"](args)
    elif args.command == "publish":
        handlers["publish"](args)
    elif args.command == "save-gate":
        handlers["save_gate"](args)
    elif args.command == "datalad":
        if args.action == "doctor":
            handlers["datalad_doctor"](args)
        elif args.action == "config":
            handlers["datalad_config"](args)
        elif args.action == "sync":
            handlers["datalad_sync"](args)
        elif args.action == "finalize":
            handlers["datalad_finalize"](args)
        elif args.action in ("enable", "save"):
            handlers[f"datalad_{args.action}"](args)
        else:
            parsers["datalad"].print_help()
    elif args.command == "environment":
        if args.action == "preview":
            handlers["environment_preview"](args)
        elif args.action == "convert":
            handlers["environment_convert"](args)
        elif args.action == "scan-mri":
            handlers["environment_scan_mri"](args)
        else:
            parsers["environment"].print_help()
    elif args.command == "demo" and args.action == "create":
        handlers["demo_create"](args)
    elif args.command == "survey":
        if args.action == "import-excel":
            handlers["survey_import_excel"](args)
        elif args.action == "convert":
            handlers["survey_convert"](args)
        elif args.action == "validate":
            handlers["survey_validate"](args)
        elif args.action == "export-lss":
            handlers["survey_export_lss"](args)
        elif args.action == "export-pavlovia":
            handlers["survey_export_pavlovia"](args)
        elif args.action == "customizer-groups":
            handlers["survey_customizer_groups"](args)
        elif args.action == "export-lss-customized":
            handlers["survey_export_lss_customized"](args)
        elif args.action == "export-questionnaire-docx":
            handlers["survey_export_questionnaire_docx"](args)
        elif args.action == "import-limesurvey":
            handlers["survey_import_limesurvey"](args)
        elif args.action == "import-codebook":
            handlers["survey_import_codebook"](args)
        elif args.action == "import-pavlovia":
            handlers["survey_import_pavlovia"](args)
        elif args.action == "answer-codes":
            handlers["survey_answer_codes"](args)
        elif args.action == "detect-columns":
            handlers["survey_detect_columns"](args)
        elif args.action == "detect-version-contexts":
            handlers["survey_detect_version_contexts"](args)
        elif args.action == "prepare-pavlovia":
            handlers["survey_prepare_pavlovia"](args)
        elif args.action == "import-limesurvey-batch":
            handlers["survey_import_limesurvey_batch"](args)
        elif args.action == "import-lsq":
            handlers["survey_import_lsq"](args)
        elif args.action == "i18n-migrate":
            handlers["survey_i18n_migrate"](args)
        elif args.action == "i18n-build":
            handlers["survey_i18n_build"](args)
        elif args.action == "i18n-autotranslate":
            handlers["survey_i18n_autotranslate"](args)
        else:
            parsers["survey"].print_help()
    elif args.command == "biometrics":
        if args.action == "detect":
            handlers["biometrics_detect"](args)
        elif args.action == "convert":
            handlers["biometrics_convert"](args)
        elif args.action == "import-excel":
            handlers["biometrics_import_excel"](args)
        else:
            parsers["biometrics"].print_help()
    elif args.command == "physio":
        if args.action == "batch-convert":
            handlers["physio_batch_convert"](args)
        else:
            parsers["physio"].print_help()
    elif args.command == "library":
        if args.action == "generate-methods-text":
            handlers["library_generate_methods_text"](args)
        elif args.action == "sync":
            handlers["library_sync"](args)
        elif args.action == "catalog":
            handlers["library_catalog"](args)
        elif args.action == "fill":
            handlers["library_fill"](args)
        elif args.action == "template-save":
            handlers["library_template_save"](args)
        elif args.action == "template-check":
            handlers["library_template_check"](args)
        elif args.action == "template-validate":
            handlers["library_template_validate"](args)
        elif args.action == "template-score":
            handlers["library_template_score"](args)
        elif args.action == "template-delete":
            handlers["library_template_delete"](args)
        elif args.action == "share-template":
            handlers["library_share_template"](args)
        elif args.action == "check-path":
            handlers["library_check_path"](args)
        else:
            parsers["library"].print_help()
    elif args.command == "dataset":
        if args.action == "build-biometrics-smoketest":
            handlers["dataset_build_biometrics_smoketest"](args)
        elif args.action == "cleanup-project-metadata":
            handlers["dataset_cleanup_project_metadata"](args)
        elif args.action == "rename-subjects":
            handlers["dataset_rename_subjects"](args)
        elif args.action == "rewrite-entities":
            handlers["dataset_rewrite_entities"](args)
        elif args.action == "rename-sessions":
            handlers["dataset_rename_sessions"](args)
        elif args.action == "renumber-runs":
            handlers["dataset_renumber_runs"](args)
        elif args.action == "undo":
            handlers["dataset_undo"](args)
        elif args.action == "build-hostile-demo":
            handlers["dataset_build_hostile_demo"](args)
        elif args.action == "validation-matrix":
            handlers["dataset_validation_matrix"](args)
        else:
            parsers["dataset"].print_help()
    elif args.command == "file-management":
        if args.action == "delete-files":
            handlers["file_management_delete_files"](args)
        elif args.action == "remove-scans-tsv":
            handlers["file_management_remove_scans_tsv"](args)
        elif args.action == "raw-peek":
            handlers["file_management_raw_peek"](args)
        elif args.action == "rename-physio":
            handlers["file_management_rename_physio"](args)
        else:
            parsers["file_management"].print_help()
    elif args.command == "json-editor":
        if args.action == "save":
            handlers["json_editor_save"](args)
        elif args.action == "validate":
            handlers["json_editor_validate"](args)
        else:
            parsers["json_editor"].print_help()
    elif args.command == "recipes":
        if args.kind in {"surveys", "survey", "surves"}:
            handlers["recipes_surveys"](args)
        elif args.kind in {"biometrics", "biometric"}:
            handlers["recipes_biometrics"](args)
        elif args.kind == "validate-file":
            handlers["recipes_validate_file"](args)
        elif args.kind == "save":
            handlers["recipes_save"](args)
        elif args.kind in {"templates", "draft", "load"}:
            handlers[f"recipes_{args.kind}"](args)
        else:
            parsers["recipes"].print_help()
    else:
        root_parser.print_help()
