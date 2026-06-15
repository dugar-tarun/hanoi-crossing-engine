"""Minimal RandomAgent that consumes only ``Observation`` + ``engine.step``."""

from __future__ import annotations

import random

from hanoi.engine import Action, Observation


class RandomAgent:
    """Stateless agent that picks a uniformly random legal action each turn."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()

    def choose_action(self, obs: Observation) -> Action:
        """Return a random action from ``obs.legal_actions`` (must be non-empty)."""
        if not obs.legal_actions:
            raise RuntimeError(
                "choose_action called on a terminal observation (legal_actions is empty)"
            )
        return self._rng.choice(obs.legal_actions)
