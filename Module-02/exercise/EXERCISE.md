# Module 2 Exercise — The Error Helper

**Time:** ~1 hour · **You will build:** the same two-step agent twice

---

## The job

You paste in a Python traceback. The agent gives you back two things:

1. **What went wrong** — in plain language, not jargon
2. **How to fix it** — concrete steps

Three real tracebacks are already in the file. You'll meet all three today.

---

## Why two steps and not one

On Friday your hello agent had **one** step. There was nothing to hand over.

Here, step 2 works from **step 1's answer** — not from the original traceback:

```text
traceback ──► explain_error ──► suggest_fix ──► answer
                    │                ▲
                    └── explanation ─┘
```

That arrow is the whole exercise. Everything else you have already seen.

After the break, the mini-project has three steps and two arrows. Same idea,
one more link in the chain.

---

## Part A — LangGraph (~25 min)

Open `starter-code/error_helper_langgraph_starter.py`. Five TODOs:

| TODO | What you write |
|---|---|
| 1 | the model client |
| 2 | the `explain_error` node |
| 3 | the `suggest_fix` node |
| 4 | register both nodes |
| 5 | entry point + edges |

Run it:

```bash
python error_helper_langgraph_starter.py       # sample 1
python error_helper_langgraph_starter.py 2     # sample 2
python error_helper_langgraph_starter.py 3     # sample 3
```

**One thing to watch.** Every node must end with `return state`. Delete that
line from one node and run it again. You get no error — just an empty section.
Nothing tells you what happened. Put it back once you have seen it.

---

## Part B — CrewAI (~25 min)

Open `starter-code/error_helper_crewai_starter.py`. Five TODOs:

| TODO | What you write |
|---|---|
| 1 | the model client |
| 2 | the Agent (role / goal / backstory) |
| 3 | Task 1 — explain |
| 4 | Task 2 — fix, with `context=[explain_task]` |
| 5 | the Crew |

**One thing to watch.** Run this experiment in order, and watch carefully:

| Try this | What happens |
|---|---|
| `context=[explain_task]` | works |
| delete the whole `context=` line | **still works** |
| `context=[]` | breaks — the answer falls apart |

The middle one surprises most people. In a sequential crew, a task with no
`context=` **automatically receives every earlier task's output**. CrewAI
connected them for you without being asked.

So `context=` is not what switches the hand-off on. It is how you **control**
it — how you say *"only this task, not everything before me."*

Now compare with LangGraph: there, nothing is connected until you draw the edge
yourself. Two very different philosophies:

> **LangGraph connects nothing until you say so. CrewAI connects everything
> unless you say otherwise.**

Neither is better. But you must know which one you are using.

---

## Done when

- [ ] Both versions run on all three samples
- [ ] Both print a diagnosis and then a fix
- [ ] You have removed `return state` in LangGraph, seen the empty section, and put it back
- [ ] You have tried `context=[]` in CrewAI, seen the answer fall apart, and put it back
- [ ] You can say which framework showed you more, and which wrote you less

---

## If you finish early

Paste in a **real** traceback from your own machine and run it.

Then look at sample 2 (`TypeError: 'NoneType' object is not subscriptable`)
and read the fix carefully. The agent says "check whether it is None." That is
true, but it is not the real cause — that traceback comes from a LangGraph node
that forgot to `return state`.

Why couldn't the agent tell you that? Because step 2 only ever saw step 1's
explanation. It never saw your code.

**Nothing is broken. The agent answered exactly what it was given.** Hold on to
that thought — giving an agent access to more than a text prompt is what the
rest of this course is about.
