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
- **Imports**: Standard library -> third-party -> local (`basilisk`), alphabetically sorted
- **Translation**: Use `_("string")` for user-facing text. Translation builtins (`_`, `gettext`, `ngettext`, `npgettext`, `pgettext`) are available globally without import
- **Translator context**: Use `# Translators:` comment before translatable strings to provide context
- **Commits**: Conventional commits format (commitizen with `cz_conventional_commits`)

## Architecture

### Entry Points

- `basilisk/__main__.py` - CLI entry point, argument parsing, singleton enforcement, IPC
- `basilisk/main_app.py` - `MainApp(wx.App)` initialization: logging, localization, main frame, IPC, server, auto-updates

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

### GUI (`basilisk/gui/`)

- `main_frame.py` - `MainFrame`: root window, notebook tabs, menu bar, status bar, system tray (`TaskBarIcon`), global hotkeys (Windows)
- `conversation_tab.py` - `ConversationTab(BaseConversation)`: chat interface with message history, prompt input, model selection, streaming
- `history_msg_text_ctrl.py` - Custom text control with NVDA accessibility
- `prompt_attachments_panel.py` - Input area with file attachment support
- Dialogs: account, preferences, conversation profile, about, update, error display, message editing

### wxPython Patterns

- Event binding: `self.Bind(wx.EVT_*, self.on_*)`
- Dialog lifecycle: always call `dialog.Destroy()` after `ShowModal()`
- Layout: use `BoxSizer` for responsive layouts, avoid fixed positioning
- Accessibility: proper labels and NVDA integration on all controls

### Supporting Systems

- `singleton_instance/` - Single-instance enforcement (Windows mutex, POSIX file lock)
- `ipc/` - Inter-process communication (Windows named pipes, POSIX file watcher) for focus and file-open signals
- `completion_handler.py` - LLM request processing and streaming
- `message_segment_manager.py` - Message text segmentation for accessible output
- `sound_manager.py` - Audio notification playback
- `updater.py` - Auto-update with release channels (stable, beta, dev)
- `provider.py` - Provider registry and factory

## Test Infrastructure

Test fixtures in `tests/conftest.py` provide: `ai_model`, `user_message`, `assistant_message`, `system_message`, `message_block`, `message_block_with_response`, `empty_conversation`, `text_file`, `image_file`, `attachment`, `image_attachment`, `segment_manager`. Markers: `slow`, `integration`.
