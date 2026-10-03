#!/usr/bin/env python3
"""
Markdown Parser Module
Extracts translatable content from Markdown while preserving structure and code blocks.
"""

import re
import json
import yaml
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path


@dataclass
class MarkdownElement:
    """Represents a single element in a Markdown document."""
    type: str  # 'heading', 'paragraph', 'code_block', 'list_item', 'table_cell', 'link_text', 'image_alt', 'html', 'frontmatter', 'raw'
    content: str
    line_number: int
    translatable: bool
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MarkdownParser:
    """Parses Markdown files and identifies translatable vs. non-translatable content."""

    def __init__(self):
        self.elements: List[MarkdownElement] = []
        self.frontmatter: Dict[str, Any] = {}
        self.frontmatter_format: str = 'yaml'  # 'yaml' or 'toml'

    def parse(self, content: str) -> List[MarkdownElement]:
        """
        Parse Markdown content and return a list of elements.

        Args:
            content: Raw Markdown text

        Returns:
            List of MarkdownElement objects
        """
        self.elements = []
        lines = content.split('\n')

        # Extract and handle frontmatter
        lines = self._extract_frontmatter(lines)

        # Parse the remaining content
        i = 0
        while i < len(lines):
            line = lines[i]

            # Skip empty lines but preserve them
            if not line.strip():
                self.elements.append(MarkdownElement(
                    type='empty_line',
                    content='\n',
                    line_number=i,
                    translatable=False
                ))
                i += 1
                continue

            # Check for code blocks
            if line.startswith('```'):
                i, code_block = self._parse_code_block(lines, i)
                self.elements.append(code_block)
                continue

            # Check for HTML blocks
            if line.startswith('<'):
                i, html_block = self._parse_html_block(lines, i)
                self.elements.append(html_block)
                continue

            # Check for headings
            if line.startswith('#'):
                heading = self._parse_heading(line, i)
                self.elements.append(heading)
                i += 1
                continue

            # Check for lists
            if line.startswith(('-', '*', '+')) and len(line) > 1 and line[1] == ' ':
                i, list_item = self._parse_list_item(lines, i)
                self.elements.append(list_item)
                continue

            # Check for ordered lists
            if re.match(r'^\d+\.\s', line):
                i, list_item = self._parse_list_item(lines, i)
                self.elements.append(list_item)
                continue

            # Check for tables
            if '|' in line and not line.startswith('|'):
                # Might be a table row, check context
                i, table = self._parse_table_row(lines, i)
                if table:
                    self.elements.append(table)
                    continue

            # Otherwise, treat as paragraph
            i, paragraph = self._parse_paragraph(lines, i)
            self.elements.append(paragraph)

        return self.elements

    def _extract_frontmatter(self, lines: List[str]) -> List[str]:
        """Extract YAML or TOML frontmatter from the beginning of the document."""
        if not lines or lines[0] not in ('---', '+++'):
            return lines

        delimiter = lines[0]
        end_index = None

        for i in range(1, len(lines)):
            if lines[i] == delimiter:
                end_index = i
                break

        if end_index is None:
            return lines

        frontmatter_text = '\n'.join(lines[1:end_index])
        self.frontmatter_format = 'yaml' if delimiter == '---' else 'toml'

        try:
            if self.frontmatter_format == 'yaml':
                self.frontmatter = yaml.safe_load(frontmatter_text) or {}
            else:
                # TOML parsing would require additional library
                self.frontmatter = {'raw': frontmatter_text}
        except Exception:
            self.frontmatter = {'raw': frontmatter_text}

        # Add frontmatter as non-translatable element
        frontmatter_content = delimiter + '\n' + frontmatter_text + '\n' + delimiter + '\n'
        self.elements.append(MarkdownElement(
            type='frontmatter',
            content=frontmatter_content,
            line_number=0,
            translatable=False
        ))

        return lines[end_index + 1:]

    def _parse_code_block(self, lines: List[str], start_index: int) -> Tuple[int, MarkdownElement]:
        """Parse a fenced code block."""
        opening = lines[start_index]
        match = re.match(r'^```(\w*)', opening)
        language = match.group(1) if match else ''

        code_lines = [opening]
        i = start_index + 1

        while i < len(lines):
            code_lines.append(lines[i])
            if lines[i].startswith('```'):
                i += 1
                break
            i += 1

        content = '\n'.join(code_lines) + '\n'
        return i, MarkdownElement(
            type='code_block',
            content=content,
            line_number=start_index,
            translatable=False,
            metadata={'language': language}
        )

    def _parse_html_block(self, lines: List[str], start_index: int) -> Tuple[int, MarkdownElement]:
        """Parse an HTML block."""
        html_lines = [lines[start_index]]
        i = start_index + 1

        # Simple heuristic: HTML blocks typically end with closing tag or blank line
        tag_match = re.match(r'^<(\w+)', lines[start_index])
        if tag_match:
            tag_name = tag_match.group(1)
            closing_tag = f'</{tag_name}>'

            while i < len(lines) and closing_tag not in lines[i]:
                html_lines.append(lines[i])
                i += 1

            if i < len(lines):
                html_lines.append(lines[i])
                i += 1

        content = '\n'.join(html_lines) + '\n'
        return i, MarkdownElement(
            type='html_block',
            content=content,
            line_number=start_index,
            translatable=False
        )

    def _parse_heading(self, line: str, line_number: int) -> MarkdownElement:
        """Parse a heading line."""
        match = re.match(r'^(#{1,6})\s+(.*?)(\s*#*)?$', line)
        if match:
            level = len(match.group(1))
            text = match.group(2)
            return MarkdownElement(
                type='heading',
                content=line + '\n',
                line_number=line_number,
                translatable=True,
                metadata={'level': level, 'text': text}
            )
        return MarkdownElement(
            type='raw',
            content=line + '\n',
            line_number=line_number,
            translatable=False
        )

    def _parse_list_item(self, lines: List[str], start_index: int) -> Tuple[int, MarkdownElement]:
        """Parse a list item (including continuation lines)."""
        line = lines[start_index]

        # Extract list marker
        if re.match(r'^\d+\.\s', line):
            marker_match = re.match(r'^(\d+\.\s)', line)
        else:
            marker_match = re.match(r'^([-*+]\s)', line)

        marker = marker_match.group(1) if marker_match else '- '
        text = line[len(marker):].rstrip()

        content_lines = [line]
        i = start_index + 1

        # Get continuation lines (indented)
        while i < len(lines) and lines[i] and lines[i][0] == ' ':
            content_lines.append(lines[i])
            i += 1

        content = '\n'.join(content_lines) + '\n'
        return i, MarkdownElement(
            type='list_item',
            content=content,
            line_number=start_index,
            translatable=True,
            metadata={'marker': marker, 'text': text}
        )

    def _parse_table_row(self, lines: List[str], start_index: int) -> Tuple[int, Optional[MarkdownElement]]:
        """Parse a table row."""
        line = lines[start_index]

        # Check if this looks like a table row
        if not line.strip().startswith('|') and not line.strip().endswith('|'):
            return start_index + 1, None

        # Check for separator row (---)
        if all(c in '-|: ' for c in line):
            return start_index + 1, MarkdownElement(
                type='table_separator',
                content=line + '\n',
                line_number=start_index,
                translatable=False
            )

        # Regular table row
        cells = [cell.strip() for cell in line.split('|') if cell.strip()]

        return start_index + 1, MarkdownElement(
            type='table_row',
            content=line + '\n',
            line_number=start_index,
            translatable=True,
            metadata={'cells': cells}
        )

    def _parse_paragraph(self, lines: List[str], start_index: int) -> Tuple[int, MarkdownElement]:
        """Parse a paragraph (one or more lines until blank line or special element)."""
        para_lines = []
        i = start_index

        while i < len(lines):
            line = lines[i]

            # Stop at blank lines
            if not line.strip():
                break

            # Stop at special Markdown elements
            if line.startswith(('#', '-', '*', '+', '`', '<')):
                break

            if re.match(r'^\d+\.\s', line):
                break

            para_lines.append(line)
            i += 1

        content = '\n'.join(para_lines) + '\n'
        return i, MarkdownElement(
            type='paragraph',
            content=content,
            line_number=start_index,
            translatable=True
        )

    def reconstruct(self, translated_elements: List[MarkdownElement]) -> str:
        """
        Reconstruct Markdown from translated elements.

        Args:
            translated_elements: List of MarkdownElement with translated content

        Returns:
            Reconstructed Markdown string
        """
        output_lines = []

        for element in translated_elements:
            output_lines.append(element.content.rstrip('\n'))

        return '\n'.join(output_lines) + '\n'

    def get_translatable_elements(self) -> List[MarkdownElement]:
        """Get only the translatable elements."""
        return [e for e in self.elements if e.translatable]

    def get_non_translatable_elements(self) -> List[MarkdownElement]:
        """Get only the non-translatable elements."""
        return [e for e in self.elements if not e.translatable]

    def export_for_translation(self) -> Dict[str, Any]:
        """Export translatable content for external translation service."""
        segments = []
        for i, element in enumerate(self.elements):
            if element.translatable:
                # Extract plain text from content
                text = element.content.strip()
                # Remove common Markdown symbols for cleaner translation
                if element.type == 'heading':
                    text = re.sub(r'^#+\s+', '', text)
                elif element.type == 'list_item':
                    text = re.sub(r'^[-*+]\s+', '', text)

                segments.append({
                    'id': i,
                    'type': element.type,
                    'text': text,
                    'context': element.metadata
                })

        return {
            'frontmatter': self.frontmatter,
            'segments': segments
        }

    def validate(self) -> Dict[str, Any]:
        """Validate Markdown structure."""
        issues = []

        # Check for unclosed code blocks
        code_block_count = len([e for e in self.elements if e.type == 'code_block'])

        # Check for table consistency
        table_rows = [e for e in self.elements if e.type == 'table_row']
        if table_rows:
            first_row_cells = len(table_rows[0].metadata.get('cells', []))
            for row in table_rows[1:]:
                if len(row.metadata.get('cells', [])) != first_row_cells:
                    issues.append(f'Inconsistent table structure at line {row.line_number}')

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'element_count': len(self.elements),
            'translatable_count': len(self.get_translatable_elements())
        }


def parse_markdown(content: str) -> List[MarkdownElement]:
    """Convenience function to parse Markdown content."""
    parser = MarkdownParser()
    return parser.parse(content)


def validate_markdown(content: str) -> Dict[str, Any]:
    """Convenience function to validate Markdown content."""
    parser = MarkdownParser()
    parser.parse(content)
    return parser.validate()


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print('Usage: python markdown_parser.py <file> [--validate]')
        sys.exit(1)

    file_path = sys.argv[1]
    validate = '--validate' in sys.argv

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    parser = MarkdownParser()
    parser.parse(content)

    if validate:
        result = parser.validate()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Print translatable segments
        export = parser.export_for_translation()
        print(json.dumps(export, indent=2, ensure_ascii=False))
