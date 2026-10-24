## 1. Settings

- [x] 1.1 Red: tests that `MODEL_URL` defaults to `http://host.docker.internal:11434/v1`, that `MODEL_API_KEY` defaults to empty, that `ALLOW_REMOTE_MODEL` is false unless set to `true`, and that the key does not appear in `repr(cfg)`
- [x] 1.2 Green: replace `ollama_url` in `Config` with `model_url`, `model_api_key` (`repr=False`), `allow_remote_model`; update `load_config` and the old default test
- [x] 1.3 Red: test that `OLLAMA_URL` set without `MODEL_URL` fails for the model commands with a message naming `MODEL_URL`, and is ignored by other commands
- [x] 1.4 Green: add a `require_model_server` flag to `load_config` and the `OLLAMA_URL` check

- [x] 1.5 Red: tests that `MODEL_REASONING_EFFORT` defaults to empty and is read from the environment
- [x] 1.6 Green: add `model_reasoning_effort` to `Config` and `load_config`

## 2. Local or remote

- [x] 2.1 Red: table tests for `is_local_model_url`: `localhost`, `127.0.0.1`, `[::1]`, `host.docker.internal`, `192.168.1.5`, `10.0.0.2`, `172.16.0.1`, `169.254.1.1` are local; `api.openai.com`, `nas.fritz.box`, `8.8.8.8`, `172.32.0.1` are remote
- [x] 2.2 Green: implement it in `config.py` with `urllib.parse` and `ipaddress`, no DNS lookup
- [x] 2.3 Red: tests that `load_config(require_model_server=True)` fails for a remote address without `ALLOW_REMOTE_MODEL`, fails for a remote `http://` address with it, passes for a remote `https://` address with it, and passes for a local `http://` address without it
- [x] 2.4 Green: add the checks to `load_config`. Refactor while green

## 3. OpenAI-compatible client

- [x] 3.1 Red: change the fake server in `tests/test_analysis_model.py` to answer in the chat completions format (`choices[0].message.content`, `finish_reason`); test that a valid answer is decoded and that the request goes to `/v1/chat/completions` with `model`, `messages`, temperature 0, `seed`, `response_format` of type `json_schema` with `strict: true` and the schema, and no `tools` or `stream`
- [x] 3.2 Green: write `OpenAICompatibleClient` in `model.py` and remove `OllamaClient`
- [x] 3.3 Red: tests that a set key is sent as `Authorization: Bearer <key>` and that no `Authorization` header is sent without a key
- [x] 3.4 Green: add the header
- [x] 3.5 Red: tests that status 400, 401, 404, 429 and 500, a body without `choices`, a refused connection and a timeout raise `ModelUnavailable`; that the error text holds the status code but not the key, nor the error `message` of the body
- [x] 3.6 Green: map the errors as in design.md decision 3
- [x] 3.7 Red: tests that a non-empty `refusal`, `finish_reason` `length` or `content_filter`, and content that is not JSON raise `InvalidAnswer`
- [x] 3.8 Green: add these checks. Refactor while green

- [x] 3.9 Red: tests that a set reasoning effort is sent as `reasoning_effort` and that an empty one sends no reasoning field
- [x] 3.10 Green: add the `reasoning_effort` argument to the client

## 4. Wiring

- [x] 4.1 Red: CLI tests that `analyze` and `evaluate` with a remote address and no permission exit with 1 before connecting to the database, and that they build the client with `MODEL_URL`, the model name, the key and the reasoning effort
- [x] 4.2 Green: add one helper in `cli.py` that builds the client, use it in `_analyze` and `_evaluate`, pass `require_model_server` for both commands
- [x] 4.3 Check that analyzer tests that use a fake `ModelClient` pass unchanged

## 5. Compose, config, and docs

- [x] 5.1 Compose: analyzer gets `MODEL_URL` (default with `/v1`), `MODEL_API_KEY`, `MODEL_REASONING_EFFORT` (default empty) and `ALLOW_REMOTE_MODEL` (default `false`); remove `OLLAMA_URL`. Keep `extra_hosts`. The notifier and poller get none of them
- [x] 5.2 `.env.example`: replace `OLLAMA_URL` with `MODEL_URL`; add `MODEL_REASONING_EFFORT=none` for Ollama, commented `MODEL_API_KEY` (marked as a secret) and `ALLOW_REMOTE_MODEL` with a cloud example
- [x] 5.3 README: any OpenAI-compatible server works; Ollama setup with `/v1`, `MODEL_REASONING_EFFORT=none` and `OLLAMA_KEEP_ALIVE=10m`; a cloud section that says plainly which mail data leaves the machine and how to opt in; LAN servers by IP; `evaluate` with `MODEL_URL`; the upgrade step from `OLLAMA_URL`; update the intro line "Mail text never leaves your machine"
- [x] 5.4 Update `openspec/config.yaml` context: the analyzer stage exists and talks to an OpenAI-compatible server, local by default

## 6. Check the real stack

- [x] 6.1 Run `evaluate` with `qwen3.5:4b` through Ollama `/v1` and `MODEL_REASONING_EFFORT=none`. Compare with the first-round results: no missed `urgent` mail, similar time per mail.
- [x] 6.2 Build the image and run the analyzer against Ollama (done as a one-off container on a throwaway database, not by restarting the live stack). Check that new mails get results and the healthcheck stays green
- [x] 6.3 Start the analyzer with a public `MODEL_URL` and no `ALLOW_REMOTE_MODEL`. Check that it fails at start and reads no mail
- [ ] 6.4 Optional, with a cloud key: run `evaluate` against one cloud model with `ALLOW_REMOTE_MODEL=true` and check that strict schema answers come back

## 7. Finish

- [x] 7.1 Run the full test suite with `TEST_DATABASE_URL` and show the result
- [x] 7.2 Run `openspec validate openai-compatible-model-api --strict`. Check the README against the final behavior
