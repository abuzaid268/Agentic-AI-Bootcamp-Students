# Part 1 — Five Real Skills, Five Different Shapes

> These are not toy examples. All five are public, installed by real people,
> and doing real work today. We are going to look at them in a deliberate
> order, because each one is a **different shape of skill**.

By the end of this hour you should stop asking *"what is a skill?"* and start
asking *"which shape does my problem need?"*

---

## The thing to notice

Everyone's first instinct is that a skill is "a prompt in a folder." Two of
these five are exactly that — and they're excellent. The other three are not,
and the difference is the lesson.

| # | Skill | Shape | What it proves |
|:-:|---|---|---|
| 1 | **file-organizer** | instructions only — **zero code** | The cheapest useful skill is a well-written procedure. No install, no dependencies. |
| 2 | **canvas-design** | a **two-phase method** | A skill can impose a *process*, not just a format. Think first, render second. |
| 3 | **artifacts-builder** | instructions **+ executable scripts** | Push deterministic work into code. The model judges; the script builds. |
| 4 | **ui-ux-pro-max** | instructions **+ a large knowledge base** | At 192 rules and 79 styles, progressive disclosure stops being an optimisation and becomes the only way it can work. |
| 5 | **open-slide** | a skill **+ its own runtime** | A skill can ship an entire framework and let the agent drive it. |

Read down that last column. That is the arc of the whole session:
**no code → a method → code → knowledge → a runtime.**

---

## Before we start: what these all have in common

Every one of them is a **folder with a `SKILL.md` at the top**, and that file
starts with the same three lines:

```markdown
---
name: file-organizer
description: Intelligently organizes your files and folders... Reduces cognitive load...
---
```

That's it. That's the format.

Anthropic published it in October 2025 and released it as an **open standard**
in December 2025. It is now read by Claude Code, Claude.ai, the Claude API,
OpenAI Codex, Cursor, Gemini CLI, Antigravity and Windsurf — and by the
90-line runner you'll build yourself in Part 3.

> **Say this out loud, because it's the commercial point:** the skill you write
> this afternoon is not locked to one vendor. It is a folder. It outlives the
> tool you wrote it for.

---

## 1. file-organizer — the skill with no code in it

**Source:** `ComposioHQ/awesome-claude-skills` → `file-organizer/SKILL.md`

Open it and scroll. There is no `scripts/`. There is no `resources/`. There is
nothing but instructions — and yet it is one of the most-used skills on the
list.

What it actually contains:

- **When to use this skill** — "Your Downloads folder is a chaotic mess,"
  "You have duplicate files taking up space." Written as *symptoms*, not
  features, so the router can match a user's complaint to it.
- **A procedure** — understand scope → analyse current state → identify
  patterns → find duplicates → **propose a plan** → execute on approval.
- **The shell commands to run at each step** — `du -sh`, `find ... -exec md5`,
  and so on. It tells the agent *which* commands, so the agent doesn't invent
  worse ones.
- **A hard safety gate** — *"Always ask for confirmation before deleting."*

### Demo script (5 min)

1. Show the frontmatter. Two fields. That's the whole public API.
2. Scroll to **"Propose Organization Plan"** and read it aloud. Point out that
   it makes the agent show a plan *before* touching anything.
3. Run it on a genuinely messy folder. Let it produce the plan. **Do not
   approve it** — the demo is the plan, not the deletion.

### The question to ask the room

> "There is no code in this file. So what is doing the work?"

The answer: the model could already move files. What it lacked was a
**procedure** and a **stopping rule**. That is what the skill added. A skill
is not new capability — it is *captured judgement*.

---

## 2. canvas-design — the skill that makes the agent think first

**Source:** `ComposioHQ/awesome-claude-skills` → `canvas-design/SKILL.md`

This one produces posters and static art as `.png` / `.pdf`. What makes it
interesting is that it **refuses to let the agent start designing.**

It forces two phases:

```
Phase 1   write a DESIGN PHILOSOPHY  (a .md file — a manifesto, 4–6 paragraphs)
             ↓
Phase 2   express that philosophy on a canvas  (the .png / .pdf)
```

Phase 1 produces no artwork at all. It names a movement — *"Brutalist Joy,"
"Chromatic Silence"* — and describes how it manifests through space, colour,
scale, rhythm and hierarchy.

Only then does phase 2 render.

### Demo script (7 min)

1. Ask for a poster **without** the skill. You'll get centred text, a purple
   gradient, rounded corners. Keep it on screen.
2. Ask for the same poster **with** the skill. Watch it stop and write the
   philosophy first.
3. Put the two side by side.

### The question to ask the room

> "We changed no model, no tools, and no data. Why is the second one better?"

Because the skill **inserted a thinking step that the model would have
skipped.** Models are eager. They jump to output. A skill can slow them down
on purpose — and that is often the entire value.

Note also the file's blunt instruction to avoid *"excessive centered layouts,
purple gradients, uniform rounded corners, and Inter font."* Someone looked at
a hundred bad outputs and wrote the anti-pattern down. **That sentence is worth
more than any amount of model scale.**

---

## 3. artifacts-builder — the skill that ships executables

**Source:** `ComposioHQ/awesome-claude-skills` → `artifacts-builder/SKILL.md`

Now code appears. The skill is a four-step pipeline, and steps 1 and 3 are
**shell scripts, not prompts**:

```
1. bash scripts/init-artifact.sh <name>    ← scaffolds React + TS + Vite +
                                             Tailwind + 40 shadcn components
2. (the agent edits the generated code)    ← the only step the model does
3. bash scripts/bundle-artifact.sh         ← Parcel build, inlines everything
                                             into ONE self-contained .html
4. show the artifact to the user
```

### Demo script (8 min)

1. Show `SKILL.md` — four steps, two of them are `bash`.
2. Ask: *"why is the scaffold a script instead of instructions?"*

Let them answer. Then make it concrete: to scaffold that project by prompting,
the model would have to emit `package.json`, `tsconfig.json`, `tailwind.config.js`,
`.parcelrc`, and 40 component files — perfectly — **every single time**, at a
cost of tens of thousands of tokens, with a fresh chance to typo on each run.

The script does it identically, in two seconds, for zero tokens.

### The rule to write on the board

> **If it is deterministic, it belongs in a script. If it needs judgement, it
> belongs in the model.**
>
> Every check you move out of the prompt and into code is a check that can no
> longer be forgotten, argued with, or hallucinated as passed.

*(You saw this exact failure yesterday in the bridge project reviews: a rule in
a prompt is advisory. A gate in code is enforced.)*

---

## 4. ui-ux-pro-max — the skill that is mostly knowledge

**Source:** `github.com/nextlevelbuilder/ui-ux-pro-max-skill`

The numbers on the tin:

- **192** industry-specific reasoning rules
- **79** searchable UI styles
- **192** colour palettes
- **74** font pairings
- **119** UX guidelines
- **22** tech stacks

Ask for a spa landing page and it returns a complete design system: pattern,
style, palette with hex codes, typography with a Google Fonts link, key
effects, **anti-patterns to avoid**, and a pre-delivery accessibility checklist.

### Demo script (8 min)

1. Show the generated design system for one prompt. It's a striking output.
2. Now ask the real question:

> **"There are 192 rules in there. How many went into the context window?"**

Five searches ran. A handful of rules came back. The other ~185 never loaded.

3. Then push it: *"What would happen if all 192 loaded every time?"*

You'd blow the window, and — worse — you'd **bury the relevant rule in noise**.
More context is not more intelligence. This is `context rot`, and it's why
Module 6 exists.

### Why this is the most important demo of the five

The first three skills are small enough that you could cheat and paste them
into a system prompt. **This one you cannot.** It is the proof that progressive
disclosure is not a nicety — at scale it is the only thing that makes a large
skill library possible at all.

---

## 5. open-slide — the skill that brings its own runtime

**Source:** `github.com/1weiho/open-slide`

```bash
npx @open-slide/cli init my-slide
cd my-slide && pnpm dev
```

The scaffold ships with skills already wired in:

- **`/create-slide`** — drafts a deck end to end. Asks four scoping questions
  (topic & aesthetic, page count, text density, motion vs. static), plans the
  structure, writes the pages.
- **`/slide-authoring`** — the technical reference: the fixed 1920×1080 canvas,
  type scale, palette, layout rules. The agent reads this *before* writing.

Every slide is an arbitrary React component. The framework handles canvas,
scaling, navigation, hot reload and present mode — so the agent only has to do
the part agents are good at: **writing code**.

Then there's the loop that makes people sit up:

> present → click any element → leave a comment *("make this red", "shrink the
> headline")* → run `/apply-comments` → the agent edits the source → repeat.

Comments persist in the source as `@slide-comment` markers.

### Demo script (10 min)

1. Scaffold a deck live. Ask for 5 slides on any topic the room shouts out.
2. Run `pnpm dev`, present it.
3. Click an element, leave a comment, run `/apply-comments`, show the diff.

### The question to ask the room

> "Where does the skill end and the product begin?"

There isn't a clean line any more — and that is the point. `/slide-authoring`
is **design constraints as a loadable file**. The framework guarantees the deck
renders; the skill guarantees it renders *well*. Two different jobs, shipped
together.

---

## Wrapping Part 1 — the four questions

Before anyone writes a line of their own skill, they should be able to answer:

1. **What is the smallest useful skill?** → instructions and nothing else
   (file-organizer).
2. **What can a skill do that a prompt can't?** → force a *process*
   (canvas-design), carry *executables* (artifacts-builder), and stay dormant
   until needed.
3. **Why not just put it all in the system prompt?** → ui-ux-pro-max. 192 rules.
   Try it and watch quality fall.
4. **Is this vendor lock-in?** → no. It's a folder with a markdown file. Open
   standard since December 2025.

---

## Trainer notes

- **Time:** 45 min total. 5 / 7 / 8 / 8 / 10, plus ~7 for discussion.
- **If a demo won't run live**, fall back to reading the `SKILL.md` aloud. The
  file *is* the lesson; the output is only the evidence. Have screenshots ready.
- **Students without Claude Code can still follow.** Every `SKILL.md` here is
  readable on GitHub, and Part 3 runs on the Python + OpenRouter setup they
  already have from Module 5. Nobody is blocked.
- **The single sentence to repeat until it sticks:**
  *MCP is how an agent reaches a tool. A skill is how it knows how to do the job well.*
