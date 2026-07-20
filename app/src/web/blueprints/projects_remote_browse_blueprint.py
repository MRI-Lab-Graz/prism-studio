"""Browse and create folders on an SSH-accessible remote server.

Backs the "Browse..." folder picker next to the rsync Destination field and
the plain-SSH-sibling case of the DataLad Server URL field (see
`push_server_section.html`) -- both need a destination folder that may or
may not already exist yet on a server the app already has non-interactive
SSH access to.

`target` (the raw field value, e.g. "user@host:/path") is only accepted on
the first `list` call, so the "user@host:path" parsing rules
(`is_remote_target`/`split_remote_target`) live in exactly one place
(`rsync_execution.py`) rather than being duplicated in the frontend. Every
subsequent call (folder navigation, mkdir) uses the `host` the first
response already resolved, plus a `path`.
"""

from flask import Blueprint, jsonify, request

from src.remote_browse import create_remote_directory, list_remote_directory
from src.rsync_execution import is_remote_target, split_remote_target

projects_remote_browse_bp = Blueprint("projects_remote_browse", __name__)


def _resolve_host_and_path(args) -> tuple[str, str] | tuple[None, None]:
    host = str(args.get("host") or "").strip()
    path = str(args.get("path") or "").strip()
    if host:
        return host, path

    target = str(args.get("target") or "").strip()
    if target and is_remote_target(target):
        return split_remote_target(target)

    return None, None


@projects_remote_browse_bp.route("/api/projects/remote-browse/list", methods=["GET"])
def remote_browse_list():
    host, path = _resolve_host_and_path(request.args)
    if not host:
        return jsonify(
            {"error": "Not an SSH destination. Type one like user@host:/path first."}
        ), 400

    result = list_remote_directory(host, path)
    if not result.get("success"):
        return jsonify({"error": result.get("message") or "Could not list remote directory."}), 502

    return jsonify(
        {
            "host": host,
            "path": result["path"],
            "parent": result["parent"],
            "dirs": result["dirs"],
        }
    )


@projects_remote_browse_bp.route("/api/projects/remote-browse/mkdir", methods=["POST"])
def remote_browse_mkdir():
    data = request.get_json() or {}
    host, path = _resolve_host_and_path(data)
    if not host:
        return jsonify(
            {"error": "Not an SSH destination. Type one like user@host:/path first."}
        ), 400
    if not path:
        return jsonify({"error": "No folder name/path was provided."}), 400

    result = create_remote_directory(host, path)
    if not result.get("success"):
        return jsonify({"error": result.get("message") or "Could not create remote folder."}), 502

    return jsonify({"success": True, "host": host, "path": result["path"]})
