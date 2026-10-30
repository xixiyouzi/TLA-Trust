---- MODULE TwoPhaseCommitC2 ----
VARIABLES p1_state, p2_state
Init == p1_state = "init" /\ p2_state = "init"
Vote1 == p1_state = "init" /\ p1_state' \in {"yes", "no"} /\ UNCHANGED p2_state
Vote2 == p2_state = "init" /\ p2_state' \in {"yes", "no"} /\ UNCHANGED p1_state
Decide == /\ p1_state \in {"yes", "no"}
          /\ p2_state \in {"yes", "no"}
          /\ IF p1_state = "yes" /\ p2_state = "yes"
             THEN (p1_state' = "commit" /\ p2_state' = "commit")
             ELSE (p1_state' = "abort" /\ p2_state' = "abort")
Done == /\ p1_state \in {"commit", "abort"}
        /\ p2_state \in {"commit", "abort"}
        /\ UNCHANGED <<p1_state, p2_state>>
Next == FALSE
Spec == Init /\ [][Next]_<<p1_state, p2_state>>
GlobalConsistency == ~(p1_state = "commit" /\ p2_state = "abort")
                  /\ ~(p1_state = "abort" /\ p2_state = "commit")
====
