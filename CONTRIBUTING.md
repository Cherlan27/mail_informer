# Contributing

How changes are made in this repository, by humans and by coding agents.
Project contract: [`.claude/workflow.yaml`](.claude/workflow.yaml). Project rules:
[`openspec/config.yaml`](openspec/config.yaml) and [`CLAUDE.md`](CLAUDE.md).

## One issue, one change, one branch

Every piece of work starts from a GitHub issue and maps one-to-one onto
(Trivial track: no OpenSpec change, see *Tracks*):

- an **OpenSpec change** under `openspec/changes/<change-name>/`,
- a **git worktree** and **branch** `issue-<number>-<short-name>`,
- a **pull request** that says `Closes #<issue>`.

Issues labelled `refinement needed` are refined first: open questions answered,
acceptance criteria and Definition of Done verifiable.
Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, …).

## Workspace

- The main checkout stays on `main`. Work happens in a per-issue worktree branched from `origin/main`.
- A fresh worktree needs `pip install -c constraints.txt -e .[dev]` before tests or dev servers run.
- Postgres (127.0.0.1:5432) is a shared port: only one worktree may run the local database at a time.

## Lifecycle of a change

Each phase is its own agent session with the model from `.claude/workflow.yaml`.
The reviewer is never the agent that wrote the code.

| # | Phase | What happens | Model (default) |
|---|---|---|---|
| 1 | **Propose** | `/opsx:propose`: proposal (`Closes #<issue>`), delta specs, design, tasks. An architecture decision gets its ADR and doc updates here, *before* implementation. | `opus` |
| | ⏸ **Gate 1** | A human approves the proposal. | human |
| 2 | **Apply** | `/opsx:apply`, task by task, red → green → refactor, one commit per task group, until `make check` passes twice in a row. | `sonnet` |
| 3 | **Review** | `/agent-workflow:review-change`: spec conformance, test evidence, project rules, correctness, security, deployment. Writes `review.md`, changes no code. | `opus` |
| | ⏸ **Gate 2** | A human decides per finding: fix, skip, or defer. | human |
| 4 | **Fixes** | Implements findings with `Decision: fix`, sets `Status: fixed`, runs `make check` twice. A second, scoped review round follows only if a CRITICAL or MAJOR finding was fixed; at most two rounds. | `sonnet` |
| 5 | **Archive & PR** | `/opsx:archive` on the branch, PR with `Closes #<issue>`. | `sonnet` |
| | ⏸ **Gate 3** | A human approves the merge and the deployment (`docker compose up -d --build`). | human |

**Verification** – `make check` must pass twice in a row at the end of phases 2
and 4 (the second run catches flaky tests). CI runs the test suite on every
pull request.

**Tracks** – the coordinator proposes a track before phase 1 and the human
confirms it. In doubt, take the higher track. If a change turns out to need an
ADR, a dependency, or a migration, it moves up.

| Track | When | Flow | Gates |
|---|---|---|---|
| **Full** | everything that is not small | phases 1–5 above | 1, 2, 3 |
| **Small** | no ADR, no new dependency, no migration, at most about 5 tasks, one area only | 3 workers: propose + apply in one session (no `design.md`), one review round, fixes + archive + PR | 3; Gate 2 only for a CRITICAL or MAJOR finding |
| **Trivial** | docs, config, typo; at most 2 files; no new behavior; no source code | no OpenSpec change, no review: branch, `make check`, PR | 3 |

The Trivial track is the only exception to "one issue, one OpenSpec change".

**Local model** – only on the Small track, with propose and apply split into two
workers. If its run leaves verification failing, or it has made no commit and
ticked no task after 10 minutes, the apply goes to `sonnet`.

**Style** – simple technical English, short sentences, no filler. Reports are at
most 5 lines, findings at most 6, gate summaries at most 10. The coordinator
talks to the human in the human's language.

**Archive before merge** – `/opsx:archive` syncs delta specs into `openspec/specs/`
and moves the change to `openspec/changes/archive/` on the branch, so
`main` never holds a finished-but-unarchived change.

**Retrospective** – after each issue, `/agent-workflow:adjust-workflow <issue>`
proposes small workflow fixes and records the approved ones in
[`docs/workflow-retros.md`](docs/workflow-retros.md), marked *generic* or *project*.

## Orchestrating with Orca

A coordinator (`claude` · `sonnet`) owns one issue. It follows
`/agent-workflow:orchestrate-issue`, starts one supervised Orca worker per phase,
checks each result itself, and stops at every gate. It does not write code.

```
orca worktree create --name issue-<n>-<name> --no-parent \
  --reference <issue-url> --agent claude --model sonnet \
  --prompt "/agent-workflow:orchestrate-issue <n>"
```

## Adapting OpenSpec

OpenSpec skills and commands in `.claude/` and `.opencode/` are generated and
overwritten on update: do not edit them. Project rules go into
`openspec/config.yaml`. Quote YAML entries that contain `": "` or `" #"` (the rest
of the line is dropped as a comment). Check with
`openspec instructions tasks --change <name> --json` that the rules arrive.
