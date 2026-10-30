# L2 Scoring Instructions — Second Reviewer

## What you are scoring

`L2` (semantic requirement completeness) measures how completely a candidate
TLA+ specification's **transition system** models the task's required
behaviours. Judge the model against the task description below, not against
the other candidates.

`L2` is deliberately independent of:

- `L1` (syntax): a specification that parses can still score low on `L2`;
- `L4` (property adequacy): `L2` is about the *model / state machine*, not
  about whether the invariant is strong or weak.

So please ignore the invariant when scoring `L2`; look at the `Init`, the
actions, and the `Next` relation.

## The six tasks

1. **Counter** — a counter that starts at 0, increments while below 10, and
   never goes negative. A complete model should be able to reach every value
   in 0..10.
2. **Mutex** — two processes competing for a critical section; at most one may
   be inside the section at any time.
3. **Buffer** — a bounded producer/consumer buffer of capacity 3; its length
   must never exceed 3.
4. **TwoPhaseCommit** — two participants first vote yes/no, then jointly decide
   commit or abort; the two must always agree (never a commit/abort mismatch).
5. **MajorityVote** — three voters cast yes/no votes, then a decision is made;
   the decision must agree with the actual majority.
6. **AlternatingBit** — an alternating-bit sender/receiver protocol over a lossy
   channel, with message acceptance gated by a one-bit sequence number.

## Anchor scale (1-5)

| Score | Meaning |
|---|---|
| 5 | The transition system covers all required states and actions of the task; behaviourally equivalent to a complete model. |
| 4 | Covers the required behaviours; only minor or auxiliary behaviours are missing or over-constrained. |
| 3 | Models a substantial subset, but one or more core actions or states are missing or wrong. |
| 2 | Parses, but the next-state relation is effectively disabled or deadlocks after (at most) the initial state, modelling almost none of the required behaviour. |
| 1 | Does not parse, or has no meaningful state space at all. |

## Procedure

1. Open the anonymised candidate files in `specs/` (named `<Task><A|B|C|D>.tla`).
2. For each candidate, read `Init`, the action definitions, and `Next`, and
   assign one score from the anchor scale.
3. Fill the scoring sheet below.
4. Work independently; do not compare notes with the other reviewer until both
   sheets are submitted. A third arbiter will resolve any disagreements.

## Scoring sheet

| Task | A | B | C | D |
|---|---|---|---|---|
| Counter |  |  |  |  |
| Mutex |  |  |  |  |
| Buffer |  |  |  |  |
| TwoPhaseCommit |  |  |  |  |
| MajorityVote |  |  |  |  |
| AlternatingBit |  |  |  |  |

Return the completed sheet together with any per-candidate notes.
