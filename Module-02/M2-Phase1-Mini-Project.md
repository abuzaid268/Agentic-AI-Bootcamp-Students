# Module 2 — Phase 1 Mini-Project
## Build the same Study Guide Agent in LangGraph and CrewAI

> **This is a hands-on coding project.** You will build the same three-task agent twice.
>
> **Estimated time:** 90–120 minutes after Saturday's class
> **Due:** before Friday 14 August 2026

---

## The project

Build a **Study Guide Agent**.

Given a topic such as `Model Context Protocol`, the agent must produce:

1. a short plain-language explanation;
2. a practical example and one common misconception;
3. a three-question mini-quiz with answers.

You must build the same purpose twice:

```text
study_guide_langgraph.py
study_guide_crewai.py
```

The task is more complex than the Module 2 hello agent because it has three connected tasks and later tasks depend on earlier results.

---

## What you are practising

This project applies the Module 2 ideas directly:

| Module 2 idea | Where you use it |
|---|---|
| State/data flow | explanation, example, and quiz move through the system |
| Explicit control flow | LangGraph nodes and edges |
| Higher-level orchestration | CrewAI sequential tasks |
| Reproducibility | same model, provider, and topic in both versions |
| Framework choice | implement the same purpose in two styles |

This is **not** the Module 7 multi-agent project. Use one worker in CrewAI and three sequential tasks. The deeper Researcher → Analyst → Writer crew comes later.

---

# Part A — LangGraph implementation

Open:

```text
starter-code/study_guide_langgraph_starter.py
```

Create a graph with these three nodes:

```text
START → explain_topic → create_example → create_quiz → END
```

## Task 1 — `explain_topic`

Read `state["topic"]` and ask the model for:

- 2–3 plain-language sentences;
- no invented statistics;
- no quiz yet.

Store the result in `state["explanation"]`.

## Task 2 — `create_example`

Read both `state["topic"]` and `state["explanation"]`.

Ask the model for:

- one practical example;
- one common misconception;
- a clear distinction between the example and the misconception.

Store the result in `state["example"]`.

## Task 3 — `create_quiz`

Read the topic, explanation, and example. This task is also the final assembly step.

Ask the model for exactly three questions followed by an answer key. Store the result in `state["quiz"]`.

The final output must contain all three sections:

```text
## Explanation
## Example and misconception
## Quiz
```

In other words, the third task must not throw away the work from Tasks 1 and 2. It must assemble the complete study guide.

## LangGraph requirements

- Use a typed state with `topic`, `explanation`, `example`, and `quiz`.
- Use three nodes.
- Use explicit edges between the nodes.
- Compile the graph.
- Invoke it with one topic.
- Return or print all three sections.

Do not hardcode the study-guide answer. The model must generate it.

---

# Part B — CrewAI implementation

Open:

```text
starter-code/study_guide_crewai_starter.py
```

Use **one Agent and three sequential Tasks**:

```text
one Study Guide Agent
        │
        ├── Task 1: explain the topic
        ├── Task 2: create an example from Task 1
        └── Task 3: create a quiz from Tasks 1 and 2
```

## Agent

Give the Agent:

- a role such as `Patient Study Guide Teacher`;
- a goal focused on accurate, understandable learning material;
- a backstory that says it must not invent facts.

## Task 1

Ask for the plain-language explanation and set a concrete `expected_output`.

## Task 2

Ask for the practical example and misconception. Pass Task 1 as context:

```python
context=[explain_task]
```

## Task 3

Ask for exactly three questions and an answer key, then assemble the complete study guide using the earlier work. Pass the earlier work as context:

```python
context=[explain_task, example_task]
```

## CrewAI requirements

- Use one Agent.
- Use three Tasks.
- Use `Process.sequential`.
- Use `kickoff(inputs={"topic": topic})`.
- Keep `tracing=False`.
- Save or print the final study guide, not only the quiz.

Do not create three agents. Multi-agent collaboration is Module 7.

---

# Part C — Test both implementations

Use the same topic and model in both programs. Try at least:

```text
Model Context Protocol
```

Then try a second topic:

```text
temperature in language models
```

Check:

- the explanation is understandable;
- the example is related to the topic;
- the misconception is not presented as a fact;
- the quiz contains exactly three questions;
- the answer key matches the questions;
- neither implementation contains a hardcoded answer.

---

# Required deliverables

Submit:

1. `study_guide_langgraph.py`
2. `study_guide_crewai.py`
3. one generated study guide from each implementation
4. `README.md` containing:
   - setup and run commands;
   - the topic you tested;
   - three short observations about building the same system twice.

Your observations should answer:

- What did LangGraph make explicit?
- What did CrewAI automate or hide?
- What would you choose for this three-task pipeline, and why?

This is a short engineering reflection, **not a comparison-table assignment**.

---

## Acceptance checklist

- [ ] Both implementations run with the same topic.
- [ ] Both implementations contain three real tasks.
- [ ] Later tasks use earlier results.
- [ ] LangGraph uses three nodes and explicit edges.
- [ ] CrewAI uses one Agent, three Tasks, and a sequential Crew.
- [ ] The final output contains explanation, example/misconception, and quiz/answers.
- [ ] `.env`, `.venv`, and `__pycache__` are not committed.
- [ ] No answer is hardcoded.

---

## Optional stretch

Only after the required project works:

- add a fourth quality-check node/task;
- add a conditional route when the topic is empty;
- count model calls and compare the cost of the two implementations.
