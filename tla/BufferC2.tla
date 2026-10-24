---- MODULE BufferC2 ----
EXTENDS Sequences, Naturals
VARIABLE buffer
N == 3
Init == buffer = <<>>
Produce == /\ Len(buffer) < N
           /\ buffer' = Append(buffer, 1)
Consume == /\ Len(buffer) > 0
           /\ buffer' = Tail(buffer)
Next == Produce \/ Consume
SafetyInv == Len(buffer) <= N
Spec == Init /\ [][Next]_buffer
====