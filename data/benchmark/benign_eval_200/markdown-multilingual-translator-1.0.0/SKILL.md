# markdown-multilingual-translator

## Overview

The **markdown-multilingual-translator** is a specialized tool for translating Markdown files while preserving all structural elements, code blocks, links, and formatting. It intelligently identifies translatable content (headings, paragraphs, list items, table cells) while protecting non-translatable elements (code, URLs, metadata). The skill supports six languages: English, Simplified Chinese, Taiwan Traditional Chinese, Japanese, Korean, and Indonesian, enabling seamless documentation localization for global audiences.

## What This Skill Does

This skill performs the following operations:

1. **Intelligent Content Parsing**: Analyzes Markdown structure to distinguish translatable text from code blocks, links, and metadata
2. **Language Detection**: Automatically detects the source language with override capabilities
3. **Multi-Language Translation**: Translates between any pair of six supported languages with context awareness
4. **Glossary Management**: Uses domain-specific terminology databases to ensure consistent translations
5. **Structure Preservation**: Maintains all Markdown formatting, links, images, tables, and code blocks exactly as they appear
6. **Quality Validation**: Verifies translation completeness and Markdown integrity
7. **Batch Processing**: Translates multiple files or entire directories simultaneously

## Supported Languages

| Language | Code | Usage |
|----------|------|-------|
| English | `en` | Base language, widely used for documentation |
| Simplified Chinese | `zh` | For mainland China audience |
| Taiwan Traditional Chinese | `zh_tw` | For Taiwan, Hong Kong, Macau audience |
| Japanese | `ja` | For Japanese-speaking developers and users |
| Korean | `ko` | For Korean-speaking developers and users |
| Indonesian | `id` | For Indonesian-speaking developers and users |

## Key Features

**Markdown Element Preservation**: All structural elements are protected from translation:
- Fenced code blocks (with any language syntax highlighting)
- Indented code blocks
- Inline code snippets
- HTML blocks and comments
- YAML/TOML frontmatter
- Links and image URLs
- Tables and their formatting

**Content Translation**: All user-facing content is intelligently translated:
- Heading text
- Paragraph content
- List items and descriptions
- Table cell text (while preserving table structure)
- Image alt text
- Link text (but not URLs)

**Language-Aware Translation**: The skill respects language-specific conventions:
- Chinese spacing and punctuation rules
- Japanese particle placement and honorifics
- Korean subject-object-verb syntax
- Indonesian grammatical structures
- Japanese/Korean pitch accent and tone considerations
- Proper localization of date and time references

**Terminology Consistency**: Uses glossaries to ensure the same terms are always translated identically:
- Technical term databases per language
- Customizable glossaries for your domain
- Automatic glossary lookups during translation
- Support for acronyms, abbreviations, and proper nouns

**Error Handling & Validation**: Robust quality assurance:
- Detects untranslated segments
- Validates Markdown syntax integrity
- Reports missing glossary terms
- Logs all translation decisions for audit trails

## Installation & Setup

### Prerequisites

- Python 3.12 or higher
- Monica AI environment with internet access
- Claude API key (for translation engine)

### Basic Setup

1. Load the skill in Monica:
   ```
   Use skill with name: markdown-multilingual-translator
   ```

2. The skill loads the SKILL.md instructions and makes available:
   - `scripts/translate_markdown.py` - Main translation script
   - `references/` - Language guides, glossaries, and examples
   - `scripts/` - Supporting modules for parsing and translation

3. Install Python dependencies (already included in Monica environment):
   - `markdown` - For Markdown parsing
   - `pyyaml` - For frontmatter handling
   - `requests` - For API calls

## Usage Guide

### Basic Translation

To translate a Markdown file from English to Simplified Chinese:

```bash
python /workspace/skills/markdown-multilingual-translator/scripts/translate_markdown.py \
  --input README.md \
  --output README_zh.md \
  --target-language zh
```

### Advanced Options

```bash
python /workspace/skills/markdown-multilingual-translator/scripts/translate_markdown.py \
  --input README.md \
  --output README_ja.md \
  --source-language en \
  --target-language ja \
  --glossary tech_glossary.json \
  --api-key YOUR_CLAUDE_API_KEY \
  --validate \
  --verbose
```

### Parameters Reference

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--input` | string | Yes | Path to input Markdown file or directory |
| `--output` | string | Yes | Path to output Markdown file or directory |
| `--source-language` | string | No | Source language code (default: auto-detect) |
| `--target-language` | string | Yes | Target language code (e.g., `zh`, `ja`, `ko`) |
| `--glossary` | string | No | Path to custom glossary JSON file |
| `--api-key` | string | No | Claude API key (uses environment var if omitted) |
| `--validate` | flag | No | Run validation after translation |
| `--verbose` | flag | No | Print detailed progress information |
| `--batch` | flag | No | Process entire directory recursively |
| `--keep-structure` | flag | No | Preserve exact directory structure |

### Common Use Cases

#### Batch Translate Documentation Directory

```bash
python scripts/translate_markdown.py \
  --input ./docs/ \
  --output ./docs_ja/ \
  --target-language ja \
  --batch
```

This translates all `.md` files in the `docs/` directory and outputs them to `docs_ja/`, maintaining the directory structure.

#### Translate with Custom Glossary

```bash
python scripts/translate_markdown.py \
  --input api_guide.md \
  --output api_guide_ko.md \
  --target-language ko \
  --glossary ./glossaries/api_terms_ko.json
```

This uses a custom Korean glossary to ensure consistent API terminology translation.

#### Translate Between Non-English Languages

```bash
python scripts/translate_markdown.py \
  --input guide_zh.md \
  --output guide_id.md \
  --source-language zh \
  --target-language id \
  --validate \
  --verbose
```

This translates from Chinese to Indonesian and validates the output, printing detailed progress.

## Understanding Translation Quality

### What Gets Translated Well

- Technical documentation with domain-specific terminology
- User guides and instructional content
- API documentation (with code examples preserved)
- Release notes and changelogs
- Blog posts and articles

### Best Practices for Quality Translation

1. **Prepare your source**: Ensure source Markdown is well-structured with clear headings and paragraphs
2. **Use glossaries**: Provide domain-specific glossaries for consistent terminology
3. **Break into sections**: Large documents translate better than very long single documents
4. **Validate output**: Always review translations, especially for legal or critical content
5. **Provide context**: Use inline code and examples to clarify technical concepts
6. **Update glossaries**: After each translation, add new terms to your glossaries for consistency

### What Requires Manual Review

- Humor, idioms, or culturally-specific references
- Complex technical puns or wordplay
- Context-dependent content requiring cultural knowledge
- Legal or regulatory text
- Marketing or promotional content with brand voice

## Output Validation

After translation, the skill can validate output:

```bash
python scripts/translate_markdown.py \
  --input source.md \
  --output translated.md \
  --target-language zh \
  --validate
```

Validation checks for:
- Markdown syntax correctness
- Untranslated segments (detection of source language text in output)
- Link and image reference integrity
- Code block preservation
- Table structure consistency
- Missing glossary terms

## Glossary Management

### Using Provided Glossaries

The skill includes technical term glossaries for each language:

```bash
# List available glossaries
ls references/glossaries/

# Copy to your project
cp references/glossaries/tech_terms_zh.json ./my_glossary_zh.json

# Customize for your domain
# (Edit JSON file to add/modify terms)

# Use in translation
python scripts/translate_markdown.py \
  --input guide.md \
  --output guide_zh.md \
  --target-language zh \
  --glossary my_glossary_zh.json
```

### Glossary Format

Glossaries are JSON files with the following structure:

```json
{
  "term_english": {
    "zh": "术语中文",
    "zh_tw": "術語中文",
    "ja": "用語日本語",
    "ko": "용어 한국어",
    "id": "istilah bahasa Indonesia"
  },
  "API": {
    "zh": "应用程序接口",
    "zh_tw": "應用程式介面",
    "ja": "アプリケーションプログラミングインターフェース",
    "ko": "응용 프로그램 인터페이스",
    "id": "Antarmuka Pemrograman Aplikasi"
  }
}
```

### Creating Custom Glossaries

1. Start with the template in `references/GLOSSARY_TEMPLATE.md`
2. Add your domain-specific terms and translations
3. Test with a small sample file
4. Expand based on translation results

## Reference Materials

This skill includes comprehensive reference documentation:

- **LANGUAGE_GUIDE.md**: Language-specific conventions and cultural considerations for each supported language
- **GLOSSARY_TEMPLATE.md**: Template and instructions for creating custom glossaries
- **EXAMPLES.md**: Practical translation examples showing input/output for each language pair
- **examples/sample_*.md**: Sample Markdown files in all six languages

Read these references to:
- Understand language-specific formatting conventions
- Learn best practices for creating glossaries
- See realistic translation examples
- Troubleshoot language-specific issues

## Integration with Monica AI

### Using in Monica Workflows

You can call this skill within Monica tasks:

```python
# Load the skill
skill = load_skill('markdown-multilingual-translator')

# Translate a file
result = run_translation(
    input_file='docs/README.md',
    target_language='ja',
    glossary='custom_glossary.json'
)

# Output location: docs/README_ja.md
```

### Combining with Other Monica Tasks

This skill works well with:
- **Document generation**: Translate newly created documentation
- **Content management**: Automate documentation localization workflows
- **Multi-language publication**: Generate documentation for all target markets simultaneously
- **Content validation**: Verify translation quality as part of QA processes

## Troubleshooting

### Common Issues

**Problem**: "ModuleNotFoundError: No module named 'markdown'"

**Solution**: Install required packages:
```bash
pip install markdown pyyaml requests
```

**Problem**: Translation output is empty or partially translated

**Solution**: 
- Check source file is valid Markdown: `python scripts/markdown_parser.py --validate source.md`
- Verify API key is set: `echo $CLAUDE_API_KEY`
- Check file permissions and encoding (UTF-8 required)

**Problem**: Specific terms not translating correctly

**Solution**:
- Add term to custom glossary with correct translation
- Verify glossary JSON syntax is valid
- Re-run translation with `--glossary` parameter

**Problem**: Code blocks or links getting translated

**Solution**:
- This indicates a parsing issue; validate source Markdown
- Report issue with example file for debugging

### Getting Help

Refer to these resources:
1. `references/EXAMPLES.md` - See working examples for your language pair
2. `references/LANGUAGE_GUIDE.md` - Understand language-specific rules
3. `ARCHITECTURE.md` - Technical design documentation
4. Test with sample files in `references/examples/`

## Performance Considerations

- **File size**: Typical 50KB files translate in 10-30 seconds
- **Batch processing**: Directory with 100 files takes 5-15 minutes depending on file sizes
- **API rate limits**: Respects Claude API rate limits with automatic retry logic
- **Memory usage**: Typical usage is under 200MB for batch operations

## Limitations & Known Issues

1. **Language detection** may be inaccurate if source contains mixed languages; specify `--source-language` explicitly
2. **Very short documents** (< 100 words) may have lower translation quality
3. **Domain-specific terminology** outside provided glossaries requires custom glossary entries
4. **Complex nested structures** (deeply nested lists, complex tables) may require manual review
5. **RTL languages** (if added in future): requires additional formatting considerations

## Roadmap & Future Enhancements

Potential future additions:
- Support for additional languages (Arabic, Russian, Spanish, Portuguese)
- Visual diff display showing changes between versions
- Automatic glossary learning from successful translations
- TM (Translation Memory) integration
- Real-time collaborative translation UI
- Support for other formats (RST, AsciiDoc, DITA)

## Support & Feedback

For issues, improvements, or to request additional languages:
- Review the reference materials in `references/`
- Check the ARCHITECTURE.md for technical details
- Test with provided examples in `references/examples/`
- Report issues with minimal reproducible examples

## License & Attribution

The markdown-multilingual-translator was created by Monica AI with comprehensive support for six languages and professional-grade translation quality.

---

**Next Steps**: Review `references/LANGUAGE_GUIDE.md` to understand language-specific considerations, then explore `references/EXAMPLES.md` to see the skill in action with real translation samples.
