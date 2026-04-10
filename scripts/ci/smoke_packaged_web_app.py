#!/usr/bin/env python3
"""Smoke-test the packaged PRISM Studio web app with a real HTTP request."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
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


def _collect_process_output(process: subprocess.Popen[str]) -> str:
    chunks: list[str] = []

    for stream in (process.stdout, process.stderr):
        if stream is None:
            continue
        try:
            data = stream.read()
        except Exception:
            data = ""
        if data:
            chunks.append(data.strip())

    return "\n".join(chunk for chunk in chunks if chunk)


def _fail(message: str, process: subprocess.Popen[str] | None, log_excerpt: str) -> int:
    print(f"[ERROR] {message}")

    if process is not None:
        output = _collect_process_output(process)
        if output:
            print("[INFO] Process output:")
            print(output)

    if log_excerpt:
        print("[INFO] prism_studio.log excerpt:")
        print(log_excerpt)

    return 1


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
    args = parser.parse_args()

    app_path = Path(args.app_path).resolve()
    if not app_path.exists():
        raise SystemExit(f"Packaged app not found: {app_path}")

    host = args.host
    port = args.port or _pick_free_port(host)
    probe_paths = args.probe_path or ["/projects", "/"]
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

    process = subprocess.Popen(
        command,
        cwd=str(app_path.parent),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
                    log_excerpt = _tail_text_file(log_file, start_offset=log_offset)
                    return _fail(
                        f"Packaged app returned HTTP {status} for {probe_path}. Response excerpt: {body[:400]}",
                        process,
                        log_excerpt,
                    )

                break
            except (ConnectionRefusedError, TimeoutError, urllib.error.URLError):
                time.sleep(0.5)
        else:
            log_excerpt = _tail_text_file(log_file, start_offset=log_offset)
            return _fail(
                f"Timed out waiting for packaged app to answer on http://{host}:{port}.",
                process,
                log_excerpt,
            )

        shutdown_url = f"http://{host}:{port}/shutdown"
        status, body = _http_request(shutdown_url, method="POST")
        if status >= 400:
            log_excerpt = _tail_text_file(log_file, start_offset=log_offset)
            return _fail(
                f"Shutdown endpoint returned HTTP {status}. Response excerpt: {body[:400]}",
                process,
                log_excerpt,
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