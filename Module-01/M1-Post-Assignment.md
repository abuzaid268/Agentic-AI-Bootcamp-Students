<!-- JHF-BRAND -->
<div align="center" style="padding:28px 20px; background:#ffffff; border:2px solid #e0e0e0; border-radius:12px;">
  <p style="margin:0 0 16px 0;">
    <img src="../assets/jhf-logo.png" alt="Jerusalem High-Tech Foundry (JHF)" height="54" style="vertical-align:middle; margin:0 22px;" />
    <img src="../assets/comcec-logo.png" alt="COMCEC - Cooperation for Development" height="72" style="vertical-align:middle; margin:0 22px;" />
  </p>
  <h1 style="color:#1a3c5e; margin:6px 0;">Agentic AI Bootcamp</h1>
  <h3 style="color:#0078d4; margin:4px 0; font-weight:600;">Module 1 &middot; Post-Session Assignment &mdash; What Agentic AI Really Is</h3>
  <hr style="border:0; border-top:1px solid #0078d4; width:60%; margin:16px auto;" />
  <p style="font-size:14px; color:#555; margin:6px 0;">
    <strong>Lead Trainer</strong><br/>
    <a href="https://www.linkedin.com/in/alaaldin-ahmed-260266150" target="_blank">Alaaldin Ahmed</a>
  </p>
  <p style="font-size:12.5px; color:#777; margin:8px 0 0 0;">
    Organized by <strong>Jerusalem High-Tech Foundry (JHF)</strong> &nbsp;&middot;&nbsp; In partnership with <strong>COMCEC</strong>
  </p>
</div>

# Module 1 — Post-Session Assignment
## What Agentic AI Really Is

> **Complete AFTER the session, before Module 2.** Estimated time: **~60 minutes.**
> This **extends** today's lab (it does not repeat it). It consolidates the agent loop and primes you for M2.
> Feeds into: your understanding for the Phase 1 mini-project. Light-touch — focus on learning, not polish.

---

## Goal

Take the agent loop you built in class and make it **more capable and more robust** — proving you understand *why* each part exists, not just that it runs.

---

## Tasks

### 1. Add a second tool (core, ~25 min)
Extend your `agent_loop.py` so the model must choose among **three** actions: `calculator`, a new **`lookup`** tool (a small hardcoded dictionary, e.g., country → capital), and `final_answer`.
- The model should call `lookup` only when the question needs it, and `calculator` only for math.
- ✅ Test: *"What is the capital of France, and what is 12 × 12?"* — the agent should use **both** tools across separate steps, then answer.

### 2. Make it robust (core, ~20 min)
Add **two** of the following hardening features (your choice):
- **Bad-JSON retry:** if the model's action can't be parsed, retry once with a "respond with ONLY valid JSON" nudge before failing.
- **Loop detection:** if the agent repeats the identical action twice in a row, stop with a clear message.
- **Cost guard:** stop if total LLM calls exceed a budget you set, returning a graceful "couldn't finish in budget."

### 3. Reflect (short, ~15 min)
Write **5–8 sentences** answering:
- Where did your agent **almost** loop or misbehave, and which guard caught it?
- Give one concrete example where adding more tools made the agent **harder** to keep reliable. (This previews why we add structure in M3.)

---

## Deliverables
1. Your updated `agent_loop.py` (three tools + two robustness features).
2. A short `reflection.md` (the 5–8 sentences from Task 3).

---

## Acceptance Checklist
- [ ] The agent correctly routes to `lookup` vs `calculator` vs `final_answer`.
- [ ] A multi-tool question is solved across multiple steps (no hardcoded sequence).
- [ ] Two robustness features work (demonstrate each, e.g., feed it a tricky input).
- [ ] The reflection names a real failure mode you observed.

---

## Looking Ahead to M2
In the next module you'll stop hand-writing the loop and let **LangGraph** and **CrewAI** run it for you. Notice, as you do this assignment, **how much plumbing you're writing by hand** (parsing, routing, guards) — that's exactly what frameworks will take over.

> Stuck? Re-read §2 of the M1 Handout (the agent loop) and revisit the lab worksheet's troubleshooting table. Compare against `solution-code/agent_loop_solution.py` only after attempting it yourself.

---

<div align="center" style="padding:14px; border-top:2px solid #0078d4; margin-top:34px;">
  <p style="margin:0 0 8px 0;">
    <img src="../assets/jhf-logo.png" alt="JHF" height="28" style="vertical-align:middle; margin:0 14px; background:#ffffff; padding:6px 10px; border-radius:6px;" />
    <img src="../assets/comcec-logo.png" alt="COMCEC" height="40" style="vertical-align:middle; margin:0 14px; background:#ffffff; padding:6px 10px; border-radius:6px;" />
  </p>
  <p style="color:#888; font-size:13px; margin:0;">
    <strong>JHF Agentic AI Bootcamp</strong> &mdash; Module 1 Assignment<br/>
    Lead Trainer: <a href="https://www.linkedin.com/in/alaaldin-ahmed-260266150">Alaaldin Ahmed</a><br/>
    Organized by Jerusalem High-Tech Foundry (JHF) &middot; In partnership with COMCEC
  </p>
</div>

