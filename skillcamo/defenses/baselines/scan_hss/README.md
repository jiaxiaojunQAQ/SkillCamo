# Skill Security Scanner

A comprehensive security scanner for Claude Code plugins/skills. Provides three complementary scanning approaches:

- **Static Analysis** (`static_analysis_scan_skill.py`) - Fast pattern-matching based security scanning using regex rules
- **LLM-Guard Analysis** (`llm_guard_scanner.py`) - Semantic threat detection using official llm-guard library
- **LLM-Based Classification** (`skillscan.py`) - Intelligent security classification using Anthropic/OpenAI models

## Three-Phase Security Framework

The scanner implements a three-phase security detection pipeline:

### Phase 1: Static Analysis
Rule-based pattern matching for known threat signatures:
- Network operations, file operations, command execution
- Injection attacks, dependency risks, suspicious instructions

### Phase 2: LLM-Guard Analysis
Semantic threat detection using the official [llm-guard](https://github.com/protectai/llm-guard) library with ML-based scanners:

| Scanner | Description | Threshold |
|---------|-------------|-----------|
| PromptInjection | Detects prompt injection attacks | 0.5 |
| Secrets | Detects hardcoded API keys, tokens | 0.5 |
| Gibberish | Detects obfuscated/gibberish content | 0.6 |
| Sentiment | Detects manipulative language (negative sentiment) | -0.05 |
| Toxicity | Detects toxic/harmful content | 0.5 |
| BanSubstrings | Blocks specific dangerous patterns | 0.5 |
| BanTopics | Blocks security-sensitive topics | 0.5 |
| Code | Detects code injection patterns | 0.5 |
| Regex | Pattern matching for secrets | 0.5 |

> **Note**: First run downloads ML models from Hugging Face (~500MB-2GB).

### Phase 3: LLM Classification

The LLM scanner evaluates AI agent skills across **8 security dimensions** with **32 pattern types**:

### 1. Data Exfiltration (DE) - Credential, Secret, or Data Theft
| Pattern | Severity | Description |
|---------|----------|-------------|
| DE1 | Critical | Credential Theft - Targeted theft of API keys, passwords, tokens |
| DE2 | High | Secret Scraping - Systematic collection of environment variables |
| DE3 | High | Data Exfiltration - Transferring sensitive data to external servers |
| DE4 | Medium | Context Harvesting - Collecting and transmitting conversation context |

### 2. Data Destruction (DD) - Data Deletion or Corruption
| Pattern | Severity | Description |
|---------|----------|-------------|
| DD1 | High | File Deletion - Deleting user or system files |
| DD2 | High | Data Corruption - Modifying or corrupting data integrity |
| DD3 | Critical | Database Damage - Dropping tables, deleting database records |
| DD4 | Medium | Configuration Sabotage - Modifying configs to cause system failure |

### 3. Denial of Service (DOS) - Disrupting Availability
| Pattern | Severity | Description |
|---------|----------|-------------|
| DOS1 | High | Resource Exhaustion - Consuming CPU/memory/disk resources |
| DOS2 | Medium | Network Flooding - Initiating massive network requests |
| DOS3 | High | Process Bombing - Creating large numbers of processes/threads |
| DOS4 | Medium | Service Disruption - Interrupting critical service operations |

### 4. Malware/Ransomware (MW) - Malicious Software Deployment
| Pattern | Severity | Description |
|---------|----------|-------------|
| MW1 | Critical | Ransomware Behavior - Encrypting user data and demanding ransom |
| MW2 | High | Dropper/Loader - Downloading and executing additional malicious code |
| MW3 | High | Persistence Mechanism - Establishing persistent presence on system |
| MW4 | Medium | Evasion Techniques - Techniques to avoid detection |

### 5. Phishing (PH) - Deceptive Credential Collection
| Pattern | Severity | Description |
|---------|----------|-------------|
| PH1 | High | Credential Harvesting - Fake interfaces to collect credentials |
| PH2 | Medium | Social Engineering - Manipulating users to reveal sensitive information |
| PH3 | High | Fake Authentication - Mimicking legitimate authentication flows |
| PH4 | Medium | Deceptive Links - Misleading links or URLs |

### 6. Backdoors (BD) - Persistent Unauthorized Access
| Pattern | Severity | Description |
|---------|----------|-------------|
| BD1 | Critical | Remote Shell - Establishing remote command execution channel |
| BD2 | Critical | Reverse Connection - Reverse connection to attacker server |
| BD3 | High | Hidden Trigger - Concealed activation mechanism |
| BD4 | Medium | Covert Channel - Covert data transmission channel |

### 7. Bias/Manipulation (BM) - Output or Bias Manipulation
| Pattern | Severity | Description |
|---------|----------|-------------|
| BM1 | High | Output Manipulation - Tampering with AI output results |
| BM2 | High | False Information Injection - Injecting false information |
| BM3 | Medium | Decision Steering - Manipulating user decision-making process |
| BM4 | Low | Narrative Influence - Influencing user perceptions or opinions |

### 8. Poisoning (PO) - Training Data or Model Poisoning
| Pattern | Severity | Description |
|---------|----------|-------------|
| PO1 | High | Training Data Poisoning - Contaminating training datasets |
| PO2 | Critical | Model Tampering - Modifying model weights or parameters |
| PO3 | High | Backdoor Injection - Injecting model backdoors |
| PO4 | Medium | Adversarial Sample - Generating adversarial samples |

## Severity-Based Thresholds

Different confidence thresholds based on pattern severity:

| Severity | Threshold | Description |
|----------|-----------|-------------|
| Critical | 0.4 | High sensitivity, catches potential threats early |
| High | 0.6 | Standard threshold |
| Medium | 0.7 | Requires higher confidence |
| Low | 0.8 | Requires very high confidence |

## Usage

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
python skillscan.py \
  --provider anthropic \
  --model claude-3-5-sonnet-latest \
  --skill-dir ./my_skill \
  --out result.json

# Using OpenAI
export OPENAI_API_KEY="your-key"
python skillscan.py \
  --provider openai \
  --model gpt-4.1 \
  --skill-dir ./my_skill \
  --out result.json

# Scan raw text
python skillscan.py \
  --provider anthropic \
  --model claude-3-5-sonnet-latest \
  --skill-text "skill content here"
```

## Output Format

The LLM scanner outputs JSON with the following structure:

```json
{
  "provider": "anthropic",
  "model": "claude-3-5-sonnet-latest",
  "classification": {
    "data_exfiltration": {
      "confidence": 0.85,
      "patterns": ["DE1", "DE2"],
      "evidence": "Found API key collection code..."
    },
    "data_destruction": {
      "confidence": 0.0,
      "patterns": [],
      "evidence": ""
    },
    ...
  },
  "summary": {
    "critical_findings": [
      {
        "dimension": "data_exfiltration",
        "pattern": "DE1",
        "confidence": 0.85
      }
    ],
    "flagged_dimensions": ["data_exfiltration"],
    "has_critical": true
  }
}
```

## Testing

Run the test suite:

```bash
python test_llm_scanner.py
```

## Dependencies

```bash
# Core dependencies
pip install llm-guard>=0.4.0

# For custom rules
pip install pyyaml

# For Anthropic Claude
pip install anthropic

# For OpenAI
pip install openai
```

**Note**: The `llm-guard` library downloads ML models from Hugging Face on first run (~500MB-2GB). Ensure network connectivity.

The static scanner works without any external dependencies (uses built-in fallback rules).
