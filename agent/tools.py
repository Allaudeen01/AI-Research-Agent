"""
Tools available to the Research Agent.
  - web_search       : searches the web using Tavily API
  - wikipedia_lookup : fetches a Wikipedia summary (no key needed)
"""

import os
import json
import urllib.request
import urllib.parse


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def web_search(query: str) -> dict:
    """
    Search the web using Tavily Search API.
    Returns a list of results with title, url, and content snippet.
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY environment variable not set.")

    payload = json.dumps({
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": 5,
        "include_answer": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))

    results = []
    if data.get("answer"):
        results.append({"type": "direct_answer", "content": data["answer"]})

    for r in data.get("results", []):
        results.append({
            "type": "web_result",
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", "")[:600],
        })

    return {"query": query, "results": results}


def wikipedia_lookup(topic: str) -> dict:
    """
    Fetch a Wikipedia summary for a given topic.
    Uses the public Wikipedia REST API — no API key required.
    """
    encoded = urllib.parse.quote(topic.replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ResearchAgent/1.0 (take-home assignment)"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        return {
            "topic": topic,
            "title": data.get("title", ""),
            "summary": data.get("extract", "No summary available."),
            "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        }
    except Exception as e:
        return {"topic": topic, "error": str(e)}


# ---------------------------------------------------------------------------
# Tool registry — schemas for OpenAI function/tool calling
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information, recent news, statistics, "
                "or any topic that needs up-to-date data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wikipedia_lookup",
            "description": (
                "Look up background, encyclopedic, or foundational information "
                "about a topic on Wikipedia."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic to look up on Wikipedia.",
                    }
                },
                "required": ["topic"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "web_search": web_search,
    "wikipedia_lookup": wikipedia_lookup,
}
