# Architecture

## Goal

Convert an unusual portfolio movement into a structured, evidence-backed investigation while keeping financial calculations deterministic and AI output bounded by retrieved evidence.

## System flow

```text
Portfolio + prices
       │
       ▼
Portfolio analytics ─── returns, weights, contribution
       │
       ▼
Movement detector ───── thresholds, volatility, abnormal return
       │
       ▼
Context engine ──────── market, sector, peers
       │
       ▼
Investigation event ─── security, timestamps, movement, context
       │
       ▼
Evidence pipeline ───── retrieve, normalize, validate time, rank
       │
       ▼
Explanation service ─── cited synthesis, confidence, abstention
       │
       ▼
Analyst experience ──── evidence, alternatives, follow-up questions
```

## Component boundaries

| Component | Responsibility | Technique |
|---|---|---|
| Portfolio analytics | Returns and holding contribution | Deterministic code |
| Movement detector | Identify unusual security behavior | Statistics; optional ML later |
| Context engine | Compare market, sector and peers | Deterministic calculations |
| Event builder | Produce an auditable investigation record | Typed domain model |
| Evidence pipeline | Retrieve, timestamp, deduplicate and rank sources | Search, rules and NLP |
| Explanation service | Synthesize only selected evidence | LLM with citation constraints |
| Evaluation | Measure retrieval and explanation quality | Offline tests and human review |

## Initial domain objects

- `Holding`: ticker and portfolio weight
- `HoldingPerformance`: holding, period return and contribution
- `PortfolioSnapshot`: validated collection of holdings
- `PortfolioAttribution`: portfolio return and ranked contributors
- `InvestigationEvent`: planned next milestone; movement plus contextual timestamps

## Trust controls

- Calculations are not delegated to an LLM.
- Evidence is selected and time-validated before synthesis.
- Material claims must link to evidence.
- Confidence is explicit and separate from sentiment.
- Insufficient or conflicting evidence triggers abstention.
- User-visible timestamps distinguish pre-, during- and post-movement sources.

## Data policy for development

Raw provider data and secrets remain local and are excluded from Git. Small synthetic fixtures may be committed for deterministic tests. Provider licenses and retention terms must be reviewed before any production use.

## Near-term implementation sequence

1. Portfolio model and attribution.
2. Market-data provider interface and local fixture provider.
3. Daily movement detector using configurable return and z-score thresholds.
4. Market and sector comparison.
5. Typed investigation-event creation.
6. News-provider interface, temporal validation and evidence ranking.
7. Grounded explanation interface with abstention.
8. Evaluation harness and lightweight analyst UI.
