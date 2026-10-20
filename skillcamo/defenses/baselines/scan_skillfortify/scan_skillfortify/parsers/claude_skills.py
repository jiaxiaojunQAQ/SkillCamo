"""Parser for Claude Code skills (.claude/skills/*.md).

This is a minimal copy for integration into unified_scanner.
Only includes ClaudeSkillsParser and exported utility functions.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from scan_skillfortify.parsers.base import ParsedSkill, SkillParser

# Export shared utilities for reuse by other parsers (e.g., StandaloneSkillParser)
__all__ = [
    "_extract_urls",
    "_extract_env_vars",
    "_extract_shell_commands",
    "_extract_code_blocks",
    "_FRONTMATTER_PATTERN",
]

# ---------------------------------------------------------------------------
# Regex patterns for security-relevant content extraction
# ---------------------------------------------------------------------------

# Match URLs: http:// or https:// followed by non-whitespace characters.
_URL_PATTERN = re.compile(r"https?://[^\s\"'`)\]>]+")

# Match environment variable references.
_ENV_VAR_PATTERN = re.compile(
    r"""(?:"""
    r"""\$\{?([A-Z][A-Z0-9_]{1,})\}?"""  # $VAR or ${VAR}
    r"""|os\.environ\[["']([A-Z][A-Z0-9_]{1,})["']\]"""  # os.environ["VAR"]
    r"""|os\.getenv\(["']([A-Z][A-Z0-9_]{1,})["']\)"""  # os.getenv("VAR")
    r"""|export\s+([A-Z][A-Z0-9_]{1,})"""  # export VAR
    r"""|(?:^|[\s=:`])([A-Z][A-Z_]{1,}[A-Z0-9_]*)(?=[=\s"'`])"""  # Standalone ALL_CAPS
    r""")""",
    re.MULTILINE,
)

# Sensitive env var name fragments that warrant heightened scrutiny.
_SENSITIVE_FRAGMENTS = {"SECRET", "KEY", "TOKEN", "PASSWORD", "CREDENTIAL"}

# Match fenced code blocks: ```lang\n...\n```
_CODE_BLOCK_PATTERN = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)

# Match YAML frontmatter: ---\n...\n---
_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _extract_env_vars(text: str) -> list[str]:
    """Extract unique environment variable names from text."""
    found: set[str] = set()
    for match in _ENV_VAR_PATTERN.finditer(text):
        for group in match.groups():
            if group:
                found.add(group)
    return sorted(found)


def _extract_urls(text: str) -> list[str]:
    """Extract all HTTP/HTTPS URLs from text."""
    return _URL_PATTERN.findall(text)


def _extract_code_blocks(text: str) -> list[str]:
    """Extract the content of all fenced code blocks."""
    return [match.group(2) for match in _CODE_BLOCK_PATTERN.finditer(text)]


def _extract_shell_commands(text: str) -> list[str]:
    """Extract shell commands from bash/shell code blocks."""
    shell_tags = {"bash", "sh", "shell", "zsh", ""}
    commands: list[str] = []
    for match in _CODE_BLOCK_PATTERN.finditer(text):
        lang = match.group(1).lower()
        if lang in shell_tags:
            block = match.group(2)
            for line in block.strip().splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    commands.append(stripped)
    return commands


class ClaudeSkillsParser(SkillParser):
    """Parser for Claude Code skills stored as Markdown in .claude/skills/."""

    def can_parse(self, path: Path) -> bool:
        """Check if the directory contains Claude Code skills."""
        skills_dir = path / ".claude" / "skills"
        if not skills_dir.is_dir():
            return False
        return any(skills_dir.glob("*.md"))

    def parse(self, path: Path) -> list[ParsedSkill]:
        """Parse all Claude Code skill files in ``.claude/skills/``."""
        skills_dir = path / ".claude" / "skills"
        if not skills_dir.is_dir():
            return []

        results: list[ParsedSkill] = []
        for md_file in sorted(skills_dir.glob("*.md")):
            skill = self._parse_file(md_file)
            if skill is not None:
                results.append(skill)
        return results

    def _parse_file(self, file_path: Path) -> ParsedSkill | None:
        """Parse a single Claude skill Markdown file."""
        try:
            raw_content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

        # Extract frontmatter.
        name = file_path.stem
        description = ""
        frontmatter_match = _FRONTMATTER_PATTERN.match(raw_content)
        if frontmatter_match:
            try:
                fm_data = yaml.safe_load(frontmatter_match.group(1))
                if isinstance(fm_data, dict):
                    name = fm_data.get("name", name)
                    description = fm_data.get("description", "")
            except yaml.YAMLError:
                pass

        # Extract security-relevant metadata from the full content.
        urls = _extract_urls(raw_content)
        env_vars = _extract_env_vars(raw_content)
        code_blocks = _extract_code_blocks(raw_content)
        shell_commands = _extract_shell_commands(raw_content)

        return ParsedSkill(
            name=name,
            version="unknown",
            source_path=file_path,
            format="claude",
            description=description,
            instructions=raw_content,
            urls=urls,
            env_vars_referenced=env_vars,
            code_blocks=code_blocks,
            shell_commands=shell_commands,
            raw_content=raw_content,
        )
