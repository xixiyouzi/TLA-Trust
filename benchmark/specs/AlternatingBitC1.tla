---- MODULE AlternatingBitC1 ----
EXTENDS Integers
VARIABLES sbit, rbit, data, ack
Init == sbit = 0 /\ rbit = 0 /\ data = -1 /\ ack = -1
Send == data = -1 /\ data' = sbit /\ UNCHANGED <<sbit, rbit, ack>>
Recv == /\ data /= -1
        /\ IF data = rbit
           THEN (rbit' = 1 - rbit /\ ack' = data)
           ELSE (rbit' = rbit /\ ack' = 1 - rbit)
        /\ data' = -1
        /\ UNCHANGED sbit
Ack == /\ ack /= -1
       /\ IF ack = sbit
          THEN sbit' = 1 - sbit
          ELSE sbit' = sbit
       /\ ack' = -1
       /\ UNCHANGED <<rbit, data>>
Next == Send \/ Recv \/ Ack
Liveness == (data = -1) ~> (data /= -1)
Spec == Init /\ [][Next]_<<sbit, rbit, data, ack>>
        /\ WF_<<sbit, rbit, data, ack>>(Send)
        /\ WF_<<sbit, rbit, data, ack>>(Recv)
        /\ WF_<<sbit, rbit, data, ack>>(Ack)
Safety == /\ sbit \in {0, 1}
          /\ rbit \in {0, 1}
          /\ data \in {-1, 0, 1}
          /\ ack \in {-1, 0, 1}
/\ UndefinedOperator(0)
====
