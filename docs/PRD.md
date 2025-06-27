# Product Requirements Document (PRD)

## Overview
`gpt_automation` is a desktop application that streamlines code refactoring and
self‑healing by leveraging both local large language models and the OpenAI
ChatGPT web interface. The application provides a GUI for selecting files,
processing them through AI models, running basic tests, and deploying updated
versions. The goal is to reduce manual code maintenance while keeping the human
in control of the automation workflow.

## Goals
- Offer a consistent interface for local LLM and ChatGPT workflows.
- Simplify code refactoring, bug fixing, and batch processing of files.
- Provide minimal setup so developers can run the tool locally without complex
dependencies.

## Key Features
1. **Model Flexibility** – Support switching between local models and ChatGPT.
2. **GUI File Browser** – Browse, preview, and select project files.
3. **Automated Refactoring** – Send file contents to the model and save the
   response as a refactored file.
4. **Self‑Healing** – Repair code using AI and save the corrected output.
5. **Batch Processing** – Process multiple files with a shared prompt.
6. **Testing Hook** – Placeholder test runner to validate AI output before
   deployment.
7. **Deployment and Backup** – Move validated files to a deployment directory
   and keep backups automatically.
8. **Logging** – Provide clear logs of every action for troubleshooting.

## Non‑Functional Requirements
- **Cross‑Platform Compatibility** – Should run on major OSes with Python 3.10+
  and ChromeDriver installed.
- **Local Execution** – Ability to run fully offline when using a local LLM.
- **Minimal External Dependencies** – Keep third‑party libraries lightweight.
- **Usability** – GUI should be straightforward with clear status messages.
- **Extensibility** – Easy to add new models or processing steps via the
  `ModelRegistry` and controller classes.

## Success Metrics
- User can process a single file end‑to‑end (refactor, test, deploy) in under
  two minutes.
- Batch processing can handle at least ten files without crashing.
- Error logs provide actionable feedback for any failed step.
