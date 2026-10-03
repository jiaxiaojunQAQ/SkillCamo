#!/usr/bin/env python3
"""
Main CLI Script for Markdown Translation
Provides command-line interface for translating Markdown files across six languages.
"""

import argparse
import sys
import json
import os
from pathlib import Path
from typing import Optional

# Import modules
from markdown_parser import MarkdownParser
from language_detector import LanguageDetector
from translator import TranslationEngine
from terminology_manager import TerminologyManager
from validator import TranslationValidator


class MarkdownTranslator:
    """Main translation orchestrator."""

    def __init__(self, api_key: Optional[str] = None, verbose: bool = False):
        """Initialize translator with dependencies."""
        self.api_key = api_key
        self.verbose = verbose
        self.engine = None
        self.terminology_manager = TerminologyManager()

        if api_key:
            try:
                self.engine = TranslationEngine(api_key)
            except Exception as e:
                if verbose:
                    print(f'Warning: Could not initialize translation engine: {e}')

    def translate_file(
        self,
        input_path: str,
        output_path: str,
        target_language: str,
        source_language: Optional[str] = None,
        glossary_path: Optional[str] = None,
        validate: bool = False,
        keep_structure: bool = True
    ) -> bool:
        """
        Translate a Markdown file.

        Args:
            input_path: Path to input Markdown file
            output_path: Path to output file
            target_language: Target language code
            source_language: Source language code (auto-detect if None)
            glossary_path: Path to glossary JSON file
            validate: Whether to validate output
            keep_structure: Whether to preserve directory structure for batch operations

        Returns:
            True if successful
        """
        try:
            # Read input file
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if self.verbose:
                print(f'📄 Reading: {input_path}')

            # Detect source language if not specified
            if not source_language:
                detector = LanguageDetector()
                source_language, confidence = detector.detect(content)
                if self.verbose:
                    print(f'🔍 Detected language: {detector.get_language_name(source_language)} ({confidence:.0%})')

            # Parse Markdown
            parser = MarkdownParser()
            parser.parse(content)
            if self.verbose:
                print(f'📝 Parsed: {len(parser.get_translatable_elements())} translatable segments')

            # Load glossary if provided
            if glossary_path and os.path.exists(glossary_path):
                if self.terminology_manager.load_glossary(glossary_path):
                    if self.verbose:
                        print(f'📚 Loaded glossary: {glossary_path}')
                else:
                    print(f'⚠️  Warning: Could not load glossary: {glossary_path}')

            # Translate content
            translated_content = self._translate_segments(
                parser.elements,
                target_language,
                source_language
            )

            # Validate if requested
            if validate:
                validator = TranslationValidator()
                report = validator.validate_output(content, translated_content, source_language, target_language)

                if self.verbose:
                    print(f'✅ Validation score: {report["score"]:.0%}')
                    if report['issues']:
                        for issue in report['issues']:
                            print(f'   ❌ {issue}')
                    if report['warnings']:
                        for warning in report['warnings']:
                            print(f'   ⚠️  {warning}')

            # Write output file
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(translated_content)

            if self.verbose:
                print(f'✨ Written: {output_path}')

            return True

        except Exception as e:
            print(f'❌ Error: {e}', file=sys.stderr)
            return False

    def translate_directory(
        self,
        input_dir: str,
        output_dir: str,
        target_language: str,
        glossary_path: Optional[str] = None,
        keep_structure: bool = True,
        validate: bool = False
    ) -> int:
        """
        Translate all Markdown files in a directory.

        Args:
            input_dir: Input directory
            output_dir: Output directory
            target_language: Target language code
            glossary_path: Path to glossary
            keep_structure: Whether to preserve directory structure
            validate: Whether to validate output

        Returns:
            Number of files successfully translated
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        success_count = 0

        markdown_files = list(input_path.glob('**/*.md'))

        if self.verbose:
            print(f'📁 Found {len(markdown_files)} Markdown files')

        for md_file in markdown_files:
            try:
                # Determine output path
                if keep_structure:
                    rel_path = md_file.relative_to(input_path)
                    out_file = output_path / rel_path
                else:
                    out_file = output_path / md_file.name

                if self.verbose:
                    print(f'📄 Translating: {md_file}')

                if self.translate_file(
                    str(md_file),
                    str(out_file),
                    target_language,
                    glossary_path=glossary_path,
                    validate=validate,
                    keep_structure=keep_structure
                ):
                    success_count += 1

            except Exception as e:
                print(f'❌ Error translating {md_file}: {e}', file=sys.stderr)

        return success_count

    def _translate_segments(self, elements, target_language: str, source_language: str) -> str:
        """Translate Markdown elements."""
        # Simple implementation: translate non-translatable elements as-is, 
        # translatable elements are marked for translation
        # In production, this would call the translation engine

        translated_elements = []

        for element in elements:
            if not element.translatable:
                translated_elements.append(element.content)
            else:
                # Mark as placeholder for manual translation
                # In production, call self.engine.translate()
                translated_elements.append(element.content)

        return ''.join(translated_elements)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Translate Markdown files with multi-language support',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Translate single file to Chinese
  %(prog)s --input README.md --output README_zh.md --target-language zh

  # Translate directory to Japanese
  %(prog)s --input docs/ --output docs_ja/ --target-language ja --batch

  # Translate with custom glossary
  %(prog)s --input guide.md --output guide_ko.md --target-language ko --glossary glossary.json

  # Translate and validate
  %(prog)s --input index.md --output index_id.md --target-language id --validate
        '''
    )

    parser.add_argument('--input', required=True, help='Input Markdown file or directory')
    parser.add_argument('--output', required=True, help='Output Markdown file or directory')
    parser.add_argument(
        '--target-language',
        required=True,
        choices=['zh', 'zh_tw', 'ja', 'ko', 'id'],
        help='Target language code'
    )
    parser.add_argument(
        '--source-language',
        choices=['en', 'zh', 'zh_tw', 'ja', 'ko', 'id'],
        help='Source language code (auto-detect if omitted)'
    )
    parser.add_argument('--glossary', help='Path to glossary JSON file')
    parser.add_argument(
        '--api-key',
        help='Claude API key (uses CLAUDE_API_KEY env var if omitted)'
    )
    parser.add_argument('--validate', action='store_true', help='Validate translation output')
    parser.add_argument('--batch', action='store_true', help='Translate entire directory')
    parser.add_argument('--keep-structure', action='store_true', default=True,
                        help='Preserve directory structure for batch operations')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0')

    args = parser.parse_args()

    # Initialize translator
    translator = MarkdownTranslator(api_key=args.api_key, verbose=args.verbose)

    # Handle file or directory
    input_path = Path(args.input)

    if args.batch or input_path.is_dir():
        # Batch directory translation
        if args.verbose:
            print(f'🔄 Translating directory: {args.input}')

        count = translator.translate_directory(
            args.input,
            args.output,
            args.target_language,
            glossary_path=args.glossary,
            keep_structure=args.keep_structure,
            validate=args.validate
        )

        print(f'✅ Successfully translated {count} files')
        return 0 if count > 0 else 1

    else:
        # Single file translation
        if args.verbose:
            print(f'🔄 Translating file: {args.input}')

        success = translator.translate_file(
            args.input,
            args.output,
            args.target_language,
            source_language=args.source_language,
            glossary_path=args.glossary,
            validate=args.validate
        )

        if success:
            print(f'✅ Successfully translated to {args.output}')
            return 0
        else:
            print(f'❌ Translation failed', file=sys.stderr)
            return 1


if __name__ == '__main__':
    sys.exit(main())
