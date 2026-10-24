---
name: reviewing-and-optimizing-prs
description: Use when asked to review a pull request of this project, to look at or answer review comments on it (also draft or pending ones), or to optimize a PR branch for code and architecture best practice before merge.
---

# Reviewing and optimizing a PR

## Overview

A review here is not done when it lists findings. It ends with each finding proven, fixed test-first on the PR branch, recorded in the OpenSpec change, and answered on the PR. **Claim nothing you have not reproduced or tested.**

## Steps

1. **Collect every comment.** `gh pr view <n> --comments` does not show a review that is still pending (draft). Also run:
   ```bash
   gh api repos/<owner>/<repo>/pulls/<n>/reviews --jq '.[] | {id, state, user: .user.login}'
   gh api repos/<owner>/<repo>/pulls/<n>/reviews/<id>/comments --jq '.[] | {path, diff_hunk, body}'
   gh api repos/<owner>/<repo>/pulls/<n>/comments   # submitted line comments
   ```
2. **Read whole files, not only diff hunks.** Use `git diff main` and read each changed module in full.
3. **Review against the checklist below.** Prove each suspected bug with a short script or a failing test before you report it.
4. **Report** one table: number, severity, finding, fix. Answer each reviewer comment with a decision and a reason. When you disagree in part, say what you do instead and why.
5. **Record in OpenSpec.** If behavior changes, add a scenario to the delta spec and a decision to `design.md`. Add a "Review fixes" task group with red/green/refactor tasks. Run `openspec validate <change> --strict`.
6. **Fix test-first.** Watch each test fail for the right reason. Do refactors only while the suite is green.
7. **Run the full suite with Postgres** on a throwaway container. **Never** use the live database on port 5432: the test fixture drops all tables.
   ```bash
   docker run -d --rm --name mi-test-pg -e POSTGRES_PASSWORD=test -e POSTGRES_USER=mail_informer \
     -e POSTGRES_DB=mail_informer_test -p 127.0.0.1:55432:5432 postgres:16
   TEST_DATABASE_URL=postgresql://mail_informer:test@127.0.0.1:55432/mail_informer_test .venv/Scripts/python -m pytest -q
   docker stop mi-test-pg
   ```
   The result must say **0 skipped**. Skipped DB tests hide broken stubs.
8. **Commit and answer.** Use conventional commits (`fix:`, `refactor:`, `docs:`). Push to the PR branch. Post one PR comment with the table and the answers. A pending review cannot get thread replies until its author submits it, so quote the comment in your PR comment.

## Checklist

| Area | Check |
|---|---|
| Layers | `config.py` only reads env vars. Rules are pure modules without I/O. `db.py` holds all SQL. `cli.py` only wires. |
| Constants | Keep them next to the rule that uses them. No shared `constants.py`. |
| Secrets | Never in logs, error texts, `repr` (`field(repr=False)`) or URLs in messages. |
| Mail content | Goes only to the configured model server. Server error bodies may echo it, so never log them. |
| HTTP clients | `urllib` follows redirects and resends `Authorization` to the new host. Refuse redirects. Check the scheme with `urlparse`, not `startswith`. |
| Errors | A server problem must not count as a failed attempt for a mail. A per-mail problem must not stop the pass. |
| Data | Writes are idempotent. Schema changes are new migrations. Rollback is described. |
| Tests | Stubs take keyword arguments. Fake servers stop fast (`serve_forever(poll_interval=0.01)`). |
| Live system | Do not rebuild the running stack or edit `.env` without asking. |

## Common mistakes

| Mistake | Fix |
|---|---|
| "No review comments" after `gh pr view` | Fetch the pending reviews (step 1). |
| Reporting a security bug from reading code alone | Reproduce it first, then turn the repro into the red test. |
| Green suite with 150+ skipped tests | Start the throwaway Postgres (step 7). |
| Fixing behavior without a spec scenario | Update the delta spec first (step 5). |
| Changing unrelated code | Add it to the report as a note only. |
