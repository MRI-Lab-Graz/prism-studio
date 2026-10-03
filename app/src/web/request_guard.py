"""Reject requests that another website makes to this local server.

A page the user visits can fire form posts / <img> GETs at
http://127.0.0.1:<port>; the Host header is genuine then, so the DNS-rebinding
check does not catch it. Browsers label such requests: `Sec-Fetch-Site`
(cross-site / same-site) and an `Origin` that is not this server. CLI clients
and tests send neither and pass through.
"""

from __future__ import annotations

import hmac
from urllib.parse import urlsplit

from flask import Flask, g, jsonify, request

_API_PREFIXES = ("/api/", "/editor/api/")


def is_cross_site_request(method: str, path: str, headers, host: str) -> bool:
    origin = headers.get("Origin")
    if origin is not None and urlsplit(origin).netloc != host:
        return True
    site = headers.get("Sec-Fetch-Site")
    if site in (None, "same-origin", "none"):
        return False
    # A link from another site to one of our pages is fine; to an API it is not.
    is_page_navigation = (
        method in ("GET", "HEAD")
        and headers.get("Sec-Fetch-Mode") == "navigate"
        and not path.startswith(_API_PREFIXES)
    )
    return not is_page_navigation


def install_public_token_guard(app: Flask) -> None:
    """With `--public` the UI is reachable on the network without a login, so
    every request must carry the per-launch token printed at startup
    (`?token=` once, then a cookie; `X-Prism-Token` for scripts). A no-op while
    `app.config["PRISM_ACCESS_TOKEN"]` is unset (default localhost-only mode)."""

    def _matches(supplied, token) -> bool:
        return bool(supplied) and hmac.compare_digest(supplied, token)

    @app.before_request
    def _require_token():
        token = app.config.get("PRISM_ACCESS_TOKEN")
        if not token or request.path == "/health":
            return None
        if _matches(request.args.get("token"), token):
            g.prism_token_from_query = True
            return None
        if _matches(request.headers.get("X-Prism-Token"), token) or _matches(
            request.cookies.get("prism_token"), token
        ):
            return None
        return jsonify({"error": "Access token required"}), 401

    @app.after_request
    def _remember_token(response):
        if g.get("prism_token_from_query"):
            response.set_cookie(
                "prism_token", app.config["PRISM_ACCESS_TOKEN"], httponly=True, samesite="Strict"
            )
        return response


def install_security_headers(app: Flask) -> None:
    """No framing (clickjacking), no MIME sniffing, no referrer leakage.

    A full script-src CSP needs the templates' inline scripts cleaned up first.
    """

    @app.after_request
    def _add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response


def install_cross_site_guard(app: Flask) -> None:
    @app.before_request
    def _reject_cross_site():
        if is_cross_site_request(request.method, request.path, request.headers, request.host):
            return jsonify({"error": "Forbidden"}), 403
        return None
