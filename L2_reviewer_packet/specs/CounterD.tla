---- MODULE CounterD ----
EXTENDS Integers
VARIABLE x
Init == x = 0
Next == FALSE
Spec == Init /\ [][Next]_x
Inv == x >= 0
====
