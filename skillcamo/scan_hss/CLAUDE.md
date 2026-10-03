# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Skill Security Scanner** for Claude Code plugins/skills. It provides two complementary scanning approaches:

1. **Static Analysis** (`static_analysis_scan_skill.py`) - Fast pattern-matching based security scanning using regex rules
2. **LLM-Based Analysis** (`skillscan.py`) - Intelligent security classification using Anthropic/OpenAI models

The LLM scanner uses a comprehensive 8-dimensional security classification framework covering modern AI security threats: Data Exfiltration, Data Destruction, Denial of Service, Malware/Ransomware, Phishing, Backdoors, Bias/Manipulation, and Poisoning.

## Running Scans

### Static Analysis Scan

```bash
# Scan current directory
python static_analysis_scan_skill.py scan .

# Recursive scan with JSON output
python static_analysis_scan_skill.py scan /path/to/skills --recursive --json report.json

# CI mode: fail on WARNING or above
python static_analysis_scan_skill.py scan . --recursive --fail-on WARNING

# Custom rules file
python static_analysis_scan_skill.py scan . --rules config/rules.yaml
```

### LLM-Based Scan

```bash
# Using Anthropic Claude
export ANTHROPIC_API_KEY="your-key"
python skillscan.py --provider anthropic --model claude-3-5-sonnet-latest --skill-dir ./my_skill --out result.json

# Using OpenAI
export OPENAI_API_KEY="your-key"
python skillscan.py --provider openai --model gpt-4.1 --skill-dir ./my_skill --out result.json
```

## Architecture

### Static Analysis Scanner

The static scanner uses a rule-based approach with YAML-configurable patterns:

- **Rule Loading**: Loads from `config/rules.yaml` or uses built-in `FALLBACK_RULES`
- **Rule Categories**: network, file, command, injection, dependency, and info rules
- **Whitelist Support**: Optional `config/whitelist.yaml` to suppress specific rule IDs
- **Output Formats**: console, JSON, or HTML report

Key data structures:
- `Rule`: Defines a security rule with ID, severity, patterns, and optional allowed domains
- `Finding`: Represents a detected security issue with file location and context

### LLM Scanner

The LLM scanner uses an 8-dimensional security classification:

1. **Data Exfiltration (DE)**: Credential theft (DE1), secret scraping (DE2), data exfiltration (DE3), context harvesting (DE4)
2. **Data Destruction (DD)**: File deletion (DD1), data corruption (DD2), database damage (DD3), configuration sabotage (DD4)
3. **Denial of Service (DOS)**: Resource exhaustion (DOS1), network flooding (DOS2), process bombing (DOS3), service disruption (DOS4)
4. **Malware/Ransomware (MW)**: Ransomware behavior (MW1), dropper/loader (MW2), persistence mechanism (MW3), evasion techniques (MW4)
5. **Phishing (PH)**: Credential harvesting (PH1), social engineering (PH2), fake authentication (PH3), deceptive links (PH4)
6. **Backdoors (BD)**: Remote shell (BD1), reverse connection (BD2), hidden trigger (BD3), covert channel (BD4)
7. **Bias/Manipulation (BM)**: Output manipulation (BM1), false information injection (BM2), decision steering (BM3), narrative influence (BM4)
8. **Poisoning (PO)**: Training data poisoning (PO1), model tampering (PO2), backdoor injection (PO3), adversarial sample (PO4)

#### Severity-Based Thresholds

The scanner uses different confidence thresholds based on pattern severity:
- **Critical**: 0.4 (high sensitivity, catches potential threats early)
- **High**: 0.6 (standard threshold)
- **Medium**: 0.7 (requires higher confidence)
- **Low**: 0.8 (requires very high confidence)

Critical findings are highlighted in the output summary.

It scans skill directories by:
1. Parsing YAML frontmatter from SKILL.md/README.md
2. Collecting bundled script files (`.py`, `.sh`, `.js`, etc.)
3. Building a combined prompt with metadata, instructions, and code excerpts
4. Returning JSON-structured classification with confidence scores and evidence
5. Flagging findings using severity-based thresholds

## Configuration

### Rules File (config/rules.yaml)

```yaml
network_rules:
  - id: NET001
    name: External network request
    severity: CRITICAL
    patterns:
      - 'curl\s+.*https?://'
      - 'wget\s+.*https?://'
    description: Potential external data exfiltration
    allowed_domains:
      - api.anthropic.com
      - github.com
```

### Whitelist File (config/whitelist.yaml)

```yaml
rules:
  - NET001  # Suppress this rule ID
```

## Dependencies

- **Optional**: `pyyaml` - Required for custom rules.yaml loading
- **Anthropic**: `anthropic` package for Claude API calls
- **OpenAI**: `openai` package for OpenAI API calls

The static scanner works without any external dependencies (uses built-in fallback rules).

## Directory Structure

```
├── static_analysis_scan_skill.py   # Regex-based scanner
├── skillscan/                       # LLM-based classifier
│   └── skillscan.py                # Main scanner module
├── test.py                          # Duplicate of static scanner
├── config/                          # Configuration files (rules, whitelist)
├── scanners/                        # Scanner modules (empty, for future modularization)
├── reporters/                       # Output formatters (empty, for future use)
├── utils/                           # Shared utilities (empty, for future use)
└── test/resources/                  # Test fixtures and sample skills
```

## Default Behavior

- The static scanner automatically includes `.claude/skills` directory if it exists
- HTML reports are timestamped: `skill_scan_report_YYYYMMDD_HHMMSS.html`
- Risk score calculation: CRITICAL × 1.8 + WARNING × 0.6 + INFO × 0.1 (max 10)
- Severity filtering with `--severity` flag controls console output verbosity
- Exit code 2 is returned when `--fail-on` threshold is exceeded
