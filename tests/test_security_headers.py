from flask import Flask

from src.web.request_guard import install_security_headers


def _headers():
    app = Flask(__name__)
    install_security_headers(app)

    @app.route("/")
    def index():
        return "x"

    return app.test_client().get("/").headers


def test_blocks_framing_and_mime_sniffing():
    h = _headers()
    assert h["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in h["Content-Security-Policy"]
    assert h["X-Frame-Options"] == "DENY"
    assert h["Referrer-Policy"] == "no-referrer"
