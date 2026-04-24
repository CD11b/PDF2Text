# PDF2Text

A layout-aware PDF text extraction pipeline that preserves reading order and filters non-body content such as headers, footers, and page numbers. Supports both digital PDFs and OCR-scanned documents.

---

## Overview

Standard PDF text extraction tools treat a document as a flat stream of characters, losing structural information about columns, paragraphs, and reading order. This library reconstructs that structure by analyzing the geometric and typographic properties of each text span (font size, position, indentation, and character count) and applying a rule-based classifier to decide whether each line belongs to the main body text.

---

## Features

- **Column detection**: identifies single and multi-column layouts and processes each column independently in reading order
- **Header and footer filtering**: detects and removes repeating page elements using per-page and document-wide boundary heuristics
- **Paragraph reconstruction**: joins hyphenated line breaks, merges split spans, and identifies paragraph boundaries
- **OCR support**: detects OCR-scanned pages and applies coordinate tolerance to account for positional jitter in recognized text
- **Delimiter cleaning**: resolves inline parenthetical expressions that span multiple lines, including hanging delimiters carried across page boundaries
- **Unicode normalization**: strips combining marks and corrects common OCR ligature errors

---

## Project Status

This project is currently under active development and should be considered unstable and subject to change without notice.

- APIs, internal data models, and rule engines may be refactored, renamed, or removed between versions
- Output formats and heuristics are not yet final and may evolve as extraction accuracy improves
- Features marked as “planned”, “not yet implemented”, or implied in documentation may be incomplete or behave inconsistently
- Backward compatibility is not guaranteed at this stage

Use in production environments is discouraged unless you are prepared to adapt to breaking changes.

---

## Architecture

Broadly, the pipeline processes one page at a time in five stages:

```
PDFReader → PageAnalyzer → FilterText → BracketCleaner → OutputWriter
```

**`PageAnalyzer`** extracts raw text spans from PyMuPDF block dictionaries, detects OCR, computes statistical heuristics (font size distribution, line spacing, indentation bounds, character count), and segments the page into columns and line groups.

**`FilterText`** classifies each line group using a `PageLayout` context that holds the column's geometric boundaries and coordinate tolerance. Each line group is assigned a `LineContext`, a snapshot of its margin position, vertical region, paragraph position, indentation, character_count, font name, and font size, and routed to one of six rule engines that decide whether to collect or skip it.

- Rule engines contain prioritized, independently testable rules. Each rule inspects only the pre-computed `LineContext` with no access to the raw iterator or layout internals.

**`BracketCleaner`** makes a second pass over collected lines to remove parenthetical asides, handling delimiters that span consecutive lines or entire paragraphs, and carrying unresolved open delimiters across page boundaries.

---

## Installation

```bash
pip install -r requirements.txt
```

Requires Python 3.10+. OCR support requires a Tesseract data directory at `./training`.

---

## Usage

```bash
python main.py --input-path ./docs/my_document.pdf
python main.py --input-path ./docs/my_document.pdf --page-start 10 --page-end 50
python main.py --input-path ./docs/my_document.pdf --log-level INFO
```

Output is written to `./generated/<document_title>.txt`.

### Arguments

| Argument              | Default             | Description                                  |
|-----------------------|---------------------|----------------------------------------------|
| `--input-path`        | `./docs/butler.pdf` | Path to the input PDF                        |
| `--page-start`        | N/A                 | First page to process (0-based)              |
| `--page-end`          | N/A                 | Last page to process (exclusive)             |
| `--log-level`         | `DEBUG`             | Logging verbosity                            |
| `--remove-references` | off                 | Skip reference pages *(not yet implemented)* |

---

## Project Structure

```
├── main.py                  # Pipeline entry point
├── classifier.py            # Line classification (margin, region, character_count, font)
├── text_heuristics.py       # Statistical heuristic computation (MAD-based bounds)
├── document_analysis.py     # PyMuPDF block extraction
├── line_collector.py        # Collect/skip decisions
├── text_cleaning.py         # Unicode normalisation, line joining, page number removal
├── models/                  # Dataclasses: StyledLine, LineContext, Heuristics, etc.
├── rule_engine/             # Base Rule and RuleEngine classes
│   ├── indented/            # Rules for indented lines
│   ├── header/              # Rules for header region lines
│   ├── footer/              # Rules for footer region lines
│   ├── at_left_margin/      # Rules for lines at the left margin
│   ├── before_left_margin/  # Rules for lines before the left margin
│   └── continuous_paragraph/# Rules for mid-paragraph continuation lines
└── IO/                      # PDFReader and OutputWriter
```

---

## Extending with New Rules

Each rule engine accepts a prioritized list of `Rule` subclasses. To add a rule, subclass `Rule` and implement `matches` and `decide`:

```python
from src.pdf2text.rule_engine import Rule
from src.pdf2text.models import Decision, Action, LineContext


class MyCustomRule(Rule):
    priority = 30  # lower runs first

    def matches(self, ctx: LineContext) -> bool:
        return ctx.font_size is FontSize.LARGE and ctx.region is VerticalRegion.BODY

    def decide(self, ctx: LineContext) -> Decision:
        return Decision(Action.SKIP, "Large font in body, likely a chapter heading", self.name)
```

Then, register it in `FilterText.__init__`.