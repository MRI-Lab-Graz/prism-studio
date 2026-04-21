"""Environment-related prism_tools command handlers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, cast

from src.web.blueprints.conversion_utils import normalize_separator_option


def _environment_backend_module() -> Any:
    import src.web.blueprints.conversion_environment_handlers as environment_module

    return environment_module


def _bool_arg(value: object, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    return default


def _emit_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _resolve_environment_preview_payload(
    input_path: Path, separator_option: str
) -> dict[str, Any]:
    environment_module = _environment_backend_module()

    suffix = input_path.suffix.lower()
    df = environment_module._load_environment_dataframe(
        input_path,
        suffix=suffix,
        separator_option=separator_option,
    )

    columns = list(df.columns)
    auto_timestamp = environment_module._detect_col(
        environment_module._CANDIDATE_TIMESTAMP,
        columns,
    )
    return {
        "columns": columns,
        "sample": df.head(5).fillna("").values.tolist(),
        "compatibility": environment_module._compatibility_report(
            df,
            columns,
            auto_timestamp,
        ),
        "auto_detected": {
            "participant_id": environment_module._detect_col(
                environment_module._CANDIDATE_PARTICIPANT,
                columns,
            ),
            "session": environment_module._detect_col(
                environment_module._CANDIDATE_SESSION,
                columns,
            ),
            "timestamp": auto_timestamp,
            "location": environment_module._detect_col(
                environment_module._CANDIDATE_LOCATION,
                columns,
            ),
            "lat": environment_module._detect_col(
                environment_module._CANDIDATE_LAT,
                columns,
            ),
            "lon": environment_module._detect_col(
                environment_module._CANDIDATE_LON,
                columns,
            ),
        },
    }


def _environment_log_callback(
    entries: list[dict[str, str]],
    *,
    log_file: Path | None,
    echo: bool,
) -> Callable[[str, str], None]:
    def _log(message: str, level: str = "info") -> None:
        entries.append({"message": message, "type": level})
        if log_file is not None:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as fh:
                fh.write(f"{level}\t{message}\n")
        if echo:
            print(message)

    return _log


def _resolve_environment_convert_payload(args) -> tuple[dict[str, object], int]:
    environment_module = _environment_backend_module()

    input_path = Path(args.input).expanduser().resolve()
    log_entries: list[dict[str, str]] = []
    log_file_text = str(getattr(args, "log_file", "") or "").strip()
    log_file = Path(log_file_text).expanduser().resolve() if log_file_text else None
    json_mode = bool(getattr(args, "json", False))
    log_callback = _environment_log_callback(
        log_entries,
        log_file=log_file,
        echo=not json_mode and log_file is None,
    )
    cancel_file_text = str(getattr(args, "cancel_file", "") or "").strip()
    cancel_file = (
        Path(cancel_file_text).expanduser().resolve() if cancel_file_text else None
    )

    try:
        result = environment_module._perform_environment_conversion(
            input_path=input_path,
            filename=input_path.name,
            suffix=input_path.suffix.lower(),
            separator_option=normalize_separator_option(
                getattr(args, "separator", None)
            ),
            timestamp_col=str(getattr(args, "timestamp_col", "") or "").strip() or None,
            participant_col=str(getattr(args, "participant_col", "") or "").strip()
            or None,
            participant_override=str(
                getattr(args, "participant_override", "") or ""
            ).strip()
            or None,
            session_col=str(getattr(args, "session_col", "") or "").strip() or None,
            session_override=str(getattr(args, "session_override", "") or "").strip()
            or None,
            location_col=str(getattr(args, "location_col", "") or "").strip() or None,
            lat_col=str(getattr(args, "lat_col", "") or "").strip() or None,
            lon_col=str(getattr(args, "lon_col", "") or "").strip() or None,
            location_label_override=str(
                getattr(args, "location_label", "") or ""
            ).strip(),
            lat_manual=(
                float(args.lat)
                if getattr(args, "lat", None) not in (None, "")
                else None
            ),
            lon_manual=(
                float(args.lon)
                if getattr(args, "lon", None) not in (None, "")
                else None
            ),
            project_path=str(getattr(args, "project", "") or "").strip(),
            pilot_random_subject=_bool_arg(
                getattr(args, "pilot_random_subject", False), default=False
            ),
            log_callback=log_callback,
            cancel_check=(
                (lambda: cancel_file.exists()) if cancel_file is not None else None
            ),
        )
        return {"log": log_entries, **result}, 0
    except ValueError as exc:
        return {"error": str(exc), "log": log_entries}, 2
    except Exception as exc:
        return {"error": str(exc), "log": log_entries}, 1


def cmd_environment_preview(args) -> None:
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        message = f"input file not found: {input_path}"
        if bool(getattr(args, "json", False)):
            _emit_json({"error": message})
        else:
            print(f"Error: {message}")
        sys.exit(1)

    environment_module = _environment_backend_module()
    allowed_suffixes = cast(set[str], environment_module.ALLOWED_SUFFIXES)
    suffix = input_path.suffix.lower()
    if suffix not in allowed_suffixes:
        allowed = ", ".join(sorted(allowed_suffixes))
        message = f"unsupported input type '{suffix}'. Supported: {allowed}"
        if bool(getattr(args, "json", False)):
            _emit_json({"error": message})
        else:
            print(f"Error: {message}")
        sys.exit(2)

    try:
        separator_option = normalize_separator_option(getattr(args, "separator", None))
        payload = _resolve_environment_preview_payload(input_path, separator_option)
    except ValueError as exc:
        if bool(getattr(args, "json", False)):
            _emit_json({"error": str(exc)})
        else:
            print(f"Error: {exc}")
        sys.exit(2)
    except Exception as exc:
        if bool(getattr(args, "json", False)):
            _emit_json({"error": str(exc)})
        else:
            print(f"Error: {exc}")
        sys.exit(1)

    if bool(getattr(args, "json", False)):
        _emit_json(payload)
        return

    print(f"Input:   {input_path}")
    print(f"Rows:    {len(payload['sample'])}")
    print(f"Columns: {', '.join(payload['columns'])}")
    print(f"Status:  {payload['compatibility']['status']}")
    print(
        "Auto:    participant={participant} session={session} timestamp={timestamp} location={location} lat={lat} lon={lon}".format(
            participant=payload["auto_detected"]["participant_id"] or "<none>",
            session=payload["auto_detected"]["session"] or "<none>",
            timestamp=payload["auto_detected"]["timestamp"] or "<none>",
            location=payload["auto_detected"]["location"] or "<none>",
            lat=payload["auto_detected"]["lat"] or "<none>",
            lon=payload["auto_detected"]["lon"] or "<none>",
        )
    )


def cmd_environment_convert(args) -> None:
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        payload: dict[str, object] = {
            "error": f"input file not found: {input_path}",
            "log": [],
        }
        if bool(getattr(args, "json", False)):
            _emit_json(payload)
        else:
            print(f"Error: {payload['error']}")
        sys.exit(1)

    payload, exit_code = _resolve_environment_convert_payload(args)

    result_file_text = str(getattr(args, "result_file", "") or "").strip()
    if result_file_text:
        result_file = Path(result_file_text).expanduser().resolve()
        result_file.parent.mkdir(parents=True, exist_ok=True)
        result_file.write_text(
            json.dumps(
                {
                    "done": True,
                    "success": exit_code == 0,
                    "result": payload if exit_code == 0 else None,
                    "error": None if exit_code == 0 else payload.get("error"),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    if bool(getattr(args, "json", False)) and not result_file_text:
        _emit_json(payload)
    elif exit_code != 0 and not result_file_text:
        print(f"Error: {payload.get('error', 'Environment conversion failed')}")
    else:
        log_items = payload.get("log")
        if isinstance(log_items, list):
            for entry in log_items:
                if isinstance(entry, dict):
                    message = str(entry.get("message") or "").strip()
                else:
                    message = str(entry).strip()
                if message:
                    print(message)

    if exit_code != 0:
        sys.exit(exit_code)
