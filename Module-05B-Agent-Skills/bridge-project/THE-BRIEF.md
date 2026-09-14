# Bridge Project 2 — Forge a skill

**Between Module 5B and Module 6.** Budget about 3 hours. Work alone.

---

## The short version

1. **Find or invent a skill** that solves a real problem *you personally have*.
2. **Build it.**
3. **Prove it works** — and prove it stays quiet when it should.
4. **Open a pull request** to [The Skill Foundry](https://github.com/Alaaldin97/Agentic-AI-Skill-Foundry).
5. **Review somebody else's.**

That's it. No report, no slides.

> ### 🔥 The Skill Foundry is live
> **[jhf-skills.azurewebsites.net](https://jhf-skills.azurewebsites.net)**
>
> Browse what already exists, see what's currently **in review**, and copy a
> one-line install command for anything merged. Your skill appears there
> automatically — in review when you open the PR, in the catalog when it merges.

---

## Why this is a pull request, not an issue

Last bridge project you submitted an issue. This one is different on purpose.

| An issue | A pull request |
|---|---|
| A conversation that gets closed | **Files that get merged** |
| I read it, grade it, and it's over | Everyone can install it, forever |
| Your work ends in a thread | Your work ends in a library |
| Nobody reviews it but me | You get reviewed — and you review |
| Dies with the course | **Grows after it** |

The Skill Foundry is a real repo that stays alive after Week 10. What you merge
there in Week 6 is still installable in Week 40, by you and by everyone else.

> **This is also the point.** You are not doing an exercise. You are making a
> contribution to a shared library that other people will depend on. That is a
> different standard, and you should feel the difference.

---

## Step 1 — Find the problem first

**Do not start by browsing skill repos.** Start with your own week.

Ask yourself: *what did I do more than twice this month that followed the same
shape every time?* That is your candidate. Some real examples:

- rewriting the same status update from a commit log
- reformatting exported data into the one layout your team accepts
- writing the first draft of a bug report from a stack trace
- turning meeting notes into tasks with owners and dates
- checking a document against a style guide nobody remembers

If nothing comes to mind, **then** go looking. Good hunting grounds:

- **[The Foundry itself](https://jhf-skills.azurewebsites.net)** — check first. Somebody may have solved it
- The `find-skills` skill already in the Foundry — it searches three directories for you
- [`awesome-claude-skills`](https://github.com/ComposioHQ/awesome-claude-skills)
- The 15 scenarios in [`../scenarios/SCENARIOS.md`](../scenarios/SCENARIOS.md)
- [Open skill requests](https://github.com/Alaaldin97/Agentic-AI-Skill-Foundry/issues) — somebody already asked for these

**Adapting an existing skill is allowed and encouraged** — as long as you say so
in `meta.yml` under `source:` and you genuinely improved it. Copying one
unchanged is not a contribution.

---

## Step 2 — Pick the smallest shape that works

| Shape | Contains | Use when |
|---|---|---|
| **Instructions only** | Just `SKILL.md` | The model already knows how — it needs telling *when* |
| **+ a method** | A forced process | It rushes to output and skips the thinking |
| **+ scripts** | `scripts/` | Something must happen the *same way* every time |
| **+ knowledge** | `resources/` | Facts it does not have and cannot guess |
| **+ a runtime** | A toolchain | The output needs real tooling to exist |

Most good skills are the first two. **Reaching for scripts too early is the most
common mistake** — if the model can already do the step reliably, a script just
adds something that can break.

---

## Step 3 — Test it properly

This is where the marks are, and it is the part people rush.

**Both directions are graded.**

### ✅ Does it fire?
Type the symptom, **never the skill name**. If you have to say *"use my
skill…"*, it failed — fix the description and try again.

### 🔇 Does it stay quiet?
Write a prompt that is *close but wrong* and confirm it does **not** load.

> `linkedin-marketing` must stay dormant on *"write me a cover letter."*
> Close — both are professional writing. But wrong.

A skill that fires on everything is **worse than no skill**. It burns context on
every turn, for everyone who installs it. With thirty skills in the Foundry, one
greedy description degrades the whole library.

Both results go in `EVIDENCE.md`. Paste what actually happened — real terminal
output, real chat text. Not a description of it.

---

## Step 4 — Submit

**You do not have write access to the Foundry — nobody does.** You work on your
own copy (a *fork*) and ask for it to be pulled in. This is how every open source
project works, and it's why the library can be open to everyone without anyone
being able to break it.

```bash
# 1. Click "Fork" on github.com/Alaaldin97/Agentic-AI-Skill-Foundry
# 2. Clone YOUR fork — note the username is yours, not mine
git clone https://github.com/YOUR-USERNAME/Agentic-AI-Skill-Foundry.git
cd Agentic-AI-Skill-Foundry
git checkout -b skill/my-skill-name

cp -r skills/_TEMPLATE skills/my-skill-name
# ... build it, test it, write the evidence ...

python scripts/validate_skill.py skills/my-skill-name   # ← run before you push

git add skills/my-skill-name
git commit -m "Add skill: my-skill-name"
git push origin skill/my-skill-name
```

Then open the PR from the link git prints. The template asks you five questions —
answer them.

> ### 📖 [Full step-by-step guide → UPLOAD-A-SKILL.md](https://github.com/Alaaldin97/Agentic-AI-Skill-Foundry/blob/main/UPLOAD-A-SKILL.md)
> Includes a **no-terminal route** (entirely in the GitHub website) if you'd
> rather not use git, plus a troubleshooting section for every error you're
> likely to hit.

> **That validator is not advice, it's a gate.** CI runs the same script on your
> PR and blocks the merge if it fails. Run it locally first and you will never be
> surprised.
>
> Notice what that means: everything in `CONTRIBUTING.md` is a suggestion you
> could ignore. The script is not. **A rule in prose is advisory; a gate in code
> is enforced.** That is Module 5B applied to the repo you are contributing to.

### What happens after you open it

1. **Checks run in about a minute.** Red isn't failure — it's a to-do list. Push
   to the same branch and it re-runs.
2. **Your skill appears under "In review"** on the live site for everyone to see.
3. **You'll get review comments.** Expect them. A first review on a first skill
   almost always finds something, usually in the description.
4. **Nothing merges without approval.** When it does, it's in the catalog and
   anyone can install it with one command.

---

## Step 5 — Review one other PR

**Required.** Pick a classmate's open PR and leave one concrete comment.

👉 **[See what's in review right now →](https://jhf-skills.azurewebsites.net#review-section)**

| Check | The question |
|---|---|
| Description scope | Would this fire on something unrelated? |
| Dormancy evidence | Did they really test a near-miss, or invent one? |
| Determinism | Is a must-happen rule sitting in prose where the model can skip it? |
| Weight | Is the body bloated with things that belong in `resources/`? |
| **The real one** | **Would I install this?** |

*"Looks good"* is not a review and will not count. Quote a line and say something
about it.

---

## How it's graded

| | Weight | What I'm looking for |
|---|---|---|
| **It works** | 30% | Fires on the symptom, unprompted |
| **It stays quiet** | 25% | A real near-miss, correctly ignored |
| **Evidence** | 20% | Real transcripts. Not descriptions of transcripts |
| **Right shape** | 15% | Smallest shape that solves it. No unnecessary scripts |
| **Your review** | 10% | One specific, useful comment on someone else's PR |

**Pass is 4 of 5 categories.** The two I weight hardest are the two that are
about *restraint* — staying quiet, and not over-building. Those are the hard
parts.

---

## Due

**Before Session 7.** PRs open earlier get reviewed earlier, and you can push
fixes right up to the merge — so opening a rough PR on day two is strictly better
than a polished one an hour before the deadline.

---

## If you get stuck

1. **`403 Permission denied` on push** → you cloned my repo instead of your fork.
   Two-command fix:
   ```bash
   git remote set-url origin https://github.com/YOUR-USERNAME/Agentic-AI-Skill-Foundry.git
   git push origin skill/my-skill-name
   ```
2. **It won't fire** → the description describes your feature, not the user's
   symptom. Rewrite it as the sentence a stranger would type.
3. **It fires on everything** → no `Does NOT fire on:` clause. Add one, name the
   near-misses.
4. **VS Code doesn't see it** → malformed frontmatter. VS Code skips bad files
   **silently**. Check with **Chat: Open Customizations → Skills**.
5. **CI is failing** → run `python scripts/validate_skill.py skills/<yours>`
   locally. Same script, same result, faster feedback.
6. **Still stuck** → the
   [troubleshooting section](https://github.com/Alaaldin97/Agentic-AI-Skill-Foundry/blob/main/UPLOAD-A-SKILL.md#troubleshooting)
   covers every common error. Then post in the group chat — somebody has hit it
   already.

---

<div align="center">
<sub>Agentic AI Bootcamp · Jerusalem High-Tech Foundry × COMCEC</sub>
</div>
