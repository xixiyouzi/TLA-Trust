---- MODULE Demo ----
VARIABLE x
Inv == x >= 0
Next == x' = x + 1
Spec == Inv /\ [][Next]_x
====