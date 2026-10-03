# markdown-multilingual-translator Architecture

## Overview

The markdown-multilingual-translator is a specialized tool for translating Markdown files while preserving structural integrity, code blocks, links, and formatting. It supports bidirectional translation between six languages: Chinese (Simplified), Taiwan Traditional Chinese, English, Japanese, Korean, and Indonesian.

## Design Principles

1. **Markdown Preservation**: Code blocks, inline code, links, images, tables, and metadata are never translated
2. **Language Detection**: Automatic source language detection with override capability
3. **Context Awareness**: Maintains translation context across headings, lists, and nested structures
4. **Consistency**: Uses terminology databases and glossaries for consistent translations
5. **Modularity**: Separate components for parsing, translation, and reconstruction
6. **Safety**: Validation ensures output Markdown is valid and structurally identical to input

## Architecture Components

### 1. Markdown Parser (`markdown_parser.py`)
- Identifies translatable vs. non-translatable content
- Preserves frontmatter (YAML, TOML)
- Extracts and protects:
  - Code blocks (fenced and indented)
  - Inline code
  - URLs and links
  - HTML comments
  - HTML blocks
  - Metadata blocks
- Maintains document structure tree

### 2. Language Detection (`language_detector.py`)
- Detects source language from content
- Returns confidence scores
- Supports override via command-line or config
- Uses statistical and regex-based heuristics

### 3. Translation Engine (`translator.py`)
- Core translation logic
- Supports six language pairs
- Integrates with external translation APIs (with fallback strategies)
- Preserves placeholders for protected content
- Handles context-aware translation

### 4. Terminology Manager (`terminology_manager.py`)
- Maintains domain-specific glossaries
- Supports per-language terminology databases
- Provides consistent translations for key terms
- Allows custom glossary loading

### 5. Quality Validator (`validator.py`)
- Verifies translation completeness
- Checks for untranslated strings
- Validates Markdown syntax
- Confirms structural integrity
- Reports errors and warnings

### 6. CLI Interface (`translate_markdown.py`)
- Command-line access point
- Batch processing support
- Configuration file support
- Progress reporting
- Error handling and logging

## File Structure

```
markdown-multilingual-translator/
├── SKILL.md                          # Main skill documentation
├── ARCHITECTURE.md                   # This file
├── scripts/
│   ├── translate_markdown.py          # Main CLI script
│   ├── markdown_parser.py             # Markdown parsing module
│   ├── language_detector.py           # Language detection
│   ├── translator.py                  # Translation engine
│   ├── terminology_manager.py         # Glossary/terminology management
│   └── validator.py                   # Output validation
├── references/
│   ├── LANGUAGE_GUIDE.md             # Language-specific guidance
│   ├── GLOSSARY_TEMPLATE.md          # Glossary format specification
│   ├── EXAMPLES.md                   # Usage examples
│   ├── glossaries/
│   │   ├── tech_terms_zh.json        # Tech glossary (Chinese)
│   │   ├── tech_terms_zh_tw.json     # Tech glossary (Taiwan Traditional)
│   │   ├── tech_terms_ja.json        # Tech glossary (Japanese)
│   │   ├── tech_terms_ko.json        # Tech glossary (Korean)
│   │   └── tech_terms_id.json        # Tech glossary (Indonesian)
│   └── examples/
│       ├── sample_en.md              # English sample
│       ├── sample_zh.md              # Chinese translation
│       ├── sample_zh_tw.md           # Taiwan Traditional translation
│       ├── sample_ja.md              # Japanese translation
│       ├── sample_ko.md              # Korean translation
│       └── sample_id.md              # Indonesian translation
```

## Language Code Mapping

| Language | Code | Display Name |
|----------|------|--------------|
| English | `en` | English |
| Simplified Chinese | `zh` | 中文（简体） |
| Taiwan Traditional Chinese | `zh_tw` | 繁體中文（台灣） |
| Japanese | `ja` | 日本語 |
| Korean | `ko` | 한국어 |
| Indonesian | `id` | Bahasa Indonesia |

## Data Flow

```
Input Markdown File
        ↓
Language Detection (auto or specified)
        ↓
Markdown Parser (extract structure & content)
        ↓
Terminology Lookup (fetch glossary terms)
        ↓
Translation Engine (translate text segments)
        ↓
Glossary Application (replace with approved terms)
        ↓
Output Reconstruction (reassemble Markdown)
        ↓
Validation (check integrity)
        ↓
Output File
```

## Translation Strategy

The skill uses a **hybrid approach**:

1. **API-based**: Primary translation via Claude/LLM APIs with language-specific prompts
2. **Glossary-based**: High-priority terminology from domain glossaries
3. **Context preservation**: Maintains heading hierarchy and list structures
4. **Fallback**: Local rule-based translation for common terms if API unavailable

## Key Features

1. **Batch Processing**: Translate multiple files or directories
2. **Configuration Files**: Store language preferences, glossaries, and API settings
3. **Progress Reporting**: Real-time feedback on translation status
4. **Error Recovery**: Graceful handling of partial translations
5. **Validation Reports**: Detailed output on translation quality
6. **Glossary Management**: Add, remove, update terminology databases
7. **Language-Specific Formatting**: Respect conventions (spacing, punctuation) of each language

## Supported Markdown Elements

| Element | Preserved | Translated |
|---------|-----------|------------|
| Heading text | No | Yes |
| Paragraph text | No | Yes |
| Code blocks | Yes | No |
| Inline code | Yes | No |
| Links (text) | No | Yes |
| Link URLs | Yes | No |
| Image alt text | No | Yes |
| Image URLs | Yes | No |
| List items | No | Yes |
| Table cells | No | Yes |
| HTML blocks | Yes | No |
| Comments | Yes | No |
| Frontmatter | Yes | No |
| Emphasis/Strong | No | Yes* |

*Formatting preserved but contained text translated

## Implementation Notes

- Uses Python 3.12+ with `markdown`, `pyyaml`, and `requests` libraries
- Claude API integration for high-quality translations
- Extensive error handling for malformed Markdown
- Supports UTF-8 encoding throughout
- Logging for debugging and audit trails
