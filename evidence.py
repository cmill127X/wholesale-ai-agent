"""Evidence and verification primitives for the wholesale agent."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, List
from urllib.parse import urlparse


@dataclass
class Evidence:
    field: str
    value: str
    source_url: str
    source_type: str = "web"
    retrieved_at: str = ""
    notes: str = ""
    reliability: float = 0.0

    def is_valid_source(self) -> bool:
        parsed = urlparse(self.source_url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


@dataclass
class VerificationResult:
    field: str
    value: str
    status: str
    evidence_count: int
    confidence: float
    sources: List[str]


def verify_evidence(evidence: Iterable[Evidence]) -> List[VerificationResult]:
    """Cross-check field evidence without claiming facts unsupported by sources.

    Two independent valid sources are treated as corroborated. One source is
    marked single_source; invalid/missing URLs are never counted as evidence.
    """
    grouped = {}
    for item in evidence:
        if not item.is_valid_source() or not item.value.strip():
            continue
        key = (item.field.strip().lower(), item.value.strip().lower())
        grouped.setdefault(key, []).append(item)

    results = []
    for (field, value), items in grouped.items():
        urls = list(dict.fromkeys(x.source_url for x in items))
        reliability = max((x.reliability for x in items), default=0.0)
        if len(urls) >= 2:
            status, confidence = "corroborated", min(0.99, 0.75 + 0.1 * len(urls) + reliability * 0.1)
        else:
            status, confidence = "single_source", min(0.70, 0.45 + reliability * 0.25)
        results.append(VerificationResult(field, value, status, len(urls), round(confidence, 2), urls))
    return results


def evidence_to_dict(items: Iterable[Evidence]):
    return [asdict(item) for item in items]
