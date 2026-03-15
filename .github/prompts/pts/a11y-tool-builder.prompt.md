---
name: build-a11y-tool
description: Build accessibility scanning tools, rule engines, document parsers, report generators, and audit automation. WCAG criterion mapping, severity scoring algorithms, CLI/GUI scanner architecture, CI/CD integration.
mode: agent
agent: a11y-tool-builder
tools:

- askQuestions
- readFile
- editFiles
- createFile
- runInTerminal
- listDirectory

______________________________________________________________________

# Build Accessibility Tool

Design and implement accessibility scanning tools, rule engines, report generators, or audit automation systems.

## Tool Type

**Project:** `${input:toolType|default=scanning-tool}`

Options: scanning-tool, rule-engine, report-generator, document-parser, cli-scanner, gui-scanner, ci-integration

## Instructions

### Step 1: Understand Requirements

Ask the user:

1. **Tool purpose** -- What accessibility problem does this tool solve?
1. **Target format** -- Web (HTML/JSX), documents (DOCX/PDF), markdown, or multi-format?
1. **WCAG coverage** -- Specific criteria (e.g., 1.4.3, 2.4.4) or full AA compliance?
1. **Output format** -- JSON, markdown, CSV, HTML report, or CI exit codes?
1. **Integration** -- Standalone CLI, CI/CD plugin, or library?

### Step 2: Design Architecture

Review the **a11y-tool-builder** agent's architecture patterns:

- Rule engine design (rule ID, severity, WCAG mapping, detection logic)
- Severity scoring formulas (0-100, A-F grades)
- Parser architecture (DOM/AST traversal, Office XML, PDF structure)
- Report generation (executive summary, findings, remediation priorities)
- CI/CD integration (exit codes, JSON output, diff mode)

### Step 3: Implement Core Components

Build the tool following accessibility-first principles:

1. **Scanner/Parser** -- Extract structure from target format
1. **Rule Engine** -- Apply accessibility rules with WCAG mapping
1. **Severity Scorer** -- Compute scores using documented formulas
1. **Report Generator** -- Format findings with remediation guidance
1. **CLI Interface** -- Argument parsing, help text, error handling

### Step 4: Test & Document

- Unit tests for each rule
- Integration tests with sample files
- CLI usage examples
- WCAG criterion reference table
- Help URL library (Accessibility Insights, Microsoft, W3C)

## Expected Output

- Working tool with clear documentation
- WCAG criterion mapping for all rules
- Example reports showing output format
- Installation and usage instructions
