"""
Module 2 Lab — STARTER (LangGraph "hello agent")
Goal: a tiny graph that, given a topic, returns a one-sentence definition.

Fill in the TODOs. Keep it minimal — the point is to FEEL explicit control flow.
Set your key in .env (OPENROUTER_API_KEY=sk-or-...) and load it with python-dotenv.
"""

from typing import TypedDict
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
# from langchain_openai import ChatOpenAI   # or your provider's integration

load_dotenv()


class State(TypedDict):
    topic: str
    definition: str


# TODO (Step 3): initialize your chat model (reads key from env).
# llm = ChatOpenAI(
#     model="openai/gpt-4o-mini", temperature=0,
#     base_url="https://openrouter.ai/api/v1",
#     api_key=os.environ["OPENROUTER_API_KEY"],   # add `import os`
# )


def define(state: State) -> State:
    """Node: produce a one-sentence definition of state['topic']."""
    # TODO (Step 3): call the model to define state["topic"] in ONE sentence,
    # write the text into state["definition"], and return state.
    raise NotImplementedError


def format_output(state: State) -> State:
    """Node (Step 4): wrap the definition, e.g. prefix 'Definition: '."""
    # TODO (Step 4)
    raise NotImplementedError


def build_graph():
    g = StateGraph(State)
    g.add_node("define", define)
    # TODO (Step 4): add the format_output node.
    g.set_entry_point("define")
    # TODO (Step 3): edge define -> END  (then in Step 4: define -> format_output -> END)
    return g.compile()


if __name__ == "__main__":
    app = build_graph()
    result = app.invoke({"topic": "agentic AI", "definition": ""})
    print(result["definition"])
