"""
gws CLI executor - runs gws commands via subprocess
"""
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


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
        err = stdout
        if err.startswith("{"):
            try:
                data = json.loads(err)
                msg = data.get("error", {}).get("message", err)
            except json.JSONDecodeError:
                msg = result.stderr or err
        else:
            msg = result.stderr or err
        raise RuntimeError(msg)

    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return stdout
