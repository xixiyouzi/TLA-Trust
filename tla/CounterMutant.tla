---- MODULE CounterMutant ----
EXTENDS Integers
VARIABLE x
Init == x = -5
Next == x < 10 /\ x' = x + 1
Inv == x >= 0
Spec == Init /\ [][Next]_x
====