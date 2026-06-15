"""CLI random-play frontend: ``hanoi-random --disks N --seed S``

Usage
-----
::

    hanoi-random --disks 3 --seed 42
    hanoi-random --disks 2 --seed 7 --max-turns 5000 --turn-order ABABAB

Options
-------
``--disks N``
    Number of disks per player (default: 3).
``--seed S``
    Integer seed for the RNG.  Omit for a random run.
``--max-turns T``
    Hard cap forwarded to ``GameConfig.max_turns`` (default: 1000).
``--turn-order PATTERN``
    A string of player characters that is *cycled* until the game ends.
    Each character must be a valid player id (``"A"`` or ``"B"`` in the
    2-player layout).  Default: ``"AB"`` (strict alternation).

Exit codes
----------
0 — always (the driver exits cleanly regardless of WON / DRAW).
"""

from __future__ import annotations

import argparse
import itertools
import random
import sys
from typing import Iterator

from hanoi.engine import (
    build_two_player_config,
    initial_state,
    is_terminal,
    project,
    step,
)
from hanoi.engine.config import ConfigError
from hanoi.modes._agent import RandomAgent


# ---------------------------------------------------------------------------
# Turn-order helpers
# ---------------------------------------------------------------------------

def _cycle_pattern(pattern: str) -> Iterator[str]:
    """Yield player ids by cycling *pattern* indefinitely."""
    for ch in itertools.cycle(pattern):
        yield ch


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="hanoi-random",
        description="Run a Hanoi Crossing game with random agents.",
    )
    parser.add_argument(
        "--disks", type=int, default=3, metavar="N",
        help="number of disks per player (default: 3)",
    )
    parser.add_argument(
        "--seed", type=int, default=None, metavar="S",
        help="RNG seed for reproducibility (omit for non-deterministic run)",
    )
    parser.add_argument(
        "--max-turns", type=int, default=1000, metavar="T",
        help="hard turn cap forwarded to GameConfig.max_turns (default: 1000)",
    )
    parser.add_argument(
        "--turn-order", type=str, default="AB", metavar="PATTERN",
        help=(
            "player-id string cycled as the turn order, e.g. 'AB' for strict "
            "alternation (default: AB)"
        ),
    )
    args = parser.parse_args(argv)

    num_disks: int = args.disks
    seed: int | None = args.seed
    max_turns: int = args.max_turns
    turn_pattern: str = args.turn_order

    if num_disks <= 0:
        print("ERROR: --disks must be a positive integer", file=sys.stderr)
        sys.exit(1)
    if max_turns <= 0:
        print("ERROR: --max-turns must be a positive integer", file=sys.stderr)
        sys.exit(1)
    if not turn_pattern:
        print("ERROR: --turn-order must be a non-empty string", file=sys.stderr)
        sys.exit(1)

    try:
        config = build_two_player_config(num_disks, max_turns=max_turns)
    except ConfigError as exc:
        print(f"ERROR: invalid config: {exc}", file=sys.stderr)
        sys.exit(1)

    # Validate turn_order characters against known players.
    player_set = set(config.players)
    for ch in turn_pattern:
        if ch not in player_set:
            print(
                f"ERROR: --turn-order contains unknown player {ch!r} "
                f"(valid: {sorted(player_set)})",
                file=sys.stderr,
            )
            sys.exit(1)

    rng = random.Random(seed)
    agents = {p: RandomAgent(rng) for p in config.players}

    state = initial_state(config)
    seed_str = str(seed) if seed is not None else "random"
    print(
        f"=== Hanoi Crossing Random Play: {num_disks} disk(s), "
        f"max_turns={max_turns}, seed={seed_str} ==="
    )
    print(f"Turn pattern: {turn_pattern!r} (cycled)")
    print()

    turn_iter = _cycle_pattern(turn_pattern)
    step_num = 0

    for player in turn_iter:
        if is_terminal(state):
            break

        obs = project(state, player)
        if not obs.legal_actions:
            break

        action = agents[player].choose_action(obs)
        state, result = step(state, player, action)
        step_num += 1

        legal_tag = "OK" if result.legal else f"ILLEGAL({result.illegality.name})"
        terminal_tag = f" [{result.terminal.name}]" if result.terminal is not None else ""
        print(
            f"  Step {step_num:4d}: player={player!r}  action={action!r}"
            f"  -> {legal_tag}{terminal_tag}"
        )

        if result.terminal is not None:
            break

    print()
    print("=== Final State ===")
    print(f"  status:        {state.status.name}")
    print(f"  winner:        {state.winner}")
    print(f"  step_count:    {state.step_count}")
    print(f"  attempt_count: {state.attempt_count}")
    print("  poles:")
    for pid in sorted(state.poles):
        print(f"    {pid}: {list(state.poles[pid])}")
    print("  hands:")
    for player in sorted(state.hands):
        print(f"    {player}: {state.hands[player]}")


if __name__ == "__main__":
    main()
