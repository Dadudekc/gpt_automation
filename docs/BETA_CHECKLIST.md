# Beta‑Ready Checklist

Use this checklist to ensure all critical pieces are in place before declaring
the project ready for beta testing.

## Functionality
- [ ] Local LLM and ChatGPT modes verified.
- [ ] GUI allows selecting, previewing, and processing files.
- [ ] Self‑heal workflow updates files as expected.
- [ ] Batch processing handles multiple files without crashes.
- [ ] Deployment and backup directories populate correctly.

## Testing
- [ ] Unit tests cover core modules (`AutomationEngine`, `GuiHelpers`, etc.).
- [ ] Integration test for end‑to‑end processing.
- [ ] Manual test plan executed on Windows, macOS, and Linux.
- [ ] Test failures log actionable messages.

## Documentation
- [ ] PRD and roadmap published in `docs/`.
- [ ] Setup instructions for dependencies (ChromeDriver, local models).
- [ ] User guide for running the GUI and command‑line options.

## Stability
- [ ] Application runs for at least one hour without memory leaks.
- [ ] Error conditions handled gracefully (missing files, driver failures).
- [ ] Logs rotate or truncate to prevent unlimited growth.

## Go/No‑Go
- [ ] All critical bugs resolved.
- [ ] Team review sign‑off.
- [ ] Backup of source code and build artifacts completed.
