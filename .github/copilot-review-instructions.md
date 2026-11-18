## Python Code Review Instructions

When reviewing pull requests, enforce these Python/wxPython standards:

### Architecture and Boundaries

- Keep business logic in presenters/services, not in views
- Avoid importing `wx` in presenters when a view proxy can be used
- Ensure callbacks that may run post-destroy are guarded

### Safety and Async

- Flag GUI updates from worker threads; require `wx.CallAfter`/event posting
- Verify cleanup paths stop running tasks and release resources
- Confirm exceptions are surfaced via view error APIs, not raw message boxes

### Style and Conventions

- Tabs for indentation, line length near 80, stable naming conventions
- Keep imports grouped and sorted (stdlib, third-party, local)
- Preserve existing quote style and avoid unnecessary refactors

### Tests

- Prefer targeted pytest coverage for changed behavior
- Use `pytest-mock` helpers (`mocker.patch*`) instead of ad-hoc patch styles
- Ensure tests avoid patterns known to break translations (e.g., bare `_` tuple unpack)
