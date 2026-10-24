## Context

`mail_informer/analysis/model.py` has one client, `OllamaClient`, that posts to Ollama's own `/api/chat` with `format` (JSON schema), `think: false`, `keep_alive`, temperature 0 and a fixed seed. It raises `ModelUnavailable` for server problems and `InvalidAnswer` for bad answers; the analyzer and `evaluate` only depend on the `ModelClient` protocol (`chat_json(messages, schema)`). `cli.py` builds the client from `OLLAMA_URL` and `ANALYZER_MODEL`. The current spec promises that mail content never leaves the machine. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**
- One client for every server that speaks the OpenAI chat completions API, Ollama included.
- Keep the `ModelClient` protocol and its two error types unchanged, so the analyzer, `evaluate`, retry logic and health checks do not change.
- Make sending mail to a remote server a conscious, visible decision, checked before any mail is read.

**Non-Goals:**
- No streaming, no tool calls, no batching across mails.
- No cost tracking or token counting.
- No DNS lookups to decide if a server is local.

## Decisions

### 1. One OpenAI-compatible client replaces `OllamaClient`

`OpenAICompatibleClient(base_url, model, api_key=None, timeout=120.0)` posts to `<base_url>/chat/completions`. Ollama is reached through its `/v1` endpoint, so the default `MODEL_URL` becomes `http://host.docker.internal:11434/v1`.

- *Rejected: keep both clients behind a `MODEL_PROVIDER` switch.* Two code paths to test and document for a small gain (Ollama-only `think` and `keep_alive`). The user chose one path.
- *Rejected: the `openai` Python package.* A new dependency for one HTTP call. `urllib` already handles it, and the fake server tests stay simple.

### 2. Request body

```json
{
  "model": "<ANALYZER_MODEL>",
  "messages": [...],
  "temperature": 0,
  "seed": 7,
  "response_format": {
    "type": "json_schema",
    "json_schema": {"name": "answer", "strict": true, "schema": <schema>}
  }
}
```

No `tools`, no `stream`. The existing `CLASSIFY_SCHEMA` and `SUMMARIZE_SCHEMA` already meet strict-mode rules (all fields required, `additionalProperties: false`), so prompts and `PROMPT_VERSION` stay. `seed` is a hint; servers that ignore it still work.

- *Rejected: `json_object` mode.* It only promises some JSON, not our fields and enums. `rules.py` would catch it, but more mails would fail.

### 3. Mapping answers to the two error types

| Server answer | Result |
|---|---|
| Cannot connect, timeout, socket error | `ModelUnavailable` |
| Any HTTP error status (400, 401, 403, 404, 429, 5xx) | `ModelUnavailable` |
| 200 but body is not JSON, or has no `choices[0].message` | `ModelUnavailable` |
| `message.refusal` is a non-empty string | `InvalidAnswer` |
| `finish_reason` is `length` or `content_filter` | `InvalidAnswer` |
| `message.content` is not valid JSON | `InvalidAnswer` |
| Otherwise | decoded JSON |

Every HTTP error counts as a server problem, also 400. A 400 is usually a setup error (wrong model name, schema not supported) that hits every mail. Counting it per mail would mark all mails `failed` after three passes. The cost: if one mail alone causes a 400, the run stops at that mail every time. The analyzer health check then turns `unhealthy`, which is visible.

- *Rejected: 400 as `InvalidAnswer`.* One bad setting would burn the attempts of up to 50 mails per pass.

Error messages carry the status code and, if present, the `error.type` / `error.code` fields of the body. They never carry the error `message` text (a server may echo input), the request body, or the key.

### 4. Settings

| Variable | Default | Meaning |
|---|---|---|
| `MODEL_URL` | `http://host.docker.internal:11434/v1` | Base address of the API |
| `MODEL_API_KEY` | empty | Sent as `Authorization: Bearer <key>` if set |
| `MODEL_REASONING_EFFORT` | empty | If set (for example `none`), sent as `reasoning_effort`. Empty: field not sent |
| `ALLOW_REMOTE_MODEL` | `false` | Must be `true` to use a remote address |
| `ANALYZER_MODEL` | required for `analyze` | Unchanged |

`Config` drops `ollama_url` and gains `model_url`, `model_api_key`, `model_reasoning_effort`, `allow_remote_model`. The key is excluded from the dataclass `repr` (`field(repr=False)`), so a logged config cannot leak it.

If `OLLAMA_URL` is set and `MODEL_URL` is not, `load_config` fails for `analyze` and `evaluate` with "OLLAMA_URL is replaced by MODEL_URL (add /v1 for Ollama)". Silently ignoring it would send requests to the default address instead of the one the user set.

### 5. Local or remote

A pure function `is_local_model_url(url) -> bool` in `config.py` decides from the URL alone:

- local: host is `localhost`, `host.docker.internal`, or a literal IP address that is loopback, private (10/8, 172.16/12, 192.168/16, fc00::/7) or link-local;
- remote: every other host name or IP address.

`load_config` runs the check when the command needs the model server (`analyze`, `evaluate`): remote without `ALLOW_REMOTE_MODEL=true` fails; remote with `http://` fails even when allowed, because the key and mail text would cross the internet in plain text. The check happens before the database is opened, so no mail is read.

- *Rejected: resolve the host name and check the IP.* The answer can change between check and request, and split DNS makes it unreliable. A LAN server with a host name (for example `nas.fritz.box`) must be given by its IP, or be allowed as remote over HTTPS. The README says so.
- *Rejected: no guard, the URL alone is the decision.* The spec promised local-only so far. A typo or a copied example `.env` should not send mail to a cloud service.

### 6. Wiring

`cli.py` builds the client in one helper, used by `_analyze` and `_evaluate`. `docker-compose.yml` passes `MODEL_URL`, `MODEL_API_KEY` and `ALLOW_REMOTE_MODEL` to the analyzer only; the notifier and poller never see them. `extra_hosts` stays for the Ollama default.

### 7. Reasoning effort is a setting, not a default

`MODEL_REASONING_EFFORT` is sent as `reasoning_effort` when it is not empty. Ollama needs `none` for `qwen3.5:4b`. Cloud models that do not reason may answer HTTP 400 to the field, so the code never sends it on its own.

- *Rejected: always send `none`.* Breaks such cloud models: every pass would end with `ModelUnavailable`.
- *Rejected: send `none` automatically for local addresses.* Hidden behavior that depends on the address, and a local vLLM or llama.cpp server may not accept the field either.
- Cost: an Ollama user must add `MODEL_REASONING_EFFORT=none` to `.env` (the example file and README say so). Without it, answers are slow and may time out.

## Risks / Trade-offs

- [Ollama through `/v1` lets thinking models think, since `think: false` is gone] → Measured with `qwen3.5:4b`: one small request took 5 s with a reasoning trace and an `evaluate` run timed out; with `reasoning_effort: "none"` the same request took 0.5 s. So `MODEL_REASONING_EFFORT=none` is needed for Ollama (see decision 7).
- [Ollama unloads the model after 5 idle minutes without `keep_alive`] → The analyzer runs every 5 minutes, so a reload can happen each pass. Set `OLLAMA_KEEP_ALIVE=10m` on the Ollama server; the README says so.
- [A remote provider stores or trains on mail text] → Opt-in only, default stays local, README states plainly what leaves the machine (sender, subject, first part of the body).
- [Cost and rate limits on a cloud API] → At most 50 mails per pass and two calls per mail bound the volume. A 429 stops the pass without marking mails failed; the next pass retries.
- [Server claims strict schema support but ignores it] → `rules.py` still checks every answer; a bad answer counts as a failed attempt as today.
- [Crash mid-run, duplicate runs] → Unchanged. Results are written per mail with the existing idempotent writes and the analyzer lock.
- [API key leaks] → Only in `.env` and the analyzer environment; not in `repr`, logs, or error messages. A test checks the key does not appear in a raised error.

## Migration Plan

1. In `.env`, replace `OLLAMA_URL=...` (if set) with `MODEL_URL=<same address>/v1`. Without either, the default points at Ollama's `/v1` on the host.
2. In `.env`, add `MODEL_REASONING_EFFORT=none` for Ollama. On the Ollama host, set `OLLAMA_KEEP_ALIVE=10m` and restart Ollama.
3. `docker compose up -d --build`.
4. For a cloud model: set `MODEL_URL`, `MODEL_API_KEY`, `ANALYZER_MODEL`, `ALLOW_REMOTE_MODEL=true`, run `evaluate` with it first.

No data migration. Existing results keep their model name; changing the model does not re-analyze mails (only a new `PROMPT_VERSION` does).

Rollback: run the previous image and put `OLLAMA_URL` back in `.env`. Results written by the new client are in the same format and stay valid.
