"""
Module 2 Lab — STARTER (CrewAI "hello agent")
Goal: one role + one task that, given a topic, returns a one-sentence definition.

Fill in the TODOs. Notice you DESCRIBE roles/tasks — you don't wire nodes/edges.
Set your key in .env (OPENROUTER_API_KEY=sk-or-...).
"""

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process

load_dotenv()


def build_crew() -> Crew:
    # TODO (Step 5): create an Agent (role / goal / backstory).
    definer = Agent(
        role="TODO",
        goal="TODO",
        backstory="TODO",
        verbose=True,
    )

    # TODO (Step 5): create a Task that defines {topic} in ONE sentence.
    define_task = Task(
        description="TODO: Define {topic} in exactly one sentence.",
        expected_output="TODO: a single-sentence definition.",
        agent=definer,
    )

    # TODO (Step 5): assemble the Crew with a sequential process.
    return Crew(
        agents=[definer],
        tasks=[define_task],
        process=Process.sequential,
        verbose=True,
    )


if __name__ == "__main__":
    crew = build_crew()
    result = crew.kickoff(inputs={"topic": "agentic AI"})
    print(result)
