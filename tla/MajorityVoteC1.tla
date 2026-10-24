---- MODULE MajorityVoteC1 ----
VARIABLES v1, v2, v3
Init == v1 = "none" /\ v2 = "none" /\ v3 = "none"
Vote1 == v1 = "none" /\ v1' \in {"yes", "no"} /\ UNCHANGED <<v2, v3>>
Vote2 == v2 = "none" /\ v2' \in {"yes", "no"} /\ UNCHANGED <<v1, v3>>
Vote3 == v3 = "none" /\ v3' \in {"yes", "no"} /\ UNCHANGED <<v1, v2>>
Next == Vote1 \/ Vote2 \/ Vote3
Safety == /\ v1 \in {"none", "yes", "no"}
          /\ v2 \in {"none", "yes", "no"}
          /\ v3 \in {"none", "yes", "no"}
Spec == Init /\ [][Next]_<<v1, v2, v3>>
====