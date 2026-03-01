# BasiliskLLM Coding Guidelines

## Architecture Overview

BasiliskLLM is a **wxPython desktop GUI** application that provides a unified interface for multiple LLM providers (OpenAI, Anthropic, Gemini, Mistral, Ollama, etc.). The codebase follows an **MVP (Model-View-Presenter)** pattern.

### Key Components

- **Main Application**: `basilisk/main_app.py` - wxPython app initialization, IPC, auto-updates
- **Views**: `basilisk/views/` - wxPython-based UI components (no business logic)
- **Presenters**: `basilisk/presenters/` - Business logic, decoupled from wx
- **Services**: `basilisk/services/` - Reusable async/thread-safe logic
- **Provider Engine**: `basilisk/provider_engine/` - Abstracted LLM provider implementations using `BaseEngine`
- **Configuration**: `basilisk/config/` - Pydantic-based settings with YAML persistence
- **Conversation System**: `basilisk/conversation/` - Pydantic models for messages, attachments, and persistence

### MVP Pattern

#### Presenters (`basilisk/presenters/`)

- `MainFramePresenter` - Root window logic, tab management, file operations
- `ConversationPresenter` - Chat logic, completion handling, streaming
- `BaseConversationPresenter` - Shared account/model resolution
- `HistoryPresenter` - Message history display and navigation
- `AccountPresenter` - Account CRUD management
- `ConversationProfilePresenter` - Profile CRUD management
- `EditBlockPresenter` - Message block editing and regeneration
- `ConversationHistoryPresenter` - Conversation history dialog
- `PreferencesPresenter` - Preferences dialog logic
- `PromptAttachmentPresenter` - File attachment handling
- `SearchPresenter` - In-conversation search
- `OCRPresenter` - Screen capture / OCR logic
- `UpdatePresenter` / `DownloadPresenter` - Auto-update flow
- `EnhancedErrorPresenter` - Error dialog with URL detection

Presenter rules:

- Receive view via constructor injection
- Avoid `import wx` where possible; delegate all wx calls to the view
- Use `from __future__ import annotations` at the top of every presenter module
- Inherit `DestroyGuardMixin` + decorate callbacks with `@_guard_destroying` to guard against post-destroy calls
- Call `view.show_error()` / `view.show_enhanced_error()` (from `ErrorDisplayMixin`) instead of `wx.MessageBox`

#### Views (`basilisk/views/`)

- Thin UI layer — layout, event binding, widget access
- Inherit `ErrorDisplayMixin` from `basilisk/views/view_mixins.py` for standardised error display
- Expose widget state through properties; delegate logic calls to the presenter

#### Services (`basilisk/services/`)

- `ConversationService` - LLM completion pipeline
- `AccountModelService` - Account/model lookup and filtering
- `SearchService` - Text search across conversation history
- `AttachmentService` - File attachment processing and resizing
- Instance-based for async operations (thread + `wx.CallAfter` callbacks); static methods for pure logic

### Presenter Mixins & Decorators

- `basilisk/presenters/presenter_mixins.py`:
  - `DestroyGuardMixin` + `_guard_destroying` decorator — skip callbacks after view is being destroyed
  - `ManagerCrudMixin` — standard add/edit/delete/move operations for list-based managers
- `basilisk/views/view_mixins.py`:
  - `ErrorDisplayMixin` — `show_error(message, title)` and `show_enhanced_error(message, title, is_completion_error)`
- `basilisk/decorators.py`:
  - `ensure_no_task_running` — guards thread-starting methods (requires `self.task`)
  - `require_list_selection(widget_attr)` — guards list-action handlers when nothing is selected
  - `measure_time` — performance logging

### Provider Engine Pattern

Each LLM provider inherits from `BaseEngine` in `basilisk/provider_engine/base_engine.py`:

```python
class AnthropicEngine(BaseEngine):
	capabilities = {
		ProviderCapability.TEXT,
		ProviderCapability.IMAGE
	}

	@cached_property
	def client(self) -> Anthropic: ...

	def completion(self, new_block, conversation, system_message): ...
```

### Configuration Architecture

- **YAML-based**: Configuration stored in user config directory using `platformdirs`
- **Pydantic Models**: Type-safe config with validation (`basilisk/config/main_config.py`)
- **Account Management**: Secure API key storage with Windows Credential Manager support
- **Main Config file**: Contains the main configuration parameters for the app (language, log level, update settings, network settings)
- **Conversation Profile**: A config file to define a profile for new conversations (account, system prompt, model, etc.)
- **Loading Order**: YAML files → Environment variables → Default values

### Main Frame Structure (`basilisk/views/main_frame.py`)

- **MainFrame**: Root window with menu bar, notebook tabs, and status bar; delegates logic to `MainFramePresenter`
- **Notebook Tabs**: Each conversation runs in a separate `ConversationTab`
- **System Tray**: `TaskBarIcon` for minimize-to-tray functionality
- **Global Hotkeys**: Windows-specific hotkey registration for screen capture

### Dialog System

- **Modal Dialogs**: Account management, preferences, about dialog
- **Base Pattern**: Always call `dialog.Destroy()` after `ShowModal()`
- **Preferences**: `PreferencesDialog` with nested configuration groups
- **Account Management**: `AccountDialog` for provider API key setup

## Development Workflows

### Building & Distribution

#### Development setup

```bash
uv sync --frozen --group dev
```

#### Build standalone executable

```bash
uv run -m cx_Freeze build_exe
```

#### Create Windows installer (requires Inno Setup)

```powerShell
iscc win_installer.iss
```

#### Available VS Code tasks

- "compile translation file" (Babel message compilation)
- "build executable" (cx_Freeze build)
- "build windows installer" (Inno Setup)

### Testing & Debugging

- **Entry point**: `uv run -m basilisk`
- **Unit Tests**: `uv run -m pytest` for test suite in `tests/`
- **Debugging**: Use VS Code debugger with `launch.json` configuration
- **Command line args**: `--log-level DEBUG`, `--minimize`, `--language`, `--no-env-account`
- **Logs**: Written to user config directory, accessible via Help → View Log
- **Config location**: Uses `platformdirs.user_config_path()` for cross-platform config storage

### Test Infrastructure

- **Fixtures**: `tests/conftest.py` (global), `tests/presenters/conftest.py` (presenter-specific)
- **pytest-mock**: Use `mocker.patch()` / `mocker.patch.object()` — no `@patch` decorators or `with patch()` context managers
- **Shared presenter fixtures**: `base_mock_view`, `mock_account`, `mock_model`, `mock_engine`
- **Parametrize syntax**: Use tuple `("a", "b")` not string `"a,b"` for multi-parameter marks (PT006)
- **Subtests**: Use native pytest 9 `subtests` fixture with `with subtests.test(label=x):`
- **Mock views** for `ConversationPresenter` must set `view._is_destroying = False` explicitly
- Do **not** use bare `_` for tuple unpacking in tests — it shadows the translation builtin and breaks `_("Error")` calls

### Translation System

- **Babel-based**: Uses `_("string")` to mark translatable strings; builtin, no import needed
- **Context comment**: Use `# Translators:` (capital T) before the string to provide context for translators
- **Compilation**: `uv run setup.py compile_catalog` before building
- **Supported**: Multiple languages with automatic locale detection

## Coding Conventions

### Code Style

- **Indentation**: Tabs, not spaces
- **Line length**: 80 characters
- **Naming**: `snake_case` for variables/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants
- **Docstrings**: Google style with type hints for all public APIs
- **Quote style**: Preserve existing quotes; prefer double quotes for new code
- **Translation**: `_("string")` is a builtin — no import needed
- **Imports**: Grouped as standard library → third-party → local; sorted alphabetically
- **Future annotations**: Add `from __future__ import annotations` in all presenter and service modules

#### Format

```bash
uv run -m ruff format
```

#### Linting

```bash
uv run -m ruff check --fix
```

### wxPython Patterns

- **Event Binding**: Use `self.Bind(wx.EVT_*, self.on_*)` pattern consistently
- **Dialog Management**: Always call `dialog.Destroy()` after `ShowModal()`
- **Sizer Layout**: Use BoxSizer for responsive layouts, avoid fixed positioning
- **Accessibility**: Support screen readers with proper labels and NVDA integration
- **No wx in presenters**: Wx imports belong in views; use view proxy methods from presenters

### Conversation & Message Handling

- **Pydantic Models**: `Conversation`, `MessageBlock`, `Message` with proper validation
- **File Attachments**: Support for images, documents with automatic resizing and base64 encoding
- **Streaming**: Real-time message display using provider-specific streaming APIs
- **Persistence**: BSKC format (JSON-based) with migration support

### Provider Integration

- **Base Engine**: Inherit from `BaseEngine`, implement `client`, `models`, `completion` methods
- **Capabilities**: Declare supported features using `ProviderCapability` enum
- **Message Format**: Use `prepare_message_request/response` for provider-specific formatting
- **Error Handling**: Graceful degradation for unsupported features

### Configuration Management

- **Settings Classes**: Inherit from `BasiliskBaseSettings` for automatic YAML loading
- **Account Security**: Use `SecretStr` for API keys, support credential manager storage
- **Validation**: Leverage Pydantic validators for robust configuration validation

## Project-Specific Patterns

### Resource Cleanup

- `ConversationTab._is_destroying` flag — set to `True` in `cleanup_resources()`
- `cleanup_resources()` calls `presenter.cleanup()` and `ocr_handler.cleanup()`
- `ConversationPresenter.cleanup()`: stops completion (`skip_callbacks=True`), aborts recording, stops sound, flushes draft
- `HistoryPresenter.cleanup()`: destroys `_search_dialog`, resets presenter reference
- `MainFramePresenter.flush_and_save_on_quit()` and `close_conversation()` call `tab.cleanup_resources()`

### Singleton & IPC

- **Single Instance**: Mutex-based (Windows) / file-lock (POSIX) enforcement
- **IPC Communication**: Windows named pipes for file open and focus signals

### Accessibility Focus

- **Screen Reader Support**: Extensive NVDA integration
- **Keyboard Navigation**: Full keyboard accessibility
- **Audio Feedback**: Optional accessible output for status updates via `sound_manager`

### Windows Integration

- **System Tray**: Minimize to tray with context menu
- **Global Hotkeys**: System-wide shortcuts for window management and screen capture
- **File Associations**: Register `.bskc` conversation files with shell integration

Remember: This is a desktop application focused on accessibility, multi-provider LLM access, and professional conversation management. Prioritize user experience, accessibility, and reliable cross-provider functionality.
