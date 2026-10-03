"""Reject requests that another website makes to this local server.

A page the user visits can fire form posts / <img> GETs at
http://127.0.0.1:<port>; the Host header is genuine then, so the DNS-rebinding
check does not catch it. Browsers label such requests: `Sec-Fetch-Site`
(cross-site / same-site) and an `Origin` that is not this server. CLI clients
and tests send neither and pass through.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from flask import Flask, jsonify, request

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


def install_cross_site_guard(app: Flask) -> None:
    @app.before_request
    def _reject_cross_site():
        if is_cross_site_request(request.method, request.path, request.headers, request.host):
            return jsonify({"error": "Forbidden"}), 403
        return None
