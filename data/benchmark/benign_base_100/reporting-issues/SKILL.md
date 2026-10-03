---
name: reporting-issues
description: Use this skill when you need to report on a troubleshooting session — turn raw debugging notes into a clear, reproducible troubleshooting report.
---

# Instructions

Turn a troubleshooting/debugging session into a structured, reproducible report. Prefer the
`@troubleshoot-report-generator` agent when it is available; otherwise produce the report
yourself by following the workflow below.

## Workflow

1. **Gather context** — collect what was observed: the symptom, when it started, the affected
   component/environment, and any error output or logs. Ask only for genuinely missing facts.
2. **Establish reproduction** — write the minimal, ordered steps that reproduce the issue, plus
   the expected vs. actual result. If it is intermittent, state the observed frequency.
3. **Diagnose** — record what was checked, what was ruled out, and the evidence that points to the
   root cause. Separate confirmed facts from hypotheses.
4. **Resolve** — describe the fix or workaround applied, and how it was verified to work.
5. **Follow up** — list residual risks, monitoring to add, and any preventive action.

## Report Template

```markdown
# Troubleshooting Report: <short title>

- **Severity:** Critical | High | Medium | Low
- **Status:** Resolved | Mitigated | Open
- **Component / Environment:** <service, version, OS, region>
- **Reported / Resolved:** <timestamps>

## 1. Summary
<one paragraph: what broke, impact, current state>

## 2. Reproduction
Steps:
1. ...
- **Expected:** ...
- **Actual:** ...
- **Frequency:** always | intermittent (~X%)

## 3. Diagnosis
- Checked: ...
- Ruled out: ...
- **Root cause:** ...

## 4. Resolution
- Fix / workaround: ...
- Verification: ...

## 5. Follow-up
- Residual risk: ...
- Monitoring / prevention: ...
```

## Quality bar

- Every claim is backed by an observation (log line, command output, metric) — no speculation in
  the root-cause section.
- The reproduction section is sufficient for someone else to trigger the issue unaided.
- The report is skimmable: a reader gets impact and root cause from the Summary alone.
