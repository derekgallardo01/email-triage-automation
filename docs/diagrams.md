# Diagrams

GitHub renders Mermaid natively. These render on the README and here.

## End-to-end triage pipeline

```mermaid
flowchart LR
    I[Inbound EML / mbox / Graph / Gmail] --> P["parser.parse_eml_bytes()"]
    P --> E[Email object]
    E --> C["Classifier.classify(email)"]
    C --> ID{Internal domain?}
    ID -- yes --> INT["label='internal'<br/>conf=1.0"]
    ID -- no --> KW[Keyword score per class]
    KW --> CR[ClassificationResult]
    INT --> CR
    CR --> R["route(result, catalog)"]
    R --> RD[RoutingDecision]
    RD --> Q{drafts_reply?}
    Q -- no --> OUT1[class.queue]
    Q -- yes --> D["Drafter.draft(email, class_name)"]
    D --> DB{Backend?}
    DB -- substitution --> SUB[Template + str.format]
    DB -. claude .-> LLM[Claude messages.create]
    SUB --> DRAFT[DraftedReply]
    LLM --> DRAFT
    DRAFT --> OUT2[Reply queued]
```

## Routing decisions (3 review paths + 1 happy path)

```mermaid
flowchart TB
    R[ClassificationResult] --> A{label == 'unknown'?}
    A -- yes --> H1["human_review<br/>reason: 'no matching class'"]
    A -- no --> B{confidence >= threshold?}
    B -- no --> H2["human_review<br/>reason: 'confidence below threshold (0.XX)'"]
    B -- yes --> C{class in catalog?}
    C -- no --> H3["human_review<br/>reason: 'class X not in catalog'"]
    C -- yes --> Q["class.queue<br/>(SLA from class.sla_hours)"]
    Q --> D{class.drafts_reply?}
    D -- yes --> DR[Drafter runs]
    D -- no --> X[No draft - queue handles it]
```

## Confidence scoring

```mermaid
flowchart LR
    T[Email subject + body] --> S[Per-class keyword scoring]
    S --> W["weight = 1.0 + 0.1 * len(kw)<br/>score += (subject_cnt * 2 + body_cnt) * weight"]
    W --> R[Top-k candidates]
    R --> M["margin = top / (top + runner_up)"]
    R --> ST["strength = min(1.0, top / 10.0)"]
    M --> C["confidence = margin * strength"]
    ST --> C
```

Subject keywords weigh 2x body keywords because in real inboxes,
subjects are denser signal.

## Drafter backends

```mermaid
flowchart TB
    subgraph Sub["substitution (default)"]
        direction TB
        S1[Template file<br/>prompts/CLASS.txt]
        S2["Extract sender first name,<br/>subject, body excerpt"]
        S3["str.format(...)"]
        S1 --> S3
        S2 --> S3
        S3 --> D1[DraftedReply<br/>backend=substitution<br/>confidence=0.7]
    end

    subgraph Claude["claude (when wired)"]
        direction TB
        L1[Template file<br/>prompts/CLASS.txt]
        L2[Email]
        L3["client.messages.create(<br/>system=...,<br/>messages=[template + email])"]
        L1 --> L3
        L2 --> L3
        L3 --> D2[DraftedReply<br/>backend=claude<br/>confidence=0.85]
    end

    Sub -. "same DraftedReply shape" .- Claude
```

## Eval suite (two independent gates)

```mermaid
sequenceDiagram
    participant CI
    participant E as evals/run.py
    participant CLS as Classifier
    participant DR as Drafter
    participant FX as Fixtures

    CI->>E: python evals/run.py
    E->>FX: load 7 EML fixtures + gold labels
    loop classification cases
        E->>CLS: classify(email)
        CLS-->>E: label + confidence
        E->>E: per-class TP/FP/FN tally
    end
    E->>E: compute P/R/F1 + accuracy
    E->>FX: load 3 draft cases (fixture + class + rubric)
    loop draft cases
        E->>DR: draft(email, class)
        DR-->>E: DraftedReply
        E->>E: verify rubric contains_all
    end
    E-->>CI: exit 0 if both gates pass
```

## Repo shape

```mermaid
flowchart TB
    R[email-triage-automation]
    R --> SRC[src/email_triage/]
    SRC --> S1[parser.py — EML/mbox stdlib parser]
    SRC --> S2[catalog.py — declarative classes]
    SRC --> S3[classifier.py — keyword scoring + router]
    SRC --> S4[drafter.py — templates + LLM seam]
    SRC --> S5[cli.py — triage/demo/list-classes]
    R --> PR[prompts/]
    PR --> P1[sales_lead.txt / support_request.txt / feature_request.txt]
    R --> FX[fixtures/]
    FX --> F1[7 EML files — 1 per class + 1 ambiguous]
    R --> T[tests/]
    T --> T1[test_parser.py]
    T --> T2[test_classifier.py]
    T --> T3[test_drafter.py]
    R --> EV[evals/]
    EV --> EG[classification.json + drafts.json]
    EV --> ER[run.py — per-class P/R/F1]
    R --> DOCS[docs/]
    R --> CI[.github/workflows/ci.yml]
    R --> DK[Dockerfile]
```
