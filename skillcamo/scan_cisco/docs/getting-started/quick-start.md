# Quick Start Guide

## Installation

### Using uv (Recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/cisco-ai-defense/scan_cisco
cd scan_cisco

# Install all dependencies
uv sync --all-extras
```

### Using pip

```bash
# Install the package
pip install cisco-ai-scan_cisco[all]
```

## Basic Usage

### Environment Setup (Optional)

```bash
# For LLM analyzer and Meta-analyzer
export SKILL_SCANNER_LLM_API_KEY="your_api_key"
export SKILL_SCANNER_LLM_MODEL="anthropic/claude-sonnet-4-20250514"

# For VirusTotal binary scanning
export VIRUSTOTAL_API_KEY="your_virustotal_api_key"

# For Cisco AI Defense
export AI_DEFENSE_API_KEY="your_aidefense_api_key"
```

See [Configuration Reference](../reference/configuration-reference.md) for every available environment variable.

### Interactive Wizard

Not sure which flags to use? Run `scan_cisco` with no arguments to launch the interactive wizard:

```bash
scan_cisco
```

It walks you through selecting a scan target, analyzers, policy, and output format step by step.

### Scan a Single Skill

```bash
# From source (with uv)
uv run scan_cisco scan evals/skills/safe-skills/simple-math

# Installed package
scan_cisco scan evals/skills/safe-skills/simple-math
```

By default, `scan` runs the core analyzers: **static + bytecode + pipeline**.

### Scan Multiple Skills

```bash
# Scan all skills in a directory
scan_cisco scan-all evals/skills --format table

# Recursive scan with detailed markdown report
scan_cisco scan-all evals/skills --format markdown --detailed --output report.md
```

## Demo Results

The project includes test skills in [`evals/skills/`](https://github.com/cisco-ai-defense/scan_cisco/tree/main/evals/skills) for evaluation and testing:

### [OK] simple-math (SAFE)

```txt
$ scan_cisco scan evals/skills/safe-skills/simple-math
============================================================
Skill: simple-math
============================================================
Status: [OK] SAFE
Max Severity: SAFE
Total Findings: 0
Scan Duration: 0.12s

```

### [FAIL] multi-file-exfiltration (CRITICAL)

```txt
$ scan_cisco scan evals/skills/behavioral-analysis/multi-file-exfiltration --use-behavioral
============================================================
Skill: config-analyzer
============================================================
Status: [FAIL] ISSUES FOUND
Max Severity: CRITICAL
Total Findings: 11
Scan Duration: 0.37s

Findings Summary:
  CRITICAL: 3
      HIGH: 3
    MEDIUM: 4
       LOW: 1
      INFO: 0
```

**Detected Threats:**
- Data exfiltration (HTTP POST to external server)
- Reading sensitive files (`~/.aws/credentials`)
- Environment variable theft (`API_KEY`, `SECRET_TOKEN`)
- Command injection (`eval` on user input)
- Base64 encoding + network exfiltration pattern

## Useful Commands

```bash
# List available analyzers
scan_cisco list-analyzers

# Validate rule signatures
scan_cisco validate-rules

# Get help
scan_cisco --help
scan_cisco scan --help
```

See [CLI Command Reference](../reference/cli-command-reference.md) for detailed flags and options for every command.

## Output Formats

See [Output Formats Reference](../reference/output-formats.md) for sample outputs and a format decision guide.

### JSON (for CI/CD)
```bash
scan_cisco scan /path/to/skill --format json --output results.json
```

### SARIF (for GitHub Code Scanning)
```bash
scan_cisco scan /path/to/skill --format sarif --output results.sarif
```

### Markdown (human-readable report)
```bash
scan_cisco scan /path/to/skill --format markdown --detailed --output report.md
```

### Table (terminal-friendly)
```bash
scan_cisco scan-all evals/skills --format table
```

## Advanced Features

### Scan Policies

Use built-in presets or a custom policy to tune detection sensitivity:

```bash
# Use a stricter preset
scan_cisco scan /path/to/skill --policy strict

# Use a more permissive preset
scan_cisco scan /path/to/skill --policy permissive

# Generate a custom policy YAML to edit
scan_cisco generate-policy -o my_policy.yaml

# Interactive policy configurator (TUI)
scan_cisco configure-policy
```

See [Scan Policy Guide](../user-guide/scan-policies-overview.md) for full details.

### Enable All Analyzers
```bash
scan_cisco scan /path/to/skill \
  --use-behavioral \
  --use-llm \
  --use-trigger \
  --use-aidefense \
  --use-virustotal
```

**LLM provider note:** `--llm-provider` currently accepts `anthropic` or `openai`.
For Bedrock, Vertex, Azure, Gemini, and other LiteLLM backends, set provider-specific model strings and environment variables (see [Dependencies and LLM Providers](../reference/dependencies-and-llm-providers.md)).

### Cross-Skill Analysis
```bash
scan_cisco scan-all /path/to/skills --check-overlap
```

### Lenient Mode

Tolerate malformed skills (missing fields, non-string descriptions) instead of failing:

```bash
scan_cisco scan /path/to/skill --lenient
scan_cisco scan-all /path/to/skills --recursive --lenient
```

### Pre-commit Hook

Using the [pre-commit](https://pre-commit.com/) framework (recommended):

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/cisco-ai-defense/scan_cisco
    rev: v1.0.0  # use the latest release tag
    hooks:
      - id: scan_cisco
```

Or install the built-in hook directly:

```bash
scan_cisco-pre-commit install
```

The hook only scans skill directories with staged changes. Use `--all` to scan everything.

## Next Steps

1. **Review the documentation:**
   - [README.md](https://github.com/cisco-ai-defense/scan_cisco/blob/main/README.md) - Project overview
   - [/architecture/](../architecture/index.md) - System design
   - [/architecture/threat-taxonomy](../architecture/threat-taxonomy.md) - Threat taxonomy and mappings
   - [/user-guide/scan-policies-overview](../user-guide/scan-policies-overview.md) - Custom policies and tuning
   - [/reference/](../reference/index.md) - Configuration, CLI, API, and output format reference

2. **Try scanning your own skills:**
   ```bash
   scan_cisco scan /path/to/your/skill
   ```

3. **Integrate with CI/CD:**
   ```bash
   scan_cisco scan-all ./skills --fail-on-severity high
   # Exit code 1 if findings at or above HIGH severity
   ```
   See [GitHub Actions Integration](../github-actions.md) for a ready-made reusable workflow.

## Troubleshooting

### UV not found
Install UV:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Module not found errors
Sync dependencies:
```bash
uv sync --all-extras
```

### Permission errors
UV manages its own virtual environment - no need for manual venv activation.
