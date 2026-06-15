"""Minimal RandomAgent that consumes only ``Observation`` + ``engine.step``.

The agent samples uniformly from ``Observation.legal_actions``, which is
non-empty in any non-terminal state and always contains ``SKIP``. If
``legal_actions`` is empty (terminal), the agent must not call ``step`` — the
driver handles that check before calling ``choose_action``.
"""

from __future__ import annotations

import random
from typing import Optional

from hanoi.engine import Action, Observation


class RandomAgent:
    """Stateless agent that picks a random legal action each turn.

    Parameters
    ----------
    rng:
        A ``random.Random`` instance for reproducibility. Callers share the
        same seeded RNG across all agents so the full game is seeded in one
        place.
    """

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self._rng = rng or random.Random()

    def choose_action(self, obs: Observation) -> Action:
        """Return a uniformly-sampled legal action from ``obs.legal_actions``.

        Precondition: ``obs.legal_actions`` is non-empty (i.e., the game is
        not yet terminal). Callers are responsible for not invoking this after
        the game ends.
        """
        if not obs.legal_actions:
            raise RuntimeError(
                "choose_action called on a terminal observation (legal_actions is empty)"
            )
        return self._rng.choice(obs.legal_actions)
