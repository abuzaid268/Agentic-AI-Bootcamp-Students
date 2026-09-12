# Part 4 — Pick a Scenario, Build a Skill

> **45 minutes. One scenario each. No two people in the room build the same one
> if we can help it.**

Open **`PICK-A-SCENARIO.html`** in a browser to claim one interactively — it
shuffles, filters by shape and difficulty, and gives you a brief you can paste
straight into your submission issue. Or just read the list below and pick.

---

## The rules

1. **One scenario. Not two.** Narrow scope is the graded criterion, and the
   fastest way to fail it is to be ambitious now and vague later.
2. **Your skill must have a `scripts/` or `resources/` file that actually gets
   called.** If everything happens in the prompt, you have written a prompt.
3. **You must show it staying dormant.** Two transcripts: one where it fires,
   one where it correctly does not.
4. **You may search for an existing skill first.** Genuinely — go and look at
   `ComposioHQ/awesome-claude-skills` (1000+ skills). If one already exists for
   your scenario, read it, then write yours and explain in two sentences what
   you did differently. *Reading a good skill before writing one is not
   cheating. It is how everybody learns this.*

---

## The shapes, from Part 1

Each scenario is tagged with the shape it most naturally takes. If you can't
decide, pick a 🟩 and finish it well.

| Tag | Shape | From the demos |
|:-:|---|---|
| 📄 | instructions only | file-organizer |
| 🔁 | a two-phase method | canvas-design |
| ⚙️ | instructions + a script | artifacts-builder |
| 📚 | instructions + a knowledge base | ui-ux-pro-max |

Difficulty: 🟩 comfortable · 🟨 some work · 🟥 ambitious

---

## The 15

### 1. Meeting → Action Items  ⚙️ 🟩
**The problem.** A meeting transcript is a wall of text. Somewhere in it are
six commitments, and they will be forgotten by Thursday.
**Build.** Transcript in → a table of `owner | action | due date | quote`.
**The script.** Validates every row: owner is a real name, due date parses to a
real date, and there is a supporting quote. Any row that fails is rejected —
so the model cannot invent a deadline nobody agreed to.
**Done when.** It refuses to output an action item with no quote behind it.

### 2. House-Style Code Reviewer  📚 🟨
**The problem.** Every team has rules that live in people's heads, and new
joiners break them for six months.
**Build.** A diff or file in → review comments against *your* written rules.
**The resource.** `resources/house-rules.md` — 10–15 real rules with a good and
bad example each.
**Done when.** It cites the rule number for every comment, and stays silent
where no rule applies. A reviewer that comments on everything is noise.

### 3. README Generator  ⚙️ 🟩
**The problem.** The project works, and nobody can start it.
**Build.** A folder path in → a README with what it is, how to run it, and
where to start reading.
**The script.** Scans the folder for entry points and dependency manifests.
**Done when.** Anything it could not determine appears under *"Questions I
could not answer"* instead of being guessed. *(Reference implementation:
`skill-runner/skills/repo-onboarder/` — read it, then do better.)*

### 4. Bilingual Post Writer — Arabic + English  📄 🟨
**The problem.** You write the English, then translate it, and the Arabic reads
like a translation.
**Build.** One idea in → two native-sounding posts out, each written *for* its
audience rather than translated across.
**The resource.** A style card per language: tone, length, hashtag rules,
whether emoji are acceptable.
**Done when.** The Arabic is not a word-for-word mirror of the English, RTL
punctuation is correct, and Latin product names stay intact inside Arabic text.

### 5. Dataset Profiler  ⚙️ 🟨
**The problem.** Someone sends you a CSV and asks "can we use this?"
**Build.** CSV in → a data-quality report: row count, nulls per column, types,
outliers, duplicate keys, and a verdict.
**The script.** Does all the counting. The model only writes the verdict and
the "what I'd fix first" section.
**Done when.** Every number in the prose traces to the script's output.

### 6. API Doc Writer  ⚙️ 🟨
**The problem.** The endpoints exist. The docs are a Slack thread.
**Build.** A source file in → endpoint docs: method, path, params, responses,
one real `curl` example each.
**The script.** Extracts route definitions so the doc can't miss an endpoint.
**Done when.** Running the generated `curl` examples actually works.

### 7. Interview Prep Coach  📚 🟩
**The problem.** "I have an interview Tuesday" is not a study plan.
**Build.** Role + seniority in → 12 likely questions, a model answer skeleton
for each, and a self-scoring rubric.
**The resource.** A question bank organised by role and competency.
**Done when.** The questions change substantially between two different roles.
If a backend role and a design role get the same list, your retrieval is fake.

### 8. Bug Report Triager  ⚙️ 🟨
**The problem.** "It's broken" is not a bug report.
**Build.** A raw report in → severity, component label, reproduction steps, and
the specific missing information to request.
**The script.** A completeness gate — version, environment, expected vs actual,
steps. Missing fields become the "please provide" list.
**Done when.** It assigns severity from written criteria, not vibes, and says
which criterion it matched.

### 9. Deck Outliner  🔁 🟨
**The problem.** People open PowerPoint and start typing. That's why the deck
is bad.
**Build.** Topic + audience + time in → a slide-by-slide outline with one
message per slide and a speaker note.
**The method.** Phase 1: write the **argument** in prose — no slides allowed.
Phase 2: only then break it into slides. *(This is canvas-design's trick, moved
to a new domain. It pairs naturally with open-slide.)*
**Done when.** Phase 1 produces zero slides, and you can feel the difference.

### 10. Receipt & Expense Organiser  📄 🟩
**The problem.** A folder of 60 files called `IMG_4471.jpg` and `scan (3).pdf`.
**Build.** Messy folder in → a proposed rename-and-sort plan plus a monthly
total.
**The safety gate.** Proposes. Never moves or deletes without an explicit
confirmation. Steal this pattern directly from file-organizer.
**Done when.** It shows the plan and stops. A skill that deletes without asking
is a bug with a nice description.

### 11. SQL Explainer & Optimiser  📚 🟨
**The problem.** A 60-line query, no comments, and the author left.
**Build.** Query in → plain-English explanation, then concrete improvements.
**The resource.** A checklist of common problems: `SELECT *`, missing index
hints, `N+1`, implicit casts, functions wrapped around indexed columns.
**Done when.** It explains *why* each suggestion helps, not just what to change.

### 12. Test-Case Generator  ⚙️ 🟥
**The problem.** Tests get written for the happy path and nothing else.
**Build.** A function in → a table of cases: happy path, edge cases, error
cases — then the actual test file.
**The script.** Runs the generated tests and reports pass/fail.
**Done when.** At least one generated test **fails** and correctly identifies a
real gap in the function. A suite that always passes has told you nothing.

### 13. Brand Image Brief  🔁 🟩
**The problem.** "Make it look premium" is not art direction.
**Build.** Product + audience in → an art-direction brief: mood, palette with
hex codes, composition, what to avoid.
**The method.** Two phases, straight from canvas-design: name the aesthetic
first, then specify it. Include an explicit **anti-pattern** section.
**Done when.** Two different products produce genuinely different briefs.

### 14. Study Plan Builder  ⚙️ 🟩
**The problem.** Exam in five weeks, syllabus in twelve sections, no plan.
**Build.** Syllabus + exam date + hours per week in → a dated weekly plan with
checkpoints.
**The script.** Does the date arithmetic and refuses to schedule past the exam
date or beyond the stated hours.
**Done when.** Changing the exam date changes the whole plan correctly. Ask any
model to do date maths in prose and watch it drift.

### 15. Release Notes Writer  ⚙️ 🟨
**The problem.** `git log` is for you. A changelog is for them.
**Build.** A commit range in → release notes grouped into Added / Changed /
Fixed, written for users.
**The script.** Runs `git log` and parses it. The model only translates commit
messages into user-facing language.
**Done when.** `fix: null check in svc layer` becomes something a customer
understands — and purely internal commits are dropped, not padded out.

---

## What you submit

Open an issue on the students repo using the project-submission template, and
include:

1. **Your scenario number and title.**
2. **Your skill folder** — `SKILL.md` plus at least one script or resource.
3. **Two transcripts** — fires correctly · stays dormant correctly.
4. **The token report** from `skill_runner.py` showing the disclosure saving.
5. **Three sentences:** why this is a skill and not a prompt, what its narrow
   scope is, and what you deliberately pushed into code instead of the model.

Graded against `skill-runner/skills/lab-grader/resources/rubric.md` — the same
rubric the `lab-grader` skill uses. You can run it on yourself before you
submit. You are encouraged to.

---

## Showcase — last 20 minutes

Two minutes each, and only three things:

1. **The description line.** Read it out. That single line is your skill's
   entire public API.
2. **Fire it.** Once.
3. **The number.** What did progressive disclosure save you?

No slides. Live, or a recorded terminal.
