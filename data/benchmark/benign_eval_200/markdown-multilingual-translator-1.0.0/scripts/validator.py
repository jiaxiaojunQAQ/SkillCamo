#!/usr/bin/env python3
"""
Validation Module
Validates translation output for completeness and correctness.
"""

import re
import json
from typing import Dict, List, Tuple, Any


class TranslationValidator:
    """Validates translated Markdown for quality and integrity."""

    def __init__(self):
        self.issues: List[str] = []
        self.warnings: List[str] = []

    def validate_output(
        self,
        original: str,
        translated: str,
        source_language: str = 'en',
        target_language: str = 'unknown'
    ) -> Dict[str, Any]:
        """
        Validate translated output.

        Args:
            original: Original Markdown content
            translated: Translated Markdown content
            source_language: Source language code
            target_language: Target language code

        Returns:
            Validation report
        """
        self.issues = []
        self.warnings = []

        # Check structure preservation
        self._check_structure(original, translated)

        # Check code block preservation
        self._check_code_blocks(original, translated)

        # Check links preservation
        self._check_links(original, translated)

        # Check for untranslated content
        self._check_untranslated_content(original, translated, source_language, target_language)

        # Check markdown validity
        self._check_markdown_validity(translated)

        # Check encoding
        self._check_encoding(translated)

        return {
            'valid': len(self.issues) == 0,
            'issues': self.issues,
            'warnings': self.warnings,
            'score': self._calculate_score(),
            'checks': {
                'structure': 'passed' if len([i for i in self.issues if 'structure' in i.lower()]) == 0 else 'failed',
                'code_blocks': 'passed' if len([i for i in self.issues if 'code' in i.lower()]) == 0 else 'failed',
                'links': 'passed' if len([i for i in self.issues if 'link' in i.lower()]) == 0 else 'failed',
                'markdown': 'passed' if len([i for i in self.issues if 'markdown' in i.lower()]) == 0 else 'failed',
            }
        }

    def _check_structure(self, original: str, translated: str) -> None:
        """Check if basic structure is preserved."""
        orig_headings = len(re.findall(r'^#+\s', original, re.MULTILINE))
        trans_headings = len(re.findall(r'^#+\s', translated, re.MULTILINE))

        if orig_headings != trans_headings:
            self.issues.append(f'Structure: Heading count mismatch (original: {orig_headings}, translated: {trans_headings})')

        orig_code_blocks = len(re.findall(r'^```', original, re.MULTILINE))
        trans_code_blocks = len(re.findall(r'^```', translated, re.MULTILINE))

        if orig_code_blocks != trans_code_blocks:
            self.issues.append(f'Structure: Code block count mismatch (original: {orig_code_blocks}, translated: {trans_code_blocks})')

        orig_lists = len(re.findall(r'^[-*+]\s', original, re.MULTILINE))
        trans_lists = len(re.findall(r'^[-*+]\s', translated, re.MULTILINE))

        if orig_lists != trans_lists:
            self.warnings.append(f'Structure: List item count difference (original: {orig_lists}, translated: {trans_lists})')

    def _check_code_blocks(self, original: str, translated: str) -> None:
        """Check if code blocks are preserved exactly."""
        orig_code_blocks = re.findall(r'```.*?```', original, re.DOTALL)
        trans_code_blocks = re.findall(r'```.*?```', translated, re.DOTALL)

        if len(orig_code_blocks) != len(trans_code_blocks):
            self.issues.append(f'Code blocks: Count mismatch')
            return

        for i, (orig_block, trans_block) in enumerate(zip(orig_code_blocks, trans_code_blocks)):
            if orig_block != trans_block:
                # Check if at least the code content is preserved
                orig_code = re.search(r'```\w*\n(.*?)\n```', orig_block, re.DOTALL)
                trans_code = re.search(r'```\w*\n(.*?)\n```', trans_block, re.DOTALL)

                if orig_code and trans_code:
                    if orig_code.group(1) != trans_code.group(1):
                        self.issues.append(f'Code blocks: Content modified in block {i + 1}')

    def _check_links(self, original: str, translated: str) -> None:
        """Check if links are preserved."""
        # Check markdown links [text](url)
        orig_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', original)
        trans_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', translated)

        if len(orig_links) != len(trans_links):
            self.warnings.append(f'Links: Count changed (original: {len(orig_links)}, translated: {len(trans_links)})')
            return

        for i, ((orig_text, orig_url), (trans_text, trans_url)) in enumerate(zip(orig_links, trans_links)):
            if orig_url != trans_url:
                self.issues.append(f'Links: URL changed in link {i + 1} ({orig_url} -> {trans_url})')

    def _check_untranslated_content(
        self,
        original: str,
        translated: str,
        source_language: str,
        target_language: str
    ) -> None:
        """Check for untranslated content (English text in non-English translation)."""
        if source_language == 'en' and target_language != 'en':
            # Look for English words that should have been translated
            # This is a heuristic check

            # Remove code blocks and URLs first
            trans_no_code = re.sub(r'```.*?```', '', translated, flags=re.DOTALL)
            trans_no_code = re.sub(r'https?://[^\s]+', '', trans_no_code)
            trans_no_code = re.sub(r'`[^`]+`', '', trans_no_code)

            # Check for common English words
            common_words = [
                'the', 'and', 'a', 'to', 'of', 'in', 'is', 'you', 'for',
                'have', 'from', 'or', 'be', 'will', 'can', 'this', 'that'
            ]

            found_english = []
            for word in common_words:
                pattern = r'\b' + word + r'\b'
                if re.search(pattern, trans_no_code, re.IGNORECASE):
                    found_english.append(word)

            if len(found_english) > 10:  # Threshold
                self.warnings.append(f'Content: Possible untranslated English words detected ({len(found_english)} instances)')

    def _check_markdown_validity(self, content: str) -> None:
        """Check for basic Markdown validity."""
        # Check for balanced brackets
        if content.count('[') != content.count(']'):
            self.warnings.append('Markdown: Unbalanced square brackets')

        if content.count('(') != content.count(')'):
            self.warnings.append('Markdown: Unbalanced parentheses')

        # Check for unclosed emphasis
        bold_markers = len(re.findall(r'\*\*', content))
        if bold_markers % 2 != 0:
            self.warnings.append('Markdown: Possible unclosed bold markers')

        italic_markers = len(re.findall(r'(?<!\*)\*(?!\*)', content))
        if italic_markers % 2 != 0:
            self.warnings.append('Markdown: Possible unclosed italic markers')

    def _check_encoding(self, content: str) -> None:
        """Check for encoding issues."""
        try:
            content.encode('utf-8')
        except UnicodeEncodeError as e:
            self.issues.append(f'Encoding: {str(e)}')

    def _calculate_score(self) -> float:
        """Calculate validation score (0.0 to 1.0)."""
        issue_count = len(self.issues)
        warning_count = len(self.warnings)

        # Each issue reduces score by 0.1, each warning by 0.05
        score = 1.0 - (issue_count * 0.1 + warning_count * 0.05)

        return max(0.0, min(1.0, score))

    def report(self, format: str = 'text') -> str:
        """
        Generate validation report.

        Args:
            format: 'text', 'json', or 'markdown'

        Returns:
            Formatted report
        """
        if format == 'json':
            return json.dumps({
                'issues': self.issues,
                'warnings': self.warnings,
                'score': self._calculate_score()
            }, indent=2, ensure_ascii=False)

        elif format == 'markdown':
            report = '# Validation Report\n\n'
            report += f'**Score**: {self._calculate_score():.0%}\n\n'

            if self.issues:
                report += '## Issues\n\n'
                for issue in self.issues:
                    report += f'- ❌ {issue}\n'
                report += '\n'

            if self.warnings:
                report += '## Warnings\n\n'
                for warning in self.warnings:
                    report += f'- ⚠️ {warning}\n'

            return report

        else:  # text format
            report = 'Translation Validation Report\n'
            report += f'Score: {self._calculate_score():.0%}\n\n'

            if self.issues:
                report += 'Issues:\n'
                for issue in self.issues:
                    report += f'  - {issue}\n'

            if self.warnings:
                report += '\nWarnings:\n'
                for warning in self.warnings:
                    report += f'  - {warning}\n'

            if not self.issues and not self.warnings:
                report += 'No issues found. Translation validated successfully.'

            return report


def validate_translation(
    original: str,
    translated: str,
    source_language: str = 'en',
    target_language: str = 'unknown'
) -> Dict[str, Any]:
    """Convenience function to validate translation."""
    validator = TranslationValidator()
    return validator.validate_output(original, translated, source_language, target_language)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print('Usage: python validator.py <original_file> <translated_file> [--json|--markdown]')
        sys.exit(1)

    original_path = sys.argv[1]
    translated_path = sys.argv[2]
    format_type = 'text'

    if '--json' in sys.argv:
        format_type = 'json'
    elif '--markdown' in sys.argv:
        format_type = 'markdown'

    try:
        with open(original_path, 'r', encoding='utf-8') as f:
            original = f.read()

        with open(translated_path, 'r', encoding='utf-8') as f:
            translated = f.read()

        validator = TranslationValidator()
        result = validator.validate_output(original, translated)

        print(validator.report(format=format_type))

    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
