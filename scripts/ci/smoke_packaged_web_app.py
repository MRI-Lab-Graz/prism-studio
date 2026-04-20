#!/usr/bin/env python3
"""Smoke-test the packaged PRISM Studio web app with a real HTTP request."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def _pick_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _http_request(url: str, method: str = "GET") -> tuple[int, str]:
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            body = response.read(1200).decode("utf-8", errors="replace")
            return int(response.status), body
    except urllib.error.HTTPError as exc:
        body = exc.read(1200).decode("utf-8", errors="replace")
        return int(exc.code), body


def _tail_text_file(path: Path, start_offset: int = 0, max_chars: int = 4000) -> str:
    if not path.exists() or not path.is_file():
        return ""

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(start_offset)
            content = handle.read()
    except OSError:
        return ""

    content = content.strip()
    if len(content) <= max_chars:
        return content
    return content[-max_chars:]


def _read_capture_file(path: Path, max_chars: int = 4000) -> str:
    if not path.exists() or not path.is_file():
        return ""

    try:
        content = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""

    if len(content) <= max_chars:
        return content
    return content[-max_chars:]


def _fail(
    message: str,
    process: subprocess.Popen[str] | None,
    log_excerpt: str,
    stdout_capture: Path,
    stderr_capture: Path,
) -> int:
    print(f"[ERROR] {message}")

    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    output = "\n".join(
        text
        for text in (
            _read_capture_file(stdout_capture),
            _read_capture_file(stderr_capture),
        )
        if text
    )
    if output:
        print("[INFO] Process output:")
        print(output)

    if log_excerpt:
        print("[INFO] prism_studio.log excerpt:")
        print(log_excerpt)

    return 1


def _require_runtime_capabilities(base_url: str) -> tuple[bool, str]:
    status, body = _http_request(f"{base_url}/api/runtime-capabilities", method="GET")
    if status >= 400:
        return False, (
            "Runtime capabilities endpoint returned "
            f"HTTP {status}. Response excerpt: {body[:400]}"
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        return False, f"Runtime capabilities endpoint returned invalid JSON: {exc}"

    if payload.get("pyreadstat_write_support") is not True:
        return False, (
            "Packaged app does not report pyreadstat write support. "
            f"Payload excerpt: {str(payload)[:400]}"
        )

    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test packaged PRISM Studio")
    parser.add_argument(
        "--app-path",
        required=True,
        help="Path to packaged PRISM Studio executable",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port to bind to (default: auto-select a free port)",
    )
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=90.0,
        help="Seconds to wait for the packaged app to answer HTTP requests",
    )
    parser.add_argument(
        "--probe-path",
        action="append",
        default=None,
        help="HTTP path to probe; may be passed multiple times",
    )
    parser.add_argument(
        "--log-file",
        default=str(Path.home() / "prism_studio.log"),
        help="Path to the packaged app log file",
    )
    parser.add_argument(
        "--require-pyreadstat-write-support",
        action="store_true",
        help="Fail if the packaged app does not report SPSS write support",
    )
    args = parser.parse_args()

    app_path = Path(args.app_path).resolve()
    if not app_path.exists():
        raise SystemExit(f"Packaged app not found: {app_path}")

    host = args.host
    port = args.port or _pick_free_port(host)
    probe_paths = args.probe_path or ["/projects", "/", "/converter"]
    log_file = Path(args.log_file).expanduser().resolve()
    log_offset = log_file.stat().st_size if log_file.exists() else 0

    command = [
        str(app_path),
        "--no-browser",
        "--no-dedicated-terminal",
        "--host",
        host,
        "--port",
        str(port),
    ]

    env = os.environ.copy()
    env["PRISM_DISABLE_DEDICATED_TERMINAL"] = "1"
    env["PRISM_DEDICATED_TERMINAL_ATTACHED"] = "1"

    with tempfile.TemporaryDirectory(prefix="prism-packaged-smoke-") as capture_dir:
        capture_root = Path(capture_dir)
        stdout_capture = capture_root / "stdout.log"
        stderr_capture = capture_root / "stderr.log"

        with stdout_capture.open(
            "w", encoding="utf-8"
        ) as stdout_handle, stderr_capture.open("w", encoding="utf-8") as stderr_handle:
            process = subprocess.Popen(
                command,
                cwd=str(app_path.parent),
                env=env,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
            )

            try:
                deadline = time.time() + args.startup_timeout

                while time.time() < deadline:
                    if process.poll() is not None:
                        log_excerpt = _tail_text_file(log_file, start_offset=log_offset)
                        return _fail(
                            f"Packaged app exited before serving requests (code {process.returncode}).",
                            process,
                            log_excerpt,
                            stdout_capture,
                            stderr_capture,
                        )

                    try:
                        results: list[tuple[str, int, str]] = []
                        for probe_path in probe_paths:
                            status, body = _http_request(
                                f"http://{host}:{port}{probe_path}",
                                method="GET",
                            )
                            results.append((probe_path, status, body))

                        failures = [
                            (probe_path, status, body)
                            for probe_path, status, body in results
                            if status >= 400
                        ]
                        if failures:
                            probe_path, status, body = failures[0]
                            log_excerpt = _tail_text_file(
                                log_file, start_offset=log_offset
                            )
                            return _fail(
                                f"Packaged app returned HTTP {status} for {probe_path}. Response excerpt: {body[:400]}",
                                process,
                                log_excerpt,
                                stdout_capture,
                                stderr_capture,
                            )

                        break
                    except (
                        ConnectionRefusedError,
                        TimeoutError,
                        urllib.error.URLError,
                    ):
                        time.sleep(0.5)
                else:
                    log_excerpt = _tail_text_file(log_file, start_offset=log_offset)
                    return _fail(
                        f"Timed out waiting for packaged app to answer on http://{host}:{port}.",
                        process,
                        log_excerpt,
                        stdout_capture,
                        stderr_capture,
                    )

                if args.require_pyreadstat_write_support:
                    ok, failure_message = _require_runtime_capabilities(
                        f"http://{host}:{port}"
                    )
                    if not ok:
                        log_excerpt = _tail_text_file(log_file, start_offset=log_offset)
                        return _fail(
                            failure_message,
                            process,
                            log_excerpt,
                            stdout_capture,
                            stderr_capture,
                        )

                shutdown_url = f"http://{host}:{port}/shutdown"
                status, body = _http_request(shutdown_url, method="POST")
                if status >= 400:
                    log_excerpt = _tail_text_file(log_file, start_offset=log_offset)
                    return _fail(
                        f"Shutdown endpoint returned HTTP {status}. Response excerpt: {body[:400]}",
                        process,
                        log_excerpt,
                        stdout_capture,
                        stderr_capture,
                    )

                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)

                if process.returncode not in (0, None):
                    log_excerpt = _tail_text_file(log_file, start_offset=log_offset)
                    return _fail(
                        f"Packaged app exited with code {process.returncode} after shutdown.",
                        process,
                        log_excerpt,
                        stdout_capture,
                        stderr_capture,
                    )

                print(
                    f"[OK] Packaged app served HTTP probes successfully on http://{host}:{port}"
                )
                return 0
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
