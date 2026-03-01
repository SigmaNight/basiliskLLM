# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BasiliskLLM is a wxPython desktop GUI application providing a unified chat interface for multiple LLM providers (Anthropic, OpenAI, Gemini, Mistral, Ollama, DeepSeek, xAI, OpenRouter). It runs on Windows with strong accessibility focus (NVDA screen reader integration). Licensed GPL-2.0, requires Python 3.14.

## Commands

```bash
# Install dependencies
uv sync --frozen --group dev

# Run the application
uv run -m basilisk
# With args: --log-level DEBUG, --minimize, --language <code>, --no-env-account, [bskc_file]

# Run all tests
uv run -m pytest

# Run a single test file
uv run -m pytest tests/test_conversation_profile.py

# Run tests by marker
uv run -m pytest -m "not slow and not integration"

# Lint and format
uv run -m ruff check --fix
uv run -m ruff format

# Build standalone executable
uv run -m cx_Freeze build_exe

# Compile translations
uv run setup.py compile_catalog
```

## Code Style

- **Indentation**: Tabs (not spaces)
- **Line length**: 80 characters
- **Quote style**: Preserve (don't change existing quotes)
- **Docstrings**: Google style
- **Naming**: `snake_case` for variables/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants
- **Imports**: Standard library -> third-party -> local (`basilisk`), alphabetically sorted; add `from __future__ import annotations` in all presenter and service modules
- **Translation**: Use `_("string")` for user-facing text. Translation builtins (`_`, `gettext`, `ngettext`, `npgettext`, `pgettext`) are available globally without import
- **Translator context**: Use `# Translators:` comment before translatable strings to provide context
- **Commits**: Conventional commits format (commitizen with `cz_conventional_commits`)

## Architecture

The codebase follows an **MVP (Model-View-Presenter)** pattern.

### Entry Points

- `basilisk/__main__.py` - CLI entry point, argument parsing, singleton enforcement, IPC
- `basilisk/main_app.py` - `MainApp(wx.App)` initialization: logging, localization, main frame, IPC, server, auto-updates

### Views (`basilisk/views/`)

Thin wxPython UI layer — layout, event binding, widget access. No business logic.

- `main_frame.py` - `MainFrame`: root window, notebook tabs, menu bar, status bar, system tray (`TaskBarIcon`), global hotkeys (Windows)
- `conversation_tab.py` - `ConversationTab(BaseConversation)`: chat interface with message history, prompt input, model selection, streaming
- `history_msg_text_ctrl.py` - Custom text control with NVDA accessibility
- `prompt_attachments_panel.py` - Input area with file attachment support
- `view_mixins.py` - `ErrorDisplayMixin`: `show_error()` / `show_enhanced_error()` for standardised error display
- Dialogs: account, preferences, conversation profile, about, update, error display, message editing

### Presenters (`basilisk/presenters/`)

Business logic layer. Receive a view via constructor injection. Avoid `import wx` where possible — delegate wx calls to the view.

- `main_frame_presenter.py` - `MainFramePresenter`: tab management, file operations, quit flow
- `conversation_presenter.py` - `ConversationPresenter`: completion, streaming, audio recording, draft
- `base_conversation_presenter.py` - `BaseConversationPresenter`: shared account/model resolution
- `history_presenter.py` - `HistoryPresenter`: message navigation, segment manager, speak-response
- `account_presenter.py` - `AccountPresenter`: account CRUD (inherits `ManagerCrudMixin`)
- `conversation_profile_presenter.py` - `ConversationProfilePresenter`: profile CRUD (inherits `ManagerCrudMixin`)
- `edit_block_presenter.py` - `EditBlockPresenter`: message block editing and regeneration
- `conversation_history_presenter.py` - `ConversationHistoryPresenter`: history dialog logic
- `preferences_presenter.py` - `PreferencesPresenter`: preferences dialog logic
- `attachment_panel_presenter.py` - `PromptAttachmentPresenter`: file attachment handling
- `search_presenter.py` - `SearchPresenter`: in-conversation search
- `ocr_presenter.py` - `OCRPresenter`: screen capture / OCR logic
- `update_presenter.py` - `UpdatePresenter` / `DownloadPresenter`: auto-update flow
- `enhanced_error_presenter.py` - `EnhancedErrorPresenter`: URL detection, clipboard, open-url
- `presenter_mixins.py`:
  - `DestroyGuardMixin` + `@_guard_destroying` — skip callbacks after view is being destroyed
  - `ManagerCrudMixin` — standard add/edit/delete/move for list-based managers

### Services (`basilisk/services/`)

Reusable, thread-safe logic. Instance-based for async (thread + `wx.CallAfter` callbacks); static methods for pure logic.

- `conversation_service.py` - `ConversationService`: LLM completion pipeline
- `account_model_service.py` - `AccountModelService`: account/model lookup and filtering
- `search_service.py` - `SearchService`: text search across conversation history
- `attachment_service.py` - `AttachmentService`: file attachment processing and resizing

### Provider Engine (`basilisk/provider_engine/`)

Each LLM provider inherits from `BaseEngine` (ABC) in `base_engine.py`. Required implementations:

- `capabilities`: set of `ProviderCapability` (TEXT, IMAGE, AUDIO, STREAMING)
- `client`: cached property returning the provider SDK client
- `models`: cached property returning `list[ProviderAIModel]`
- `completion()`, `prepare_message_request()`, `prepare_message_response()`
- `completion_response_with_stream()`, `completion_response_without_stream()`

### Configuration (`basilisk/config/`)

Pydantic-based settings with YAML persistence (stored via `platformdirs`):

- `main_config.py` - `BasiliskConfig`: general, conversation, images, recordings, server, network settings
- `account_config.py` - `AccountManager`: per-provider accounts with `SecretStr` API keys (Keyring/Windows Credential Manager)
- `conversation_profile.py` - `ConversationProfile`: per-conversation defaults (account, model, system prompt, temperature, etc.)
- Base class `BasiliskBaseSettings` handles YAML load/save. Loading order: YAML -> env vars -> defaults

### Conversation System (`basilisk/conversation/`)

- `conversation_model.py` - Pydantic models: `Conversation` > `MessageBlock` (request/response pair) > `Message` + attachments
- `conversation_helper.py` - BSKC file format (JSON-based) I/O with version migrations
- `attached_file.py` - `AttachmentFile` and `ImageFile` with base64 encoding and auto-resize

### wxPython Patterns

- Event binding: `self.Bind(wx.EVT_*, self.on_*)`
- Dialog lifecycle: always call `dialog.Destroy()` after `ShowModal()`
- Layout: use `BoxSizer` for responsive layouts, avoid fixed positioning
- Accessibility: proper labels and NVDA integration on all controls
- No wx in presenters: use `view.show_error()` / `view.show_enhanced_error()` (from `ErrorDisplayMixin`) instead of `wx.MessageBox`

### Supporting Systems

- `singleton_instance/` - Single-instance enforcement (Windows mutex, POSIX file lock)
- `ipc/` - Inter-process communication (Windows named pipes, POSIX file watcher) for focus and file-open signals
- `completion_handler.py` - LLM request processing and streaming
- `message_segment_manager.py` - Message text segmentation for accessible output
- `sound_manager.py` - Audio notification playback
- `updater.py` - Auto-update with release channels (stable, beta, dev)
- `provider.py` - Provider registry and factory
- `decorators.py` - `ensure_no_task_running`, `measure_time`, `require_list_selection(widget_attr)`

### Resource Cleanup Pattern

- `ConversationTab._is_destroying = False` — set to `True` in `cleanup_resources()`
- `cleanup_resources()` calls `presenter.cleanup()` and `ocr_handler.cleanup()`
- `ConversationPresenter.cleanup()`: stops completion (`skip_callbacks=True`), aborts recording, stops sound, flushes draft
- `HistoryPresenter.cleanup()`: destroys `_search_dialog`, resets `_search_presenter` to `None`
- `MainFramePresenter.flush_and_save_on_quit()` and `close_conversation()` call `tab.cleanup_resources()`
- Presenter callbacks that may fire after destruction are decorated with `@_guard_destroying`

## Test Infrastructure

- Global fixtures in `tests/conftest.py`: `ai_model`, `user_message`, `assistant_message`, `system_message`, `message_block`, `message_block_with_response`, `empty_conversation`, `text_file`, `image_file`, `attachment`, `image_attachment`, `segment_manager`; autouse `mock_display_error_msg` and `mock_settings_sources`
- Presenter fixtures in `tests/presenters/conftest.py`: `base_mock_view` (`_is_destroying=False`), `mock_account`, `mock_model`, `mock_engine`
- **pytest-mock**: Use `mocker.patch()` / `mocker.patch.object()` — prefer over `@patch` decorators and `with patch()` context managers
- **Parametrize**: Use tuple syntax `("a", "b")` not string `"a,b"` for multi-parameter marks (PT006)
- **Subtests**: Use native pytest 9 `subtests` fixture with `with subtests.test(label=x):`
- **Mock views** for `ConversationPresenter` must set `view._is_destroying = False` explicitly
- Do **not** use bare `_` for tuple unpacking — it shadows the translation builtin and breaks `_("Error")` calls
- Markers: `slow`, `integration`
