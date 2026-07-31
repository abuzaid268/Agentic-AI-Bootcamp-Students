<!-- JHF-BRAND -->
<div align="center" style="padding:28px 20px; background:#ffffff; border:2px solid #e0e0e0; border-radius:12px;">
  <p style="margin:0 0 16px 0;">
    <img src="../assets/jhf-logo.png" alt="Jerusalem High-Tech Foundry (JHF)" height="54" style="vertical-align:middle; margin:0 22px;" />
    <img src="../assets/comcec-logo.png" alt="COMCEC - Cooperation for Development" height="72" style="vertical-align:middle; margin:0 22px;" />
  </p>
  <h1 style="color:#1a3c5e; margin:6px 0;">Agentic AI Bootcamp</h1>
  <h3 style="color:#0078d4; margin:4px 0; font-weight:600;">Module 1 &middot; Lab Worksheet &mdash; Build an Agent from Scratch</h3>
  <hr style="border:0; border-top:1px solid #0078d4; width:60%; margin:16px auto;" />
  <p style="font-size:14px; color:#555; margin:6px 0;">
    <strong>Lead Trainer</strong><br/>
    <a href="https://www.linkedin.com/in/alaaldin-ahmed-260266150" target="_blank">Alaaldin Ahmed</a>
  </p>
  <p style="font-size:12.5px; color:#777; margin:8px 0 0 0;">
    Organized by <strong>Jerusalem High-Tech Foundry (JHF)</strong> &nbsp;&middot;&nbsp; In partnership with <strong>COMCEC</strong>
  </p>
</div>

# Module 1 — Lab Worksheet
## Build an Autonomous Agent from Scratch (no frameworks)

> **Time:** ~1h45 (Part 1) + ~45 min (Part 2)
> **Files:** edit `starter-code/agent_loop_starter.py` → save your work as `agent_loop.py`
> **Rule of the day:** do **not** hardcode the steps. The *model* must decide each action. Use GitHub Copilot to write boilerplate faster, but you must understand every line.

---

## Goal

Build an agent that, given a question, decides whether to use a **calculator** tool or return a **final answer**, loops while feeding tool results back into context, and stops safely (final answer or step cap).

**Definition of done:** it solves
> *"What is (23 × 19) + 100, and is that more than 500?"*
by choosing tools on its own across multiple steps.

---

## Before you start (setup gate — 5 min)

1. Confirm Python 3.11+ : `python --version`
2. Set your API key as an environment variable (don't paste keys in code):
   - PowerShell: `$env:OPENROUTER_API_KEY="sk-or-..."`
   - macOS/Linux: `export OPENROUTER_API_KEY="sk-or-..."`
3. Run the one-line smoke test in the starter file's `__main__` guard (instructions in the file). You must get a model response before continuing. **If your key fails, raise your hand now.**

---

## PART 1 — One reasoning step + tool execution (Steps 1–4)

### Step 1 — Define the calculator tool
Write a Python function `calculator(expr: str) -> str` that safely evaluates a simple arithmetic expression and returns the result as a string.
- Keep it simple but **don't use raw `eval` on untrusted input** carelessly — restrict to digits, operators, parentheses, spaces. (Copilot can generate a safe evaluator; review it.)

### Step 2 — Write the system prompt
Tell the model:
- It is an agent that solves problems step by step.
- It **cannot do arithmetic itself** — it must use the `calculator` tool.
- It must respond with **ONLY JSON**, one of:
  - `{"action": "calculator", "args": {"expr": "<expression>"}}`
  - `{"action": "final_answer", "args": {"text": "<answer>"}}`

### Step 3 — Call the model and parse its decision
- Send the system prompt + the user question.
- Parse the returned JSON into a Python dict. (Strip ```` ``` ```` fences if present.)
- 🧪 Checkpoint: print the parsed action. For "What is 23 × 19?" you should see an action `calculator` with `expr` ≈ `"23*19"`.

### Step 4 — Execute the chosen action
- If `action == "calculator"`: call your `calculator()` and capture the result.
- If `action == "final_answer"`: print the text and stop.
- 🧪 Checkpoint: running on "What is 23 × 19?" prints `437` from the tool.

> ✅ **End of Part 1:** the model *chooses*, your code *executes*. You have one turn of the loop working.

---

## PART 2 — The loop, multi-step, and safe stopping (Steps 5–7)

### Step 5 — Wrap it in the agent loop
- Maintain a `messages` list (the running context). Start with system + user.
- Loop:
  1. Call the model with `messages`.
  2. Parse the action.
  3. If `final_answer` → print and break.
  4. If `calculator` → run it, then **append the observation** to `messages` (e.g., a message like `Observation: 437`) so the next reasoning step can see it.

### Step 6 — Add the stopping guards (mandatory)
- Add `MAX_STEPS = 6`. Increment a counter each iteration; if it exceeds `MAX_STEPS`, break with a message like `"Stopped: step budget exhausted."`
- This must be checked **every** iteration. Never rely on the model to stop.

### Step 7 — Add a cost counter
- Track the number of LLM calls and (if your API returns it) total tokens. Print the totals when the loop ends.
- 🧪 **Final checkpoint:** run
  > *"What is (23 × 19) + 100, and is that more than 500?"*
  Your agent should: calc `23*19` → observe `437` → calc `437+100` → observe `537` → final answer "537, yes, more than 500." Print the step count and call count at the end.

---

## Stretch goals (if you finish early)

- **Third tool:** add a stub tool (e.g., `fake_weather(city)`) so the model must choose among **three** actions. Confirm it only calls weather when relevant.
- **Bad-JSON resilience:** make your parser retry once with a "respond with ONLY valid JSON" nudge when parsing fails.
- **Loop detection:** detect if the agent repeats the identical action twice and break early.

---

## Troubleshooting

| Problem | Try this |
|---|---|
| `JSONDecodeError` | Strip code fences; tighten the prompt to "ONLY JSON, no prose"; print the raw output to see what the model sent. |
| Loops forever | Check `MAX_STEPS` is incremented and tested every iteration. |
| Model answers math itself | Strengthen the system prompt: "You may NOT compute arithmetic yourself." |
| Next step ignores the result | Make sure each observation is appended to `messages` before the next call. |
| Repeats the same calc | Print `messages` — confirm observations are actually being added and are visible to the model. |

---

## Submit

1. `agent_loop.py` — runs end-to-end on the final checkpoint question, with `MAX_STEPS` and a cost counter.
2. Your 1-page **"Is this an agent?" note** classifying systems (a), (b), (c) from the handout.

Compare your result with `solution-code/agent_loop_solution.py` **after** you have your own version working.

---

<div align="center" style="padding:14px; border-top:2px solid #0078d4; margin-top:34px;">
  <p style="margin:0 0 8px 0;">
    <img src="../assets/jhf-logo.png" alt="JHF" height="28" style="vertical-align:middle; margin:0 14px; background:#ffffff; padding:6px 10px; border-radius:6px;" />
    <img src="../assets/comcec-logo.png" alt="COMCEC" height="40" style="vertical-align:middle; margin:0 14px; background:#ffffff; padding:6px 10px; border-radius:6px;" />
  </p>
  <p style="color:#888; font-size:13px; margin:0;">
    <strong>JHF Agentic AI Bootcamp</strong> &mdash; Module 1 Lab<br/>
    Lead Trainer: <a href="https://www.linkedin.com/in/alaaldin-ahmed-260266150">Alaaldin Ahmed</a><br/>
    Organized by Jerusalem High-Tech Foundry (JHF) &middot; In partnership with COMCEC
  </p>
</div>

