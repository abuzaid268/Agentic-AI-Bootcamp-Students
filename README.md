<!-- JHF-BRAND -->
<div align="center" style="padding:28px 20px; background:#ffffff; border:2px solid #e0e0e0; border-radius:12px;">
  <p style="margin:0 0 16px 0;">
    <img src="assets/jhf-logo.png" alt="Jerusalem High-Tech Foundry (JHF)" height="54" style="vertical-align:middle; margin:0 22px;" />
    <img src="assets/comcec-logo.png" alt="COMCEC - Cooperation for Development" height="72" style="vertical-align:middle; margin:0 22px;" />
  </p>
  <h1 style="color:#1a3c5e; margin:6px 0;">Agentic AI Bootcamp</h1>
  <h3 style="color:#0078d4; margin:4px 0; font-weight:600;">Course Plan &mdash; 76-Hour Program</h3>
  <hr style="border:0; border-top:1px solid #0078d4; width:60%; margin:16px auto;" />
  <p style="font-size:14px; color:#555; margin:6px 0;">
    <strong>Lead Trainer</strong><br/>
    <a href="https://www.linkedin.com/in/alaaldin-ahmed-260266150" target="_blank">Alaaldin Ahmed</a>
  </p>
  <p style="font-size:12.5px; color:#777; margin:8px 0 0 0;">
    Organized by <strong>Jerusalem High-Tech Foundry (JHF)</strong> &nbsp;&middot;&nbsp; In partnership with <strong>COMCEC</strong>
  </p>
</div>

# Agentic AI Bootcamp: From Foundations to Professional Systems

**A 76-Hour, Project-Based, Instructor-Led Program**

> 📅 **[Session Schedule & Calendar → SCHEDULE.md](SCHEDULE.md)** — all 19 sessions, dates, phases, and assessment weighting.
> 📖 **[Glossary → GLOSSARY.md](GLOSSARY.md)** · 🧩 **[Pattern Catalog → PATTERNS.md](PATTERNS.md)** · 🧠 **[Mental Models → MENTAL-MODELS.md](MENTAL-MODELS.md)** · 🧭 **[Module 0 · LLM & Reasoning Primer](Module-00-LLM-Reasoning-Primer/M0-Learner-Handout.md)** · 📚 **[Further Reading → FURTHER-READING.md](FURTHER-READING.md)**

![An Agent = an LLM + modules](assets/diagrams/augmented-llm-base.png)

> **The mental model for the whole course:** an **agent = a plain LLM + modules** (reasoning, memory, tools). Each module lights up one piece. This spine follows the reference book *An Illustrated Guide to AI Agents* (M. Grootendorst).

| Attribute | Detail |
|---|---|
| **Audience** | Graduate students with basic Python proficiency |
| **Cohort size** | 20 learners |
| **Total duration** | 76 hours (instructor-led, workshop format) |
| **Hands-on ratio** | ~70% labs/projects, ~30% concept + design |
| **Outcome** | Job-ready: design, build, evaluate, and deploy agentic AI systems — self-hosted **and** on the cloud (Microsoft Foundry) |
| **Core stack** | Python · LangGraph · CrewAI · MCP · A2A · **Microsoft Foundry** · GitHub Copilot |
| **LLM access** | OpenRouter (OpenAI-compatible) · default model `openai/gpt-4o-mini`; Phase 7 uses Azure/Foundry-hosted models |
| **Pedagogy** | Build → Test → Improve; framework-agnostic principles first, then implementation, then the managed cloud twin |
| **Excluded** | Legacy "chatbot-only" patterns |

---

## Course Plan — 7 Phases · 16 Modules · Capstone

```
Agentic AI Bootcamp  (76h)
│
├─ PHASE 1 · Foundations & Mental Models ........................... 8h
│   ├─ M1 · What Agentic AI Really Is .............................. 4h   BUILT
│   └─ M2 · Architectures & the 2026 Stack ........................ 4h   BUILT
│       └─ Mini-project: scripted agent loop + dual-framework "hello agent"
│
├─ PHASE 2 · Core Agent Design Patterns ........................... 10h
│   ├─ M3 · ReAct, Planning & Tool-Use Patterns ................... 5h   BUILT
│   └─ M4 · Reflection, Self-Critique & Robustness ................ 5h   BUILT
│       └─ Mini-project: Self-Improving Research Agent
│
├─ PHASE 3 · Tools, Skills, Integrations & Memory ............... 14h
│   ├─ M5 · Tools, APIs & the Model Context Protocol (MCP) ........ 5h   BUILT
│   ├─ M5B · Agent Skills (reusable, loadable capabilities) ....... 4h   BUILT
│   └─ M6 · Memory Systems: Short-Term & Long-Term ................ 5h   BUILT
│       └─ Mini-project: Personal Knowledge Assistant + reusable skill
│
├─ PHASE 4 · Multi-Agent Systems & Protocols ..................... 12h
│   ├─ M7 · Multi-Agent Foundations with CrewAI ................... 4h   BUILT
│   ├─ M8 · Orchestration Patterns & Control Flow ................. 4h   BUILT
│   └─ M9 · Agent-to-Agent Communication (A2A) .................... 4h   BUILT
│       └─ Mini-project: Cross-Framework Agent Network (MCP + A2A)
│
├─ PHASE 5 · Production, Evaluation & Safety ..................... 10h
│   ├─ M10 · Evaluation & Observability ........................... 5h   BUILT
│   └─ M11 · Guardrails, Safety & Cost/Latency Engineering ........ 5h   BUILT
│       └─ Mini-project: Production-Hardened Agent
│
├─ PHASE 6 · Deployment & Advanced Patterns ...................... 4h
│   └─ M12 · Deploy an agent service (FastAPI + Docker, self-hosted) 4h   BUILT
│
├─ PHASE 7 · Agentic AI in the Cloud — Microsoft Foundry ........ 12h   ⟵ NEW
│   │   The managed cloud twin of Phases 1–6. Each module bridges to the
│   │   from-scratch module it mirrors.
│   ├─ M13 · Microsoft Foundry & Cloud Models .................... 4h   (bridges M1–M2)
│   ├─ M14 · Cloud Agents & Knowledge (Agent Service + grounding)  4h   (bridges M5–M6)
│   └─ M15 · Orchestration, Safety & Observability in Foundry .... 4h   (bridges M8/M10/M11)
│       └─ Mini-project: grounded, guardrailed, traced cloud agent
│       └─ Appendix (self-study): Foundry cognitive tools (Translator/Language/Speech/Vision)
│
└─ CAPSTONE · Production-Grade Agentic System ................... 4h   BUILT
    └─ Choose a CODE track (self-hosted) or a CLOUD track (Foundry) + Demo Day
```

**Progression:** single agent → tools & workflows → memory → multi-agent → production → self-hosted deploy → **managed cloud (Foundry)** → capstone

---

## Module Index

| # | Module | Phase | Hrs | Status |
|---|---|---|---|---|
| M0 | LLM & Reasoning Primer *(pre-work)* | Foundations | ~1 | Built |
| M1 | What Agentic AI Really Is | Foundations | 4 | Built |
| M2 | Architectures & the 2026 Stack | Foundations | 4 | Built |
| M3 | ReAct, Planning & Tool-Use Patterns | Core Patterns | 5 | Built |
| M4 | Reflection, Self-Critique & Robustness | Core Patterns | 5 | Built |
| M5 | Tools, APIs & MCP | Tools & Memory | 5 | Built |
| **M5B** | **Agent Skills (reusable, loadable capabilities)** | **Tools & Memory** | **4** | **Built** |
| M6 | Memory Systems & Context Engineering | Tools & Memory | 5 | Built |
| M7 | Multi-Agent Foundations (CrewAI) | Multi-Agent | 4 | Built |
| M8 | Orchestration Patterns & Control Flow | Multi-Agent | 4 | Built |
| M9 | Agent-to-Agent Communication (A2A) | Multi-Agent | 4 | Built |
| M10 | Evaluation & Observability (metrics + failure-fixes) | Production | 5 | Built |
| M11 | Guardrails, Safety & Cost/Latency | Production | 5 | Built |
| M12 | Deployment & Advanced Patterns | Deployment | 4 | Built |
| **M13** | **Microsoft Foundry & Cloud Models** | **Cloud (Foundry)** | **4** | **Built** |
| **M14** | **Cloud Agents & Knowledge (Agent Service + grounding)** | **Cloud (Foundry)** | **4** | **Built** |
| **M15** | **Orchestration, Safety & Observability in Foundry** | **Cloud (Foundry)** | **4** | **Built** |
| — | Capstone: Production-Grade System (Code **or** Cloud track) | Capstone | 4 | Built |

---

## Hours Ledger

| Phase | Concept | Hands-on | Total |
|---|---|---|---|
| 1 — Foundations | 3.5 | 4.5 | 8 |
| 2 — Core Patterns | 3.0 | 7.0 | 10 |
| 3 — Tools, Skills & Memory | 4.5 | 9.5 | 14 |
| 4 — Multi-Agent | 4.0 | 8.0 | 12 |
| 5 — Production/Eval | 3.0 | 7.0 | 10 |
| 6 — Deployment | 1.0 | 3.0 | 4 |
| 7 — Cloud (Foundry) | 4.5 | 7.5 | 12 |
| Capstone | 0.5 | 3.5 | 4 |
| **Total** | **24.0** | **52.0** | **76** |

**Hands-on ratio ≈ 68%.**

---

## Assessment

| Component | Weight |
|---|---|
| Phase quizzes (7) | 10% |
| Mini-projects (6 — incl. Phase 7 Cloud mini-project) | 35% |
| Practical evaluations (2) | 15% |
| Participation & lab completion | 10% |
| **Capstone** | **30%** |

**Pass bar:** ≥70% overall **and** a working capstone meeting all mandatory requirements. Choose one:
- **Code track** — self-hosted multi-agent system (MCP + A2A, memory, guardrails, evaluation, deployment).
- **Cloud track** — the same capabilities built on **Microsoft Foundry** (Agent Service + grounding, content safety, tracing/eval, deployed endpoint).

---

## Repository Structure

```
Agentic-AI-Bootcamp-Cloud/
├─ README.md                  ← this course plan
├─ SCHEDULE.md                ← 19-session calendar
├─ assets/                    ← shared logos (JHF, COMCEC)
├─ Module-01/
│  ├─ M1-Learner-Handout.md
│  ├─ M1-Lab-Worksheet.md
│  ├─ starter-code/
│  └─ solution-code/          (instructor repo)
├─ Module-02 ... Module-05/   (same layout each)
├─ Module-05B-Agent-Skills/   ← NEW: Agent Skills session (after MCP)
│  ├─ M5B-Learner-Handout.md
│  └─ M5B-Lab-Worksheet.md
├─ Module-06 ... Module-12/   (same layout each)
├─ Phase-7-Cloud-Foundry/     ← NEW: Microsoft Foundry cloud track
│  ├─ README.md
│  ├─ Phase-7-Pre-Work.md              (Azure onboarding for all of M13–M15)
│  ├─ Module-13-Microsoft-Foundry-and-Cloud-Models/
│  │  ├─ M13-Learner-Handout.md · M13-Lab-Worksheet.md · *.pptx decks
│  ├─ Module-14-Cloud-Agents-and-Knowledge/
│  │  ├─ M14-Learner-Handout.md · M14-Lab-Worksheet.md · *.pptx decks
│  ├─ Module-15-Orchestration-Safety-Observability/
│  │  ├─ M15-Learner-Handout.md · M15-Lab-Worksheet.md · *.pptx deck
│  └─ Appendix-Foundry-Tools/  (self-study cognitive-tools deck)
└─ Capstone/
   ├─ Capstone-Brief.md        (Code or Cloud track)
   ├─ Capstone-Evaluation-Rubric.md
   └─ Capstone-Starter-Scaffold.md
```

Each module folder contains: **Instructor Guide** (facilitation only), **Learner Handout** (concepts + quiz), **Lab Worksheet** (hands-on steps), and `starter-code/` + `solution-code/`.

---

## Teaching Notes

- Code calls all models through **OpenRouter** (an OpenAI-compatible gateway) using the standard `openai` / `langchain-openai` / CrewAI clients; default model `openai/gpt-4o-mini`. See **[SCHEDULE.md](SCHEDULE.md)** and each module's setup for details.
- **Setup:** each learner creates an **OpenRouter API key** (https://openrouter.ai/keys), sets `OPENROUTER_API_KEY` in a git-ignored `.env` (see `.env.example`), base URL `https://openrouter.ai/api/v1`. Full walkthrough in **Module 1 Pre-Work**.
- Pin a tested `requirements.txt` before class; have learners freeze a lockfile.
- Distribute `solution-code/` only after each lab/debrief.
- Continuous threads across all modules: **GitHub Copilot** as accelerator, **Build → Test → Improve** rhythm, **cost/latency awareness**, and **reproducibility & secrets hygiene**.
- **Reference book:** the curriculum is aligned to *An Illustrated Guide to AI Agents* (M. Grootendorst) and a wider library (see **[FURTHER-READING.md](FURTHER-READING.md)**). The **augmented-LLM** anchor diagram, **agency-levels** ladder (`assets/diagrams/`), **M0 primer**, **M6 context-engineering**, **[PATTERNS.md](PATTERNS.md)** (21-pattern catalog), and **GLOSSARY.md** come from it. Modules note their source inline.

> **Status:** All 12 modules + Capstone built. Full 60-hour program complete.

---

<div align="center" style="padding:14px; border-top:2px solid #0078d4; margin-top:34px;">
  <p style="margin:0 0 8px 0;">
    <img src="assets/jhf-logo.png" alt="JHF" height="28" style="vertical-align:middle; margin:0 14px; background:#ffffff; padding:6px 10px; border-radius:6px;" />
    <img src="assets/comcec-logo.png" alt="COMCEC" height="40" style="vertical-align:middle; margin:0 14px; background:#ffffff; padding:6px 10px; border-radius:6px;" />
  </p>
  <p style="color:#888; font-size:13px; margin:0;">
    <strong>JHF Agentic AI Bootcamp</strong> &mdash; Course Plan<br/>
    Lead Trainer: <a href="https://www.linkedin.com/in/alaaldin-ahmed-260266150">Alaaldin Ahmed</a><br/>
    Organized by Jerusalem High-Tech Foundry (JHF) &middot; In partnership with COMCEC
  </p>
</div>

