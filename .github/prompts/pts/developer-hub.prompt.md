---
name: developer-command-center
description: Developer command center for Python, wxPython, desktop accessibility, and accessibility tooling.
mode: agent
agent: developer-hub
tools:
  - askQuestions
  - readFile
  - runSubagent
  - runInTerminal
  - getTerminalOutput
---

# Developer Hub - Command Center

Start here for Python and desktop development tasks.

## Task

**Task:** `${input:task}`

## Routing

- Python debugging/testing/packaging -> `python-specialist`
- wxPython GUI implementation -> `wxpython-specialist`
- Desktop accessibility API implementation -> `desktop-a11y-specialist`
- Desktop accessibility testing workflow -> `desktop-a11y-testing-coach`
- Accessibility scanner/tool architecture -> `a11y-tool-builder`

## Expected Output

- Correct specialist chosen
- Actionable implementation steps
- Code changes and validation commands when applicable
