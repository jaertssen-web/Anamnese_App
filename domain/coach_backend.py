"""
domain/coach_backend.py — Anamnese_App

Abstractielaag voor de coach-evaluator.

FASE 1 (actief):   HeuristicCoach — puur heuristisch, geen LLM
FASE 2 (stub):     LLMCoach — nog NIET actief, klaar voor inpluggen

Om later over te schakelen naar een lokale LLM-coach:
  1. Implementeer LLMCoach.evaluate() met Ollama- of MLX-backend
  2. Vervang HeuristicCoach() door LLMCoach(...) in get_coach()
  3. Voeg 'requests' toe aan requirements.txt (voor Ollama HTTP)

De publieke API (CoverageCoachResult, get_coach) blijft ongewijzigd.
app/main.py hoeft niet te worden aangepast bij de wissel.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from domain.basic_coverage_coach import CoverageCoachResult


# ---------------------------------------------------------------------------
# Protocol (structurele typering — geen verplichte overerving)
# ---------------------------------------------------------------------------

@runtime_checkable
class CoachBackend(Protocol):
    def evaluate(self, state: dict) -> list[CoverageCoachResult]:
        ...


# ---------------------------------------------------------------------------
# Fase 1: HeuristicCoach (actief)
# ---------------------------------------------------------------------------

class HeuristicCoach:
    """
    Actieve coach: puur heuristisch, geen LLM, geen externe dependencies.
    Delegeert naar domain.basic_coverage_coach.evaluate_basic_coverage().
    """

    def evaluate(self, state: dict) -> list[CoverageCoachResult]:
        from domain.basic_coverage_coach import evaluate_basic_coverage
        return evaluate_basic_coverage(state)


# ---------------------------------------------------------------------------
# Fase 2: LLMCoach (stub — nog niet actief)
# ---------------------------------------------------------------------------

class LLMCoach:
    """
    Stub voor toekomstige lokale LLM-coach.

    NIET ACTIEF in v1/v2.

    Activeren:
      1. Implementeer evaluate() met Ollama-aanroep
         (zie future/coach_system_full.txt voor de prompt)
      2. Output: zelfde CoverageCoachResult structuur
      3. Vervang get_coach() retourwaarde
      4. Voeg 'requests>=2.31' toe aan requirements.txt

    Architectuureis: output MOET CoverageCoachResult-lijst zijn,
    zodat app/main.py ongewijzigd blijft.
    """

    def __init__(self, model_name: str = "gemma3:12b"):
        self.model_name = model_name

    def evaluate(self, state: dict) -> list[CoverageCoachResult]:
        raise NotImplementedError(
            "LLMCoach is niet actief. "
            "Gebruik HeuristicCoach of implementeer Ollama-integratie."
        )


# ---------------------------------------------------------------------------
# Factory — wissel hier van coach
# ---------------------------------------------------------------------------

def get_coach() -> CoachBackend:
    """
    Retourneert de actieve coach-implementatie.

    Fase 1: HeuristicCoach (huidig)
    Fase 2: vervang door LLMCoach(model_name="gemma3:12b")
    """
    return HeuristicCoach()
