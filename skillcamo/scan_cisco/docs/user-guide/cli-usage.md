# CLI Usage

This guide explains practical CLI usage patterns for local scans, CI gates, and policy-driven operation.

> [!TIP]
> **Most Common Command**
> ```bash
> scan_cisco scan ./my-skill
> ```
> Runs the default static analyzers and prints a findings summary. Add `--use-behavioral`, `--use-llm`, or `--policy strict` to deepen the analysis.

## Core Commands

- `scan_cisco scan <skill_directory>`
- `scan_cisco scan-all <skills_directory>`
- `scan_cisco list-analyzers`
- `scan_cisco validate-rules`
- `scan_cisco generate-policy`
- `scan_cisco configure-policy`
- `scan_cisco interactive`

## Common Workflows

### Local smoke scan

```bash
scan_cisco scan ./my-skill
```

### Recursive CI scan with failure gate

```bash
scan_cisco scan-all ./skills --recursive --fail-on-findings
```

### Deep analysis profile

```bash
scan_cisco scan ./my-skill \
  --use-behavioral \
  --use-llm \
  --enable-meta
```

### Security reporting (SARIF)

```bash
scan_cisco scan-all ./skills \
  --recursive \
  --format sarif \
  --output results.sarif \
  --fail-on-findings
```

### Policy-based enforcement

```bash
scan_cisco scan ./my-skill --policy strict
scan_cisco scan ./my-skill --policy ./my-org-policy.yaml
```

## Choosing Analyzers

Not sure which flags to use? Pick the row that matches your situation:

| Scenario | Suggested flags |
|---|---|
| Fast local iteration | default analyzers |
| Suspicious third-party skill | `--use-behavioral --policy strict` |
| High-confidence triage | `--use-llm --enable-meta` |
| Binary-heavy package | `--use-virustotal` |

## Exit Code Behavior

- `0`: successful command (or no fail condition triggered)
- `1`: runtime error, or findings detected when `--fail-on-findings` is enabled

When `--fail-on-findings` is active:

- **`scan`**: exits `1` if `result.is_safe` is false (any CRITICAL or HIGH finding)
- **`scan-all`**: exits `1` if `critical_count > 0` or `high_count > 0` across all scanned skills

## Detailed Reference

For exhaustive argument tables and full `--help` snapshots, see:

- [CLI Command Reference](../reference/cli-command-reference.md)

## See Also

- [Configuration Reference](../reference/configuration-reference.md) — environment variables for LLM providers, analyzers, and feature toggles
- [Python SDK](python-sdk.md) — embed scanning directly in Python applications
- [API Server](api-server.md) — REST API for upload-driven and CI/CD workflows
