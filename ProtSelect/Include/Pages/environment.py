"""
The Environment Setup page.

Reports which of the external tools the plugin drives are present, installs the
ones that can be installed, and saves the resulting paths into the plugin
configuration so the blocks find them.

Horus mounts these endpoints under the page's own URL, so the HTML reaches them
with relative fetches.
"""

import flask

import HorusAPI

import env_manager


def get_status():
    """Return the state of every tool, plus which blocks are currently blocked."""
    remote = flask.request.args.get("remote", "Local")
    try:
        rows = env_manager.status(remote)
        return {
            "remote": remote,
            "tools": rows,
            "blocked": env_manager.blocked_blocks(rows),
            "config_path": env_manager.config_path(remote),
        }
    except Exception as error:  # pylint: disable=broad-except
        return {"error": str(error)}, 500


def post_install():
    """
    Install one tool.

    Credentials arrive in the body, are handed to the installer, and are dropped
    when this returns. They are redacted from the log and never persisted.
    """
    payload = flask.request.get_json(silent=True) or {}
    key = payload.get("key")
    if not key:
        return {"error": "No tool was given."}, 400

    remote = payload.get("remote", "Local")
    try:
        result = env_manager.install(
            key,
            options=payload.get("options") or {},
            credentials=payload.get("credentials") or {},
            remote=remote,
        )
        return {"ok": True, "log": result["log"], "config": result["config"]}
    except Exception as error:  # pylint: disable=broad-except
        # The message may quote a failing command, so redact anything supplied
        # as a credential before it reaches the page.
        message = str(error)
        for secret in (payload.get("credentials") or {}).values():
            if secret:
                message = message.replace(str(secret), "***")
        return {"ok": False, "error": message}, 500


def post_save_paths():
    """Write the detected (or user-edited) paths into the plugin configuration."""
    payload = flask.request.get_json(silent=True) or {}
    remote = payload.get("remote", "Local")
    values = payload.get("values")

    try:
        if not values:
            values = env_manager.detected_paths(remote)
        if not values:
            return {"ok": False, "error": "There is nothing to save."}, 400
        path = env_manager.write_config(values, remote)
        return {"ok": True, "saved": values, "path": path}
    except Exception as error:  # pylint: disable=broad-except
        return {"ok": False, "error": str(error)}, 500


environment_page = HorusAPI.PluginPage(
    id="environment",
    name="Environment Setup",
    description="Check and install the external tools this plugin needs",
    html="environment.html",
    hidden=False,
)

environment_page.addEndpoint(
    HorusAPI.PluginEndpoint(url="/status", methods=["GET"], function=get_status)
)
environment_page.addEndpoint(
    HorusAPI.PluginEndpoint(url="/install", methods=["POST"], function=post_install)
)
environment_page.addEndpoint(
    HorusAPI.PluginEndpoint(url="/save_paths", methods=["POST"], function=post_save_paths)
)
