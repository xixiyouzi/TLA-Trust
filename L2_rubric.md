# L2 Scoring Rubric — Semantic Requirement Completeness (Double-Blind)

`L2` is the second level of the TLA-Trust rubric. It measures **how completely a
candidate specification's state machine models the task's required behaviours**,
judged against the gold reference specification. It is independent of syntax
(`L1`) and of whether the invariant is strong enough (`L4`); a candidate can
parse and yet still score low on `L2` because it does not model the system.

## Anchor scale (1-5)

| Score | Descriptor | Concrete criterion |
|---|---|---|
| 5 | Complete | The transition system covers all required states and actions of the gold reference; behaviourally equivalent. |
| 4 | Mostly complete | Covers the required behaviours; only minor/auxiliary behaviours are missing or over-constrained. |
| 3 | Partial | Models a substantial subset of behaviours, but one or more core actions/states are missing or wrong. |
| 2 | Behaviourally vacuous | Parses, but the next-state relation is effectively disabled or deadlocks after (at most) the initial state, so it models almost no required behaviour. |
| 1 | No usable model | Does not parse (syntax/semantic error), or contains no meaningful state space at all. |

## Protocol (per the manuscript, Section on quality rubric)

1. Anonymise the 24 candidate `.tla` files: rename them to neutral IDs and strip
   author/class labels so reviewers cannot tell `C1/C2/C3/C4` apart.
2. Two reviewers with TLA+ expertise score each candidate independently.
3. Compute Cohen's kappa; lock scores only when `kappa >= 0.80`.
4. Any disagreement is resolved by a third arbiter.

## Scoring sheet (24 candidates)

Rows are ordered by task and a neutral candidate code `A/B/C/D`. Do **not** show
the defect class to reviewers.

| Task | Candidate | Reviewer 1 | Reviewer 2 | Agreed L2 | Notes |
|---|---|---|---|---|---|
| Counter | A |  |  |  |  |
| Counter | B |  |  |  |  |
| Counter | C |  |  |  |  |
| Counter | D |  |  |  |  |
| Mutex | A |  |  |  |  |
| Mutex | B |  |  |  |  |
| Mutex | C |  |  |  |  |
| Mutex | D |  |  |  |  |
| Buffer | A |  |  |  |  |
| Buffer | B |  |  |  |  |
| Buffer | C |  |  |  |  |
| Buffer | D |  |  |  |  |
| TwoPhaseCommit | A |  |  |  |  |
| TwoPhaseCommit | B |  |  |  |  |
| TwoPhaseCommit | C |  |  |  |  |
| TwoPhaseCommit | D |  |  |  |  |
| MajorityVote | A |  |  |  |  |
| MajorityVote | B |  |  |  |  |
| MajorityVote | C |  |  |  |  |
| MajorityVote | D |  |  |  |  |
| AlternatingBit | A |  |  |  |  |
| AlternatingBit | B |  |  |  |  |
| AlternatingBit | C |  |  |  |  |
| AlternatingBit | D |  |  |  |  |

Reference anchor (do not show to reviewers): in the original dataset the
agreed L2 values were C1=1, C2=2, C3=5, C4=5, i.e. a syntax error scores 1, a
single-state deadlock scores 2, and both the weak-invariant candidate (whose
*model* is the gold model) and the gold score 5.
