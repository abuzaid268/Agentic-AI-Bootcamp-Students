<!-- JHF-BRAND -->
<div align="center" style="padding:24px 20px; background:#ffffff; border:2px solid #e0e0e0; border-radius:12px;">
  <p style="margin:0 0 14px 0;">
    <img src="assets/jhf-logo.png" alt="Jerusalem High-Tech Foundry (JHF)" height="50" style="vertical-align:middle; margin:0 20px;" />
    <img src="assets/comcec-logo.png" alt="COMCEC - Cooperation for Development" height="66" style="vertical-align:middle; margin:0 20px;" />
  </p>
  <h2 style="color:#1a3c5e; margin:6px 0;">Agentic AI Bootcamp — Pattern Catalog</h2>
  <p style="font-size:13px; color:#555;">One shared "pattern language" for the whole course. Each pattern says where it's taught.</p>
</div>

# Agent Design Patterns — Catalog

A **design pattern** is a reusable way to structure part of an agent. This catalog is the course's shared vocabulary: whenever a module says *"this is the Routing pattern,"* you can look it up here and see where else it shows up.

**How to read this page**
- Start with the **5 Core Patterns** — the ones every learner must know (they cover ~80% of real agents).
- The **Full Catalog (21 patterns)** is your reference as agents get more advanced.
- Each row shows the **module** where you build it.

> *Sources: the 5 core patterns follow the* Illustrated Guidebook *(Chawla & Pachaar); the full catalog follows* Agentic Design Patterns *(A. Gullí). Content here is written for this course — see `FURTHER-READING.md` for the originals.*

---

## The 5 Core Patterns (know these cold)

| # | Pattern | One-line idea | Build it in |
|---|---|---|---|
| 1 | **Reflection** | The agent reviews its own output and revises until it's good enough. | **M4** |
| 2 | **Tool Use** | The agent calls external tools (APIs, code, search) to act, not just talk. | **M5** |
| 3 | **ReAct** (Reason + Act) | A loop of *Thought → Action → Observation* until the task is solved. | **M3** |
| 4 | **Planning** | Break a task into a roadmap of sub-steps before executing. | **M3** |
| 5 | **Multi-Agent** | Several specialized agents cooperate, delegating to each other. | **M7–M8** |

> **Mental model:** ReAct = Tool Use + Reflection in a loop. Planning sits on top when tasks are multi-step. Multi-Agent is what you reach for when one agent is juggling too much.

---

## Full Catalog (21 patterns)

### A · Control flow & reasoning
| Pattern | What it does | Module |
|---|---|---|
| **Prompt Chaining** | Feed one step's output into the next as a fixed pipeline. | M2 |
| **Routing** | The model picks which path/tool/agent handles the input. | M2, M8 |
| **Parallelization** | Run independent sub-tasks at once, then aggregate. | M8 |
| **Planning** | Produce a plan (sub-tasks, order) before acting. | M3 |
| **Reasoning Techniques** | Chain-of-thought / step-by-step "thinking" to improve decisions. | M0, M3 |
| **ReAct** | Interleave reasoning and tool actions in a loop. | M3 |
| **Reflection** | Self-critique and iterate on the output. | M4 |
| **Goal Setting & Monitoring** | Track progress against an explicit goal; stop when met. | M3 |

### B · Tools, knowledge & memory
| Pattern | What it does | Module |
|---|---|---|
| **Tool Use (Function Calling)** | Call functions/APIs via structured schemas. | M5 |
| **Model Context Protocol (MCP)** | Standardize tool connections (N×M → N+M). | M5 |
| **Knowledge Retrieval (RAG)** | Ground answers in retrieved documents. | M6 |
| **Memory Management** | Short-term + long-term memory; context engineering. | M6 |
| **Learning & Adaptation** | Improve from feedback/experience over time. | Appendix |

### C · Multi-agent & communication
| Pattern | What it does | Module |
|---|---|---|
| **Multi-Agent Collaboration** | Specialized agents split and combine work. | M7 |
| **Inter-Agent Communication (A2A)** | A standard protocol for agent-to-agent messaging. | M9 |

### D · Safety, reliability & operations
| Pattern | What it does | Module |
|---|---|---|
| **Guardrails / Safety** | Constrain inputs/outputs; block unsafe behavior. | M11 |
| **Human-in-the-Loop** | Pause for human approval on high-risk steps. | M11 |
| **Exception Handling & Recovery** | Detect failures and retry/fall back gracefully. | M11 |
| **Evaluation & Monitoring** | Measure quality with metrics + tracing. | M10 |
| **Resource-Aware Optimization** | Manage cost/latency (model routing, caching). | M10, M11 |

### E · Advanced / research
| Pattern | What it does | Module |
|---|---|---|
| **Prioritization** | Decide what to work on first among competing tasks. | Advanced |
| **Exploration & Discovery** | Seek new information/options rather than exploit known ones. | Advanced |

---

## Pattern → Module index (reverse lookup)

| Module | Patterns you'll build |
|---|---|
| **M2** | Prompt Chaining · Routing |
| **M3** | ReAct · Planning · Reasoning · Goal Setting & Monitoring |
| **M4** | Reflection |
| **M5** | Tool Use · MCP |
| **M6** | RAG · Memory Management |
| **M7** | Multi-Agent Collaboration |
| **M8** | Routing · Parallelization |
| **M9** | Inter-Agent Communication (A2A) |
| **M10** | Evaluation & Monitoring · Resource-Aware Optimization |
| **M11** | Guardrails · Human-in-the-Loop · Exception Handling |
| **Capstone** | Whichever patterns your system needs — cite them in your design doc. |

---

<div align="center" style="padding:14px; border-top:2px solid #0078d4; margin-top:24px;">
  <p style="color:#888; font-size:12px;">JHF Agentic AI Bootcamp — Pattern Catalog · Sources credited in FURTHER-READING.md · Organized by JHF · in partnership with COMCEC</p>
</div>
