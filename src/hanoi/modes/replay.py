"""CLI replay frontend: ``hanoi-replay path/to/game.json``

Input JSON schema (schema_version 1):

    {
      "schema_version": 1,
      "config": { "num_disks": 3, "max_turns": 1000 },
      "turn_order": ["A", "B", "A", "B"],
      "moves": [
        {"type": "lift", "pole": "1a"},
        {"type": "place", "pole": "3a"},
        ...
      ]
    }

``config.max_turns`` is optional; the ``build_two_player_config`` default
(1000) is used when omitted.

Exit codes:
  0 — clean run (including runs with ILLEGAL engine results; illegal moves are
      valid replay content, not driver errors).
  1 — malformed input detected *before* calling ``engine.step``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from hanoi.engine import (
    Action,
    build_two_player_config,
    initial_state,
    step,
)
from hanoi.engine.config import ConfigError
from hanoi.engine.serialization import action_from_dict


def _die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def _validate_input(data: Any) -> tuple[int, int, list[str], list[Action]]:
    """Validate the parsed JSON and return ``(num_disks, max_turns, turn_order, actions)``.

    Raises ``SystemExit(1)`` on any error found before the engine is involved.
    """
    if not isinstance(data, dict):
        _die("top-level JSON value must be an object")

    schema_version = data.get("schema_version")
    if schema_version != 1:
        _die(f"unsupported schema_version: {schema_version!r} (expected 1)")

    config_data = data.get("config")
    if not isinstance(config_data, dict):
        _die("missing or invalid 'config' field (must be an object)")

    num_disks = config_data.get("num_disks")
    if not isinstance(num_disks, int) or num_disks <= 0:
        _die(f"config.num_disks must be a positive integer, got {num_disks!r}")

    raw_max_turns = config_data.get("max_turns", 1000)
    if not isinstance(raw_max_turns, int) or raw_max_turns <= 0:
        _die(f"config.max_turns must be a positive integer, got {raw_max_turns!r}")
    max_turns: int = raw_max_turns

    turn_order = data.get("turn_order")
    if not isinstance(turn_order, list) or not turn_order:
        _die("'turn_order' must be a non-empty list of player ids")
    for i, p in enumerate(turn_order):
        if not isinstance(p, str):
            _die(f"turn_order[{i}] must be a string, got {p!r}")

    moves_data = data.get("moves")
    if not isinstance(moves_data, list):
        _die("'moves' must be a list of action objects")

    if len(moves_data) != len(turn_order):
        _die(
            f"'moves' length ({len(moves_data)}) must equal 'turn_order' length ({len(turn_order)})"
        )

    actions: list[Action] = []
    for i, m in enumerate(moves_data):
        if not isinstance(m, dict):
            _die(f"moves[{i}] must be an object, got {m!r}")
        try:
            actions.append(action_from_dict(m))
        except (KeyError, ValueError) as exc:
            _die(f"moves[{i}] is invalid: {exc}")

    return num_disks, max_turns, list(turn_order), actions


def _render_state(state: Any) -> None:
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="hanoi-replay",
        description="Replay a recorded Hanoi Crossing game from a JSON file.",
    )
    parser.add_argument("path", help="Path to the game JSON file")
    args = parser.parse_args(argv)

    path = Path(args.path)
    if not path.exists():
        _die(f"file not found: {path}")

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        _die(f"cannot read file: {exc}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        _die(f"malformed JSON: {exc}")

    num_disks, max_turns, turn_order, actions = _validate_input(data)

    try:
        config = build_two_player_config(num_disks, max_turns=max_turns)
    except ConfigError as exc:
        _die(f"invalid config: {exc}")

    state = initial_state(config)

    print(f"=== Hanoi Crossing Replay: {num_disks} disk(s), max_turns={max_turns} ===")
    print(f"Turn order: {turn_order}")
    print()

    for i, (player, action) in enumerate(zip(turn_order, actions, strict=True)):
        state, result = step(state, player, action)
        if result.legal:
            legal_tag = "OK"
        else:
            assert result.illegality is not None
            legal_tag = f"ILLEGAL({result.illegality.name})"
        terminal_tag = f" [{result.terminal.name}]" if result.terminal is not None else ""
        print(
            f"  Step {i + 1:3d}: player={player!r}  action={action!r}  -> {legal_tag}{terminal_tag}"
        )
        if result.terminal is not None:
            break

    print()
    _render_state(state)


if __name__ == "__main__":
    main()
