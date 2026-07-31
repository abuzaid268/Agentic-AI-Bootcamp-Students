<!-- JHF-BRAND -->
<div align="center" style="padding:24px 20px; background:#ffffff; border:2px solid #e0e0e0; border-radius:12px;">
  <p style="margin:0 0 14px 0;">
    <img src="assets/jhf-logo.png" alt="Jerusalem High-Tech Foundry (JHF)" height="50" style="vertical-align:middle; margin:0 20px;" />
    <img src="assets/comcec-logo.png" alt="COMCEC - Cooperation for Development" height="66" style="vertical-align:middle; margin:0 20px;" />
  </p>
  <h2 style="color:#1a3c5e; margin:6px 0;">Agentic AI Bootcamp — Glossary</h2>
  <p style="font-size:13px; color:#555;">Shared vocabulary across all modules. Aligned to <i>An Illustrated Guide to AI Agents</i> (M. Grootendorst).</p>
</div>

# Glossary

One shared vocabulary for the whole bootcamp so terms mean the same thing in every module. Terms are grouped by theme; the **Module** column shows where each is taught, and **Book** shows the source chapter in the reference book.

> The reference book is *An Illustrated Guide to AI Agents* by Maarten Grootendorst (O'Reilly). Chapter numbers below use the book's final numbering (Memory = Ch. 4, Tooling = Ch. 5).

## The model (foundations)

| Term | Plain-language meaning | Module | Book |
|---|---|---|---|
| **LLM** | A function that takes tokens (text) and predicts the next tokens. Stateless by itself. | M0 | Ch. 2 |
| **Token** | A chunk of text (≈ ¾ of a word) the model reads/writes. | M0 | Ch. 2 |
| **Context window** | The max tokens (input + output) the model can consider at once. | M0, M6 | Ch. 2, 4 |
| **Temperature** | Randomness of the model's choices; `0` = deterministic (used in agent labs). | M0 | Ch. 2 |
| **Parametric memory** | Facts baked into the model's weights during training (frozen, can hallucinate). | M0, M6 | Ch. 4 |
| **Reasoning LLM** | A model trained to spend "thinking tokens" before answering; better at planning & tool selection. | M0, M3, M5 | Ch. 3 |
| **Hallucination** | A confident but incorrect answer; reduced by giving the model real context (RAG). | M0, M6 | Ch. 4 |

## The agent

| Term | Plain-language meaning | Module | Book |
|---|---|---|---|
| **Agent** | An LLM augmented with modules (reasoning, memory, tools) that can decide and act. | M1 | Ch. 6 |
| **Augmented LLM** | The mental model of this course: `LLM + reasoning + memory + tools = agent`. | M1 | whole book |
| **Agent loop** | Perceive → Reason → Act → Observe, repeated with a hard stop. *The model decides; your code executes.* | M1 | Ch. 6 |
| **Autonomy spectrum** | From fixed tool flow → the agent choosing which tool to use and when. | M1, M5 | Ch. 5 |

## Memory & context (M6 · Book Ch. 4)

| Term | Plain-language meaning | Book |
|---|---|---|
| **Working memory** | Short-term memory = the recent conversation history kept in context. | Ch. 4 |
| **Episodic memory** | Long-term memory of past events/actions the agent took and their outcomes. | Ch. 4 |
| **Semantic memory** | Long-term world/domain knowledge (e.g., your docs), usually via RAG. | Ch. 4 |
| **Procedural memory** | "How-to" knowledge and rules — often the system prompt (or model weights). | Ch. 4 |
| **RAG** (Retrieval-Augmented Generation) | Give the LLM long-term memory: **ingestion** (embed → store) + **inference** (embed query → retrieve → augment → generate). | Ch. 4 |
| **Embedding** | A numeric vector representing text by meaning; similar meaning → similar vector. | Ch. 4 |
| **Agentic RAG** | The agent (not a static step) decides *which* source to retrieve from and *how often* — RAG as a router/tool. | Ch. 4 |
| **Context engineering** | Optimizing the **whole** context (select, compress, order), not just the prompt. | Ch. 4 |
| **Lost-in-the-middle** | LLMs attend best to the start/end of context; middle info gets missed. | Ch. 4 |
| **Context rot** | Quality degrades as you add irrelevant tokens — more context ≠ better. | Ch. 4 |
| **Re-ranking** | Re-scoring retrieved results by relevance and keeping only the top few. | Ch. 4 |
| **MMR** (Maximal Marginal Relevance) | Keep results that are relevant **and** non-redundant (diverse). | Ch. 4 |
| **Context as specification** | Treating the agent's context (query, `PLAN.md`, `REQUIREMENTS.md`) as the tracked spec of the work. | Ch. 4 |

## Tools & protocols (M5 · Book Ch. 5)

| Term | Plain-language meaning | Book |
|---|---|---|
| **Tool** | A function (code or API) the agent can call to act on the world or fetch data. | Ch. 5 |
| **Tool lifecycle** | The five steps: **Creation → Definition → Selection → Calling → Output Processing**. | Ch. 5 |
| **Agent Skill** | A reusable, self-contained bundle of instructions (+ optional scripts/resources) an agent loads on demand — a "playbook" vs. a tool's single "action." | M5B |
| **Progressive disclosure** | Show the agent skill names/descriptions first; load full instructions/resources only when a task matches (keeps context small). | M5B |
| **Function calling / JSON Schema** | A structured way to tell the LLM a tool's name, description, and parameters. | Ch. 5 |
| **Tool call = intent** | The LLM only *emits* a tool call as text; **your code** actually executes it. | Ch. 5 |
| **Tool learning** | How models learn tool use: in-context (examples), supervised fine-tuning, or reinforcement learning. | Ch. 5 |
| **MCP** (Model Context Protocol) | An open standard ("USB-C of AI") that turns **N×M** custom integrations into **N+M**. | Ch. 5 |
| **MCP Host / Client / Server / Resources** | The four MCP parts: the app (Host) with a Client that connects to Servers exposing tools/data (Resources). | Ch. 5 |
| **Functions / Extensions / Data Stores** | Google's tool taxonomy: your code runs it (Function) · the agent calls it live (Extension) · the agent retrieves knowledge (Data Store = RAG). | — |
| **A2A** (Agent-to-Agent) | The inter-agent communication protocol — the "agent↔agent" analogue of MCP's "agent↔tools" (taught in M9). | Ch. 5 (noted) |

## Multi-agent, production & cloud

| Term | Plain-language meaning | Module |
|---|---|---|
| **Multi-agent system** | Several specialized agents cooperating; smaller agents also help carry the **context** burden. | M7–M9 |
| **Supervisor / router** | An orchestrator agent that routes work to specialists and aggregates results. | M8 |
| **Guardrails** | Input/output checks + approval gates that keep an agent safe. | M11 |
| **Observability / tracing** | Recording an agent's runs (spans, tokens, latency) to debug and measure it. | M10 |
| **Evaluation scorecard** | Metrics for an agent: success rate, cost/run, p95 latency, groundedness. | M10 |
| **Agency levels (1–5)** | Basic Responder → Router → Tool Calling → Multi-Agent → Autonomous. | M1 |
| **Design pattern** | A reusable way to structure part of an agent (see `PATTERNS.md`). | M2–M11 |
| **Microsoft Foundry** | Azure's managed platform — the "cloud twin" of the modules you build from scratch. | M13–M15 |

---

<div align="center" style="padding:14px; border-top:2px solid #0078d4; margin-top:24px;">
  <p style="color:#888; font-size:12px;">JHF Agentic AI Bootcamp — Glossary · Aligned to <i>An Illustrated Guide to AI Agents</i> (M. Grootendorst) · Organized by JHF · in partnership with COMCEC</p>
</div>
