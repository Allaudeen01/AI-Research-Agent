"""
Core agentic loop for the Research Agent.

Pipeline:
  1. [Planning]    Planner node analyses the query and produces a research plan.
  2. [Searching /  Agentic tool-calling loop — model autonomously calls web_search
     Reading]      and wikipedia_lookup until it has enough information.
  3. [Summarizing] Model synthesises all findings into a structured JSON report.
  4. [Done]        Confidence score is computed and attached to the report.
"""

import os
import json
import datetime
from typing import Callable, Optional

from agent.llm_client import get_client, provider_info
from agent.tools import TOOLS, TOOL_FUNCTIONS
from agent.planner import make_plan
from agent.logger import ReasoningLogger
from agent.confidence import compute_confidence
from agent.credibility import classify_sources, credibility_summary

# Groq-specific error — import gracefully so the code works without groq installed
try:
    from groq import BadRequestError as GroqBadRequestError
except ImportError:
    GroqBadRequestError = None


MAX_ITERATIONS = 10  # safety cap on the agentic loop

SYSTEM_PROMPT = """You are an expert research assistant. A research plan has been
provided to you. Follow it as closely as possible:

1. Call `web_search` and `wikipedia_lookup` as specified in the plan.
2. You may add extra tool calls if you need more data.
3. After gathering enough information, produce a structured research report in the
   following JSON format (output ONLY valid JSON, no markdown fences):

{
  "title": "...",
  "query": "...",
  "summary": "3-4 sentence executive summary",
  "key_findings": ["finding 1", "finding 2", "finding 3", "..."],
  "sources": [
    {"title": "...", "url": "..."},
    ...
  ],
  "limitations": "What this report might be missing or caveats to keep in mind"
}
"""


class ResearchAgent:
    def __init__(
        self,
        verbose: bool = True,
        on_log: Optional[Callable] = None,
    ):
        """
        Parameters
        ----------
        verbose  : print log entries to stdout
        on_log   : optional callback(LogEntry) for real-time UI updates

        The LLM provider and model are read from environment variables:
          LLM_PROVIDER = "groq"   (default) | "openai"
          GROQ_API_KEY / OPENAI_API_KEY
          GROQ_MODEL   / OPENAI_MODEL       (optional overrides)
        """
        self.client, self.model = get_client()
        self.verbose = verbose
        self.on_log = on_log
        self._provider = provider_info()

    def _make_logger(self) -> ReasoningLogger:
        def _callback(entry):
            if self.verbose:
                print(str(entry))
            if self.on_log:
                self.on_log(entry)

        return ReasoningLogger(on_entry=_callback)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, query: str) -> dict:
        """
        Run the full agent pipeline for a given query.
        Returns a structured report dict that includes confidence scoring
        and the full reasoning log.
        """
        logger = self._make_logger()
        tool_calls_log: list[str] = []   # ordered list of tool names called

        if self.verbose:
            prov = self._provider
            print(f"\n{'='*60}")
            print(f"  Research Agent  |  {prov['icon']} {prov['provider']} / {prov['model']}")
            print(f"  Query: {query}")
            print(f"{'='*60}")

        # ── Stage 1: Planning ──────────────────────────────────────────
        logger.planning("Analysing query and generating research plan...")
        plan = make_plan(self.client, self.model, query)

        logger.planning(
            f"Plan ready — {len(plan.get('tool_plan', []))} steps, "
            f"{len(plan.get('sub_questions', []))} sub-questions",
            detail=f"Goal: {plan.get('research_goal', query)}",
        )

        # Embed the plan into the first user message so the agent follows it
        plan_text = json.dumps(plan, indent=2)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Research query: {query}\n\n"
                    f"Your research plan:\n```json\n{plan_text}\n```\n\n"
                    "Execute the plan now."
                ),
            },
        ]

        # ── Stage 2: Tool-calling loop (Searching / Reading) ───────────
        tool_call_count = 0
        MAX_RETRIES = 2

        for iteration in range(MAX_ITERATIONS):

            # Retry wrapper — handles Groq tool_use_failed malformed JSON
            response = None
            for attempt in range(MAX_RETRIES):
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        tools=TOOLS,
                        tool_choice="auto",
                    )
                    break  # success
                except Exception as exc:
                    is_tool_use_failed = (
                        GroqBadRequestError is not None
                        and isinstance(exc, GroqBadRequestError)
                        and "tool_use_failed" in str(exc)
                    )
                    if is_tool_use_failed and attempt < MAX_RETRIES - 1:
                        logger.log("Error", f"Malformed tool call (attempt {attempt+1}), retrying…")
                        # Remove the bad assistant message if it was appended
                        if messages and messages[-1].get("role") == "assistant":
                            messages.pop()
                        # Nudge the model to use correct JSON syntax
                        messages.append({
                            "role": "user",
                            "content": (
                                "Your previous tool call had malformed JSON. "
                                "Please call the tool again using strictly valid JSON arguments."
                            ),
                        })
                    else:
                        raise  # re-raise if not retryable or out of retries

            message = response.choices[0].message
            messages.append(message)

            # No more tool calls → move to summarising
            if not message.tool_calls:
                break

            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                tool_call_count += 1
                tool_calls_log.append(fn_name)

                # Log with the right stage label
                arg_preview = list(fn_args.values())[0] if fn_args else ""
                logger.for_tool(
                    fn_name,
                    f"Calling {fn_name}",
                    detail=f'Input: "{arg_preview}"',
                )

                if fn_name not in TOOL_FUNCTIONS:
                    result = {"error": f"Unknown tool: {fn_name}"}
                    logger.error(f"Unknown tool requested: {fn_name}")
                else:
                    try:
                        result = TOOL_FUNCTIONS[fn_name](**fn_args)
                        # Brief result preview in the log
                        preview = str(result)[:180].replace("\n", " ")
                        logger.for_tool(fn_name, f"{fn_name} returned results", detail=preview)
                    except Exception as exc:
                        result = {"error": str(exc)}
                        logger.error(f"{fn_name} failed", detail=str(exc))

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                })

        # ── Stage 3: Summarising ───────────────────────────────────────
        logger.summarizing(
            f"Synthesising findings from {tool_call_count} tool calls..."
        )

        raw_content = message.content or ""
        report = self._parse_report(raw_content, query)

        # ── Stage 4: Attach metadata ───────────────────────────────────
        report["tool_calls_made"] = tool_call_count
        report["tool_calls_log"] = tool_calls_log
        report["plan"] = plan
        report["generated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        report["llm"] = self._provider   # e.g. {"provider": "Groq", "model": "llama-3.3-70b-versatile", "icon": "⚡"}

        # ── Stage 5: Source credibility ranking ───────────────────────
        raw_sources = report.get("sources", [])
        if raw_sources:
            logger.log("Evaluating", f"Classifying {len(raw_sources)} sources for credibility...")
            ranked = classify_sources(raw_sources)
            report["sources"] = ranked
            report["source_credibility_summary"] = credibility_summary(ranked)
            avg = report["source_credibility_summary"]["average_stars"]
            logger.log("Evaluating", f"Average source credibility: {avg}/5 stars")

        # Confidence scoring (uses enriched sources)
        confidence = compute_confidence(report)
        report["confidence"] = confidence

        logger.done(
            f"Report ready  |  confidence: {confidence['icon']} {confidence['label']} "
            f"({confidence['score']}/100)"
        )

        # Attach the full reasoning log to the report
        report["reasoning_log"] = logger.stage_summary()

        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_report(self, content: str, query: str) -> dict:
        """Try to extract JSON from the model's final response."""
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "title": f"Research Report: {query}",
                "query": query,
                "summary": cleaned[:500],
                "key_findings": [],
                "sources": [],
                "limitations": "Could not parse structured output from model.",
            }
