# Hanoi Crossing Engine

A deterministic, fully-testable game engine for **Hanoi Crossing** — a two-player
variant of the Tower of Hanoi where each player races to move their disks across
a shared board onto their goal pole.

## Documentation

The full design and rules live in the Technical Requirements Document at
[`docs/TRD.md`](docs/TRD.md). It covers:

- **Scope and goals** — a correct, deterministic, fully testable engine.
- **Key rule decisions** — the win condition (ownership + shared-pole cleared,
  evaluated on full state), disk "trapping" as a legal strategy, win-check
  timing, illegal-action semantics, external turn order vs. internal turn
  counting, the `max_turns` DRAW cap, and disk identity = disk size.
- **Engine public API** — the symbols re-exported from `hanoi.engine`
  (`config.py`, `state.py`, `actions.py`, `engine.py`, `observation.py`).
- **Frontends** — the `replay` and `random_play` CLI modes, including the
  replay JSON schema.

## Quick Start

Requires **Python 3.11+**. This project uses [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install uv (skip if already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Create the virtual environment (.venv) and install all dependencies
uv sync

# 3. Run a game with random agents
uv run hanoi-random --disks 3 --seed 42

# 4. Replay a recorded game
uv run hanoi-replay examples/n1_a_wins.json

# 5. Run the test suite
uv run pytest
```

`uv sync` creates the `.venv` and installs everything pinned in `uv.lock`; you
don't need to create or activate the environment manually. To get an explicit
environment first, run `uv venv` before `uv sync`. To run inside the activated
venv instead of prefixing with `uv run`, use `source .venv/bin/activate`.

## Layout

```
hanoi-crossing-engine/
  pyproject.toml                 # uv-managed project + ruff config, python = "3.11"
  uv.lock                        # pinned dependency lockfile
  .pre-commit-config.yaml        # ruff + hygiene hooks (commit) and pytest (push)
  README.md                      # this document
  docs/
    TRD.md                       # technical requirements / design decisions
    submission.md                # submission notes
  src/
    hanoi/
      engine/
        __init__.py              # public re-exports (import from hanoi.engine)
        config.py                # GameConfig, PoleSpec, build_two_player_config()
        state.py                 # GameState (frozen), Status
        actions.py               # Action sum type: Lift | Place | _Skip (SKIP singleton)
        rules.py                 # legality + win predicate
        engine.py                # initial_state, step, legal_actions, is_terminal
        observation.py           # Observation + project()
        serialization.py         # to_dict / from_dict for state, action, config
      modes/
        replay.py                # CLI: hanoi-replay path/to/game.json
        random_play.py           # CLI: hanoi-random --seed 42 --disks 3
        _agent.py                # tiny RandomAgent using only Observation + step
  examples/                      # ready-to-run replay JSON files (see Examples)
  tests/
    conftest.py                  # shared fixtures / state builders
    test_config.py
    test_rules.py
    test_engine.py
    test_observation.py
    test_serialization.py
    test_replay.py
    test_random_play.py
    test_end_to_end.py
```

## Usage

```bash
# Play a game with random agents
uv run hanoi-random --disks 3 --seed 42

# Replay a recorded game from JSON
uv run hanoi-replay examples/n3_a_wins_optimal.json
```

## Examples

The [`examples/`](examples/) folder contains recorded games in the replay JSON
schema. Run any of them with `hanoi-replay`:

```bash
uv run hanoi-replay examples/<file>.json
```

| File | Outcome | Demonstrates |
| --- | --- | --- |
| `n1_a_wins.json` | A wins | Minimal N=1 game; A solves while B lifts a disk. |
| `n2_b_wins.json` | B wins | N=2 solo solve by B over the shared pole. |
| `n3_a_wins_optimal.json` | A wins | Optimal 14-move N=3 solve by A. |
| `draw_skip_only.json` | Draw | Both players only `skip` until `max_turns` (6) is hit. |
| `illegal_moves_valid_replay.json` | A wins | Illegal moves are valid replay content — rejected, game still concludes. |
| `trapping_a_traps_b_disk4.json` | A wins | "Trapping": A parks B's disk 4 on its own goal pole. |
| `trapping_b_traps_a.json` | In progress | Replay ends mid-game (move list contains illegal moves and never reaches a terminal state). |

> Note: `hanoi-replay` applies exactly the moves in the file and prints the
> resulting state. If the move list doesn't reach a win or the `max_turns` draw
> cap, the final status is `IN_PROGRESS` (as with `trapping_b_traps_a.json`).

## Development

```bash
uv run pytest        # run the test suite
uv run ruff check .  # lint
uv run ruff format . # format
```

### Pre-commit hooks

[pre-commit](https://pre-commit.com/) keeps the tree clean automatically. After
`uv sync`, install the git hooks once:

```bash
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

- **on commit:** trailing-whitespace / EOF fixers, YAML/TOML checks, and
  `ruff` lint (`--fix`) + format.
- **on push:** the full `pytest` suite.

Run every hook manually with `uv run pre-commit run --all-files`.
