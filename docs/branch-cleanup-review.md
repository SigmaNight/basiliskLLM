# Branch Cleanup Review — feat/dynamicModels, feat/reasoning-storage, feat/token-usage-block-properties, feat/audio-output

> Date: 2026-03-14

## Summary

The four feature branches were reviewed for cleanliness. Several issues were found:

### 1. Migration Contamination in feat/dynamicModels

**Current state:** feat/dynamicModels contains migrations 002 (audio), 003 (reasoning), and 004 (web_search_mode).

**Target state:**

- **feat/dynamicModels** should only have: 004 (web_search_mode), down_revision=001
- **feat/reasoning-storage** should add: 003 (reasoning), down_revision=004
- **feat/token-usage-block-properties** should add: 005 (usage/timing), down_revision=003
- **feat/audio-output** should add: 002 (audio), down_revision=005

**Migration chain:** 001 → 004 → 003 → 005 → 002

### 2. Model and Manager Contamination

feat/dynamicModels includes in `DBMessage` and `Message`:

- `reasoning` — belongs in feat/reasoning-storage
- `audio_data`, `audio_format` — belong in feat/audio-output

The database manager uses these fields. Splitting requires coordinated changes across branches.

### 3. IPC Test Flakiness — FIXED

`tests/ipc/test_ipc_architecture.py::TestBasiliskIpc::test_send_signal_no_receiver` and `test_multiple_signals` occasionally failed (timing/race on Windows). Fixed by increasing sleep times (0.1→0.15s for receiver start, 0.05→0.08s between signals, 0.2→0.3s for callback wait).

### 4. Code Coverage

- **master:** 56.15%
- **feat/dynamicModels:** 55.18% (slight decrease, expected due to new code)
- All branches: 805+ tests pass (excluding flaky IPC)

## Branch-Specific Findings

### feat/dynamicModels (based on master)

- **Correct:** dynamic_model_loader, provider engines, reasoning mode UI, web search, ResponsesAPIEngine, content_utils (base), reasoning_params_helper
- **Remove:** migrations 002, 003; DB model fields reasoning, audio_data, audio_format; manager code for those fields
- **Keep:** content_utils (handles legacy \`\`\`think format for streaming display)

### feat/reasoning-storage (based on feat/dynamicModels)

- **Correct:** reasoning storage, show/hide UI, content_utils display format change (<think></think>)
- **Add:** migration 003 (down=004)
- **Clean:** No audio or token-usage code

### feat/token-usage-block-properties (based on feat/reasoning-storage)

- **Correct:** usage_utils, TokenUsage, ResponseTiming, migration 005, block properties dialog
- **Clean:** No audio code

### feat/audio-output (based on feat/token-usage-block-properties)

- **Correct:** audio_utils, sound_manager, playback, DB persistence
- **Add:** migration 002 (down=005) — currently inherited from dynamicModels
- **Clean:** No token-usage or reasoning-storage specific code

## Recommended Actions

1. **feat/dynamicModels:** Remove 002, 003; update 004 down_revision to 001; remove reasoning/audio from models and manager
1. **feat/reasoning-storage:** Add migration 003 (down=004); add reasoning to models/manager
1. **feat/token-usage-block-properties:** Ensure 005 has down=003 (already correct)
1. **feat/audio-output:** Add migration 002 (down=005); ensure audio in models/manager
1. **IPC tests:** Add `@pytest.mark.flaky` or increase sleep for reliability
1. **Rebase:** Rebase feat/reasoning-storage → feat/token-usage → feat/audio-output onto cleaned feat/dynamicModels

## Complexity Note

The full cleanup requires significant coordinated changes because:

- DBMessage and Message models are shared
- Manager save/load logic is intertwined
- content_utils is used by both dynamicModels (legacy \`\`\`think) and reasoning-storage (<think></think>)

A pragmatic alternative: keep migrations 002, 003 in feat/dynamicModels for now (schema foundation), but document that the *code* that meaningfully uses them lives in the respective branches. The manager uses getattr(..., None) so it tolerates missing columns if models are adjusted.
