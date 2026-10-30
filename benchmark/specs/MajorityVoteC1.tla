---- MODULE MajorityVoteC1 ----
VARIABLES v1, v2, v3
Init == v1 = "none" /\ v2 = "none" /\ v3 = "none"
Vote1 == v1 = "none" /\ v1' \in {"yes", "no"} /\ UNCHANGED <<v2, v3>>
Vote2 == v2 = "none" /\ v2' \in {"yes", "no"} /\ UNCHANGED <<v1, v3>>
Vote3 == v3 = "none" /\ v3' \in {"yes", "no"} /\ UNCHANGED <<v1, v2>>
Done == /\ v1 /= "none" /\ v2 /= "none" /\ v3 /= "none"
        /\ UNCHANGED <<v1, v2, v3>>
Next == Vote1 \/ Vote2 \/ Vote3 \/ Done
YesWin == (v1 = "yes" /\ v2 = "yes") \/ (v1 = "yes" /\ v3 = "yes") \/ (v2 = "yes" /\ v3 = "yes")
NoWin  == (v1 = "no" /\ v2 = "no") \/ (v1 = "no" /\ v3 = "no") \/ (v2 = "no" /\ v3 = "no")
Spec == Init /\ [][Next]_<<v1, v2, v3>>
Safety == /\ v1 \in {"none", "yes", "no"}
          /\ v2 \in {"none", "yes", "no"}
          /\ v3 \in {"none", "yes", "no"}
/\ UndefinedOperator(0)
====
