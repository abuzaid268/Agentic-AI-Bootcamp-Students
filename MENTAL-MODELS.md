<!-- JHF-BRAND -->
<div align="center" style="padding:24px 20px; background:#ffffff; border:2px solid #e0e0e0; border-radius:12px;">
  <p style="margin:0 0 14px 0;">
    <img src="assets/jhf-logo.png" alt="Jerusalem High-Tech Foundry (JHF)" height="50" style="vertical-align:middle; margin:0 20px;" />
    <img src="assets/comcec-logo.png" alt="COMCEC - Cooperation for Development" height="66" style="vertical-align:middle; margin:0 20px;" />
  </p>
  <h2 style="color:#1a3c5e; margin:6px 0;">Agentic AI Bootcamp — Mental Models</h2>
  <p style="font-size:13px; color:#555;">Simple analogies you can carry through the whole course. Reread this page whenever a concept feels abstract.</p>
</div>

# Mental Models & Analogies

Agent AI has a lot of jargon. These plain-language pictures cut through it. Each one is reused in the module where it's taught — keep this page open as your "cheat sheet."

> These are **original teaching analogies** written for this course, synthesizing ideas from our reference books (see `FURTHER-READING.md`). They're meant to build intuition first; the precise details come in each module.

---

## 1. The big one: an Agent = an LLM + modules

**An LLM on its own is like a brilliant, very well-read intern who:**
- answers only from memory (what they read during training),
- forgets everything the moment each question ends,
- and never leaves the room (can't look anything up or take action).

**To turn that intern into an *agent*, you give them four things:**

| You add… | Real term | What it does | Taught in |
|---|---|---|---|
| a **to-do list** | Planning | break a goal into steps | M3 |
| a **notebook** | Memory | remember within and across tasks | M6 |
| a **phone** | Tools | look things up and take action | M5 |
| a **habit of double-checking** | Reflection | review and improve their own work | M4 |

> **The model to remember:** **Agent = Brain (LLM) + Planning + Memory + Tools**, all tied together by a **loop** (M1).

---

## 2. The agent is a **project manager**

An agent behaves like a good project manager given a *goal*, not a script:
1. **Understands the goal** (the request).
2. **Plans** — breaks it into steps (M3).
3. **Delegates** to specialists — calls tools (M5).
4. **Remembers** what's done and what was learned (M6).
5. **Checks** the result and redoes it if needed (M4).
6. Knows when to **stop** (budgets & guardrails — M1, M11).

If you only remember one analogy, remember this one.

---

## 3. Workflow vs. Agent = **recipe vs. chef**

- A **workflow** is a **recipe**: fixed steps in a fixed order. Reliable, predictable, cheap. *You* decided the steps in advance.
- An **agent** is a **chef**: given "make a good dinner," it decides what to cook and how, adapting as it goes. More capable, but more expensive and less predictable.

> **Rule:** if a recipe reliably solves it, use the recipe. Reach for a chef only when the steps can't be fixed in advance. (See the "Agent vs. Workflow" checklist in M1.)

---

## 4. The LLM is a **reasoning engine**, not a database

- Ask it a fact and it *reconstructs* an answer from training — sometimes wrong (a **hallucination**).
- So we don't trust its memory for specifics; we **hand it the facts** at runtime (that's RAG / memory — M6).
- Analogy: *an open-book exam beats a from-memory exam.* RAG gives the model the open book.

---

## 5. Memory has four "places" — like an office

| Memory type | Office analogy | Example |
|---|---|---|
| **Working** (short-term) | what's **on your desk** right now | the current conversation |
| **Episodic** | your **diary** of what happened | "I already searched arXiv" |
| **Semantic** | the **company wiki** | your product docs (via RAG) |
| **Procedural** | the **staff handbook** | the system prompt / rules |

**Context engineering** (M6) is just *keeping your desk tidy*: put the right notes in the right order, and don't bury the important one under clutter.

---

## 6. Tools are **specialist employees**; MCP is the **standard hiring form**

- A **tool** is a specialist you can call: a calculator, a web-search employee, a database clerk.
- Every model used to need a **custom contract** to work with every tool → chaos (N models × M tools = N×M wires).
- **MCP** is a **standard job-application form**: any manager (LLM) can hire any specialist (tool) that fills it out. Now it's N + M connections, not N × M. That's why MCP is called the "USB-C of AI."

**Key truth:** when the model "calls a tool," it only *writes down the intent*. **Your code actually does the work** and hands back the result. (M5)

---

## 7. Multi-agent = a **small company**

One agent doing everything is an overloaded generalist who makes mistakes. A **multi-agent system** is a small company:
- a **manager** (orchestrator/supervisor) delegates,
- **specialists** (agents) each do one job well,
- work is **handed off** down the line, and
- each specialist only gets the **tools and context they need** (least privilege).

Specialized teams beat one exhausted generalist — every time. (M7–M8)

---

## 8. Guardrails = **seatbelts and speed limits**

An agent without limits can loop forever, overspend, or be tricked. Guardrails are the safety system:
- **Input check** — is this request safe/sane?
- **Output check** — don't leak secrets; validate before use.
- **Action allow-list + approval gate** — a human signs off on risky moves.
- **Budgets** — a hard cap on steps and cost (your very first guardrail, back in M1).

**Prompt injection** in one line: *treat anything the agent reads (web pages, documents) like a stranger's note — useful information, never orders.* (M11)

---

## 9. Evaluation = the agent's **report card**

You wouldn't ship code with no tests. An agent needs a **report card** measured on four things:
- **Outcome:** did it get the right result?
- **Trajectory:** did it get there sensibly (right tools, no wasteful loops)?
- **Operational:** was it fast and affordable?
- **Safety:** did it behave?

*A capstone with no report card is a demo. With one, it's a system.* (M10)

---

<div align="center" style="padding:14px; border-top:2px solid #0078d4; margin-top:24px;">
  <p style="color:#888; font-size:12px;">JHF Agentic AI Bootcamp — Mental Models · original teaching analogies · sources in FURTHER-READING.md</p>
</div>
