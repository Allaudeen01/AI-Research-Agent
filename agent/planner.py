"""
Planner node — runs before tool execution.

Asks the model to produce an explicit research plan: what sub-questions to
answer, which tools to use for each, and in what order. The plan is injected
into the conversation so the reasoning loop executes it step-by-step.
"""

import json


PLANNER_PROMPT = """You are a research planning expert. Given a research query,
produce a structured execution plan as JSON (output ONLY valid JSON, no fences):

{
  "research_goal": "one sentence describing the overall goal",
  "sub_questions": [
    "specific question 1 to answer",
    "specific question 2 to answer",
    "..."
  ],
  "tool_plan": [
    {"tool": "wikipedia_lookup", "input": "topic to look up", "reason": "why"},
    {"tool": "web_search",       "input": "search query",     "reason": "why"},
    ...
  ],
  "expected_sections": ["section name 1", "section name 2", "..."]
}

Rules:
- Always include at least one wikipedia_lookup and one web_search.
- Keep sub_questions to 3-5 focused questions.
- tool_plan should have 2-5 steps.
"""


def make_plan(client, model: str, query: str) -> dict:
    """
    Call the model to generate a research plan for the given query.
    Returns the parsed plan dict.
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": PLANNER_PROMPT},
            {"role": "user", "content": f"Research query: {query}"},
        ],
        temperature=0.3,
    )

    raw = response.choices[0].message.content or ""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1])

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback minimal plan
        return {
            "research_goal": query,
            "sub_questions": [query],
            "tool_plan": [
                {"tool": "wikipedia_lookup", "input": query, "reason": "background"},
                {"tool": "web_search", "input": query, "reason": "current info"},
            ],
            "expected_sections": ["Summary", "Key Findings", "Sources"],
        }
