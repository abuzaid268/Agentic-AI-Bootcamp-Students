<!-- JHF-BRAND -->
<div align="center" style="padding:28px 20px; background:#ffffff; border:2px solid #e0e0e0; border-radius:12px;">
  <p style="margin:0 0 16px 0;">
    <img src="../assets/jhf-logo.png" alt="Jerusalem High-Tech Foundry (JHF)" height="54" style="vertical-align:middle; margin:0 22px;" />
    <img src="../assets/comcec-logo.png" alt="COMCEC - Cooperation for Development" height="72" style="vertical-align:middle; margin:0 22px;" />
  </p>
  <h1 style="color:#1a3c5e; margin:6px 0;">Agentic AI Bootcamp</h1>
  <h3 style="color:#0078d4; margin:4px 0; font-weight:600;">Module 5B &middot; Agent Skills &mdash; Learner Handout</h3>
  <hr style="border:0; border-top:1px solid #0078d4; width:60%; margin:16px auto;" />
  <p style="font-size:13px; color:#555;">Phase 3 &middot; Tools &amp; Memory &nbsp;|&nbsp; comes right after MCP (M5) &nbsp;|&nbsp; 4 hours</p>
</div>

# Module 5B — Agent Skills

> **Lead Trainer:** [Alaaldin Ahmed](https://www.linkedin.com/in/alaaldin-ahmed-260266150)
>
> **Duration:** 4 hours · **Prereq:** M5 (Tools, APIs & MCP).
> **You need:** your M5 environment, `OPENROUTER_API_KEY` in `.env`, a browser.
>
> In M5 you gave your agent **tools**. Today you give it **skills** — reusable,
> self-contained playbooks it loads only when a task needs them.

![Where we are in the stack — Tools](../assets/diagrams/augmented-llm-tools.png)

> 🧩 **Builds on:** Tool Use + MCP (M5) · procedural memory (M6). See
> **[PATTERNS.md](../PATTERNS.md)** and **[MENTAL-MODELS.md](../MENTAL-MODELS.md)**.

---

## Learning Objectives

After this module you can:

1. **Explain** how a skill differs from a tool, an MCP server, and a system prompt.
2. **Read** a real, production skill and name its *shape*.
3. **Author** a skill as a portable folder — instructions plus optional scripts and resources.
4. **Implement** progressive disclosure and measure what it saved you.
5. **Prove** a skill fires on the right task and stays dormant on the wrong one.
6. **Design** a skill that delegates to sub-agents, and say why that beats one big prompt.

---

## 1. The shift: from connection to competence

Two years of agent tooling have answered two different questions, in order.

**2024–2025 asked: how does an agent *reach* things?** The answer was tools,
then function calling, then — because every vendor had reinvented the same
wiring — **MCP**. That was Module 5. You built a server, connected a client, and
borrowed somebody else's server without reading its source. Connection: solved.

**2026 is asking a different question: how does an agent know how to do the job
*well*?** An agent with fifty tools and no procedure is an intern with building
access and no training. It can reach everything. It still does the job badly.

That is the gap skills fill.

> **The one-sentence version, and the one to memorise:**
> **MCP is how an agent reaches a tool. A skill is how it knows how to do the job well.**

They are not competitors. In production all three layers run together:
**MCP for access · tools for actions · skills for behaviour.**

### Why this happened now

Anthropic published the Agent Skills format in **October 2025** and released it
as an **open standard in December 2025**. It is now read by Claude Code,
Claude.ai, the Claude API, OpenAI Codex, Cursor, Gemini CLI, Antigravity and
Windsurf.

That matters commercially, so say it plainly: **the skill you write today is a
folder, and it outlives the tool you wrote it for.** Same story as MCP — a
format nobody owns beats a feature somebody owns.

---

## 2. Skill vs. Tool vs. MCP vs. System Prompt

| | What it is | Analogy | Reach for it when… |
|---|---|---|---|
| **Tool / Function** | one callable action | a **phone call** to a specialist | the agent must *do* a discrete thing |
| **MCP** | a standard for connecting tools to any agent | the **standard hiring form** | you want tools reusable across agents (M5) |
| **Skill** | a bundle of instructions + resources for a whole task | a **playbook** off the shelf | there is a right way to do a recurring job |
| **System prompt** | text present on *every* turn | a **tattoo** | it genuinely applies to everything |
| **Fine-tuning** | behaviour baked into weights | **months of training** | stable, high-volume, worth the cost |

**The distinction that matters:** a tool answers *"what action can I take?"*
A skill answers *"how do we do this kind of task properly, and what do I need?"*
A skill often *uses* tools. It sits above them.

**And the one people actually get wrong:** the difference between a skill and a
system prompt is **not** the content — it's that a skill is **absent until
summoned**. A skill that fires on every request has become a system prompt, and
you've paid for the folder without buying the benefit.

---

## 3. Anatomy — what's inside

```
my-skill/
├─ SKILL.md          # required. name + description + instructions
├─ scripts/          # optional. deterministic work
│   └─ check.py
└─ resources/        # optional. templates, rules, reference data
    └─ template.md
```

`SKILL.md` opens with frontmatter:

```markdown
---
name: my-skill
description: <one line — this is the entire public API>
---
```

### The description is the whole API

At discovery time the router sees **only** `name` and `description` — roughly
100 tokens per skill. Not your instructions, not your scripts. If the
description is wrong, nothing else you wrote will ever run.

**Write the symptom the user will type, not the feature you built.**

| ✗ | ✓ |
|---|---|
| `A skill for documents.` | `Turn a meeting transcript into dated action items. Use when the user asks for action items, follow-ups, or "who owns what".` |

`file-organizer` — the most-used skill we look at today — lists its triggers as
*"Your Downloads folder is a chaotic mess."* A symptom, in the user's voice.

### The body: three sections, in order

```markdown
## When to use this      ← Fires on: ... / Does NOT fire on: ...
## Steps                 ← numbered, unambiguous, name the scripts
## Rules                 ← the non-negotiables
```

Nobody skips *Steps*. Everybody skips *Does NOT fire on*. That line is what
keeps your skill dormant — and dormancy is half your grade.

---

## 4. The five shapes

The single most useful thing from today. A skill is not one thing:

| Shape | Demo | The lesson |
|---|---|---|
| 📄 **instructions only** | `file-organizer` | The cheapest useful skill has no code at all. It adds a *procedure* and a *stopping rule*. |
| 🔁 **a method** | `canvas-design` | A skill can force a thinking step the model would have skipped. Philosophy first, render second. |
| ⚙️ **+ executable scripts** | `artifacts-builder` | Scaffolding by prompt costs thousands of tokens and can typo. A script costs zero and cannot. |
| 📚 **+ a knowledge base** | `ui-ux-pro-max` | 192 rules. You *cannot* paste this into a prompt. Proof that disclosure is mandatory, not optional. |
| 🧩 **a runtime** | `open-slide` | A skill can ship a whole framework and let the agent drive it. |

And a sixth we build ourselves: **an orchestrator** (`lab-grader`) — see §7.

---

## 5. Progressive disclosure — why skills scale

Three stages:

1. **Discovery (cheap).** The agent sees each skill's name + description. ~100
   tokens each.
2. **Load on demand.** On a match, it opens *that one* `SKILL.md` in full.
   Typically under 5,000 tokens.
3. **Deep resources.** Scripts and large references load **only** when actually
   used.

Measured on our own runner, with three skills:

```
  menu shown to the router .... ~235 tokens
  if we had loaded ALL of them. ~1,481 tokens
  we actually loaded .......... ~397 tokens (jhf-brief)
  SAVED ....................... ~1,084 tokens
```

Now scale it. At **100 skills**: menu ~8,000 tokens, one body ~400. Load
everything and you're at ~40,000 tokens before the user speaks — and the
relevant instruction is buried under 99 irrelevant ones.

> **More context is not more intelligence.** Precision falls as irrelevant
> material grows. That is `context rot` — the idea Module 6 is built on. A
> skill you're not using should cost you almost nothing.

---

## 6. Determinism belongs in code

Anything **countable, checkable, or formattable** should be a script, not a hope.

> **A rule in a prompt is advisory. A gate in code is enforced.**

You watched this fail live in yesterday's bridge-project reviews: a submission's
prompt said "verify the headline," the model didn't verify it, and it reported
success anyway. Stating the instruction more firmly only moved the gap. Moving
the check into code closed it.

Test: *could this be wrong and still look right?* If yes, it belongs in a script.

---

## 7. Skills that run agents — the closing idea

A skill is not only instructions. **A skill can start other agents.**

Our `lab-grader` grades a submission against five criteria by spawning **five
sub-agents**, one per criterion:

```
lab-grader (a skill)
    │
    ├── sub-agent 1 ──► sees ONLY criterion 1 + the submission
    ├── sub-agent 2 ──► sees ONLY criterion 2 + the submission
    ├── ... ×5
    │
    └── parent aggregates five verdicts into one report
```

**Why not one prompt with five questions?** The **halo effect**. The model reads
criterion 1, forms an impression, and marks the rest to match. Exam boards mark
question-by-question for exactly this reason.

Two consequences, both real:

1. **No anchoring** — examiner 4 can't be swayed by a mark it never saw.
2. **The parent's context stays small** — it sees five verdicts, never the
   reasoning behind them. The submission could be 50 pages.

> This is why skills matter to agentic systems, and it's the note we close on:
> **tools give an agent hands. MCP gives it reach. Skills give it a craft — and
> when the job is big enough, a skill hires other agents to help.**

---

## 8. Today's Lab (preview)

- **Part 1** — five real skills, five shapes. Watch, then read the source.
- **Part 2** — build one skill together.
- **Part 3** — run the runner; measure your own disclosure saving.
- **Part 4** — claim one of **15 scenarios**, build your skill, show it.

Full steps: **`M5B-Lab-Worksheet.md`**.

---

## 9. Deliverables (graded)

1. **A working skill folder** — `SKILL.md` + at least one script or resource
   that is actually called.
2. **Two transcripts** — it fires correctly · it stays dormant correctly.
3. **The token report** from `skill_runner.py`.
4. **Three sentences** — why a skill and not a prompt; its narrow scope; what
   you pushed into code.

Rubric: `skill-runner/skills/lab-grader/resources/rubric.md`. Run `lab-grader`
on yourself first.

---

## 10. Key Terms

| Term | Meaning |
|---|---|
| **Agent Skill** | A reusable folder of instructions (+ optional scripts/resources) an agent loads on demand. Open standard since Dec 2025. |
| **`SKILL.md`** | The instruction file: frontmatter (`name`, `description`) + body. |
| **Progressive disclosure** | Show names/descriptions first; load the full body only on a match; load resources only when used. |
| **Discovery / routing** | Matching a request to a skill using its description alone. |
| **Dormancy** | A skill correctly *not* firing. Half the grade. |
| **Shape** | What kind of skill it is: instructions · method · scripts · knowledge · runtime · orchestrator. |
| **Halo effect** | One judgement contaminating the next. The reason `lab-grader` uses five separate sub-agents. |
| **Sub-agent** | A second agent with its own fresh context, given one job, returning one answer. |
| **Context rot** | Accuracy falling as irrelevant context grows. The reason disclosure exists. |

---

## 11. Quiz (5 min)

1. In one sentence: how is a **skill** different from a **tool**? And from a
   **system prompt**?
2. Your skill fires on every single request. What is wrong, and in which file?
3. Name three of the five **shapes**, with an example of each.
4. Why can't `ui-ux-pro-max` simply be pasted into a system prompt?
5. Give one thing you'd move from your prompt into a **script**, and say how
   you'd know it was working.
6. `lab-grader` spawns five sub-agents instead of asking once. Name the failure
   mode it's avoiding — and the second benefit that falls out for free.

---

<div align="center" style="padding:14px; border-top:2px solid #0078d4; margin-top:30px;">
  <img src="../assets/jhf-logo.png" alt="JHF" height="26" style="vertical-align:middle; margin:0 12px;" />
  <img src="../assets/comcec-logo.png" alt="COMCEC" height="36" style="vertical-align:middle; margin:0 12px;" />
  <p style="color:#888; font-size:12px; margin-top:8px;">JHF Agentic AI Bootcamp &mdash; Module 5B &middot; Organized by JHF &middot; in partnership with COMCEC</p>
</div>
