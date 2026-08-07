<!-- JHF-BRAND -->
<div align="center" style="padding:28px 20px; background:#ffffff; border:2px solid #e0e0e0; border-radius:12px;">
  <p style="margin:0 0 16px 0;">
    <img src="../assets/jhf-logo.png" alt="Jerusalem High-Tech Foundry (JHF)" height="54" style="vertical-align:middle; margin:0 22px;" />
    <img src="../assets/comcec-logo.png" alt="COMCEC - Cooperation for Development" height="72" style="vertical-align:middle; margin:0 22px;" />
  </p>
  <h1 style="color:#1a3c5e; margin:6px 0;">Agentic AI Bootcamp</h1>
  <h3 style="color:#0078d4; margin:4px 0; font-weight:600;">Module 2 &middot; Lab Worksheet &mdash; Hello Agent in LangGraph &amp; CrewAI</h3>
  <hr style="border:0; border-top:1px solid #0078d4; width:60%; margin:16px auto;" />
  <p style="font-size:14px; color:#555; margin:6px 0;">
    <strong>Lead Trainer</strong><br/>
    <a href="https://www.linkedin.com/in/alaaldin-ahmed-260266150" target="_blank">Alaaldin Ahmed</a>
  </p>
  <p style="font-size:12.5px; color:#777; margin:8px 0 0 0;">
    Organized by <strong>Jerusalem High-Tech Foundry (JHF)</strong> &nbsp;&middot;&nbsp; In partnership with <strong>COMCEC</strong>
  </p>
</div>

# Module 2 — Lab Worksheet
## Bootstrap a Reproducible Repo + "Hello Agent" in LangGraph and CrewAI

> **Time:** ~1h05 · **Goal:** a clean, reproducible project and the **same task** running in **both** frameworks, so you can compare them.
> Use GitHub Copilot for boilerplate — but understand every line.

---

## The task both agents perform
Keep it trivial on purpose: **given a topic, return a one-sentence definition.** Same input, both frameworks — you're comparing the *plumbing*, not the difficulty.

---

## PART A — Reproducible scaffold (Steps 1–2)

### Step 1 — Project + virtual environment
1. Create a project folder, e.g. `m2-hello-agents/`.
2. Create and activate a venv:
   - PowerShell: `python -m venv .venv` then `.\.venv\Scripts\Activate.ps1`
3. Confirm you're in the venv (prompt shows `(.venv)`).

### Step 2 — Lockfile, secrets, gitignore
1. Create `requirements.txt` (pin versions — see `starter-code/requirements.txt`):
   ```
   openai
   langgraph
   langchain-openai
   crewai
   python-dotenv
   ```
   Install: `pip install -r requirements.txt`. Then **freeze pinned versions**: `pip freeze > requirements.lock.txt`.
2. Create `.env` (all LLM calls go through OpenRouter — OpenAI-compatible):
   ```
   OPENROUTER_API_KEY=sk-or-...
   OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
   ```
3. Create `.gitignore` containing at least:
   ```
   .venv/
   .env
   __pycache__/
   ```
4. 🧪 Checkpoint: `.env` must be listed in `.gitignore` **before** any commit. (Instructor will check.)

---

## PART B — Hello agent in LangGraph (Steps 3–4)

### Step 3 — One-node graph
Open `starter-code/hello_langgraph_starter.py`. Build:
- A typed state (a dict with at least `topic` and `definition`).
- One **node** `define(state)` that calls the model to produce a one-sentence definition and writes it into state.
- Set the **entry point** to `define`, add an edge `define → END`, **compile**, and **invoke** with `{"topic": "agentic AI"}`.
- 🧪 Checkpoint: prints a one-sentence definition.

### Step 4 — Feel the edges (add a second node)
Add a second node `format_output(state)` that wraps the definition (e.g., prefixes `"Definition: "`). Wire `define → format_output → END`.
- 🧪 Checkpoint: you now *see* control flow as explicit edges. Note how the state flows node-to-node.

---

## PART C — Hello agent in CrewAI (Step 5)

### Step 5 — One role, one task
Open `starter-code/hello_crewai_starter.py`. Build:
- One `Agent` with a role like *"Concise Encyclopedia"*, a goal, and a backstory.
- One `Task` whose description is *"Define {topic} in exactly one sentence."* with an `expected_output`.
- A `Crew` with that agent + task and a **sequential** process; call `crew.kickoff(inputs={"topic": "agentic AI"})`.
- 🧪 Checkpoint: prints a one-sentence definition for the same topic.

> Notice: you **described roles and a task**; you did **not** wire nodes/edges. That's the philosophical difference.

---

## PART D — Compare (Step 6, deliverable)

### Step 6 — Fill in the comparison table (from YOUR experience)

| Question | LangGraph | CrewAI |
|---|---|---|
| Lines of code to first result | | |
| Where did control flow live? | | |
| What felt verbose? | | |
| What felt "magical"/hidden? | | |
| When would you choose this one? | | |

Write 2–3 sentences: *for the multi-agent module later, which would you reach for first, and why?*

---

## Stretch goals

- **LangGraph conditional edge:** add a node that, if the topic is empty, routes to an "ask for topic" node instead of `define` (preview of M3 control flow).
- **CrewAI tiny tool:** give the agent a trivial tool (e.g., a function returning today's date) and have the task use it.
- **Same model, both frameworks:** confirm both call the *same* model/provider via your `.env` so the comparison is fair.

---

## Troubleshooting

| Problem | Try this |
|---|---|
| Install conflicts | Fresh venv; pin versions; `pip install -r requirements.txt` inside the venv. |
| Auth/KeyError | Confirm `load_dotenv()` runs and the var name matches `.env`. |
| LangGraph "does nothing" | Check `set_entry_point`, the edge to `END`, `.compile()`, and `.invoke()`. |
| CrewAI no output | Verify agent→task→crew wiring and that you called `crew.kickoff(...)`. |
| Accidentally committed `.env` | Add to `.gitignore`, remove from tracking, and rotate the key. |

---

## Submit
1. The repo scaffold (venv excluded, lockfile + `.gitignore` + git-ignored `.env`).
2. `hello_langgraph.py` and `hello_crewai.py` producing the same one-sentence definition.
3. Your completed comparison table.

Compare with `solution-code/` **after** you have both running.

---

<div align="center" style="padding:14px; border-top:2px solid #0078d4; margin-top:34px;">
  <p style="margin:0 0 8px 0;">
    <img src="../assets/jhf-logo.png" alt="JHF" height="28" style="vertical-align:middle; margin:0 14px; background:#ffffff; padding:6px 10px; border-radius:6px;" />
    <img src="../assets/comcec-logo.png" alt="COMCEC" height="40" style="vertical-align:middle; margin:0 14px; background:#ffffff; padding:6px 10px; border-radius:6px;" />
  </p>
  <p style="color:#888; font-size:13px; margin:0;">
    <strong>JHF Agentic AI Bootcamp</strong> &mdash; Module 2 Lab<br/>
    Lead Trainer: <a href="https://www.linkedin.com/in/alaaldin-ahmed-260266150">Alaaldin Ahmed</a><br/>
    Organized by Jerusalem High-Tech Foundry (JHF) &middot; In partnership with COMCEC
  </p>
</div>

