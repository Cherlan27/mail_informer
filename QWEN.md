# QWEN.md

## Workflow

This repo runs the **agent-workflow** multi-model issue workflow. Qwen Code is
loaded here as one of the phase workers or as the coordinator — load the real
rules from the files below, not from this section (it is only a pointer).

- **Rules:** [`CONTRIBUTING.md`](CONTRIBUTING.md) and the project contract
  [`.claude/workflow.yaml`](.claude/workflow.yaml). Read both before phase work.
- **Coordinator role:** run `/agent-workflow:orchestrate-issue <issue>` — it picks
  a track, starts one worker per phase, and stops at Gates 1/2/3. Do not write code.
- **Worker role:** do only the phase your session was started for, keep artifacts
  short, and report in at most 5 lines.
- **Local flow:** when the cloud models are at their token limit, the flow runs
  on the local model via `--local` — see `CONTRIBUTING.md` §Local flow and the
  `local:` block in `.claude/workflow.yaml`.
- After a shipped issue, run the `/agent-workflow:adjust-workflow <issue>` retro.
