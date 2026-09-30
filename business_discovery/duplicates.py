"""Explainable, conservative duplicate candidate scoring for human review."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from .models import Company


@dataclass(frozen=True, slots=True)
class DuplicateCandidate:
    left_id: str
    right_id: str
    score: int
    reasons: tuple[str, ...]


def candidate(left: Company, right: Company) -> DuplicateCandidate | None:
    if left.id == right.id: return None
    score, reasons = 0, []
    if left.domain and left.domain == right.domain:
        score += 70; reasons.append("same_domain")
    if left.phone and left.phone == right.phone:
        score += 60; reasons.append("same_phone")
    name_similarity = SequenceMatcher(None, left.name.casefold(), right.name.casefold()).ratio()
    if name_similarity >= .90:
        score += 30; reasons.append("similar_name")
    if left.city and left.city == right.city:
        score += 10; reasons.append("same_city")
    return DuplicateCandidate(left.id, right.id, min(score, 100), tuple(reasons)) if score >= 60 else None


def find_candidates(companies: list[Company]) -> list[DuplicateCandidate]:
    return [match for index, left in enumerate(companies) for right in companies[index + 1:] if (match := candidate(left, right))]
