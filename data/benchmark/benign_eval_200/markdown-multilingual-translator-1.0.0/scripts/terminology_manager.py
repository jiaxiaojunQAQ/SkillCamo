#!/usr/bin/env python3
"""
Terminology Manager Module
Manages glossaries and ensures consistent terminology across translations.
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class TerminologyManager:
    """Manages glossaries and terminology lookup."""

    def __init__(self):
        self.glossaries: Dict[str, Dict[str, Dict[str, str]]] = {}
        self.cache = {}

    def load_glossary(self, glossary_path: str, language: str = 'all') -> bool:
        """
        Load a glossary from a JSON file.

        Args:
            glossary_path: Path to glossary JSON file
            language: Which language glossary to load (or 'all')

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(glossary_path, 'r', encoding='utf-8') as f:
                glossary_data = json.load(f)

            # Filter out metadata
            glossary = {k: v for k, v in glossary_data.items() if not k.startswith('_')}

            # Store by glossary name
            glossary_name = Path(glossary_path).stem

            if language == 'all':
                self.glossaries[glossary_name] = glossary
            else:
                if glossary_name not in self.glossaries:
                    self.glossaries[glossary_name] = {}
                # Store only the language data
                for term, translations in glossary.items():
                    if term not in self.glossaries[glossary_name]:
                        self.glossaries[glossary_name][term] = {}
                    if language in translations:
                        self.glossaries[glossary_name][term][language] = translations[language]

            self.cache.clear()
            return True

        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f'Error loading glossary {glossary_path}: {e}')
            return False

    def load_glossaries_from_directory(self, directory: str) -> int:
        """
        Load all glossary JSON files from a directory.

        Args:
            directory: Path to directory containing glossary files

        Returns:
            Number of glossaries loaded
        """
        directory = Path(directory)
        count = 0

        for glossary_file in directory.glob('*.json'):
            if self.load_glossary(str(glossary_file)):
                count += 1

        return count

    def get_translation(self, term: str, target_language: str, source_language: str = 'en') -> Optional[str]:
        """
        Get the translation of a term for a target language.

        Args:
            term: The term to translate (usually English)
            target_language: Target language code
            source_language: Source language code

        Returns:
            Translation string or None if not found
        """
        # Normalize term
        normalized_term = self._normalize_term(term)

        # Check all glossaries
        for glossary_name, glossary in self.glossaries.items():
            if normalized_term in glossary:
                entry = glossary[normalized_term]
                if isinstance(entry, dict) and target_language in entry:
                    return entry[target_language]
                elif isinstance(entry, str):
                    return entry

        return None

    def get_translations(self, term: str, source_language: str = 'en') -> Optional[Dict[str, str]]:
        """
        Get all available translations for a term.

        Args:
            term: The term to look up
            source_language: Source language (for context)

        Returns:
            Dictionary of language codes to translations
        """
        normalized_term = self._normalize_term(term)

        # Check all glossaries
        for glossary in self.glossaries.values():
            if normalized_term in glossary:
                entry = glossary[normalized_term]
                if isinstance(entry, dict):
                    # Filter to only translation keys (language codes)
                    return {
                        k: v for k, v in entry.items()
                        if k in ['en', 'zh', 'zh_tw', 'ja', 'ko', 'id']
                    }

        return None

    def _normalize_term(self, term: str) -> str:
        """Normalize term for comparison (lowercase, strip whitespace)."""
        return term.strip().lower()

    def apply_glossary_to_text(self, text: str, target_language: str, case_sensitive: bool = False) -> str:
        """
        Apply glossary replacements to text.

        Args:
            text: Text to process
            target_language: Target language code
            case_sensitive: Whether to do case-sensitive replacement

        Returns:
            Text with glossary terms replaced
        """
        result = text

        for glossary in self.glossaries.values():
            for english_term, entry in glossary.items():
                if not isinstance(entry, dict):
                    continue

                if target_language not in entry:
                    continue

                translated_term = entry[target_language]

                # Create regex pattern for replacement
                flags = 0 if case_sensitive else re.IGNORECASE
                pattern = r'\b' + re.escape(english_term) + r'\b'

                # Replace while preserving case
                result = re._replace_with_case(result, pattern, translated_term, flags)

        return result

    def export_glossary(self, output_path: str, glossary_name: Optional[str] = None) -> bool:
        """
        Export merged glossaries to a file.

        Args:
            output_path: Path to export to
            glossary_name: Specific glossary to export (or None for all)

        Returns:
            True if successful
        """
        try:
            if glossary_name and glossary_name in self.glossaries:
                output = self.glossaries[glossary_name]
            else:
                # Merge all glossaries
                output = {}
                for glossary in self.glossaries.values():
                    output.update(glossary)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print(f'Error exporting glossary: {e}')
            return False

    def add_term(self, english_term: str, translations: Dict[str, str], glossary_name: str = 'custom') -> bool:
        """
        Add a new term to a glossary.

        Args:
            english_term: The English term
            translations: Dictionary of language codes to translations
            glossary_name: Glossary to add to

        Returns:
            True if successful
        """
        try:
            if glossary_name not in self.glossaries:
                self.glossaries[glossary_name] = {}

            self.glossaries[glossary_name][english_term.lower()] = translations
            self.cache.clear()
            return True

        except Exception as e:
            print(f'Error adding term: {e}')
            return False

    def list_glossaries(self) -> List[str]:
        """List all loaded glossary names."""
        return list(self.glossaries.keys())

    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about loaded glossaries."""
        total_terms = 0
        glossaries_count = len(self.glossaries)

        for glossary in self.glossaries.values():
            total_terms += len(glossary)

        return {
            'glossaries_loaded': glossaries_count,
            'total_unique_terms': total_terms,
            'supported_languages': 6,
        }

    def validate_glossary(self, glossary_name: str) -> Dict[str, any]:
        """
        Validate a glossary for completeness and consistency.

        Args:
            glossary_name: Name of glossary to validate

        Returns:
            Validation report
        """
        if glossary_name not in self.glossaries:
            return {'valid': False, 'error': 'Glossary not found'}

        glossary = self.glossaries[glossary_name]
        issues = []
        missing_languages = {}

        languages = ['en', 'zh', 'zh_tw', 'ja', 'ko', 'id']

        for term, entry in glossary.items():
            if not isinstance(entry, dict):
                issues.append(f'Term "{term}": Not a dictionary')
                continue

            for lang in languages:
                if lang not in entry:
                    if lang not in missing_languages:
                        missing_languages[lang] = 0
                    missing_languages[lang] += 1

        report = {
            'valid': len(issues) == 0,
            'total_terms': len(glossary),
            'issues': issues,
            'coverage': {
                lang: ((len(glossary) - missing_languages.get(lang, 0)) / len(glossary) * 100)
                for lang in languages
            }
        }

        return report

    @staticmethod
    def create_template(output_path: str, languages: List[str] = None) -> bool:
        """
        Create a glossary template.

        Args:
            output_path: Path to save template
            languages: List of language codes

        Returns:
            True if successful
        """
        if languages is None:
            languages = ['en', 'zh', 'zh_tw', 'ja', 'ko', 'id']

        template = {
            '_metadata': {
                'version': '1.0.0',
                'languages': languages,
                'notes': 'Template glossary file'
            },
            'example_term': {
                lang: f'Translation in {lang}' for lang in languages
            }
        }

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(template, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f'Error creating template: {e}')
            return False


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print('Usage: python terminology_manager.py <glossary_file> [--validate]')
        sys.exit(1)

    glossary_path = sys.argv[1]
    validate = '--validate' in sys.argv

    manager = TerminologyManager()
    if not manager.load_glossary(glossary_path):
        sys.exit(1)

    if validate:
        glossary_name = Path(glossary_path).stem
        report = manager.validate_glossary(glossary_name)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        stats = manager.get_statistics()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
