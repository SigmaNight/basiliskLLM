## Python Commit Message Instructions

Use conventional commits focused on Python/wxPython scope:

- `feat(presenter): add retry flow for completion errors`
- `fix(wx): prevent crash when dialog closes during callback`
- `refactor(service): simplify account/model resolution`
- `test(presenters): add coverage for cleanup guard behavior`

When relevant, include one short body section with impact:

```text
fix(conversation): guard post-destroy callback access

- skip async callback when view is destroying
- prevent invalid widget access on tab close
```
