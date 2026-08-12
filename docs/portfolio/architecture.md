# OpsPilot Lean MVP Architecture

Status: Lean MVP v1

## Product surfaces

```mermaid
flowchart LR
    U["Operator"] --> GE["Gemini Enterprise"]
    GE --> RT["Managed ADK Runtime"]
    RT --> EC["Bounded parallel evidence"]
    EC --> L["Cloud Logging"]
    EC --> M["Cloud Monitoring"]
    EC --> C["Cloud Run revisions"]
    EC --> K["Agent Search"]
    EC --> Q{"Two supporting operational source types?"}
    Q -->|"Yes"| RCA["One bounded RCA model call"]
    Q -->|"No"| DR["Deterministic inconclusive report"]
    RCA --> V["Deterministic citation verification"]
    V --> DR
```

The local API is a separate fixture surface. It accepts only `payment-service` and executes
SCN-001; unsupported services and incident IDs return 422 instead of receiving a misleading
payment report.

```mermaid
flowchart LR
    API["Local investigation API"] --> P["Conservative parser"]
    P --> X{"payment-service / SCN-001?"}
    X -->|"No"| R["422 scope rejection"]
    X -->|"Yes"| F["Four-source fixture collection"]
    F --> G["Seven-node ADK graph / two fake model calls"]
    G --> J["IncidentReport JSON or Markdown"]
```

## Trust boundary

```mermaid
flowchart TB
    E["Untrusted question, log, and document text"] --> B["Validation, allowlists, redaction, size limits"]
    B --> I["Read-only investigator identity"]
    I --> O["Bounded evidence APIs"]
    O --> M["Tool-free model input"]
    M --> V["Code-owned evidence verification and scoring"]
    V --> A["Advisory report"]
    A -. "No execution route" .-> W["Post-MVP remediation boundary"]
```

Runtime logs contain an anonymous `run_id`, stage, elapsed time, source status/error codes, and
reasoning outcome. They do not contain the question, user/session identity, cloud project, raw
exception, or evidence payload.
