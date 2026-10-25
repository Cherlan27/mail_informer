## Why

The analyzer can only talk to Ollama through its own `/api/chat` API. This rules out cloud models (OpenAI, OpenRouter, Mistral, ...) and other local servers (vLLM, llama.cpp, LM Studio), which all speak the OpenAI chat completions API. Some users have no GPU for a good local model, or want to compare a cloud model with `evaluate`.

## What Changes

- Replace the Ollama client with one client for the OpenAI-compatible chat completions API (`POST <base>/chat/completions`). Ollama keeps working through its own `/v1` endpoint.
- The answer is forced into the existing JSON schemas with `response_format: {"type": "json_schema", "strict": true}`. The existing checks in `rules.py` still validate every answer.
- New settings: `MODEL_URL` (base address, default `http://host.docker.internal:11434/v1`) and an optional `MODEL_API_KEY`, sent as a bearer token and never logged.
- New guard: mail content goes to a model server outside this machine or the local network only when `ALLOW_REMOTE_MODEL=true` is set. Without it, the analyzer and `evaluate` refuse to start with a remote address. A remote address must use `https://`.
- A refusal or a cut-off answer from the model counts as an invalid answer for that mail. Auth errors, rate limits and other HTTP errors count as "model server unavailable", as today.
- **BREAKING**: `OLLAMA_URL` is removed. If it is still set and `MODEL_URL` is not, the analyzer fails at start with a message that names the new setting.
- **BREAKING**: Ollama-only options (`think: false`, `keep_alive`) are no longer sent. Keep-alive moves to the Ollama server setting `OLLAMA_KEEP_ALIVE`.

## Non-goals

- No provider-specific SDK (no `openai` package). The standard library stays enough.
- No automatic fallback between servers, and no use of two models at once.
- No change to prompts, schemas, categories, the bulk guard, or `PROMPT_VERSION`.
- No change to how results are stored. No migration.
- No per-account choice of model. One model server serves all mails.
- No `json_object` fallback for servers that do not support `json_schema`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `mail-analysis`: "Mail content stays local" becomes "Mail content goes only to the configured model server" with an explicit opt-in for remote servers. New requirement for model server settings (address, key, HTTPS for remote). "Model server unavailable" covers auth and rate-limit errors. Refused or cut-off answers count as invalid answers.

## Impact

- Code: `mail_informer/analysis/model.py` (new client replaces `OllamaClient`), `mail_informer/config.py` (new settings and the remote check), `mail_informer/cli.py` (wiring for `analyze` and `evaluate`).
- Tests: `tests/test_analysis_model.py` (fake server speaks the OpenAI format), `tests/test_config.py`.
- Deploy: `docker-compose.yml` and `.env.example` (`MODEL_URL`, `MODEL_API_KEY`, `ALLOW_REMOTE_MODEL`; `OLLAMA_URL` removed). README sections on Ollama, `evaluate`, and privacy.
- Data: none. Stored results keep the model name. Existing results stay valid.
- Dependencies: none new.
- Privacy: with `ALLOW_REMOTE_MODEL=true`, sender, subject, and the first part of every mail body leave the machine. The default stays local.
