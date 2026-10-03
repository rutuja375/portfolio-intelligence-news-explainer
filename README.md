# Portfolio Intelligence / News Explainer

An evidence-first investigation system for understanding potential drivers of unusual portfolio and security-level movements.

The product combines deterministic portfolio attribution, abnormal-movement detection, market and sector context, time-aligned evidence retrieval, and grounded AI explanations. It is designed to accelerate investigation—not establish causality, recommend trades, or replace human judgment.

## Product principles

1. Evidence before explanation.
2. Deterministic where possible; AI where useful.
3. Association is not causation.
4. Abstain rather than fabricate certainty.
5. Human judgment remains final.

The canonical product definition is [Product Source of Truth v1.0](docs/product-source-of-truth-v1.0.pdf).

## MVP workflow

```text
Portfolio returns
      ↓
Holding attribution
      ↓
Abnormal-movement detection
      ↓
Market / sector context
      ↓
Time-aligned evidence retrieval and ranking
      ↓
Grounded explanation, citations and abstention
```

## Current status

Phase 1 is underway. The repository now includes the deterministic portfolio-attribution foundation, a provider-independent market-data contract, validated adjusted-price series, daily return calculations, and configurable abnormal-movement detection using absolute-return and z-score thresholds. Live provider integration remains intentionally deferred until the offline analytics are stable.

## Repository structure

```text
docs/                         Product source of truth and architecture
src/portfolio_intelligence/   Application and domain code
tests/                        Automated tests
```

## Local setup

Requirements: Python 3.11 or newer.

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
pytest
```

Copy `.env.example` to `.env` before configuring future market-data, news, or model providers. Never commit secrets.

## Responsible-use boundary

This project is for investigation and education. It does not provide personalized investment advice, predict prices, prove that news caused a market movement, or execute trades.

## Roadmap

- **MVP — Detect & Explain:** attribution, movement detection, retrieval and grounded explanation
- **V1 — Context:** market, sector and peer comparisons
- **V2 — Trust:** evaluation, confidence, abstention and failure analysis
- **V3 — Investigation:** interactive dashboard and conversational investigation
- **V4 — Intelligence:** richer evidence types and contradictory evidence
- **V5 — Enterprise readiness:** monitoring, audit trails, permissions and governance

## License

MIT
