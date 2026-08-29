"""
Module 3 Lab — STARTER
ReAct + Planning agent in LangGraph with STRUCTURED OUTPUTS.

Part 1: ReAct graph (reason -> act -> observe) using a schema-validated Action.
Part 2: add a planner (plan-and-execute) + replan loop.

Fill in the TODOs. No manual JSON parsing — use with_structured_output().
Set your key in .env (OPENROUTER_API_KEY=sk-or-...).
"""

from typing import TypedDict, Literal, Optional
import re
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
# from langchain_openai import ChatOpenAI

load_dotenv()

MAX_STEPS = 8
MAX_REPLANS = 5

# llm = ChatOpenAI(
#     model="openai/gpt-4o-mini", temperature=0,
#     base_url="https://openrouter.ai/api/v1",
#     api_key=os.environ["OPENROUTER_API_KEY"],   # add `import os`
# )


# ---------------------------------------------------------------------------
# Tool: calculator (reuse M1 — safe, returns error string instead of raising)
# ---------------------------------------------------------------------------
_ALLOWED = re.compile(r"^[0-9+\-*/().\s]+$")

def calculator(expr: str) -> str:
    # TODO (Step 3): validate against _ALLOWED, eval safely, return result or error string.
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Schemas (structured outputs)
# ---------------------------------------------------------------------------
class Action(BaseModel):
    """Step 2: the schema-validated action the model must return."""
    tool: Literal["calculator", "final_answer"]
    args: dict = Field(default_factory=dict)


class Plan(BaseModel):
    """Step 6: an ordered list of concrete, tool-executable steps."""
    steps: list[str]


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------
class State(TypedDict):
    question: str
    scratchpad: list
    action: Optional[dict]
    answer: Optional[str]
    plan: list
    past_steps: list


# ---------------------------------------------------------------------------
# PART 1 — ReAct nodes
# ---------------------------------------------------------------------------
def reason(state: State) -> State:
    # TODO (Step 4): call llm.with_structured_output(Action) with question + scratchpad,
    # store the chosen action dict in state["action"].
    raise NotImplementedError


def act(state: State) -> State:
    # TODO (Step 4): if tool == final_answer -> set state["answer"].
    #                if tool == calculator   -> run it, append observation to scratchpad.
    raise NotImplementedError


def is_done(state: State) -> str:
    # TODO (Step 5): return "end" if state["answer"] else "loop"
    raise NotImplementedError


# ---------------------------------------------------------------------------
# PART 2 — Planning nodes
# ---------------------------------------------------------------------------
def planner(state: State) -> State:
    # TODO (Step 6): produce a Plan from the question; store steps in state["plan"].
    raise NotImplementedError


def executor(state: State) -> State:
    # TODO (Step 7): take next plan step, run it via ReAct mechanics (reason+act),
    # append (step, observation) to state["past_steps"].
    raise NotImplementedError


def replan(state: State) -> State:
    # TODO (Step 8): decide finish (set state["answer"]) or update remaining plan.
    raise NotImplementedError


def replan_done(state: State) -> str:
    # TODO (Step 8): "end" if answer else "loop"
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------
def build_react_graph():
    """Part 1 graph: reason -> act -> (loop|END)."""
    g = StateGraph(State)
    g.add_node("reason", reason)
    g.add_node("act", act)
    g.set_entry_point("reason")
    g.add_edge("reason", "act")
    # TODO (Step 5): conditional edge after act -> {"end": END, "loop": "reason"}
    return g.compile()


def build_plan_execute_graph():
    """Part 2 graph: planner -> executor -> replan -> (loop|END)."""
    g = StateGraph(State)
    # TODO (Steps 6-8): add planner, executor, replan nodes; wire edges + conditional.
    return g.compile()


if __name__ == "__main__":
    q = "A team has 3 sprints of 12, 19, and 8 story points. " \
        "What's the average per sprint, and is it above 12?"
    app = build_plan_execute_graph()
    result = app.invoke({
        "question": q, "scratchpad": [], "action": None,
        "answer": None, "plan": [], "past_steps": [],
    })
    print("ANSWER:", result.get("answer"))
    # Step 9: visualize ->  app.get_graph().draw_mermaid_png()  (or print mermaid)
