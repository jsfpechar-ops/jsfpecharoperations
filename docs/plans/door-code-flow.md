# Door code flow (picture)

The rules behind each box are in [ttlock-door-codes](ttlock-door-codes.md) §6. Green: the guest has a code. Orange: the host is mailed (support in copy) and makes the code in the TTLock app.

## 1. Making the code

```mermaid
flowchart TD
    A[Last guest form saved] --> B{Property has a lock,<br/>check-in and check-out hours?}
    B -- no --> Z[Nothing happens]
    B -- yes --> C[Ask the TTLock cloud for a random code<br/>for check-in -1 h to check-out +1 h<br/>nothing is sent to the lock:<br/>the lock checks the code by itself]

    C -- code --> OK1[Guest sees the code at once<br/>and gets it by mail, host in CC<br/>use it within 24 h of the start]
    C -- "-1026 period taken" --> W[Mail host and support:<br/>an older code covers these hours,<br/>check it was deleted]
    C -- network or timeout --> R[Worker tries again in 1 min<br/>first looks for the code by name and window]
    C -- "UbyHost access was removed" --> F

    R -- code --> OK1
    R -- fails again --> F

    W --> ADD[Within about 1 min the worker<br/>creates a custom code<br/>through the gateway]
    ADD -- code --> OK2[Guest sees the code<br/>and gets it by mail, host in CC<br/>no 24 h rule]
    ADD -- "-2012 no gateway" --> F
    ADD -- gateway not answering --> RB[Try again after 1 min, then 5 min]
    RB -- code --> OK2
    RB -- still no answer --> F
    ADD -- access removed, lock memory full --> F

    F[Hand over: host mail<br/>create a code in the TTLock app<br/>Guest sees: your host will send you the door code]

    classDef ok fill:#d9f2e3,stroke:#2e8b57,color:#000
    classDef host fill:#fde8cf,stroke:#d9822b,color:#000
    class OK1,OK2 ok
    class F,W host
```

## 2. After the code exists

```mermaid
flowchart TD
    S[Stay has a code] --> E{What happens next?}

    E -- stay ends --> X[Code expires by itself<br/>no call to TTLock]

    E -- stay cancelled --> D[Delete the code<br/>through the gateway]
    D -- deleted --> DM[Host mail: code deleted<br/>it no longer opens the door]
    D -- gateway down --> DR[Try again: 1, 15, 60 min<br/>custom code: every hour until its end]
    DR -- deleted --> DM
    DR -- still down --> DH[Host mail:<br/>delete the code in the TTLock app]

    E -- dates or hours changed --> N[New code for the new window<br/>random, or custom if -1026]
    N -- code --> NM[Guest gets one new mail]
    NM --> O[Delete the old code]
    O -- deleted --> DONE[Done]
    O -- failed --> OH[Host mail:<br/>delete the old code in the TTLock app]
    N -- fails --> NH[Old code keeps working for the guest<br/>retry in 15 min, or host mail]

    classDef ok fill:#d9f2e3,stroke:#2e8b57,color:#000
    classDef host fill:#fde8cf,stroke:#d9822b,color:#000
    class X,DM,NM,DONE ok
    class DH,OH,NH host
```
