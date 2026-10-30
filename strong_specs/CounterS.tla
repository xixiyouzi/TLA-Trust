---- MODULE CounterS ----
EXTENDS Integers
VARIABLE x
Init == x = 0
Next == (x < 10 /\ x' = x + 1) \/ (x = 10 /\ UNCHANGED x)
Inv == 0 <= x /\ x <= 10
Spec == Init /\ [][Next]_x
====