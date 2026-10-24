---- MODULE MutexC3 ----
VARIABLES p0_in_cs, p1_in_cs
Init == /\ p0_in_cs = FALSE /\ p1_in_cs = FALSE
P0Enter == ~p1_in_cs /\ p0_in_cs' = TRUE /\ UNCHANGED p1_in_cs
P0Exit  == p0_in_cs /\ p0_in_cs' = FALSE /\ UNCHANGED p1_in_cs
P1Enter == ~p0_in_cs /\ p1_in_cs' = TRUE /\ UNCHANGED p0_in_cs
P1Exit  == p1_in_cs /\ p1_in_cs' = FALSE /\ UNCHANGED p0_in_cs
Next == P0Enter \/ P0Exit \/ P1Enter \/ P1Exit
MutualExclusion == ~(p0_in_cs /\ p1_in_cs)
Spec == Init /\ [][Next]_<<p0_in_cs, p1_in_cs>>
====