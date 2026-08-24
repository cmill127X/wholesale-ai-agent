"""Vercel entrypoint for the Wholesale AI Agent."""
from typing import Any, Dict, List

from fastapi import FastAPI
from pydantic import BaseModel, Field

from qc import second_pass

app = FastAPI(title="Wholesale AI Agent", version="0.1.0")


class RunRequest(BaseModel):
    records: List[Dict[str, Any]] = Field(default_factory=list)


@app.get("/api")
def home():
    return {
        "service": "Wholesale AI Agent",
        "status": "online",
        "pipeline": "normalize -> deduplicate -> score -> second-pass QC",
    }


@app.post("/api/run")
def run(request: RunRequest):
    return {"status": "ok", "result": second_pass(request.records)}
