# SkillFortify Scanner

Static security analyzer for AI agent skills, integrated into the unified scanner framework.

## Features

- **Multi-format support**: Claude Code skills (`.claude/skills/*.md`) and standalone `SKILL.md` files
- **Three-phase analysis**:
  1. Capability inference from skill content
  2. Dangerous pattern detection (shell commands, code blocks, URLs, env vars)
  3. Capability violation checking against declared permissions
- **Pattern-based detection**: Identifies risky constructs like `curl | sh`, `rm -rf`, `eval()`, etc.

## Installation

```bash
cd scan_skillfortify
pip install -e .
```

## Usage

### As a standalone library

```python
from scan_skillfortify.parsers.registry import default_registry
from scan_skillfortify.core.analyzer.engine import StaticAnalyzer

# Discover and parse skills
registry = default_registry()
skills = registry.discover(Path("/path/to/skill"))

# Analyze for security issues
analyzer = StaticAnalyzer()
for skill in skills:
    result = analyzer.analyze(skill)
    if not result.is_safe:
        print(f"Found {len(result.findings)} issues in {skill.name}")
```

### Via the unified scanner

```python
from unified_scanner import UnifiedSkillScanner

scanner = UnifiedSkillScanner(enabled_scanners=["scan_skillfortify"])
result = scanner.scan("/path/to/skill")
```

## Detection Patterns

| Pattern | Severity | Description |
|---------|----------|-------------|
| `curl \| sh` | CRITICAL | Remote code execution via pipe to shell |
| `rm -rf` | CRITICAL | Destructive file operations |
| `base64 -d \| sh` | CRITICAL | Obfuscated code execution |
| `eval()` | HIGH | Dynamic code evaluation |
| External URLs | HIGH | Potential data exfiltration |
| Sensitive env vars | HIGH | Access to secrets/credentials |

## Architecture

```
scan_skillfortify/
├── scan_skillfortify/
│   ├── parsers/          # Skill format parsers
│   │   ├── base.py       # Abstract base and ParsedSkill model
│   │   ├── claude_skills.py
│   │   ├── standalone_skill.py
│   │   └── registry.py   # Auto-discovery
│   └── core/
│       ├── analyzer/
│       │   └── engine.py # Static analysis engine
│       └── capabilities/
│           └── models.py # Capability lattice (AccessLevel, Capability, CapabilitySet)
```

## License

Apache-2.0
