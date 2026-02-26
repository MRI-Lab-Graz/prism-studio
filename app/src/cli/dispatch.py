"""Command dispatch utilities for prism_tools CLI.

This module provides a central dispatch function. Command registration is
introduced incrementally as handlers are extracted from app/prism_tools.py.
"""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from typing import Callable, Mapping


CommandHandler = Callable[[Namespace], None]


def dispatch_command(
    args: Namespace,
    handlers: Mapping[str, CommandHandler],
) -> bool:
    """Dispatch to a top-level command handler if present.

    Returns True when a handler was found and executed, otherwise False.
    """
    command = getattr(args, "command", None)
    if not command:
        return False

    handler = handlers.get(command)
    if not handler:
        return False

    handler(args)
    return True


def dispatch_prism_tools(
    args: Namespace,
    parsers: Mapping[str, ArgumentParser],
    handlers: Mapping[str, CommandHandler],
) -> None:
    """Dispatch prism_tools commands with compatibility-preserving fallback help output."""
    root_parser = parsers["root"]

    if args.command == "anonymize":
        handlers["anonymize"](args)
    elif args.command == "convert" and args.modality == "physio":
        handlers["convert_physio"](args)
    elif args.command == "demo" and args.action == "create":
        handlers["demo_create"](args)
    elif args.command == "survey":
        if args.action == "import-excel":
            handlers["survey_import_excel"](args)
        elif args.action == "convert":
            handlers["survey_convert"](args)
        elif args.action == "validate":
            handlers["survey_validate"](args)
        elif args.action == "import-limesurvey":
            handlers["survey_import_limesurvey"](args)
        elif args.action == "import-limesurvey-batch":
            handlers["survey_import_limesurvey_batch"](args)
        elif args.action == "i18n-migrate":
            handlers["survey_i18n_migrate"](args)
        elif args.action == "i18n-build":
            handlers["survey_i18n_build"](args)
        else:
            parsers["survey"].print_help()
    elif args.command == "biometrics":
        if args.action == "import-excel":
            handlers["biometrics_import_excel"](args)
        else:
            parsers["biometrics"].print_help()
    elif args.command == "library":
        if args.action == "generate-methods-text":
            handlers["library_generate_methods_text"](args)
        elif args.action == "sync":
            handlers["library_sync"](args)
        elif args.action == "catalog":
            handlers["library_catalog"](args)
        elif args.action == "fill":
            handlers["library_fill"](args)
        else:
            parsers["library"].print_help()
    elif args.command == "dataset":
        if args.action == "build-biometrics-smoketest":
            handlers["dataset_build_biometrics_smoketest"](args)
        else:
            parsers["dataset"].print_help()
    elif args.command == "recipes":
        if args.kind in {"surveys", "survey", "surves"}:
            handlers["recipes_surveys"](args)
        elif args.kind in {"biometrics", "biometric"}:
            handlers["recipes_biometrics"](args)
        else:
            parsers["recipes"].print_help()
    else:
        root_parser.print_help()
