---- MODULE CounterC3 ----
EXTENDS Integers
VARIABLE x
Init == x = 0
Next == (x < 10 /\ x' = x + 1) \/ (x = 10 /\ UNCHANGED x)
Spec == Init /\ [][Next]_x
Inv == TRUE
====
