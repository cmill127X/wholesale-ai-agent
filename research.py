"""Pluggable research interface.

The MVP intentionally ships with no paid provider. Providers can implement
ResearchSource and return evidence; the verification layer then cross-checks it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol
from evidence import Evidence


@dataclass
class ResearchRequest:
    query: str
    location: str = ""
    max_results: int = 25


class ResearchSource(Protocol):
    name: str

    def search(self, request: ResearchRequest) -> List[Evidence]:
        ...


class ManualResearchSource:
    """Safe fallback: accepts evidence collected by a human or another tool."""
    name = "manual"

    def search(self, request: ResearchRequest) -> List[Evidence]:
        return []


def run_research(request: ResearchRequest, sources: List[ResearchSource]) -> List[Evidence]:
    evidence: List[Evidence] = []
    for source in sources:
        try:
            evidence.extend(source.search(request)[: request.max_results])
        except Exception:
            # One failed source must not destroy the whole research run.
            continue
    return evidence
