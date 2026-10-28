# mail_informer

Polls several mail accounts (Gmail and IMAP), archives new mails in Postgres,
rates them with an LLM, and pushes `urgent`/`important` mails to a Home Assistant webhook.

Project rules: [`openspec/config.yaml`](openspec/config.yaml).
Full workflow: [`CONTRIBUTING.md`](CONTRIBUTING.md).
Project contract: [`.claude/workflow.yaml`](.claude/workflow.yaml).

## Workflow

Rules agents need most:

- One issue = one OpenSpec change = one worktree and branch (`issue-<number>-<short-name>`) = one PR with `Closes #<issue>`. Never develop in the main checkout. Exception: the Trivial track (docs/config, at most 2 files) has no OpenSpec change.
- Each phase is its own agent session with the model from `.claude/workflow.yaml`. A coordinator (`/agent-workflow:orchestrate-issue`) picks a track (Full, Small, Trivial; see `CONTRIBUTING.md`) and stops for a human after propose, after review, and before merge/deploy. Do only your phase.
- When the cloud models (claude/codex) are at their token limit, run the same flow on the local model: `/agent-workflow:orchestrate-issue <issue> --local`. Every phase (including the review) uses `local.model`; the review round is marked in `review.md` as a local-model review and you decide each finding at Gate 2. See `CONTRIBUTING.md`.
- A phase is done when `make check` passes (twice in a row after apply and fixes). Tick a task only after its test or command passed in your session. Tests must be deterministic (no equality of two clock reads).
- Never delete, skip, or loosen a test, or weaken the check, to make it pass. If you are blocked or a test looks wrong, stop and report it; do not work around it.
- Review (`/agent-workflow:review-change`) writes findings to `openspec/changes/<change>/review.md` and changes no code; fixes implement only findings with `Decision: fix`.
- Run `/opsx:archive` on the branch before merging.
- A fresh worktree needs the `setup` command from `.claude/workflow.yaml` (`pip install -c constraints.txt -e .[dev] && trail build`).
- Never edit generated OpenSpec skills/commands in `.claude/` or `.opencode/`; put project rules in `openspec/config.yaml`.
- Style: simple technical English, short sentences, no filler. Reports at most 5 lines.
- After a shipped issue, `/agent-workflow:adjust-workflow <issue>` records workflow changes in `docs/workflow-retros.md`.
