# Home Assistant Multizone Climate - System Diagrams

This document contains comprehensive diagrams illustrating the algorithms, flows, and automations of the Home Assistant Multizone Climate integration.

## Quick Reference Guide

**New to the system?** Start here:
- [System Architecture Overview](#system-architecture-overview) - See how all components fit together
- [System Component Integration](#system-component-integration) - Understand external systems and HA integration

**Understanding the algorithms?** Check these:
- [Calculate Main Target Temperature](#calculate-main-target-temperature-algorithm) - How main thermostat target is determined
- [Update Valves Algorithm](#update-valves-algorithm) - How zones control their valves
- [Zone Satisfaction State Machine](#zone-satisfaction-state-machine) - State transitions with hysteresis

**Implementing the system?** Essential diagrams:
- [Redis Data Schema](#redis-data-schema) - Complete data model
- [Background Jobs and Process Locking](#background-jobs-and-process-locking) - Job execution flow
- [Coordinator Process Flow](#coordinator-process-flow) - Main 15s cycle

**Debugging issues?** Look at:
- [Timing Sequences](#timing-sequences) - Real-world execution timelines
- [Valve Lock Mechanism](#valve-lock-mechanism) - Preventing valve chattering
- [Error Handling and Recovery](#error-handling-and-recovery) - Failure modes and retries

**Safety critical?** Must read:
- [Safety Valve Check Algorithm](#safety-valve-check-algorithm) - Minimum valve enforcement
- [Open-First-Then-Close Sequence](#open-first-then-close-sequence) - Maintaining system flow

## Table of Contents
1. [System Architecture Overview](#system-architecture-overview)
2. [Calculate Main Target Temperature Algorithm](#calculate-main-target-temperature-algorithm)
3. [Update Valves Algorithm](#update-valves-algorithm)
4. [Safety Valve Check Algorithm](#safety-valve-check-algorithm)
5. [Zone Satisfaction State Machine](#zone-satisfaction-state-machine)
6. [Background Jobs and Process Locking](#background-jobs-and-process-locking)
7. [Redis Data Schema](#redis-data-schema)
8. [Automation Flow](#automation-flow)
9. [Coordinator Process Flow](#coordinator-process-flow)
10. [Timing Sequences](#timing-sequences)
11. [Open-First-Then-Close Sequence](#open-first-then-close-sequence)
12. [System Component Integration](#system-component-integration)
13. [Priority Sorting Example](#priority-sorting-example)
14. [Configuration Flow](#configuration-flow)
15. [Valve Lock Mechanism](#valve-lock-mechanism)
16. [Multizone Enable/Disable States](#multizone-enable-disable-states)
17. [Error Handling and Recovery](#error-handling-and-recovery)

---

## System Architecture Overview

```mermaid
graph TB
    subgraph "Home Assistant"
        MainClimate[Main Climate Entity<br/>Thermostat Control]
        Sensors[Temperature Sensors<br/>Per Room]
        Valves[Valve Switches<br/>Per Room]
    end
    
    subgraph "Multizone Integration"
        MainDevice[Main Climate Device<br/>Config Entry]
        ZoneDevices[Climate Zone Subdevices<br/>Per Room]
        
        subgraph "Core Logic"
            CoreLogic[Core Logic<br/>Redis Client]
        end
        
        subgraph "Background Jobs"
            CalcTemp[Calculate Main<br/>Target Temperature]
            UpdateValves[Update Valves]
            SafetyCheck[Safety Valve Check]
        end
        
        subgraph "Automations"
            UpdateTempAuto[Update Main Target<br/>Temperature Automation]
            SafetyAuto[Safety Valve Check<br/>Automation]
        end
        
        Coordinator[Coordinator<br/>Runs every 15s]
        
        subgraph "Queues"
            CalcQueue[Calculate Temp Queue]
            ValveQueue[Update Valves Queue]
        end
    end
    
    subgraph "Redis Storage"
        Config[Global Config]
        ZoneState[Zone States]
        JobQueues[Job Queues]
        ValveLocks[Valve Locks]
        JobLocks[Job Locks]
        JobStatus[Job Status]
    end
    
    subgraph "HVAC System"
        HVACUnit[HVAC Unit<br/>De Dietrich]
        HeatPipes[Heating Pipes]
    end
    
    %% Data flow connections
    Sensors -->|Read Temps| ZoneDevices
    ZoneDevices -->|Target Change| UpdateTempAuto
    UpdateTempAuto -->|Enqueue Job| CalcQueue
    UpdateTempAuto -->|Enqueue Job| ValveQueue
    
    SafetyAuto -->|Trigger| SafetyCheck
    
    Coordinator -->|Dequeue| CalcQueue
    Coordinator -->|Dequeue| ValveQueue
    Coordinator -->|Execute| CalcTemp
    Coordinator -->|Execute| UpdateValves
    Coordinator -->|Execute| SafetyCheck
    
    CalcTemp -->|Read/Write| CoreLogic
    UpdateValves -->|Read/Write| CoreLogic
    SafetyCheck -->|Read/Write| CoreLogic
    
    CoreLogic -->|Store/Retrieve| Config
    CoreLogic -->|Store/Retrieve| ZoneState
    CoreLogic -->|Store/Retrieve| JobQueues
    CoreLogic -->|Store/Retrieve| ValveLocks
    CoreLogic -->|Store/Retrieve| JobLocks
    CoreLogic -->|Store/Retrieve| JobStatus
    
    CalcTemp -->|Update Target| MainClimate
    UpdateValves -->|Open/Close| Valves
    
    MainClimate -->|Control| HVACUnit
    HVACUnit -->|Heat Water| HeatPipes
    Valves -->|Control Flow| HeatPipes
    HeatPipes -->|Heat Rooms| Sensors
    
    style MainDevice fill:#e1f5ff
    style ZoneDevices fill:#e1f5ff
    style CoreLogic fill:#fff4e1
    style Coordinator fill:#ffe1f5
    style Config fill:#e1ffe1
    style ZoneState fill:#e1ffe1
```

---

## Calculate Main Target Temperature Algorithm

### Slider-Based Linear Interpolation (Choice A)

```mermaid
flowchart TD
    Start([Start: Calculate Main Target]) --> CheckZones{Active Zones<br/>Available?}
    
    CheckZones -->|No| ReturnNull[Return None]
    CheckZones -->|Yes| FilterOff[Filter: Get Active Zones<br/>state != OFF]
    
    FilterOff --> CheckActive{Active Zones<br/>Found?}
    CheckActive -->|No| ReturnNull
    CheckActive -->|Yes| FilterOverheat[Filter: Exclude Overheated Zones<br/>satisfaction != overheated]
    
    FilterOverheat --> CheckNonOverheat{Non-Overheated<br/>Zones Found?}
    CheckNonOverheat -->|Yes| UseNonOverheat[Use Non-Overheated Zone Targets]
    CheckNonOverheat -->|No| UseAll[Use All Active Zone Targets<br/>Fallback]
    
    UseNonOverheat --> CheckMode{Calculation<br/>Mode?}
    UseAll --> CheckMode
    
    CheckMode -->|Average Mode| CalcAverage[main_target_raw =<br/>sum of targets / count]
    CheckMode -->|Slider Mode| FindMinMax[Find min and max targets]
    
    FindMinMax --> CheckEqual{min == max?}
    CheckEqual -->|Yes| UseSingle[main_target_raw = min]
    CheckEqual -->|No| CalcInterp[main_target_raw = min +<br/>slider × (max - min)]
    
    CalcAverage --> Round
    UseSingle --> Round
    CalcInterp --> Round
    
    Round[Round to nearest 0.5°C<br/>(round(value × 2)) / 2] --> Clamp[Clamp to limits<br/>main_min_temp, main_max_temp]
    
    Clamp --> CheckThreshold{abs(main_target -<br/>current_main_target)<br/>>= threshold?}
    
    CheckThreshold -->|No| ReturnNull
    CheckThreshold -->|Yes| ReturnTarget[Return main_target]
    
    ReturnTarget --> UpdateClimate[Update Main Climate<br/>Entity Target]
    ReturnNull --> End([End])
    UpdateClimate --> End
    
    style Start fill:#e1f5ff
    style End fill:#e1f5ff
    style CheckMode fill:#fff4e1
    style UpdateClimate fill:#ffe1e1
```

### Example Calculation Flow

```mermaid
flowchart LR
    subgraph Input
        Z1[Bedroom: 20°C]
        Z2[Living: 22°C]
        Z3[Kitchen: 19°C]
        Z4[Bath: 23°C]
    end
    
    subgraph Config
        Slider[Slider: 0.5 (50%)]
        Min[Min: 18°C]
        Max[Max: 30°C]
        Thresh[Threshold: 0.5°C]
    end
    
    subgraph Calculation
        FindRange[Min: 19°C<br/>Max: 23°C]
        Interpolate[19 + 0.5 × (23-19)<br/>= 19 + 2 = 21°C]
        RoundVal[Round: 21.0°C]
        ClampVal[Clamp: 21.0°C<br/>within 18-30]
    end
    
    subgraph Output
        Result[Main Target: 21.0°C]
    end
    
    Z1 & Z2 & Z3 & Z4 --> FindRange
    Slider --> Interpolate
    FindRange --> Interpolate
    Interpolate --> RoundVal
    RoundVal --> ClampVal
    Min & Max --> ClampVal
    ClampVal --> Result
    
    style Input fill:#e1f5ff
    style Config fill:#fff4e1
    style Calculation fill:#ffe1f5
    style Output fill:#e1ffe1
```

---

## Update Valves Algorithm

```mermaid
flowchart TD
    Start([Start: Update Valves]) --> CheckMultizone{Multizone<br/>Enabled?}
    
    CheckMultizone -->|No| IndividualMode[Individual Zone Mode<br/>Each zone manages own valve]
    IndividualMode --> IndivLoop{For each<br/>active zone}
    IndivLoop --> CheckSat[Check satisfaction state]
    CheckSat --> IndivAction{State?}
    IndivAction -->|Underheated| OpenValve[Add to valves_to_open]
    IndivAction -->|Overheated| CloseValve[Add to valves_to_close]
    IndivAction -->|Satisfied| MaintainValve[Maintain current state]
    OpenValve --> IndivLoop
    CloseValve --> IndivLoop
    MaintainValve --> IndivLoop
    IndivLoop -->|Done| SafetyCheck
    
    CheckMultizone -->|Yes| DetermineSat[Determine Satisfaction State<br/>for each zone]
    
    DetermineSat --> CalcSort[Calculate Sort Key<br/>priority, deficit]
    
    CalcSort --> SortZones[Sort Zones by Priority<br/>user priority first, then deficit]
    
    SortZones --> DesiredStates[Determine Desired Valve States]
    
    DesiredStates --> Loop{For each<br/>zone}
    
    Loop -->|OFF| AddClose[Add valve to<br/>valves_to_close]
    Loop -->|Underheated/Undercooled| AddOpen[Add valve to<br/>valves_to_open]
    Loop -->|Overheated/Overcooled| AddClose2[Add valve to<br/>valves_to_close]
    Loop -->|Satisfied| AddOpenSat[Add valve to<br/>valves_to_open<br/>maintain temp]
    
    AddClose --> Loop
    AddOpen --> Loop
    AddClose2 --> Loop
    AddOpenSat --> Loop
    
    Loop -->|Done| SafetyCheck[Safety Check:<br/>Ensure min_valves_open]
    
    SafetyCheck --> CheckMin{Will have<br/>min valves<br/>open?}
    
    CheckMin -->|Yes| CheckLocks
    CheckMin -->|No| ForceFallback[Force open fallback valves<br/>shortage = min - will_be_open]
    
    ForceFallback --> CheckLocks[Check Valve Locks<br/>cooldown]
    
    CheckLocks --> FilterLocked[Remove locked valves from<br/>valves_to_open/close]
    
    FilterLocked --> CheckSwap{At minimum AND<br/>need to swap?}
    
    CheckSwap -->|Yes| OpenFirst[OPEN new valves FIRST<br/>set locks]
    OpenFirst --> Schedule[Schedule CLOSE old valves<br/>after valve_actuation_delay]
    Schedule --> Execute
    
    CheckSwap -->|No| SimultaneousClose[Close valves<br/>set locks]
    SimultaneousClose --> SimultaneousOpen[Open valves<br/>set locks]
    SimultaneousOpen --> Execute
    
    Execute[Execute Valve Actions] --> UpdateRedis[Update Zone States<br/>in Redis]
    
    UpdateRedis --> End([End])
    
    style Start fill:#e1f5ff
    style End fill:#e1f5ff
    style CheckMultizone fill:#fff4e1
    style SafetyCheck fill:#ffe1e1
    style CheckSwap fill:#ffe1f5
```

---

## Safety Valve Check Algorithm

```mermaid
flowchart TD
    Start([Start: Safety Check]) --> GetOpen[Get Currently Open Valves<br/>from zones]
    
    GetOpen --> Count[Count open valves]
    
    Count --> CheckMin{Count >=<br/>min_valves_open?}
    
    CheckMin -->|Yes| LogOK[Log: System OK]
    LogOK --> End([End])
    
    CheckMin -->|No| LogWarn[Log WARNING:<br/>Insufficient valves open]
    
    LogWarn --> CalcShortage[shortage =<br/>min_valves_open - count]
    
    CalcShortage --> GetFallback[Get Fallback Valves<br/>is_fallback_valve = true<br/>exclude currently open]
    
    GetFallback --> SelectValves[Select first 'shortage'<br/>fallback valves]
    
    SelectValves --> ForceLoop{For each<br/>fallback valve}
    
    ForceLoop --> LogForce[Log WARNING:<br/>Force opening fallback valve]
    
    LogForce --> OpenFallback[Open fallback valve]
    
    OpenFallback --> SetLock[Set valve lock<br/>cooldown period]
    
    SetLock --> ForceLoop
    
    ForceLoop -->|Done| UpdateRedis[Update valve states<br/>in Redis]
    
    UpdateRedis --> End
    
    style Start fill:#e1f5ff
    style End fill:#e1f5ff
    style CheckMin fill:#ffe1e1
    style LogWarn fill:#ffcccc
    style LogForce fill:#ffcccc
```

---

## Zone Satisfaction State Machine

### Heating Mode State Transitions

```mermaid
stateDiagram-v2
    [*] --> Unknown
    Unknown --> Underheated: temp < target - opening_offset
    Unknown --> Satisfied: within bounds
    Unknown --> Overheated: temp > target + closing_offset
    
    Underheated --> Satisfied: temp >= target + satisfaction_eps<br/>(while rising)
    Satisfied --> Underheated: temp < target - opening_offset
    
    Satisfied --> Overheated: temp > target + closing_offset
    Overheated --> Satisfied: temp <= target - satisfaction_eps<br/>(while falling)
    
    note right of Underheated
        Valve: OPEN
        Below: target - opening_offset
        Exit: reaches target + satisfaction_eps
    end note
    
    note right of Satisfied
        Valve: OPEN (maintain temp)
        Within: opening_offset to closing_offset
        Hysteresis: stays satisfied within bounds
    end note
    
    note right of Overheated
        Valve: CLOSED
        Above: target + closing_offset
        Exit: reaches target - satisfaction_eps
    end note
```

### Cooling Mode State Transitions

```mermaid
stateDiagram-v2
    [*] --> Unknown
    Unknown --> Undercooled: temp > target + opening_offset
    Unknown --> Satisfied: within bounds
    Unknown --> Overcooled: temp < target - closing_offset
    
    Undercooled --> Satisfied: temp <= target - satisfaction_eps<br/>(while falling)
    Satisfied --> Undercooled: temp > target + opening_offset
    
    Satisfied --> Overcooled: temp < target - closing_offset
    Overcooled --> Satisfied: temp >= target + satisfaction_eps<br/>(while rising)
    
    note right of Undercooled
        Valve: OPEN
        Above: target + opening_offset
        Exit: reaches target - satisfaction_eps
    end note
    
    note right of Satisfied
        Valve: OPEN (maintain temp)
        Within: closing_offset to opening_offset
        Hysteresis: stays satisfied within bounds
    end note
    
    note right of Overcooled
        Valve: CLOSED
        Below: target - closing_offset
        Exit: reaches target + satisfaction_eps
    end note
```

### Satisfaction Boundaries Diagram

```mermaid
graph LR
    subgraph "Heating Mode: Target = 21.0°C"
        subgraph "opening_offset = 0.3, closing_offset = 0.3, satisfaction_eps = 0.1"
            LB[Lower Bound<br/>20.7°C]
            TSM[Satisfied Exit<br/>20.9°C<br/>target - eps]
            T[Target<br/>21.0°C]
            TSP[Satisfied Entry<br/>21.1°C<br/>target + eps]
            UB[Upper Bound<br/>21.3°C]
        end
    end
    
    LB -.->|Underheated Zone| TSM
    TSM -.->|Satisfied Zone| UB
    UB -.->|Overheated Zone| R[>21.3°C]
    
    style LB fill:#ffcccc
    style TSM fill:#ffffcc
    style T fill:#ccffcc
    style TSP fill:#ffffcc
    style UB fill:#ffcccc
```

---

## Background Jobs and Process Locking

```mermaid
sequenceDiagram
    participant Auto as Automation
    participant Queue as Job Queue
    participant Coord as Coordinator
    participant Lock as Job Lock (Redis)
    participant Job as Background Job
    participant Redis as Redis Store
    participant HA as Home Assistant
    
    Auto->>Queue: Enqueue calculate_main_temp job
    Auto->>Queue: Enqueue update_valves job
    
    Note over Coord: Runs every 15 seconds
    
    Coord->>Queue: Dequeue calculate_main_temp
    Queue-->>Coord: Job details
    
    Coord->>Lock: Try acquire lock(calculate_main_temp)
    
    alt Lock available
        Lock-->>Coord: Lock acquired
        Coord->>Job: Execute calculate_main_temp
        Job->>Redis: Fetch config & zone states
        Redis-->>Job: Data
        Job->>Job: Calculate main target
        Job->>HA: Update main climate target
        Job->>Redis: Update job status
        Job-->>Coord: Job completed
        Coord->>Lock: Release lock(calculate_main_temp)
    else Lock held
        Lock-->>Coord: Lock denied
        Coord->>Queue: Re-enqueue job
        Note over Coord: Will retry next cycle
    end
    
    Coord->>Queue: Dequeue update_valves
    Queue-->>Coord: Job details
    
    Coord->>Lock: Try acquire lock(update_valves)
    Lock-->>Coord: Lock acquired
    Coord->>Job: Execute update_valves
    Job->>Redis: Fetch config & zone states
    Redis-->>Job: Data
    Job->>Job: Determine valve actions
    Job->>HA: Open/Close valves
    Job->>Redis: Set valve locks
    Job->>Redis: Update zone states
    Job-->>Coord: Job completed
    Coord->>Lock: Release lock(update_valves)
```

### Job Queue Management

```mermaid
flowchart TD
    subgraph "Job Enqueueing"
        E1[Zone Target Changed] --> Q1[Enqueue: calculate_main_temp]
        E1 --> Q2[Enqueue: update_valves]
        E2[Timer: Every valve_delay/2] --> Q3[Direct Execute: safety_check]
    end
    
    subgraph "Coordinator Cycle - 15s"
        Start([Coordinator Wakes]) --> UpdateSensors[Update Sensor States<br/>from Redis]
        UpdateSensors --> CheckCalcQueue{Calculate Queue<br/>Has Job?}
        CheckCalcQueue -->|Yes| CheckCalcLock{Lock Available?}
        CheckCalcLock -->|Yes| ExecCalc[Execute Calculate Job]
        CheckCalcLock -->|No| SkipCalc[Skip - Will retry]
        ExecCalc --> CheckValveQueue
        SkipCalc --> CheckValveQueue
        CheckCalcQueue -->|No| CheckValveQueue
        
        CheckValveQueue{Valve Queue<br/>Has Job?} -->|Yes| CheckValveLock{Lock Available?}
        CheckValveLock -->|Yes| ExecValve[Execute Valve Job]
        CheckValveLock -->|No| SkipValve[Skip - Will retry]
        ExecValve --> Sleep
        SkipValve --> Sleep
        CheckValveQueue -->|No| Sleep[Sleep 15s]
        Sleep --> Start
    end
    
    Q1 --> CheckCalcQueue
    Q2 --> CheckValveQueue
    Q3 -.-> SafetyJob[Safety Check Job]
    
    style Start fill:#e1f5ff
    style ExecCalc fill:#ffe1e1
    style ExecValve fill:#ffe1e1
    style SafetyJob fill:#ffcccc
```

---

## Redis Data Schema

```mermaid
erDiagram
    CONFIG ||--o{ ZONES : manages
    CONFIG {
        string main_climate_entity_id
        float main_target_all_zones_satisfied
        boolean use_average_mode
        int min_valves_open
        float main_min_temp
        float main_max_temp
        float main_change_threshold
        int valve_actuation_delay
        int coordinator_interval
        float satisfaction_eps
    }
    
    ZONES ||--|{ ZONE_STATE : contains
    ZONES {
        array zone_ids
    }
    
    ZONE_STATE {
        string id
        string name
        string temperature_sensor_entity_id
        string valve_switch_entity_id
        float current_temperature
        float target_temperature
        string state
        string satisfaction
        string valve_state
        float opening_offset
        float closing_offset
        boolean is_fallback_valve
        int priority
        timestamp last_updated
    }
    
    MAIN_CLIMATE {
        string entity_id
        float current_temperature
        float target_temperature
        float outdoor_temperature
        string hvac_mode
        string hvac_action
        boolean multizone_enabled
        timestamp last_updated
    }
    
    JOB_QUEUES ||--|{ QUEUE_ENTRY : contains
    JOB_QUEUES {
        string queue_calculate_main_temp
        string queue_update_valves
    }
    
    QUEUE_ENTRY {
        string job_id
        string job_type
        timestamp enqueued_at
        json parameters
    }
    
    VALVE_LOCKS {
        string valve_id
        timestamp locked_until
        string reason
    }
    
    JOB_LOCKS {
        string job_type
        timestamp acquired_at
        string acquired_by
    }
    
    JOB_STATUS {
        string job_id
        string job_type
        string status
        timestamp started_at
        timestamp completed_at
        int duration_ms
        int actions_taken
        json result
    }
```

### Redis Key Structure

```mermaid
graph TD
    Root[ha_multizone: prefix] --> Config[config<br/>Hash]
    Root --> Zones[zones<br/>List]
    Root --> MainClimate[main_climate<br/>Hash]
    
    Root --> ZoneHash[zone:zone_id<br/>Hash - per zone]
    
    Root --> QueueCalc[queue:calculate_main_temp<br/>List FIFO]
    Root --> QueueValve[queue:update_valves<br/>List FIFO]
    
    Root --> ValveLock[valvelock:valve_id<br/>String + TTL]
    Root --> JobLock[joblock:job_type<br/>String + TTL]
    Root --> JobStat[jobstatus:job_id<br/>Hash + TTL]
    
    style Config fill:#e1ffe1
    style Zones fill:#e1ffe1
    style MainClimate fill:#e1ffe1
    style ZoneHash fill:#ffe1f5
    style QueueCalc fill:#fff4e1
    style QueueValve fill:#fff4e1
    style ValveLock fill:#ffcccc
    style JobLock fill:#ffcccc
    style JobStat fill:#e1f5ff
```

---

## Automation Flow

```mermaid
flowchart TD
    subgraph "Trigger Events"
        T1[Zone Temperature Changed]
        T2[Zone Target Changed]
        T3[Zone State Changed]
        T4[Timer: Every valve_delay/2]
    end
    
    subgraph "Update Main Target Automation"
        T1 --> Check1{Debounce<br/>~5 seconds}
        T2 --> Check1
        T3 --> Check1
        Check1 --> Enqueue1[Enqueue Job:<br/>calculate_main_temp]
        Check1 --> Enqueue2[Enqueue Job:<br/>update_valves]
    end
    
    subgraph "Safety Check Automation"
        T4 --> DirectExec[Direct Execute:<br/>safety_valve_check]
    end
    
    subgraph "Job Queues in Redis"
        Enqueue1 --> CalcQueue[(Calculate Queue)]
        Enqueue2 --> ValveQueue[(Valve Queue)]
    end
    
    subgraph "Coordinator Execution"
        CalcQueue --> Coord[Coordinator<br/>15s interval]
        ValveQueue --> Coord
        DirectExec --> SafetyJob[Safety Job]
        
        Coord --> DequeueCalc[Dequeue & Execute<br/>Calculate Main Temp]
        Coord --> DequeueValve[Dequeue & Execute<br/>Update Valves]
    end
    
    subgraph "Actions"
        DequeueCalc --> UpdateMain[Update Main Climate<br/>Target Temperature]
        DequeueValve --> UpdateValves[Open/Close<br/>Zone Valves]
        SafetyJob --> ForceOpen[Force Open<br/>Fallback Valves]
    end
    
    style T1 fill:#e1f5ff
    style T2 fill:#e1f5ff
    style T3 fill:#e1f5ff
    style T4 fill:#ffcccc
    style CalcQueue fill:#fff4e1
    style ValveQueue fill:#fff4e1
    style UpdateMain fill:#ffe1e1
    style UpdateValves fill:#ffe1e1
    style ForceOpen fill:#ffcccc
```

---

## Coordinator Process Flow

```mermaid
flowchart TD
    Start([Coordinator Timer<br/>Every 15s]) --> FetchRedis[Fetch Latest Data<br/>from Redis]
    
    FetchRedis --> UpdateSensors[Update Sensor Entities<br/>Only if changed]
    
    UpdateSensors --> UpdateStates[Update Entity States<br/>Only if changed]
    
    UpdateStates --> CheckCalcQ{Calculate Queue<br/>Has Jobs?}
    
    CheckCalcQ -->|No| CheckValveQ
    CheckCalcQ -->|Yes| TryCalcLock[Try Acquire Lock:<br/>calculate_main_temp]
    
    TryCalcLock --> CalcLocked{Lock<br/>Acquired?}
    CalcLocked -->|No| CheckValveQ
    CalcLocked -->|Yes| DequeueCalc[Dequeue Job from<br/>Calculate Queue]
    
    DequeueCalc --> ExecCalc[Execute:<br/>Calculate Main Target]
    
    ExecCalc --> ReleaseCalcLock[Release Lock:<br/>calculate_main_temp]
    
    ReleaseCalcLock --> CheckValveQ{Valve Queue<br/>Has Jobs?}
    
    CheckValveQ -->|No| Wait
    CheckValveQ -->|Yes| TryValveLock[Try Acquire Lock:<br/>update_valves]
    
    TryValveLock --> ValveLocked{Lock<br/>Acquired?}
    ValveLocked -->|No| Wait
    ValveLocked -->|Yes| DequeueValve[Dequeue Job from<br/>Valve Queue]
    
    DequeueValve --> ExecValve[Execute:<br/>Update Valves]
    
    ExecValve --> ReleaseValveLock[Release Lock:<br/>update_valves]
    
    ReleaseValveLock --> Wait[Wait for Next Cycle<br/>15 seconds]
    
    Wait --> Start
    
    style Start fill:#e1f5ff
    style FetchRedis fill:#e1ffe1
    style ExecCalc fill:#ffe1e1
    style ExecValve fill:#ffe1e1
```

---

## Timing Sequences

### Scenario 1: Zone Temperature Drop

```mermaid
sequenceDiagram
    participant Sensor as Temperature Sensor
    participant Zone as Zone Entity
    participant Auto as Automation
    participant Queue as Job Queue
    participant Coord as Coordinator (15s)
    participant CalcJob as Calculate Job
    participant ValveJob as Valve Job
    participant Main as Main Climate
    participant Valve as Valve Switch
    
    Note over Sensor: T=0s
    Sensor->>Zone: Bedroom temp: 20.4°C
    Zone->>Zone: Check: 20.4 < 20.7 → Underheated
    Zone->>Auto: Temperature changed event
    
    Note over Auto: Debounce ~5s
    Auto->>Queue: Enqueue: calculate_main_temp
    Auto->>Queue: Enqueue: update_valves
    
    Note over Coord: T=15s: Coordinator wakes
    Coord->>Queue: Dequeue calculate_main_temp
    Coord->>CalcJob: Execute
    CalcJob->>CalcJob: Calculate new main target
    CalcJob->>Main: Set target: 21.0°C
    Main-->>CalcJob: Updated
    
    Coord->>Queue: Dequeue update_valves
    Coord->>ValveJob: Execute
    ValveJob->>ValveJob: Bedroom underheated → open valve
    ValveJob->>Valve: Open Bedroom valve
    Valve-->>ValveJob: Opening...
    ValveJob->>ValveJob: Set valve lock until T=135s
    
    Note over Valve: T=15s to T=135s: Physical valve opening
    Note over Valve: T=135s: Valve fully open, lock expires
```

### Scenario 2: Multiple Rapid Changes

```mermaid
sequenceDiagram
    participant Z1 as Bedroom Zone
    participant Z2 as Kitchen Zone
    participant Z3 as Living Zone
    participant Queue as Job Queue
    participant Coord as Coordinator
    
    Note over Z1,Coord: T=0s
    Z1->>Queue: Bedroom target changed
    Queue->>Queue: Enqueue: calc_temp_1, update_valves_1
    
    Note over Z1,Coord: T=5s
    Z2->>Queue: Kitchen target changed
    Queue->>Queue: Enqueue: calc_temp_2, update_valves_2
    
    Note over Z1,Coord: T=10s
    Z3->>Queue: Living target changed
    Queue->>Queue: Enqueue: calc_temp_3, update_valves_3
    
    Note over Z1,Coord: Queue: [calc_1, valve_1, calc_2, valve_2, calc_3, valve_3]
    
    Note over Coord: T=15s: Coordinator cycle 1
    Coord->>Queue: Dequeue calc_temp_1
    Coord->>Coord: Execute calc_temp_1
    Coord->>Queue: Dequeue update_valves_1
    Coord->>Coord: Execute update_valves_1
    
    Note over Coord: T=30s: Coordinator cycle 2
    Coord->>Queue: Dequeue calc_temp_2
    Coord->>Coord: Execute calc_temp_2
    Coord->>Queue: Dequeue update_valves_2
    Coord->>Coord: Execute update_valves_2
    
    Note over Coord: T=45s: Coordinator cycle 3
    Coord->>Queue: Dequeue calc_temp_3
    Coord->>Coord: Execute calc_temp_3
    Coord->>Queue: Dequeue update_valves_3
    Coord->>Coord: Execute update_valves_3
    
    Note over Queue: T=60s: All jobs processed
```

---

## Open-First-Then-Close Sequence

```mermaid
sequenceDiagram
    participant System as Update Valves
    participant VB as Bedroom Valve (Open)
    participant VK as Kitchen Valve (Closed)
    participant Lock as Valve Locks
    participant Redis as Redis
    
    Note over System: Initial: Bedroom OPEN (only 1 valve)<br/>min_valves_open = 1<br/>valve_actuation_delay = 120s
    
    Note over System: T=0s: Algorithm detects swap needed
    System->>System: Bedroom: satisfied → should close
    System->>System: Kitchen: underheated → should open
    System->>System: Currently at minimum (1 valve)
    System->>System: Need swap: OPEN FIRST
    
    Note over VK: T=0s: Open Kitchen valve FIRST
    System->>VK: Command: OPEN
    VK->>VK: Motor starts opening...
    System->>Lock: Set lock: Kitchen until T=120s
    Lock->>Redis: Store: valvelock:kitchen_valve
    
    Note over VB,VK: T=0s to T=120s: BOTH valves open (safe)
    Note over VK: Physical valve opening (120 seconds)
    
    Note over VB: T=120s: Lock expires, now safe to close Bedroom
    System->>VB: Command: CLOSE
    VB->>VB: Motor starts closing...
    System->>Lock: Set lock: Bedroom until T=240s
    Lock->>Redis: Store: valvelock:bedroom_valve
    
    Note over VB: T=120s to T=240s: Bedroom closing
    Note over VK: Kitchen remains OPEN
    
    Note over System: T=240s: Final state
    Note over VK: Kitchen: OPEN (minimum maintained)
    Note over VB: Bedroom: CLOSED
    Note over System: ✓ Minimum flow maintained throughout
```

### Safety Guarantee Diagram

```mermaid
graph TD
    subgraph "Time: T=0s"
        T0State["Valves Open: 1<br/>Bedroom: OPEN<br/>Kitchen: CLOSED"]
    end
    
    subgraph "Time: T=0s Action"
        T0Action["OPEN Kitchen valve<br/>Set lock: 120s"]
    end
    
    subgraph "Time: T=0-120s"
        T1State["Valves Open: 2<br/>Bedroom: OPEN<br/>Kitchen: OPENING<br/>✓ SAFE: Above minimum"]
    end
    
    subgraph "Time: T=120s Action"
        T2Action["CLOSE Bedroom valve<br/>Set lock: 120s"]
    end
    
    subgraph "Time: T=120-240s"
        T3State["Valves Open: 1+<br/>Bedroom: CLOSING<br/>Kitchen: OPEN<br/>✓ SAFE: At minimum"]
    end
    
    subgraph "Time: T=240s Final"
        T4State["Valves Open: 1<br/>Bedroom: CLOSED<br/>Kitchen: OPEN<br/>✓ SAFE: At minimum"]
    end
    
    T0State --> T0Action
    T0Action --> T1State
    T1State --> T2Action
    T2Action --> T3State
    T3State --> T4State
    
    style T1State fill:#ccffcc
    style T3State fill:#ccffcc
    style T4State fill:#ccffcc
```

---

## System Component Integration

```mermaid
graph TB
    subgraph "External Systems"
        HVAC[HVAC Unit<br/>De Dietrich Strateo]
        Cloud[Cloud API<br/>Remeha]
        HeatPipes[Heating Pipes<br/>Water Circulation]
    end
    
    subgraph "Home Assistant Core"
        MainThermo[Main Thermostat Entity<br/>remeha_home_by_chester]
        TempSensors[Temperature Sensors<br/>Per Room]
        ValveSwitches[Valve Switches<br/>Per Room]
    end
    
    subgraph "Multizone Integration Components"
        subgraph "Config Entry"
            MainDevice[Main Climate Device]
            ZoneDevices[Zone Climate Devices]
            ConfigFlow[Configuration Flow]
        end
        
        subgraph "Core Components"
            CoreLogic[Core Logic<br/>Redis Client]
            Coordinator[Data Update Coordinator<br/>15s interval]
        end
        
        subgraph "Background Services"
            CalcService[Calculate Main Target Service]
            ValveService[Update Valves Service]
            SafetyService[Safety Check Service]
        end
        
        subgraph "Automations"
            TempAuto[Temperature Change Automation]
            SafetyAuto[Safety Timer Automation]
        end
        
        subgraph "Entities"
            ClimatePlatform[Climate Platform<br/>Zone Entities]
            SensorPlatform[Sensor Platform<br/>State Sensors]
            SwitchPlatform[Switch Platform<br/>Multizone Enable]
        end
    end
    
    subgraph "Redis Database"
        GlobalConfig[Global Config]
        ZoneStates[Zone States]
        Queues[Job Queues]
        Locks[Locks & Status]
    end
    
    subgraph "Frontend UI"
        IntegrationUI[Integration Setup UI]
        ConfigEditor[Config Editor]
        ZoneManager[Zone Manager]
        Cards[Lovelace Cards]
        Dashboards[Dashboards]
    end
    
    %% External connections
    HVAC <-->|WiFi/Cloud| Cloud
    Cloud <-->|API| MainThermo
    HVAC -->|Heat Water| HeatPipes
    HeatPipes -->|Heat Rooms| TempSensors
    
    %% HA Core connections
    MainThermo -->|Read/Write| MainDevice
    TempSensors -->|Read Temps| ZoneDevices
    ValveSwitches <-->|Control| ValveService
    
    %% Integration internal
    ConfigFlow -->|Setup| MainDevice
    ConfigFlow -->|Setup| ZoneDevices
    
    TempSensors -->|State Change| TempAuto
    ZoneDevices -->|Target Change| TempAuto
    TempAuto -->|Enqueue Jobs| Queues
    
    SafetyAuto -->|Trigger| SafetyService
    
    Coordinator -->|Dequeue| Queues
    Coordinator -->|Execute| CalcService
    Coordinator -->|Execute| ValveService
    Coordinator -->|Update| SensorPlatform
    
    CalcService -->|Use| CoreLogic
    ValveService -->|Use| CoreLogic
    SafetyService -->|Use| CoreLogic
    
    CoreLogic <-->|Store/Retrieve| GlobalConfig
    CoreLogic <-->|Store/Retrieve| ZoneStates
    CoreLogic <-->|Store/Retrieve| Locks
    
    MainDevice -->|Expose| ClimatePlatform
    ZoneDevices -->|Expose| ClimatePlatform
    
    SwitchPlatform -->|Enable/Disable| Coordinator
    
    %% Frontend connections
    IntegrationUI -->|Configure| ConfigFlow
    ConfigEditor <-->|Read/Write| GlobalConfig
    ZoneManager <-->|Manage| ZoneStates
    Cards -->|Display| ClimatePlatform
    Cards -->|Display| SensorPlatform
    Dashboards -->|Compose| Cards
    
    style HVAC fill:#ffcccc
    style MainThermo fill:#e1f5ff
    style CoreLogic fill:#fff4e1
    style Coordinator fill:#ffe1f5
    style GlobalConfig fill:#e1ffe1
    style Cards fill:#e1e1ff
```

### Data Flow: User Changes Zone Target

```mermaid
flowchart LR
    User[User] -->|Sets Target| Card[Lovelace Climate Card]
    Card -->|Update| ZoneEntity[Zone Climate Entity]
    ZoneEntity -->|Write| Redis[(Redis: Zone State)]
    ZoneEntity -->|Fire Event| Auto[Temperature Change Automation]
    Auto -->|Enqueue| Queue[(Job Queue)]
    Queue -->|Wait| Coord[Coordinator: Next Cycle]
    Coord -->|Dequeue & Execute| CalcJob[Calculate Main Target Job]
    CalcJob -->|Read| Redis
    CalcJob -->|Calculate| NewTarget[New Main Target]
    NewTarget -->|Update| MainClimate[Main Climate Entity]
    MainClimate -->|API Call| Cloud[Cloud API]
    Cloud -->|Control| HVAC[HVAC Unit]
    
    Coord -->|Dequeue & Execute| ValveJob[Update Valves Job]
    ValveJob -->|Read| Redis
    ValveJob -->|Determine Actions| Actions[Valve Actions]
    Actions -->|Open/Close| ValveSwitches[Valve Switches]
    ValveSwitches -->|Physical Control| Valves[Physical Valves]
    
    style User fill:#e1f5ff
    style Redis fill:#e1ffe1
    style HVAC fill:#ffcccc
    style Valves fill:#ffe1e1
```

---

## Priority Sorting Example

```mermaid
graph TD
    subgraph "Zones with Priority"
        ZA["Zone A: Bedroom<br/>Priority: 10<br/>Target: 21°C, Current: 19°C<br/>Deficit: 2.0°C<br/>Sort Key: (10, 2.0)"]
        
        ZB["Zone B: Kitchen<br/>Priority: 5<br/>Target: 22°C, Current: 19°C<br/>Deficit: 3.0°C<br/>Sort Key: (5, 3.0)"]
        
        ZC["Zone C: Living<br/>Priority: 0<br/>Target: 20°C, Current: 16°C<br/>Deficit: 4.0°C<br/>Sort Key: (0, 4.0)"]
        
        ZD["Zone D: Bathroom<br/>Priority: 0<br/>Target: 23°C, Current: 22°C<br/>Deficit: 1.0°C<br/>Sort Key: (0, 1.0)"]
    end
    
    subgraph "Sorted Order (High to Low Priority)"
        S1["1st: Zone A<br/>Highest user priority"]
        S2["2nd: Zone B<br/>Second user priority"]
        S3["3rd: Zone C<br/>Default priority, largest deficit"]
        S4["4th: Zone D<br/>Default priority, smallest deficit"]
    end
    
    ZA --> S1
    ZB --> S2
    ZC --> S3
    ZD --> S4
    
    S1 --> Action1[Managed First]
    S2 --> Action2[Managed Second]
    S3 --> Action3[Managed Third]
    S4 --> Action4[Managed Last]
    
    style S1 fill:#ffcccc
    style S2 fill:#ffddcc
    style S3 fill:#ffeecc
    style S4 fill:#ffffcc
```

---

## Configuration Flow

```mermaid
flowchart TD
    Start([User Adds Integration]) --> Welcome[Welcome Screen<br/>Multizone Climate]
    
    Welcome --> RedisConfig[Configure Redis Connection]
    RedisConfig -->|Input| RedisFields["Host: localhost<br/>Port: 6379<br/>Password: optional<br/>DB: 0<br/>Prefix: ha_multizone"]
    
    RedisFields --> TestRedis{Test Redis<br/>Connection}
    TestRedis -->|Failed| RedisError[Show Error]
    RedisError --> RedisConfig
    TestRedis -->|Success| MainClimateConfig
    
    MainClimateConfig[Select Main Climate Entity] -->|Entity Selector| MainEntity[climate.main_thermostat]
    
    MainEntity --> AutoConfig[Configure Automation Settings]
    AutoConfig -->|Input| AutoFields["Mode: Slider/Average<br/>Slider: 50% default<br/>Min Valves: 1<br/>Min Temp: 18°C<br/>Max Temp: 30°C<br/>Change Threshold: 0.5°C<br/>Valve Delay: 120s<br/>Satisfaction Eps: 0.0°C"]
    
    AutoFields --> Validate{Validate<br/>Config}
    Validate -->|Invalid| ShowValidation[Show Validation Errors]
    ShowValidation --> AutoConfig
    
    Validate -->|Valid| CreateEntry[Create Config Entry]
    CreateEntry --> SetupDevice[Setup Main Climate Device]
    SetupDevice --> InitRedis[Initialize Redis Schema]
    InitRedis --> Complete[Setup Complete]
    
    Complete --> ShowOptions[Show Options:<br/>Add Climate Zone]
    
    style Start fill:#e1f5ff
    style Complete fill:#ccffcc
    style RedisError fill:#ffcccc
    style ShowValidation fill:#ffcccc
```

### Add Zone Flow

```mermaid
flowchart TD
    Start([User Adds Zone]) --> ZoneForm[Zone Configuration Form]
    
    ZoneForm -->|Input| ZoneFields["Name: Bedroom<br/>Temp Sensor: sensor.bedroom_temp<br/>Valve Switch: switch.bedroom_valve<br/>Target Threshold: 0.1°C<br/>Opening Offset: 0.3°C<br/>Closing Offset: 0.3°C<br/>Is Fallback: false<br/>Priority: 0"]
    
    ZoneFields --> ValidateZone{Validate<br/>Entities Exist?}
    ValidateZone -->|No| EntityError[Show Error:<br/>Entity not found]
    EntityError --> ZoneForm
    
    ValidateZone -->|Yes| CheckFallback{Check Fallback<br/>Requirements}
    CheckFallback -->|Need more fallbacks| WarnFallback[Warn: Configure as fallback?]
    WarnFallback --> ZoneForm
    
    CheckFallback -->|OK| CreateZone[Create Zone Device]
    CreateZone --> StoreRedis[Store Zone in Redis]
    StoreRedis --> CreateEntity[Create Climate Entity]
    CreateEntity --> InitialState[Set Initial State: OFF]
    InitialState --> ZoneComplete[Zone Added]
    
    ZoneComplete --> EnableOption[User can now:<br/>Turn zone ON<br/>Set target temp<br/>Enable multizone]
    
    style Start fill:#e1f5ff
    style ZoneComplete fill:#ccffcc
    style EntityError fill:#ffcccc
    style WarnFallback fill:#ffffcc
```

---

## Valve Lock Mechanism

```mermaid
sequenceDiagram
    participant Algo as Update Valves Algorithm
    participant Redis as Redis
    participant Valve as Physical Valve
    
    Note over Algo: T=0s: Need to open Bedroom valve
    
    Algo->>Redis: Check: Is bedroom_valve locked?
    Redis-->>Algo: No lock found
    
    Algo->>Valve: Command: OPEN
    Valve->>Valve: Motor activates...
    
    Algo->>Redis: Set lock: bedroom_valve<br/>locked_until = T+120s<br/>TTL = 120s
    Redis-->>Algo: Lock set
    
    Note over Valve: T=0 to T=120s: Physical valve opening
    
    Note over Algo: T=30s: Algorithm runs again
    Algo->>Redis: Check: Is bedroom_valve locked?
    Redis-->>Algo: Locked until T=120s
    Algo->>Algo: Skip valve action (locked)
    
    Note over Algo: T=90s: Algorithm runs again
    Algo->>Redis: Check: Is bedroom_valve locked?
    Redis-->>Algo: Locked until T=120s
    Algo->>Algo: Skip valve action (locked)
    
    Note over Valve: T=120s: Valve fully open
    Note over Redis: T=120s: Lock TTL expires automatically
    
    Note over Algo: T=125s: Algorithm runs again
    Algo->>Redis: Check: Is bedroom_valve locked?
    Redis-->>Algo: No lock (expired)
    Algo->>Algo: Valve can be actuated again
```

---

## Multizone Enable/Disable States

```mermaid
stateDiagram-v2
    [*] --> Disabled: Initial Setup
    
    Disabled --> CheckZones: User enables multizone
    CheckZones --> Disabled: No zones configured
    CheckZones --> CheckActive: Zones exist
    
    CheckActive --> Disabled: No zones turned ON
    CheckActive --> Enabled: At least 1 zone ON
    
    Enabled --> Operating: Automations active
    Operating --> Enabled: Continue operation
    
    Enabled --> Disabled: User disables OR<br/>All zones turned OFF
    
    note right of Disabled
        - Multizone switch: OFF
        - Each zone manages own valve
        - Safety check still runs
        - Main climate: manual control
    end note
    
    note right of Enabled
        - Multizone switch: ON
        - Coordinated valve management
        - Main target auto-calculated
        - Automations active
    end note
    
    note right of Operating
        - Coordinator runs every 15s
        - Jobs process from queues
        - Valves coordinated
        - Main target updated
    end note
```

---

## Error Handling and Recovery

```mermaid
flowchart TD
    Start([Job Execution]) --> TryAcquire{Try Acquire<br/>Job Lock}
    
    TryAcquire -->|Timeout/Failed| Requeue1[Re-enqueue Job]
    Requeue1 --> End1([Will Retry Next Cycle])
    
    TryAcquire -->|Success| Execute[Execute Job Logic]
    
    Execute --> TryRedis{Redis<br/>Connection OK?}
    TryRedis -->|No| LogError1[Log Error: Redis unavailable]
    LogError1 --> ReleaseLock1[Release Job Lock]
    ReleaseLock1 --> Requeue2[Re-enqueue Job]
    Requeue2 --> End2([Will Retry Next Cycle])
    
    TryRedis -->|Yes| TryHA{HA API<br/>Call OK?}
    TryHA -->|No| LogError2[Log Error: HA API failed]
    LogError2 --> CheckRetry{Retry<br/>Count < 3?}
    CheckRetry -->|Yes| ReleaseLock2[Release Job Lock]
    ReleaseLock2 --> Requeue3[Re-enqueue Job]
    Requeue3 --> End3([Will Retry Next Cycle])
    CheckRetry -->|No| LogCritical[Log Critical: Job failed]
    LogCritical --> UpdateStatus1[Update Job Status: FAILED]
    UpdateStatus1 --> ReleaseLock3[Release Job Lock]
    ReleaseLock3 --> End4([Job Abandoned])
    
    TryHA -->|Success| UpdateStatus2[Update Job Status: COMPLETED]
    UpdateStatus2 --> ReleaseLock4[Release Job Lock]
    ReleaseLock4 --> End5([Job Success])
    
    style LogError1 fill:#ffcccc
    style LogError2 fill:#ffcccc
    style LogCritical fill:#ff9999
    style End5 fill:#ccffcc
```

---

## Summary

This document provides comprehensive visual representations of:

1. **System Architecture** - Overall component structure and data flow
2. **Core Algorithms** - Calculate main target, update valves, safety checks
3. **State Machines** - Zone satisfaction state transitions with hysteresis
4. **Process Management** - Job queuing, locking, and coordination
5. **Data Schema** - Redis storage structure and key patterns
6. **Automation Flows** - Event triggers and job execution
7. **Timing Sequences** - Real-time behavior and valve coordination
8. **Safety Mechanisms** - Open-first-then-close, valve locks, minimum valves
9. **Configuration** - Setup flows and user interfaces
10. **Error Handling** - Recovery and retry mechanisms

All diagrams use Mermaid syntax for easy rendering in GitHub, documentation tools, and Markdown viewers.

---

## Viewing These Diagrams

### GitHub
These diagrams render automatically when viewing this file on GitHub.

### Automated PDF Generation
When DIAGRAMS.md is updated in the `master` or `dev` branches, a PDF is automatically generated via GitHub Actions:
- **Download**: Go to [Actions → Generate Diagrams PDF](../../actions/workflows/generate-diagrams-pdf.yml) and download the latest artifact
- **Manual Trigger**: You can also manually trigger the workflow from the Actions tab
- **Auto-commit**: The generated PDF is automatically committed back to the repository

### VS Code
Install the "Markdown Preview Mermaid Support" extension.

### Command Line
Use `mermaid-cli` to generate images locally:
```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i DIAGRAMS.md -o diagrams.pdf -t dark -b transparent
```

### Online
Copy any diagram to [Mermaid Live Editor](https://mermaid.live/) for interactive viewing and editing.
