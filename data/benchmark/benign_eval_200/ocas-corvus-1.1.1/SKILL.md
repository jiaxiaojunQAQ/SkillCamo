---
name: ocas-corvus
description: Exploratory pattern analysis engine for the system knowledge graph and skill journals. Detects routines, emerging interests, anomalies, stalled threads, and cross-domain opportunities from accumulated activity signals. Use when analyzing patterns, detecting routines, running exploration cycles, or checking for anomalies. Do not use for web research (Sift), person investigations (Scout), or system architecture changes (Mentor).
metadata: {"openclaw":{"emoji":"🐦‍⬛"}}
---

# Corvus

Corvus is the system's exploratory intelligence engine. It analyzes the knowledge graph and activity signals to discover behavioral patterns, test hypotheses, and produce structured insight proposals supported by evidence.

## When to use

- Detect recurring behavioral patterns and routines
- Identify emerging interests from activity clusters
- Discover anomalies or meaningful deviations from established patterns
- Find cross-domain opportunities connecting previously unrelated entities
- Monitor stalled threads and incomplete activity clusters
- Run periodic analysis during idle cycles

## When not to use

- Web research or fact-checking — use Sift
- OSINT investigations on people — use Scout
- System architecture changes or skill evaluation — use Mentor
- Storing user preferences — use Taste
- Direct communication — use Dispatch

## Responsibility boundary

Corvus owns exploratory pattern analysis across the knowledge graph and skill journals.

Corvus does not own: skill evaluation (Mentor), behavioral refinement (Praxis), web research (Sift), knowledge graph writes (Elephas), preference persistence (Taste), browsing interpretation (Thread).

Corvus emits BehavioralSignal files to Praxis and InsightProposal files to Vesper. Corvus receives research thread signals from Thread.

## Commands

- `corvus.analyze.light` — run a light analysis cycle: routine detection, thread monitoring, interest clustering
- `corvus.analyze.deep` — run a deep exploration cycle: cross-domain traversal, hypothesis testing, model refinement
- `corvus.proposals.list` — list current insight proposals with confidence scores
- `corvus.proposals.detail` — show full evidence and reasoning for a specific proposal
- `corvus.hypotheses.list` — list active hypotheses under investigation
- `corvus.status` — return current analysis state: patterns detected, proposals pending, graph coverage
- `corvus.journal` — write journal for the current run; called at end of every run

## Operation modes

### Light Analysis Cycle
Runs frequently during idle periods. Focuses on routine detection, thread monitoring, and interest clustering. Low cost, fast execution.

### Deep Exploration Cycle
Runs less frequently during extended idle periods. Performs cross-domain graph traversal, hypothesis testing, and model refinement. Higher cost, produces richer insight proposals.

## Curiosity engine

Corvus prioritizes graph regions for exploration using three internal drives:

- **Novelty** — prefer regions that recently appeared or changed
- **Uncertainty** — prefer entities with many signals but incomplete understanding
- **Prediction error** — prefer patterns where predicted outcomes diverge from observed events

Each drive generates hypotheses. Hypotheses are tested through graph queries and evidence gathering. Validated hypotheses become insight proposals.

Read `references/curiosity_engine.md` for drive mechanics and priority scoring.

## Pattern validation rules

Patterns must pass all validation checks before becoming proposals:

- Minimum signal count met
- Temporal consistency confirmed
- Cross-domain corroboration present
- Falsification attempt completed without contradiction

Patterns failing validation remain internal hypotheses for future evaluation.

Read `references/pattern_engines.md` for per-engine detection criteria and validation rules.

## Insight proposal format

Each proposal includes: proposal_id, proposal_type, description, confidence_score, supporting_entities, supporting_relationships, predicted_outcome, suggested_follow_up.

Proposal types: routine_prediction, thread_continuation, opportunity_discovery, anomaly_alert, behavioral_signal.

Read `references/schemas.md` for exact proposal schema.

## Inter-skill interfaces

Corvus writes BehavioralSignal files to: `~/openclaw/data/ocas-praxis/intake/{signal_id}.json`
Written when a validated pattern has proposal_type: behavioral_signal.

Corvus writes InsightProposal files to: `~/openclaw/data/ocas-vesper/intake/{proposal_id}.json`
Written when a validated proposal reaches sufficient confidence (excludes behavioral_signal type).

Corvus receives research thread signals from Thread at: `~/openclaw/data/ocas-corvus/intake/{thread_id}.json`
Read during analysis cycles as additional signal context.

See `spec-ocas-interfaces.md` for schemas and handoff contracts.

## Storage layout

```
~/openclaw/data/ocas-corvus/
  config.json
  hypotheses.jsonl
  patterns.jsonl
  proposals.jsonl
  decisions.jsonl
  intake/
    {thread_id}.json
    processed/
  reports/

~/openclaw/journals/ocas-corvus/
  YYYY-MM-DD/
    {run_id}.json
```

The OCAS_ROOT environment variable overrides `~/openclaw` if set.

Default config.json:
```json
{
  "skill_id": "ocas-corvus",
  "skill_version": "2.0.0",
  "config_version": "1",
  "created_at": "",
  "updated_at": "",
  "curiosity": {
    "novelty_weight": 0.4,
    "uncertainty_weight": 0.3,
    "prediction_error_weight": 0.3
  },
  "validation": {
    "min_signal_count": 3,
    "min_confidence_for_proposal": 0.5
  },
  "retention": {
    "days": 0,
    "max_records": 10000
  }
}
```

## OKRs

Universal OKRs from spec-ocas-journal.md apply to all runs.

```yaml
skill_okrs:
  - name: proposal_precision
    metric: fraction of proposals confirmed as useful within 30 days
    direction: maximize
    target: 0.70
    evaluation_window: 30_runs
  - name: pattern_validation_rate
    metric: fraction of detected patterns passing all validation checks
    direction: maximize
    target: 0.80
    evaluation_window: 30_runs
  - name: graph_coverage
    metric: fraction of active graph regions analyzed within one deep cycle
    direction: maximize
    target: 0.90
    evaluation_window: 30_runs
  - name: false_anomaly_rate
    metric: fraction of anomaly alerts dismissed as noise
    direction: minimize
    target: 0.15
    evaluation_window: 30_runs
```

## Optional skill cooperation

- Elephas — read Chronicle (read-only) for graph context during pattern analysis
- Thread — receives research thread signals via intake directory
- Vesper — receives InsightProposal files via Vesper intake directory
- Praxis — receives BehavioralSignal files via Praxis intake directory
- Mentor — Mentor may read Corvus data for evaluation context

## Journal outputs

Observation Journal — all analysis cycles (light and deep).

## Visibility

public

## Support file map

File | When to read
`references/schemas.md` | Before creating hypotheses, patterns, or proposals
`references/curiosity_engine.md` | Before drive scoring or hypothesis generation
`references/pattern_engines.md` | Before pattern detection or validation
`references/journal.md` | Before corvus.journal; at end of every run
