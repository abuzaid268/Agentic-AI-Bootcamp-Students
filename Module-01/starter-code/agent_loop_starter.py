"""
Module 1 Lab — STARTER
Build an autonomous agent loop from scratch (no frameworks).

Fill in the TODOs. Do NOT hardcode the steps — the MODEL must decide each action.
Use GitHub Copilot to help, but understand every line.

Setup:
  1) python --version   (need 3.11+)
  2) Set your key:  PowerShell ->  $env:OPENROUTER_API_KEY="sk-or-..."
  3) pip install openai   (OpenRouter is OpenAI-compatible; we use the openai SDK).

This bootcamp calls models through OpenRouter. Implement `call_model(messages)`
using the openai SDK pointed at OpenRouter's base URL (see the hint below).
"""

import os
import re
import json

MAX_STEPS = 6                    # hard stop — never trust the model to stop itself
MODEL = "openai/gpt-4o-mini"     # OpenRouter model id (note the "provider/" prefix)
BASE_URL = "https://openrouter.ai/api/v1"

# ---------------------------------------------------------------------------
# 1) TOOL: calculator
# ---------------------------------------------------------------------------
def calculator(expr: str) -> str:
    """Safely evaluate a simple arithmetic expression and return the result."""
    # TODO (Step 1): allow only digits, + - * / ( ) . and spaces, then evaluate.
    # Reject anything else. Return the result as a string.
    raise NotImplementedError


# ---------------------------------------------------------------------------
# 2) SYSTEM PROMPT
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
TODO (Step 2): Write the system prompt.
- You are an agent that solves problems step by step.
- You CANNOT do arithmetic yourself; you must use the `calculator` tool.
- Respond with ONLY JSON, one of:
    {"action": "calculator",   "args": {"expr": "<expression>"}}
    {"action": "final_answer", "args": {"text": "<answer>"}}
No prose, no code fences.
"""


# ---------------------------------------------------------------------------
# 3) MODEL CALL  (implement with the openai SDK -> OpenRouter)
# ---------------------------------------------------------------------------
def call_model(messages: list) -> str:
    """Send messages to the LLM and return the raw text content of the reply."""
    # TODO: build an OpenAI client with api_key=os.environ["OPENROUTER_API_KEY"]
    #       and base_url=BASE_URL, then call client.chat.completions.create(
    #       model=MODEL, messages=messages, temperature=0). Return the text.
    raise NotImplementedError


def parse_action(raw: str) -> dict:
    """Parse the model's JSON action. Strips ``` fences if present."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# 4 + 5 + 6 + 7) THE AGENT LOOP
# ---------------------------------------------------------------------------
def run_agent(question: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    llm_calls = 0

    for step in range(1, MAX_STEPS + 1):
        # TODO (Step 5): call model, count the call, parse the action.
        # TODO (Step 4): if final_answer -> return it.
        #                if calculator   -> run it, append observation to messages.
        # TODO (Step 6): the for-loop already caps steps; print a message if exhausted.
        # TODO (Step 7): track llm_calls and print totals when done.
        raise NotImplementedError

    print(f"[stopped] step budget exhausted. llm_calls={llm_calls}")
    return "No final answer (budget exhausted)."


if __name__ == "__main__":
    # Smoke test (Setup gate): uncomment to verify your key/model works first.
    # print(call_model([{"role": "user", "content": "Reply with the single word: ok"}]))

    q = "What is (23 * 19) + 100, and is that more than 500?"
    print(run_agent(q))
