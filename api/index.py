"""Tiny dependency-free HTTP endpoint suitable for a serverless adapter."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qc import second_pass


def handler(request):
    """Accept a JSON body containing {"records": [...]} and return QC output."""
    try:
        body = request.get_json(silent=True) if hasattr(request, "get_json") else {}
        records = body.get("records", []) if isinstance(body, dict) else []
        result = second_pass(records)
        return {"status": "ok", "result": result}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
