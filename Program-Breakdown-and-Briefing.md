<!-- JHF-BRAND -->
<div align="center" style="padding:28px 20px; background:#ffffff; border:2px solid #e0e0e0; border-radius:12px;">
  <p style="margin:0 0 16px 0;">
    <img src="assets/jhf-logo.png" alt="Jerusalem High-Tech Foundry (JHF)" height="54" style="vertical-align:middle; margin:0 22px;" />
    <img src="assets/comcec-logo.png" alt="COMCEC - Cooperation for Development" height="72" style="vertical-align:middle; margin:0 22px;" />
  </p>
  <h1 style="color:#1a3c5e; margin:6px 0;">Agentic AI Bootcamp</h1>
  <h3 style="color:#0078d4; margin:4px 0; font-weight:600;">Program Breakdown &amp; Delivery Briefing</h3>
  <hr style="border:0; border-top:1px solid #0078d4; width:60%; margin:16px auto;" />
  <p style="font-size:14px; color:#555; margin:6px 0;">
    <strong>Lead Trainer</strong><br/>
    <a href="https://www.linkedin.com/in/alaaldin-ahmed-260266150" target="_blank">Alaaldin Ahmed</a>
  </p>
  <p style="font-size:12.5px; color:#777; margin:8px 0 0 0;">
    Organized by <strong>Jerusalem High-Tech Foundry (JHF)</strong> &nbsp;&middot;&nbsp; In partnership with <strong>COMCEC</strong>
  </p>
</div>

# Agentic AI Bootcamp — Program Breakdown & Delivery Briefing

**A module-by-module briefing of what is delivered, plus a suggested hours split for each.**

> 60 hours · 6 phases · 12 modules + Capstone · ~71% hands-on
> Stack: Python · LangGraph · CrewAI · MCP · A2A · GitHub Copilot

This document is for planning and stakeholder briefing. Each module's full content lives in its own folder (`Module-0X/`) as an Instructor Guide, Learner Handout, Lab Worksheet, and starter/solution code.

---

## How to Read the Hours Split

Each module's time is divided into four delivery activities:

| Activity | What happens |
|---|---|
| **Concept** | Instructor-led teaching: principles, diagrams, demos. |
| **Lab** | Hands-on building (the core of the module). |
| **Debrief** | Sharing results, reviewing failure modes, Q&A. |
| **Quiz/Assess** | Short knowledge check + bridge to next module. |

Breaks are scheduled within each session but excluded from the splits below (teaching time only).

---

## PHASE 1 — Foundations & Mental Models (8h)

### M1 · What Agentic AI Really Is — **4h**
- **Delivered:** Learners build a **bare-metal agent loop in pure Python** (no frameworks) and a 1-page "Is this an agent?" decision note. They leave able to distinguish a single LLM call vs a workflow vs an autonomous agent, and to run the perceive→reason→act→observe loop with a step budget + cost counter.
- **Hours split:** Concept **1.5** · Lab **2.0** · Debrief **0.3** · Quiz **0.2**

### M2 · Architectures & the 2026 Stack — **4h**
- **Delivered:** A **reproducible repo scaffold** (venv, lockfile, git-ignored secrets) and the **same "hello agent" in both LangGraph and CrewAI**, plus a comparison table. Learners can draw the agentic reference architecture and correctly place MCP (agent↔tools) vs A2A (agent↔agent).
- **Hours split:** Concept **2.0** · Lab **1.5** · Debrief **0.3** · Quiz **0.2**

**Phase 1 mini-project:** scripted agent loop + dual-framework hello agent.

---

## PHASE 2 — Core Agent Design Patterns (10h)

### M3 · ReAct, Planning & Tool-Use — **5h**
- **Delivered:** A **graph-based ReAct + Planning agent** in LangGraph that decomposes multi-step questions, uses **structured outputs** (no fragile JSON parsing), and replans — with a visualized state graph and a failure-mode note.
- **Hours split:** Concept **1.5** · Lab **3.0** · Debrief **0.3** · Quiz **0.2**

### M4 · Reflection, Self-Critique & Robustness — **5h**
- **Delivered:** A **Self-Improving Research Agent** (critic–actor loop) that drafts, critiques itself against a rubric, and revises — bounded by iteration, cost, and "good-enough" stops — plus hardening against loops, hallucinated tools, and oscillation.
- **Hours split:** Concept **1.5** · Lab **3.0** · Debrief **0.3** · Quiz **0.2**

**Phase 2 mini-project:** Self-Improving Research Agent.

---

## PHASE 3 — Tool Use, Integrations & Memory (10h)

### M5 · Tools, APIs & MCP — **5h**
- **Delivered:** A **custom MCP server** (typed tools, validation, timeouts) and a **LangGraph agent that consumes it as an MCP client**, calling live tools through the protocol — with documented tool schemas.
- **Hours split:** Concept **1.5** · Lab **3.0** · Debrief **0.3** · Quiz **0.2**

### M6 · Memory Systems (Short & Long-Term) — **5h**
- **Delivered:** The **Personal Knowledge Assistant** — short-term summarization + **persistent long-term vector memory** that recalls preferences **across a restart** and cites sources, with a documented memory policy.
- **Hours split:** Concept **1.5** · Lab **3.0** · Debrief **0.3** · Quiz **0.2**

**Phase 3 mini-project:** Personal Knowledge Assistant.

---

## PHASE 4 — Multi-Agent Systems & Protocols (12h)

### M7 · Multi-Agent Foundations (CrewAI) — **4h**
- **Delivered:** A **3-role CrewAI crew** (Researcher→Analyst→Writer) that turns one brief into a structured report, with per-role tools and a single-vs-multi-agent reflection.
- **Hours split:** Concept **1.0** · Lab **2.5** · Debrief **0.3** · Quiz **0.2**

### M8 · Orchestration Patterns & Control Flow — **4h**
- **Delivered:** A **LangGraph supervisor/router** that routes tasks to specialists and **fans out work in parallel**, aggregates results, and always terminates within global budgets — with a topology visualization.
- **Hours split:** Concept **1.5** · Lab **2.0** · Debrief **0.3** · Quiz **0.2**

### M9 · Agent-to-Agent Communication (A2A) — **4h**
- **Delivered:** The **Cross-Framework Agent Network** — a supervisor delegates across a CrewAI crew and a LangGraph agent **via A2A**, each using **MCP** tools — with an architecture diagram labeling both layers.
- **Hours split:** Concept **1.5** · Lab **2.0** · Debrief **0.3** · Quiz **0.2**

**Phase 4 mini-project:** Cross-Framework Agent Network (MCP + A2A).

---

## PHASE 5 — Production, Evaluation & Safety (10h)

### M10 · Evaluation & Observability — **5h**
- **Delivered:** The Phase-4 system **instrumented with tracing** plus a **~15-task eval suite** producing a **scorecard** (success rate, cost, p95 latency), and **before/after fixes** of the two worst cases diagnosed from traces.
- **Hours split:** Concept **1.5** · Lab **3.0** · Debrief **0.3** · Quiz **0.2**

### M11 · Guardrails, Safety & Cost/Latency — **5h**
- **Delivered:** The **Production-Hardened Agent** — input/output guardrails, an **injection red-team** (blocked), a **human-in-the-loop approval gate**, plus **model routing + caching** with a measured cost/latency improvement and a one-page reliability report.
- **Hours split:** Concept **1.5** · Lab **3.0** · Debrief **0.3** · Quiz **0.2**

**Phase 5 mini-project:** Production-Hardened Agent.

---

## PHASE 6 — Advanced Systems & Capstone (10h)

### M12 · Deployment & Advanced Patterns — **3h**
- **Delivered:** A **deployed, callable agent service** (FastAPI + Docker) with health + trace verification, plus advanced patterns (async/long-running tasks, streaming, externalized state) and a deployment checklist.
- **Hours split:** Concept **1.0** · Lab **1.6** · Debrief **0.2** · Quiz/Kickoff **0.2**

### Capstone · Production-Grade Agentic System — **7h**
- **Delivered:** A **complete, deployed, evaluated, guard-railed multi-agent system** integrating all 12 modules — with source repo, architecture diagram, eval scorecard, reliability notes, and a **10-minute live demo + Q&A**.
- **Hours split:** Design/scoping **0.5** · Build **5.0** · Checkpoints (3 reviews) **0.75** · Demo + Q&A **0.75**

---

## Summary Table — Hours by Activity

| Module | Concept | Lab | Debrief | Quiz/Other | Total |
|---|---|---|---|---|---|
| M1 | 1.5 | 2.0 | 0.3 | 0.2 | 4 |
| M2 | 2.0 | 1.5 | 0.3 | 0.2 | 4 |
| M3 | 1.5 | 3.0 | 0.3 | 0.2 | 5 |
| M4 | 1.5 | 3.0 | 0.3 | 0.2 | 5 |
| M5 | 1.5 | 3.0 | 0.3 | 0.2 | 5 |
| M6 | 1.5 | 3.0 | 0.3 | 0.2 | 5 |
| M7 | 1.0 | 2.5 | 0.3 | 0.2 | 4 |
| M8 | 1.5 | 2.0 | 0.3 | 0.2 | 4 |
| M9 | 1.5 | 2.0 | 0.3 | 0.2 | 4 |
| M10 | 1.5 | 3.0 | 0.3 | 0.2 | 5 |
| M11 | 1.5 | 3.0 | 0.3 | 0.2 | 5 |
| M12 | 1.0 | 1.6 | 0.2 | 0.2 | 3 |
| Capstone | 0.5 (design) | 5.0 (build) | 0.75 (checkpoints) | 0.75 (demo) | 7 |
| **Total** | **~18.5** | **~38.6** | **~4.3** | **~3.4** | **60** |

> Lab + build ≈ **42.5h (~71%)** hands-on, the target ratio. Concept ≈ 29%.

---

## Scheduling Options

| Cadence | Layout |
|---|---|
| **Intensive (2 weeks)** | 6 hrs/day × 10 days |
| **Part-time evenings (6 weeks)** | 2 × 5h sessions/week |
| **Weekend (10 weeks)** | 1 × 6h session/week (capstone over the final 2 weekends) |

---

## Assessment Across the Program

| Component | Weight | When |
|---|---|---|
| Phase quizzes (6) | 10% | End of each phase |
| Mini-projects (5) | 35% | End of Phases 1–5 |
| Practical evaluations (2) | 15% | After Phase 3 & Phase 5 |
| Participation & lab completion | 10% | Continuous |
| **Capstone** | **30%** | Phase 6 |

**Pass bar:** ≥70% overall **and** a working capstone meeting all mandatory requirements.

---

<div align="center" style="padding:14px; border-top:2px solid #0078d4; margin-top:34px;">
  <p style="margin:0 0 8px 0;">
    <img src="assets/jhf-logo.png" alt="JHF" height="28" style="vertical-align:middle; margin:0 14px; background:#ffffff; padding:6px 10px; border-radius:6px;" />
    <img src="assets/comcec-logo.png" alt="COMCEC" height="40" style="vertical-align:middle; margin:0 14px; background:#ffffff; padding:6px 10px; border-radius:6px;" />
  </p>
  <p style="color:#888; font-size:13px; margin:0;">
    <strong>JHF Agentic AI Bootcamp</strong> &mdash; Program Briefing<br/>
    Lead Trainer: <a href="https://www.linkedin.com/in/alaaldin-ahmed-260266150">Alaaldin Ahmed</a><br/>
    Organized by Jerusalem High-Tech Foundry (JHF) &middot; In partnership with COMCEC
  </p>
</div>

