# PROVENANCE — scan_skill_auditor / scan_skill_vetter / scan_skill_slowmist

These three directories are **Claude Code skills**, not Python packages:
each is a `SKILL.md` (plus supporting files) executed by the Claude Code
CLI during evaluation. They are the paper's "skill-based" baseline scanners.

- **scan_skill_auditor** — ClawGuard Auditor (CG-A), enterprise-grade
  three-phase security review. Baseline "Auditor" in the paper.
- **scan_skill_vetter** — Skill Vetter (ClawHub). Baseline "Vetter".
- **scan_skill_slowmist** — SlowMist Agent Security review framework
  (see its own LICENSE). Baseline "SlowMist".

## Execution

All three run through the locally installed `claude` CLI
(Claude Code v2.1.108 in the paper, Haiku 4.5 backbone), orchestrated by
`skillcamo/unified_scanner/adapters/scan_skill_{auditor,vetter,slowmist}.py`.

## Local modifications (evaluation harness only)

- Directory-name leakage removal and isolated working directories during
  CLI invocation (evaluation hygiene).
