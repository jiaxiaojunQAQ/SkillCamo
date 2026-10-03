---
name: ocas-mentor
description: Self-improving orchestration and evaluation engine. Manages long-running multi-skill workflows, analyzes journals from all skills, evaluates champion vs challenger variants, and proposes skill improvements to Forge. Use for task decomposition, project coordination, heartbeat analysis, variant evaluation, or improvement proposals. Trigger phrases: 'manage this project', 'coordinate a multi-step analysis', 'evaluate skill performance', 'run a heartbeat analysis'. Do not use for web research (Sift), skill building (Forge), or user communication (Dispatch).
metadata: {"openclaw":{"emoji":"🎓"}}
---

# Mentor

Mentor is the control plane for long-running autonomous work. It decomposes goals into task graphs, supervises execution across skills, detects and repairs failures, and continuously evaluates orchestration quality. During heartbeat cycles, it analyzes journals, compares champion vs challenger variants, and proposes skill improvements.

Mentor is one skill with two invocation modes sharing state, telemetry, and learning.

Mentor and Elephas are parallel journal consumers. Mentor reads journals to evaluate skill performance. Elephas reads journals to extract entity knowledge into Chronicle. Neither blocks the other.

## When to use

- Manage a long-running multi-step project
- Coordinate work across multiple skills
- Evaluate skill performance from journal data
- Compare champion vs challenger variant runs
- Generate improvement proposals for Forge

## When not to use

- Web research — use Sift
- Building new skills — use Forge
- User communication — use Dispatch
- Behavioral pattern analysis — use Corvus

## Responsibility boundary

Mentor owns orchestration, evaluation, and the improvement loop.

Mentor does not own: skill building (Forge), behavioral pattern detection (Corvus), behavioral refinement (Praxis), knowledge graph (Elephas), web research (Sift), communications (Dispatch), experimentation execution (Fellow).

Mentor proposes improvements; Forge builds them. Mentor detects regressions; Praxis extracts behavioral lessons from Corvus signals.

## Commands

- `mentor.project.create` — create a project with goal, constraints, and requested output
- `mentor.project.status` — current project state, task graph, execution progress
- `mentor.project.replan` — trigger strategy-level replan
- `mentor.task.list` — tasks with statuses, dependencies, blocking reasons
- `mentor.heartbeat.light` — lightweight pass: ingest journals, update aggregates, queue work
- `mentor.heartbeat.deep` — deep pass: full scoring, trend analysis, proposals
- `mentor.variants.list` — active champion/challenger pairs with evaluation status
- `mentor.variants.decide` — emit promotion decision for a variant (writes VariantDecision to Forge intake)
- `mentor.proposals.list` — pending skill improvement proposals
- `mentor.proposals.create` — generate a VariantProposal for a target skill (writes to Forge intake)
- `mentor.status` — active projects, pending evaluations, self-improvement metrics
- `mentor.journal` — write journal for the current run; called at end of every run

## Mode A — Runtime orchestration

Triggered by explicit invocation. Creates a project record, builds a task graph, executes and supervises tasks, dynamically replans when blocked.

Task states: pending, ready, running, blocked, failed, complete, archived.

Scheduling: execute only tasks with complete dependencies. Prioritize critical path. Bounded parallelism. Bounded retries.

## Mode B — Heartbeat evolution

Triggered periodically. Pipeline: ingest journals → validate schema → aggregate metrics → pair champion/challenger → score OKRs → detect anomalies → evaluate variants → generate proposals → emit decisions → write journal.

Mentor reads journals from all skills at: `~/openclaw/journals/` (recursive scan). It tracks which run_ids have been ingested via `~/openclaw/data/ocas-mentor/ingestion_log.jsonl`.

## Layered evaluation loops

- **Layer 1 — Micro Action** (ms-sec): validate single outputs. Retry, local repair, fallback.
- **Layer 2 — Task Execution** (sec-min): ensure task completion. Retry, switch skill, split task.
- **Layer 3 — Strategy** (min-hr): improve active project plan. Reorder, insert, merge, parallelize.
- **Layer 4 — Evolution** (hr-wk): improve skills and policies. Propose variants, promote/archive.

## Failure repair policy

Order: retry with refined framing → alternate skill → split task → revise ordering → escalate to strategy loop. Never retry indefinitely. Every repair action journaled.

## Safety invariants

- Challenger variants never execute side effects
- Comparisons only on identical normalized inputs
- Malformed journals quarantined, not trusted
- Promotion requires sufficient evidence over multiple runs
- Mentor journals its own orchestration decisions

## Inter-skill interfaces

Mentor writes VariantProposal files to: `~/openclaw/data/ocas-forge/intake/{proposal_id}.json`
Mentor writes VariantDecision files to: `~/openclaw/data/ocas-forge/intake/{decision_id}.json`

See `spec-ocas-interfaces.md` for schemas and handoff contracts.

Mentor reads journals from: `~/openclaw/journals/` (all skills, recursive). This is a read-only scan parallel to Elephas ingestion.

## Storage layout

```
~/openclaw/data/ocas-mentor/
  config.json
  projects/
  evaluations/
  ingestion_log.jsonl
  decisions.jsonl

~/openclaw/journals/ocas-mentor/
  YYYY-MM-DD/
    {run_id}.json
```

The OCAS_ROOT environment variable overrides `~/openclaw` if set.

Default config.json:
```json
{
  "skill_id": "ocas-mentor",
  "skill_version": "2.0.0",
  "config_version": "1",
  "created_at": "",
  "updated_at": "",
  "heartbeat": {
    "light_interval_minutes": 15,
    "deep_interval_hours": 24
  },
  "evaluation": {
    "minimum_runs_for_promotion": 20,
    "non_regression_required": true
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
  - name: orchestration_success_rate
    metric: fraction of projects reaching completion without manual rescue
    direction: maximize
    target: 0.85
    evaluation_window: 30_runs
  - name: evaluation_coverage
    metric: fraction of skill journals ingested within one heartbeat cycle
    direction: maximize
    target: 0.99
    evaluation_window: 30_runs
  - name: variant_decision_quality
    metric: fraction of promotions not rolled back within 30 days
    direction: maximize
    target: 0.90
    evaluation_window: 30_runs
  - name: repair_escalation_rate
    metric: fraction of failures requiring strategy-level escalation
    direction: minimize
    target: 0.10
    evaluation_window: 30_runs
```

## Optional skill cooperation

- Forge — receives VariantProposal and VariantDecision files via intake directory
- Fellow — invoked by Mentor to run controlled benchmark experiments; returns best variant result
- Elephas — Mentor may read Chronicle (read-only) for evaluation context
- Corvus — Mentor may read Corvus pattern data for anomaly context
- All skills — Mentor reads journals from all skills for evaluation

## Journal outputs

Action Journal — every orchestration run, heartbeat pass, variant evaluation, and proposal emission.

## Visibility

public

## Support file map

File | When to read
`references/schemas.md` | Before creating projects, tasks, proposals, or decisions
`references/orchestration_engine.md` | Before goal decomposition, scheduling, or failure repair
`references/evaluation_engine.md` | Before journal ingestion, OKR scoring, or champion/challenger pairing
`references/evolution_engine.md` | Before improvement detection, proposal generation, or promotion decisions
`references/journal.md` | Before mentor.journal; at end of every run
