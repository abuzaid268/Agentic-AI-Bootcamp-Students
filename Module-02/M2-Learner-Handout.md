<!-- JHF-BRAND -->
<div align="center" style="padding:28px 20px; background:#ffffff; border:2px solid #e0e0e0; border-radius:12px;">
  <p style="margin:0 0 16px 0;">
    <img src="../assets/jhf-logo.png" alt="Jerusalem High-Tech Foundry (JHF)" height="54" style="vertical-align:middle; margin:0 22px;" />
    <img src="../assets/comcec-logo.png" alt="COMCEC - Cooperation for Development" height="72" style="vertical-align:middle; margin:0 22px;" />
  </p>
  <h1 style="color:#1a3c5e; margin:6px 0;">Agentic AI Bootcamp</h1>
  <h3 style="color:#0078d4; margin:4px 0; font-weight:600;">Module 2 &middot; Architectures &amp; the 2026 Stack &mdash; Learner Handout</h3>
  <hr style="border:0; border-top:1px solid #0078d4; width:60%; margin:16px auto;" />
  <p style="font-size:14px; color:#555; margin:6px 0;">
    <strong>Lead Trainer</strong><br/>
    <a href="https://www.linkedin.com/in/alaaldin-ahmed-260266150" target="_blank">Alaaldin Ahmed</a>
  </p>
  <p style="font-size:12.5px; color:#777; margin:8px 0 0 0;">
    Organized by <strong>Jerusalem High-Tech Foundry (JHF)</strong> &nbsp;&middot;&nbsp; In partnership with <strong>COMCEC</strong>
  </p>
</div>

# Module 2 — Architectures & the 2026 Stack
## Learner Handout

> **Duration:** 4 hours · **Prereq:** M1 (you built an agent loop by hand).
> **You need:** Python 3.11+, an LLM API key, your editor with GitHub Copilot.
> By the end of today you'll have a **reproducible repo** and the **same "hello agent" running in both LangGraph and CrewAI**.

> 🏗️ **Analogy — a framework is scaffolding.** **LangGraph** gives you labeled pipes you connect by hand (explicit control). **CrewAI** gives you a team you brief and let run (role-based). Same building, two ways to assemble it. See **[MENTAL-MODELS.md](../MENTAL-MODELS.md)**.

---

## Learning Objectives

After this module you can:
1. **Draw** the reference architecture of an agentic system and label every part.
2. **Distinguish** control flow from data flow.
3. **Compare** LangGraph (graph-based) and CrewAI (role-based) and pick the right one.
4. **Place** MCP and A2A correctly as integration standards.
5. **Bootstrap** a clean, reproducible environment and run a "hello agent" in both frameworks.

---

## 1. The Reference Architecture of an Agentic System

In M1 you *were* the orchestrator — you wrote the loop by hand. Here's every part a real system has:

```
                       ┌──────────────────────────────────────┐
                       │            OBSERVABILITY               │
                       │  (traces, logs, tokens, cost, latency) │
                       └──────────────────────────────────────┘
                                      ▲ instruments everything
   ┌──────────┐    ┌──────────────────────────────┐    ┌──────────────┐
   │  INPUT   │──▶ │        ORCHESTRATOR           │ ◀─▶│    MEMORY    │
   │ (goal /  │    │  (runs the loop; routing;     │    │ short + long │
   │  request)│    │   control flow; multi-agent)  │    │   term       │
   └──────────┘    └──────────────────────────────┘    └──────────────┘
                         │  ▲              │  ▲
                  decides│  │observe       │  │
                         ▼  │              ▼  │
                    ┌─────────────┐   ┌──────────────┐
                    │   MODEL(S)  │   │    TOOLS     │ ── via MCP ──▶ APIs,
                    │ (reasoner)  │   │ (fns, APIs)  │    data, systems
                    └─────────────┘   └──────────────┘
                  ┌──────────────────────────────────────────────┐
                  │  GUARDRAILS (validation, safety, HITL gates)  │
                  └──────────────────────────────────────────────┘
```

| Component | What it does | M1 connection | Deep dive |
|---|---|---|---|
| **Model** | The reasoner (the "reason" step) | Your `call_model` | — |
| **Tools** | Actions on the world (the "act" step) | Your `calculator` | M3, M5 |
| **Orchestrator** | Runs the loop, routing, control flow, multi-agent | Your `for`-loop + `if/else` | M3, M4, M8 |
| **Memory** | Short-term (working) + long-term (recall) | (M1 just resent history — costly) | M6 |
| **Guardrails** | Validation, safety, human-in-the-loop gates | (none in M1) | M11 |
| **Observability** | Traces, logs, cost, latency | (your print/cost counter) | M10 |

> Every box is a future module. Today you get the **map of the whole bootcamp**.

---

## 2. Control Flow vs Data Flow

- **Control flow** = the *order* things run — branching, loops, when to stop, which agent goes next.
- **Data flow** = the *information* passed between components (the message/state).

In your M1 agent: the **loop + if/else was the control flow**; the **`messages` list was the data flow**. Frameworks mostly differ in *how you express control flow*.

---

## 3. LangGraph vs CrewAI

| Dimension | **LangGraph** | **CrewAI** |
|---|---|---|
| Mental model | A **graph/state machine** of nodes & edges | A **team of roles** with goals & tasks |
| Control flow | **Explicit** — you wire nodes, edges, conditions, loops | **Higher-level** — a process (sequential / hierarchical) |
| Best for | Precise branching, looping, stateful flows | Fast multi-agent role collaboration |
| Control level | Low-level, maximum control | High-level, fast to assemble |
| Used in bootcamp | Orchestration backbone (M3, M4, M8) | Multi-agent crews (M7, M9) |

> They're **not rivals** — they're different abstraction levels. Often you use LangGraph as the orchestration spine and CrewAI where role collaboration is natural. Today you'll run the *same task* in both to *feel* the difference.

---

## 4. MCP & A2A — Two Different Layers

This is the #1 thing people get wrong. Memorize the one-liner:

> **MCP = agent ↔ tools. A2A = agent ↔ agent.**

| Protocol | Connects | Analogy | Deep dive |
|---|---|---|---|
| **MCP** (Model Context Protocol) | Agent ↔ **tools / data / resources** | "USB-C for tools" | M5 |
| **A2A** (Agent-to-Agent) | Agent ↔ **agent** (even across frameworks/orgs) | "How agents talk & hand off work" | M9 |

They **compose**: a network of agents talking over A2A, each using MCP to reach its own tools. They are **not** competing standards.

---

## 5. Environment Hygiene (do this right, once)

Professional agent code is reproducible and safe:
- **Virtual environment** per project (don't pollute global Python).
- **Lockfile** — pin versions (`requirements.txt` pinned, or `uv`/`poetry`) so it runs the same everywhere.
- **Secrets in `.env`**, and `.env` is in **`.gitignore`**. **Never commit API keys.**

> We will check that your `.env` is git-ignored. Treat leaked keys as a real incident — rotate immediately.

---

## 6. Today's Lab (preview)

You'll:
1. Scaffold a reproducible repo (venv, lockfile, `.env`, `.gitignore`).
2. Build a **"hello agent" in LangGraph** (a tiny graph).
3. Build the **same agent in CrewAI** (a role + task).
4. Fill in a **comparison table** from your own experience.

Full steps: **`M2-Lab-Worksheet.md`**. Starters: **`starter-code/`**.

The task both frameworks do is intentionally trivial (*"given a topic, return a one-sentence definition"*) — so you compare the *plumbing*, not the capability.

---

## 7. Deliverables (graded)

1. **Repo scaffold** — venv + pinned lockfile + git-ignored `.env`.
2. **Two working "hello agents"** — `hello_langgraph.py` and `hello_crewai.py` producing the same result.
3. **Comparison table** — your honest notes: where each framework was verbose, where it was easy, and when you'd choose each.

---

## 8. Key Terms

| Term | Meaning |
|---|---|
| Orchestrator | The code/engine that runs the agent loop and control flow. |
| Control flow | The order in which steps/agents execute. |
| Data flow | The information passed between components. |
| Node / edge (LangGraph) | A unit of work / a transition between units. |
| Role / task / crew (CrewAI) | A specialized agent / a job / a team running a process. |
| MCP | Standard for connecting agents to tools & data. |
| A2A | Standard for agents communicating with each other. |
| Lockfile | Pinned dependency versions for reproducible installs. |

---

## 9. Quiz (5 min)

1. Name the six core components of the agentic reference architecture.
2. Which component is the "reason" step of the M1 loop? Which is "act"?
3. Define control flow and data flow in one line each.
4. Give the core mental model of LangGraph and of CrewAI.
5. One sentence: what does MCP connect, and what does A2A connect?
6. Why use a lockfile and a git-ignored `.env`?
7. You need precise branching, loops, and stateful control in one workflow — which framework leans more natural, and why?
8. True/False: MCP and A2A are competing standards for the same job.

---

<div align="center" style="padding:14px; border-top:2px solid #0078d4; margin-top:34px;">
  <p style="margin:0 0 8px 0;">
    <img src="../assets/jhf-logo.png" alt="JHF" height="28" style="vertical-align:middle; margin:0 14px; background:#ffffff; padding:6px 10px; border-radius:6px;" />
    <img src="../assets/comcec-logo.png" alt="COMCEC" height="40" style="vertical-align:middle; margin:0 14px; background:#ffffff; padding:6px 10px; border-radius:6px;" />
  </p>
  <p style="color:#888; font-size:13px; margin:0;">
    <strong>JHF Agentic AI Bootcamp</strong> &mdash; Module 2<br/>
    Lead Trainer: <a href="https://www.linkedin.com/in/alaaldin-ahmed-260266150">Alaaldin Ahmed</a><br/>
    Organized by Jerusalem High-Tech Foundry (JHF) &middot; In partnership with COMCEC
  </p>
</div>

