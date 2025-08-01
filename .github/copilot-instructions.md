# BasiliskLLM Coding Guidelines

## Architecture Overview

BasiliskLLM is a **wxPython desktop GUI** application that provides a unified interface for multiple LLM providers (OpenAI, Anthropic, Gemini, Mistral, Ollama, etc.).

### Key Components

- **Main Application**: `basilisk/main_app.py` - wxPython app initialization, IPC, auto-updates
- **GUI Framework**: `basilisk/gui/` - wxPython-based interface with conversation tabs, dialogs, preferences
- **Provider Engine**: `basilisk/provider_engine/` - Abstracted LLM provider implementations using `BaseEngine`
- **Configuration**: `basilisk/config/` - Pydantic-based settings with YAML persistence
- **Conversation System**: `basilisk/conversation/` - Pydantic models for messages, attachments, and persistence

### Provider Engine Pattern

Each LLM provider inherits from `BaseEngine` in `basilisk/provider_engine/base_engine.py`:

```python
class AnthropicEngine(BaseEngine):
    capabilities = {ProviderCapability.TEXT, ProviderCapability.IMAGE}

    @cached_property
    def client(self) -> Anthropic: ...

    def completion(self, new_block, conversation, system_message): ...
```

### Configuration Architecture

- **YAML-based**: Configuration stored in user config directory using `platformdirs`
- **Pydantic Models**: Type-safe config with validation (`basilisk/config/main_config.py`)
- **Account Management**: Secure API key storage with Windows Credential Manager support
- **Main Config file**: Contains the main configuration parameters for the app (langage, log level, update settings, network settings)
- **Conversation Profile**: a config file to define a profile for new conversation (account, system prompt, model, ETC)
- **Loading Order**: YAML files → Environment variables → Default values
- **Hot Reload**: Settings changes applied immediately without restart where possible

### UI Architecture & Component Division

#### Main Frame Structure (`basilisk/gui/main_frame.py`)

- **MainFrame**: Root window with menu bar, notebook tabs, and status bar
- **Notebook Tabs**: Each conversation runs in separate `ConversationTab`
- **System Tray**: `TaskBarIcon` for minimize-to-tray functionality
- **Global Hotkeys**: Windows-specific hotkey registration for screen capture

#### Dialog System

- **Modal Dialogs**: Account management, preferences, about dialog
- **Base Pattern**: Always call `dialog.Destroy()` after `ShowModal()`
- **Preferences**: `PreferencesDialog` with nested configuration groups
- **Account Management**: `AccountDialog` for provider API key setup

#### Conversation UI Components

- **ConversationTab**: Main chat interface inheriting from `BaseConversation`
- **PromptAttachmentsPanel**: Input area with file attachment support
- **Message History**: Scrollable display with accessibility support
- **Model Selection**: Provider/model picker with capability indicators

#### Component Communication

- **Event System**: wxPython event binding (`self.Bind(wx.EVT_*, self.on_*)`)
- **Configuration Updates**: Dialogs directly modify config objects
- **Tab Management**: MainFrame manages notebook and tab lifecycle
- **Cross-Component**: Use parent references and method calls for coordination

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

- **Entry point**: `uv run -m basilisk` or `uv run basilisk/__main__.py`
- **Unit Tests**: `uv run -m pytest` for test suite in `tests/`
- **Debugging**: Use VS Code debugger with `launch.json` configuration
- **Command line args**: `--log-level DEBUG`, `--minimize`, `--language`, `--no-env-account`
- **Logs**: Written to user config directory, accessible via Help → View Log
- **Config location**: Uses `platformdirs.user_config_path()` for cross-platform config storage

### Translation System

- **Babel-based**: Uses `_("string")` for translatable strings with `# translator:` context comments
- **Compilation**: `python setup.py compile_catalog` before building
- **Supported**: Multiple languages with automatic locale detection

## Coding Conventions

### Code Style

- **Indentation**: Tabs, not spaces
- **Naming**: `snake_case` for variables/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants
- **Docstrings**: Google style with type hints for all public APIs
- **Strings**: Double quotes, use `_("string")` for translatable text
- **Custtom builtin functons**: the translation function is defined as a builtin and you don't need to import it explicitly.
- **Imports**: Grouped as standard library, third-party, local imports; sorted alphabetically

#### format

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
- **Hot Reload**: Settings changes applied immediately without restart where possible

## Project-Specific Patterns

### Singleton & IPC

- **Single Instance**: Use `SingletonInstance` class to prevent multiple app instances
- **IPC Communication**: Windows named pipes for opening files and focus management
- **Signal Handling**: Cross-instance communication for file associations

### Accessibility Focus

- **Screen Reader Support**: Extensive NVDA integration with custom add-on
- **Keyboard Navigation**: Full keyboard accessibility with standard shortcuts
- **Audio Feedback**: Optional accessible output for status updates

### Windows Integration

- **System Tray**: Minimize to tray with context menu
- **Global Hotkeys**: System-wide shortcuts for window management and screen capture
- **File Associations**: Register `.bskc` conversation files with shell integration

Remember: This is a desktop application focused on accessibility, multi-provider LLM access, and professional conversation management. Prioritize user experience, accessibility, and reliable cross-provider functionality.
