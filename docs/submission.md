# Hanoi Crossing

## Game

Two players. Each has a row of 3 poles and N disks stacked on their pole 1
(largest at bottom). The middle pole (pole 2) is shared: both players see it
and either can interact with disks on it. Neither player can see the other's
poles 1 and 3, nor what the other holds in hand.

Player A starts with disks of odd sizes (1, 3, 5, ...).
Player B starts with disks of even sizes (2, 4, 6, ...).

Standard Tower of Hanoi placement rule: a disk may only be placed on an empty
pole or on top of a strictly larger disk.

The game is turn-based. On their turn a player performs exactly one action:

- **Lift** the top disk from any visible pole into their hand.
- **Place** the held disk onto any visible pole.
- **Skip** — do nothing.

A player may hold at most one disk at a time. Either player may lift any top
disk from the shared pole.

An illegal action does not change the game state; the turn is wasted.

Turn order is external to the game: provided as a sequence that says which
player acts on each step. The engine must not assume any particular
turn-order pattern.

**Win condition:** a player wins when their hand is empty and, among
their visible poles, only pole 3 has disks on it.

## Board

```
        1a
        |
 1b -- [2] -- 3b
        |
        3a
```

Player A sees poles: 1a – 2 – 3a
Player B sees poles: 1b – 2 – 3b

## Example (N = 1)

Player A has disk 1 on 1a. Player B has disk 2 on 1b.
Turn order: [A, B, A].

1. Player A lifts disk 1 from pole 1a (now holding it).
2. Player B lifts disk 2 from pole 1b (now holding it).
3. Player A places disk 1 onto pole 3a. Hand empty, poles 1a and 2 clear
   — Player A wins.

## Task

Build a game engine in Python with two frontends: a **replay** CLI (reads
pre-recorded moves + turn order, outputs final state) and a **random-play**
mode (both players make random valid moves). Tests should exercise the
engine directly.

Design the engine for reuse beyond these frontends: it should later serve,
unchanged, as the environment core of an RL training loop, or of an online
simulation service that maintains many concurrent games. Do **not** build
either — but the engine must not need changes to support them. Your random
player should already consume the engine exactly the way such an external
agent would.

Design the input format, output format, and internal model yourself.
Where the rules are open to interpretation, be creative — make a decision
and document it. Describe your choices and design decisions in a README.

## Constraints

- Core engine: under 500 lines of Python
- Standard project layout (e.g. uv)

## Submission

- Mandatory git repository. We are interested in your journey, not just the final result.
- Unrestricted use of AI tools is allowed. Disclose what you used and how.
- Expected effort ~2 hours. It's also fine if the submission is in a PoC/WIP stage.