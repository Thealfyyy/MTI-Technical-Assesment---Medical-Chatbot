---
project: MTI Medical Knowledge Chatbot
purpose: intake for new feature/change requests, written by Adham, triaged into TASKS.md by the agent
last_updated: 2026-11-04
---

# Feature & Change Requests

This file is where **you** write down new ideas, features, or changes as
they occur to you — instead of typing them into the agent's chat box.
Write as much or as little structure as you want; the point is to get it
down somewhere durable and elaborate on it properly instead of firing off
a half-formed prompt.

**This is not append-only** (unlike `PROGRESS_LOG.md`) — it's a working
list, like `TASKS.md`. Entries move through statuses as the agent
triages them. The agent should never rewrite your `Description` or `Why`
— only update `Status` and add its own `Triage note` underneath.

## How this feeds into the rest of the system

1. You add a new entry here, `Status: New`.
2. At the start of a session (per the `project-continuity` skill), the
   agent reads this file after `BRIEF.md`/`PROGRESS_LOG.md`/`TASKS.md`.
3. For each `New` entry, the agent either:
   - turns it into one or more tasks in `TASKS.md` and sets this entry's
     status to `Queued`, with a note pointing at the task(s), or
   - if the request is unclear or conflicts with current scope
     (`BRIEF.md` §5), leaves it as `New` and adds a `Triage note`
     asking you a specific question or flagging the conflict, rather
     than guessing.
4. Once the linked task is actually done, the agent sets this entry to
   `Done` (it's already reflected as done in `TASKS.md` too — this is
   just so the request list itself stays accurate).

## Entry template (copy this for each new request)

\`\`\`
## REQ-<n> — <short title> — <date written>

**Status:** New

**Type:** Feature | Change | Bug fix | Question / investigation

**Description:**
<what you want, in your own words — as much detail as you want>

**Why:**
<what problem this solves, or why it matters now — helps the agent
judge priority and whether it fits current scope>

**Acceptance criteria (optional):**
- <how you'll know this is actually done>

**Notes for you to fill in (optional):**
<constraints, things to avoid, related existing code/areas>

**Triage note (agent fills this in, doesn't touch your fields above):**
<e.g. "Queued as Day 4 task in TASKS.md" or "Unclear — do you mean X or
Y?" or "This conflicts with the out-of-scope list in BRIEF.md §5,
confirm before I build it">
\`\`\`

---

<!-- Start writing requests below this line. Number them REQ-1, REQ-2, etc. -->
