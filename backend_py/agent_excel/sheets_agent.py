"""
Sheets agent (Google Sheets data injection)

Implements a Gemini function-calling agent that can create/read/update/format
Google Sheets via the `gws` CLI wrappers in `backend_py/gws/executor.py`.
All Sheets-specific code lives in this folder.
"""

from __future__ import annotations

import json
import logging
import os
import numbers
from typing import Any

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

from gws import run_gws

log = logging.getLogger("agent.sheets")


SHEETS_TOOLS: list[FunctionDeclaration] = [
    FunctionDeclaration(
        name="sheets_spreadsheets_create",
        description="Create a new Google Spreadsheet. Use when the user does not provide a spreadsheetId and needs a new sheet.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Spreadsheet title"}
            },
        },
    ),
    FunctionDeclaration(
        name="sheets_spreadsheets_get",
        description="Get spreadsheet metadata (including sheets/worksheet ids and titles). Use to confirm structure before writing ranges.",
        parameters={
            "type": "object",
            "properties": {"spreadsheetId": {"type": "string"}},
            "required": ["spreadsheetId"],
        },
    ),
    FunctionDeclaration(
        name="sheets_values_get",
        description="Read a range of cells from a spreadsheet using A1 notation (e.g. 'Sheet1!A1:D10').",
        parameters={
            "type": "object",
            "properties": {
                "spreadsheetId": {"type": "string"},
                "range": {"type": "string", "description": "A1 range (e.g. Sheet1!A1:C10)"},
                "majorDimension": {"type": "string", "description": "ROWS or COLUMNS"},
                "valueRenderOption": {"type": "string", "description": "FORMATTED_VALUE or UNFORMATTED_VALUE"},
            },
            "required": ["spreadsheetId", "range"],
        },
    ),
    FunctionDeclaration(
        name="sheets_values_update",
        description=(
            "Overwrite values in a range. Provide values as a 2D array: values[rowIndex][colIndex]. "
            "Use for header rows and deterministic table writes."
        ),
        parameters={
            "type": "object",
            "properties": {
                "spreadsheetId": {"type": "string"},
                "range": {"type": "string", "description": "A1 range start (e.g. Sheet1!A1)"},
                "valueInputOption": {"type": "string", "description": "USER_ENTERED or RAW"},
                "values": {
                    "type": "array",
                    "description": "2D values array (rows x cols). Each cell should be a string/number primitive.",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "required": ["spreadsheetId", "range", "values"],
        },
    ),
    FunctionDeclaration(
        name="sheets_values_append",
        description=(
            "Append values to the bottom of a sheet/table (still controlled by the provided A1 range). "
            "Use for adding new rows of financial data, transactions, or time series."
        ),
        parameters={
            "type": "object",
            "properties": {
                "spreadsheetId": {"type": "string"},
                "range": {"type": "string", "description": "A1 range start (e.g. Sheet1!A1)"},
                "valueInputOption": {"type": "string", "description": "USER_ENTERED or RAW"},
                "insertDataOption": {"type": "string", "description": "OVERWRITE or INSERT_ROWS"},
                "values": {
                    "type": "array",
                    "description": "2D values array (rows x cols). Each cell should be a string/number primitive.",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "required": ["spreadsheetId", "range", "values"],
        },
    ),
    FunctionDeclaration(
        name="sheets_spreadsheets_batchUpdate",
        description=(
            "Apply formatting and structural changes using the Sheets batchUpdate API. "
            "Use for beautification: bold header rows, borders, auto-resize columns, and basic styling."
        ),
        parameters={
            "type": "object",
            "properties": {
                "spreadsheetId": {"type": "string"},
                "requests": {
                    "type": "array",
                    "description": "Sheets API requests array (repeatCell, updateBorders, autoResizeDimensions, etc.)",
                    "items": {"type": "object"},
                },
            },
            "required": ["spreadsheetId", "requests"],
        },
    ),
]


SHEETS_SYSTEM = """You are a data-injection assistant for a sell-side investment bank. Your job is to build and populate Google Sheets for financial models and client-facing reporting. Be factual, precise, and professional. No fluff.

Language: Use the same language as the user request when it is clear; otherwise use standard financial and legal terminology based only on what the user provides and what the Sheets tool returns.

Core behavior:
- If spreadsheetId is known: write to it; otherwise ask for spreadsheetId or create a new spreadsheet if the user requests creation.
- When writing tabular content: always use a deterministic header row and then append/update rows under it.
- Use values as a 2D array for tool calls (rows x columns). Ensure range strings are valid A1 notation.
- If you create a new spreadsheet: assume the default worksheet name is `Sheet1` for ranges (unless `sheets_spreadsheets_get` output shows a different title).
- For formatting (batchUpdate): keep it minimal and consistent (e.g. bold header row, light borders, auto-resize columns). Do not attempt complex layouts unless explicitly requested.

Output requirements:
- Provide a short, tool-grounded summary of what you changed/read (ranges, row counts if available, and any key computed results derived from tool output).
- Do not claim effects you did not verify via tools.
- If an operation fails, return the error text you received and propose the next safest step.
"""


def _to_jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if hasattr(obj, "items") and callable(getattr(obj, "items")):
        try:
            return {str(k): _to_jsonable(v) for k, v in obj.items()}
        except Exception:
            pass
    if hasattr(obj, "__iter__") and not isinstance(obj, (bytes, str)):
        try:
            return [_to_jsonable(v) for v in obj]
        except Exception:
            pass
    return str(obj)


def _normalize_tool_args(args: dict) -> dict:
    """Normalize common Gemini output shapes to what our gws wrapper expects."""
    out = dict(args or {})
    # Gemini can sometimes return tuple-like lists or numbers as floats; normalize where safe.
    if "values" in out and isinstance(out["values"], list):
        # Keep as-is; gws will accept primitives as strings/numbers.
        pass
    return out


def _coerce_whole_number_floats_to_ints(obj: Any, keys: set[str]) -> Any:
    """
    Sheets batchUpdate schema is strict: index fields must be integers.
    Gemini sometimes emits 0.0 / 4.0, which become JSON numbers (floats).
    We coerce ONLY for known index keys.
    """

    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k in keys and isinstance(v, numbers.Real):
                # Gemini-provided values sometimes come through as non-`float` numeric
                # types (e.g. numpy/proto). Coerce any whole-number real to int.
                try:
                    fv = float(v)
                    if fv.is_integer():
                        out[k] = int(fv)
                    else:
                        out[k] = v
                except Exception:
                    out[k] = v
            else:
                out[k] = _coerce_whole_number_floats_to_ints(v, keys)
        return out

    if isinstance(obj, list):
        return [_coerce_whole_number_floats_to_ints(v, keys) for v in obj]

    return obj


def _execute_sheets_tool(name: str, args: dict, default_spreadsheet_id: str | None) -> str:
    try:
        log.info("Sheets tool call: %s args=%s", name, args)
        args = _normalize_tool_args(args)
        if default_spreadsheet_id and not args.get("spreadsheetId"):
            args["spreadsheetId"] = default_spreadsheet_id

        if name == "sheets_spreadsheets_create":
            title = args.get("title") or "Untitled Spreadsheet"
            r = run_gws(["sheets", "spreadsheets", "create"], json_body={"properties": {"title": title}})
            return json.dumps(r, indent=2) if isinstance(r, dict) else str(r)

        if name == "sheets_spreadsheets_get":
            r = run_gws(["sheets", "spreadsheets", "get"], params={"spreadsheetId": args["spreadsheetId"]})
            return json.dumps(r, indent=2) if isinstance(r, dict) else str(r)

        if name == "sheets_values_get":
            params: dict[str, Any] = {"spreadsheetId": args["spreadsheetId"], "range": args["range"]}
            if args.get("majorDimension"):
                params["majorDimension"] = args["majorDimension"]
            if args.get("valueRenderOption"):
                params["valueRenderOption"] = args["valueRenderOption"]
            r = run_gws(
                ["sheets", "spreadsheets.values", "get"],
                params=params,
            )
            return json.dumps(r, indent=2) if isinstance(r, dict) else str(r)

        if name == "sheets_values_update":
            params: dict[str, Any] = {
                "spreadsheetId": args["spreadsheetId"],
                "range": args["range"],
                "valueInputOption": args.get("valueInputOption") or "USER_ENTERED",
            }
            values = args.get("values") or []
            # Ensure each cell is a primitive string/number; USER_ENTERED can coerce strings to numbers.
            if isinstance(values, list):
                for r_idx, row in enumerate(values):
                    if not isinstance(row, list):
                        values[r_idx] = [str(row)]
                        continue
                    for c_idx, cell in enumerate(row):
                        if cell is None:
                            values[r_idx][c_idx] = ""
                        elif not isinstance(cell, (str, int, float, bool)):
                            values[r_idx][c_idx] = str(cell)
                        else:
                            # Normalize bools to strings to avoid schema mismatch.
                            values[r_idx][c_idx] = str(cell) if isinstance(cell, bool) else cell
            value_body = {"values": values}
            try:
                r = run_gws(
                    ["sheets", "spreadsheets.values", "update"],
                    params=params,
                    json_body=value_body,
                )
            except RuntimeError as e:
                # gws subcommand naming can vary by CLI generation; retry alternate form.
                msg = str(e).lower()
                if "unrecognized subcommand" in msg or "unknown command" in msg:
                    r = run_gws(
                        ["sheets", "spreadsheets", "values", "update"],
                        params=params,
                        json_body=value_body,
                    )
                else:
                    raise
            log.info("Sheets values.update response type=%s", type(r).__name__)
            return json.dumps(r, indent=2) if isinstance(r, dict) else str(r)

        if name == "sheets_values_append":
            params: dict[str, Any] = {
                "spreadsheetId": args["spreadsheetId"],
                "range": args["range"],
                "valueInputOption": args.get("valueInputOption") or "USER_ENTERED",
                "insertDataOption": args.get("insertDataOption") or "INSERT_ROWS",
            }
            values = args.get("values") or []
            if isinstance(values, list):
                for r_idx, row in enumerate(values):
                    if not isinstance(row, list):
                        values[r_idx] = [str(row)]
                        continue
                    for c_idx, cell in enumerate(row):
                        if cell is None:
                            values[r_idx][c_idx] = ""
                        elif not isinstance(cell, (str, int, float, bool)):
                            values[r_idx][c_idx] = str(cell)
                        else:
                            values[r_idx][c_idx] = str(cell) if isinstance(cell, bool) else cell
            value_body = {"values": values}
            try:
                r = run_gws(
                    ["sheets", "spreadsheets.values", "append"],
                    params=params,
                    json_body=value_body,
                )
            except RuntimeError as e:
                msg = str(e).lower()
                if "unrecognized subcommand" in msg or "unknown command" in msg:
                    r = run_gws(
                        ["sheets", "spreadsheets", "values", "append"],
                        params=params,
                        json_body=value_body,
                    )
                else:
                    raise
            log.info("Sheets values.append response type=%s", type(r).__name__)
            return json.dumps(r, indent=2) if isinstance(r, dict) else str(r)

        if name == "sheets_spreadsheets_batchUpdate":
            # Fix schema validation failures from Gemini emitting floats for index fields.
            # The Sheets API expects integer indices (start/end row/col, sheetId, etc.).
            index_keys = {
                "sheetId",
                "startRowIndex",
                "endRowIndex",
                "startColumnIndex",
                "endColumnIndex",
                "startIndex",
                "endIndex",
            }
            requests = args.get("requests") or []
            requests = _coerce_whole_number_floats_to_ints(requests, index_keys)
            r = run_gws(
                ["sheets", "spreadsheets", "batchUpdate"],
                params={"spreadsheetId": args["spreadsheetId"]},
                json_body={"requests": requests},
            )
            log.info("Sheets batchUpdate response type=%s", type(r).__name__)
            return json.dumps(r, indent=2) if isinstance(r, dict) else str(r)

        return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def run_sheets_agent(
    messages: list[dict],
    spreadsheet_id: str | None = None,
) -> dict:
    """
    Run the Sheets agent using Gemini tool calling.

    Args:
        messages: chat messages in {role, content} format.
        spreadsheet_id: optional default spreadsheetId to apply when Gemini omits it.
    Returns:
        {text: str, tool_calls: [{name, args}, ...]}
    """
    api_key = os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"text": "No LLM configured. Set GOOGLE_GENERATIVE_AI_API_KEY in .env", "tool_calls": []}

    default_ctx = ""
    if spreadsheet_id:
        default_ctx = f"\n\n[[DEFAULT SPREADSHEET ID]] spreadsheetId={spreadsheet_id}\nUse this spreadsheetId for tool calls unless the user asks for a different one."

    system_instruction = SHEETS_SYSTEM + default_ctx

    model_name = (
        os.environ.get("SHEETS_AGENT_MODEL")
        or os.environ.get("AGENT_MODEL")
        or os.environ.get("GEMINI_MODEL")
        or os.environ.get("GOOGLE_GENERATIVE_AI_MODEL")
        or "gemini-2.5-flash"
    )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=model_name,
        tools=[Tool(function_declarations=SHEETS_TOOLS)],
        system_instruction=system_instruction,
    )

    # Convert our message format into Gemini chat history parts.
    history = []
    for m in messages[:-1]:
        role = m.get("role")
        content = m.get("content", "")
        if isinstance(content, list):
            content = content[0].get("text", "") if content else ""
        if role == "user":
            history.append({"role": "user", "parts": [str(content)]})
        elif role == "assistant":
            history.append({"role": "model", "parts": [str(content)]})

    last = messages[-1] if messages else {}
    user_content = last.get("content", "")
    if isinstance(user_content, list):
        user_content = user_content[0].get("text", "") if user_content else ""
    user_content = str(user_content)

    from google.generativeai import protos

    chat = model.start_chat(history=history)
    tool_calls_made: list[dict[str, Any]] = []
    max_rounds = int(os.environ.get("SHEETS_AGENT_MAX_ROUNDS") or os.environ.get("AGENT_MAX_ROUNDS", "20"))

    try:
        response = chat.send_message(user_content)
    except Exception as e:
        log.warning("Sheets agent send_message failed: %s", e)
        return {"text": f"Sheets agent failed: {e}", "tool_calls": []}

    round_num = 0
    while response.candidates and round_num < max_rounds:
        round_num += 1
        parts = response.candidates[0].content.parts
        if not parts:
            break

        function_responses = []
        has_text = False
        text_content = ""

        for part in parts:
            fc = getattr(part, "function_call", None)
            if fc:
                name = fc.name
                args = _to_jsonable(dict(fc.args)) if fc.args else {}
                result = _execute_sheets_tool(name=name, args=args, default_spreadsheet_id=spreadsheet_id)
                tool_calls_made.append({"name": str(name), "args": _to_jsonable(args)})
                function_responses.append(
                    protos.Part(
                        function_response=protos.FunctionResponse(
                            name=name,
                            response={"result": result},
                        )
                    )
                )
            else:
                has_text = True
                text_content = getattr(part, "text", None) or ""

        if has_text and not function_responses:
            return {"text": text_content, "tool_calls": tool_calls_made}

        if not function_responses:
            break

        try:
            response = chat.send_message(function_responses)
        except Exception as e:
            log.warning("Sheets agent failed after tools: %s", e)
            if tool_calls_made:
                return {"text": f"Some actions completed, but the model failed to continue. Tools used: {[t['name'] for t in tool_calls_made]}.", "tool_calls": tool_calls_made}
            return {"text": f"Sheets agent failed: {e}", "tool_calls": []}

    final = getattr(response, "text", "") or ""
    if not final and tool_calls_made:
        final = f"Reached max rounds ({max_rounds}). Tools used: {[t['name'] for t in tool_calls_made]}."
    return {"text": final or "No response", "tool_calls": tool_calls_made}

