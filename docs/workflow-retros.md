# Workflow retrospective

After each shipped issue, `/agent-workflow:adjust-workflow <issue>` records approved
workflow changes here: time, token cost, friction, and the change made (marked
*generic* or *project*).

## 2026-11-14 · Issue #11 · add-sender-prefilter

Track full · code map trail · 17 min worker time (propose 3, apply 9, review 3, ship 2; wall clock 6 days, mostly waiting for Docker and a resumed session) · 4 workers · 1 review round ·
findings C/M/m 0/0/1 · findings judged wrong 0 · escaped defects 0 ·
recommendations accepted unchanged yes

Human feedback: nothing in particular. Workers did not report trail as missing; no earlier `none` run to compare with yet.

| # | Change | Expected effect | File | Scope | Status |
|---|---|---|---|---|---|
| A1 | `make test` fails when `TEST_DATABASE_URL` is unset (baseline passed with 159 Postgres tests skipped, ship check with 178) | A local `make check` pass always includes the Postgres tests | `Makefile` | project | applied |
| A2 | Document the throwaway test DB on 127.0.0.1:55432; `shared_ports` becomes 55432 (5432 is the live stack) | No gate question about the test DB; workers get the setup from CONTRIBUTING | `CONTRIBUTING.md`, `.claude/workflow.yaml` | project | applied |
| A3 | Gate 3: run `gh pr checks <pr> --watch` before `gh pr merge`; push no commits after the PR is open (the Gate 3 log commit re-ran CI and the first merge was refused) | Merge succeeds on the first try | orchestrate-issue skill | generic | proposed for plugin repo |
| A4 | Commit graft's key order in `.claude/settings.json`; `eol=lf` for it and `.trail/*.cjs` | New worktrees start with a clean `git status`; accept checks need no exceptions | `.claude/settings.json`, `.gitattributes` | project | applied |

Previous changes: none (first retro).
