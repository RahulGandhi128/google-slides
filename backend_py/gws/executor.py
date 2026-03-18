"""
gws CLI executor - runs gws commands via subprocess
"""
import json
import os
import platform
import shutil
import subprocess
import logging
import textwrap
from pathlib import Path

log = logging.getLogger("gws.executor")


def _get_gws_cmd() -> list[str]:
    """Get command to run gws. On Windows, use node + run-gws.js for reliable arg passing."""
    if platform.system() == "Windows" and os.environ.get("APPDATA"):
        run_gws = Path(os.environ["APPDATA"]) / "npm" / "node_modules" / "@googleworkspace" / "cli" / "run-gws.js"
        if run_gws.exists():
            node = shutil.which("node") or "node"
            return [node, str(run_gws)]
    return ["gws"]


def run_gws(args: list[str], params: dict | None = None, json_body: dict | None = None) -> dict | str | None:
    """
    Run a gws command and return parsed JSON
    Args:
        args: e.g. ["slides", "presentations", "create"]
        params: URL/query params
        json_body: Request body for POST/PATCH
    """
    base = _get_gws_cmd()
    all_args = list(args)
    if params:
        all_args.extend(["--params", json.dumps(params)])
    if json_body:
        all_args.extend(["--json", json.dumps(json_body)])

    env = os.environ.copy()
    env["GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND"] = "file"

    # Log the exact command so we can debug "unrecognized subcommand" and other CLI issues.
    # Keep payload logs truncated to avoid huge output in terminals.
    try:
        params_preview = textwrap.shorten(json.dumps(params, default=str), width=800) if params is not None else None
        json_preview = textwrap.shorten(json.dumps(json_body, default=str), width=800) if json_body is not None else None
    except Exception:
        params_preview = None
        json_preview = None

    log.info("Running gws: %s %s", base, all_args)
    if params_preview:
        log.info("gws --params preview: %s", params_preview)
    if json_preview:
        log.info("gws --json preview: %s", json_preview)

    result = subprocess.run(
        base + all_args,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        shell=False,
    )

    stdout = result.stdout.strip()
    if result.returncode != 0:
        err_stdout = stdout
        err_stderr = (result.stderr or "").strip()

        # Log both streams for maximum debuggability.
        log.error(
            "gws failed rc=%s. stdout=%s stderr=%s",
            result.returncode,
            textwrap.shorten(err_stdout, width=1200),
            textwrap.shorten(err_stderr, width=1200),
        )

        err = err_stdout
        if err_stdout.startswith("{"):
            try:
                data = json.loads(err_stdout)
                msg = data.get("error", {}).get("message", err)
            except json.JSONDecodeError:
                msg = err_stderr or err_stdout
        else:
            msg = err_stderr or err_stdout

        # Make sure the raised error includes the stderr snippet (this is where CLI subcommand errors usually are).
        if err_stderr and err_stderr not in msg:
            msg = f"{msg}\n\n[stderr]\n{err_stderr}"
        raise RuntimeError(msg)

    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return stdout
