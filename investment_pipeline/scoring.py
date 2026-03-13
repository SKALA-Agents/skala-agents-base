from __future__ import annotations

from typing import Dict

from .models import Recommendation, Stage


STAGE_WEIGHTS: Dict[Stage, Dict[str, float]] = {
    "Seed": {
        "team": 0.30,
        "market": 0.25,
        "technology": 0.25,
        "traction": 0.05,
        "competition": 0.10,
        "risk": 0.05,
    },
    "Series A": {
        "team": 0.25,
        "market": 0.20,
        "technology": 0.25,
        "traction": 0.15,
        "competition": 0.10,
        "risk": 0.05,
    },
    "Series B": {
        "team": 0.20,
        "market": 0.20,
        "technology": 0.20,
        "traction": 0.25,
        "competition": 0.10,
        "risk": 0.05,
    },
    "Series C+": {
        "team": 0.15,
        "market": 0.15,
        "technology": 0.15,
        "traction": 0.25,
        "competition": 0.15,
        "risk": 0.15,
    },
}


def weighted_score(signal: int, weight: float) -> float:
    return signal / 5 * weight * 100


def to_recommendation(score: int) -> Recommendation:
    if score >= 80:
        return "High Priority DD"
    if score >= 65:
        return "Selective DD"
    if score >= 50:
        return "Watchlist"
    return "No DD"
