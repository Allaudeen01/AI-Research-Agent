"""
Confidence scoring for research reports.

Scores are computed from signals in the report itself — no extra API call needed.

Score breakdown (total 100 points):
  Source credibility : up to 25 pts  (average star rating of ranked sources)
  Source diversity   : up to 20 pts  (mix of web + wikipedia = better)
  Finding depth      : up to 20 pts  (number and length of key_findings)
  Tool coverage      : up to 20 pts  (both tool types used)
  Summary quality    : up to 15 pts  (summary length as a proxy for synthesis)

Final score is mapped to a label:
  90-100 → "Very High"
  75-89  → "High"
  55-74  → "Medium"
  35-54  → "Low"
  0-34   → "Very Low"
"""

from __future__ import annotations


LABEL_THRESHOLDS = [
    (90, "Very High", "🟢"),
    (75, "High",      "🟢"),
    (55, "Medium",    "🟡"),
    (35, "Low",       "🟠"),
    (0,  "Very Low",  "🔴"),
]


def _source_credibility_score(sources: list[dict]) -> tuple[int, str]:
    """
    Score based on the average credibility star rating of classified sources.
    Falls back to source count if sources haven't been classified yet.
    """
    n = len(sources)
    if n == 0:
        return 0, "No sources found"

    rated = [s for s in sources if "stars" in s]
    if not rated:
        # Fallback: pure quantity signal (pre-credibility-ranking path)
        if n >= 6:   pts = 25
        elif n >= 4: pts = 20
        elif n >= 2: pts = 12
        elif n == 1: pts = 6
        else:        pts = 0
        return pts, f"{n} sources (unclassified)"

    avg = sum(s["stars"] for s in rated) / len(rated)
    # 5 stars → 25 pts, 4 → 20, 3 → 14, 2 → 7, 1 → 2
    star_to_pts = {5: 25, 4: 20, 3: 14, 2: 7, 1: 2}
    base = star_to_pts.get(round(avg), 10)

    # Bonus: quantity on top of quality (up to cap)
    qty_bonus = min(n - 1, 3) * 1   # +1 per extra source, max +3
    pts = min(base + qty_bonus, 25)

    # Pull categories for the note
    cats = list({s.get("category", "Unknown") for s in rated})
    cats_str = ", ".join(sorted(cats)[:3]) + ("…" if len(cats) > 3 else "")
    return pts, f"{n} sources, avg {avg:.1f}★ ({cats_str})"


def _source_diversity_score(sources: list[dict], tool_calls: list[str]) -> tuple[int, str]:
    """Reward having both web and wikipedia sources."""
    has_web  = "web_search" in tool_calls
    has_wiki = "wikipedia_lookup" in tool_calls
    if has_web and has_wiki:
        return 20, "Both web and Wikipedia sources used"
    elif has_web or has_wiki:
        return 10, "Only one source type used"
    return 0, "No tool calls recorded"


def _finding_depth_score(findings: list[str]) -> tuple[int, str]:
    n = len(findings)
    avg_len = sum(len(f) for f in findings) / max(n, 1)
    pts = 0
    if n >= 5:
        pts += 12
    elif n >= 3:
        pts += 8
    elif n >= 1:
        pts += 4

    if avg_len >= 100:
        pts += 8
    elif avg_len >= 50:
        pts += 5
    elif avg_len >= 20:
        pts += 2

    pts = min(pts, 20)
    return pts, f"{n} findings, avg length {int(avg_len)} chars"


def _tool_coverage_score(tool_calls_made: int, tool_calls: list[str]) -> tuple[int, str]:
    unique_tools = len(set(tool_calls))
    total_calls  = tool_calls_made
    if unique_tools >= 2 and total_calls >= 3:
        return 20, f"{total_calls} total calls across {unique_tools} tool types"
    elif unique_tools >= 2:
        return 14, f"{total_calls} calls, {unique_tools} tool types"
    elif total_calls >= 1:
        return 7, f"{total_calls} calls, only 1 tool type"
    return 0, "No tool calls"


def _summary_quality_score(summary: str) -> tuple[int, str]:
    length = len(summary)
    if length >= 300:
        pts = 15
    elif length >= 150:
        pts = 10
    elif length >= 50:
        pts = 5
    else:
        pts = 0
    return pts, f"Summary length: {length} chars"


def _label(score: int) -> tuple[str, str]:
    for threshold, label, icon in LABEL_THRESHOLDS:
        if score >= threshold:
            return label, icon
    return "Very Low", "🔴"


def compute_confidence(report: dict) -> dict:
    """
    Compute a confidence score for a research report.

    Parameters
    ----------
    report : dict
        The report dict as produced by ResearchAgent.run().
        Expects:
          - sources          : list of source dicts (optionally credibility-enriched)
          - key_findings     : list of str
          - summary          : str
          - tool_calls_made  : int
          - tool_calls_log   : list of str  (tool names in order called)

    Returns
    -------
    dict with keys:
      score          : int 0-100
      label          : str
      icon           : str emoji
      breakdown      : list of {component, points, max, note}
      interpretation : str  human-readable explanation
    """
    sources      = report.get("sources", [])
    findings     = report.get("key_findings", [])
    summary      = report.get("summary", "")
    total_calls  = report.get("tool_calls_made", 0)
    tool_log     = report.get("tool_calls_log", [])

    sc_pts, sc_note = _source_credibility_score(sources)
    sd_pts, sd_note = _source_diversity_score(sources, tool_log)
    fd_pts, fd_note = _finding_depth_score(findings)
    tc_pts, tc_note = _tool_coverage_score(total_calls, tool_log)
    su_pts, su_note = _summary_quality_score(summary)

    score = sc_pts + sd_pts + fd_pts + tc_pts + su_pts
    label, icon = _label(score)

    breakdown = [
        {"component": "Source credibility", "points": sc_pts, "max": 25, "note": sc_note},
        {"component": "Source diversity",   "points": sd_pts, "max": 20, "note": sd_note},
        {"component": "Finding depth",      "points": fd_pts, "max": 20, "note": fd_note},
        {"component": "Tool coverage",      "points": tc_pts, "max": 20, "note": tc_note},
        {"component": "Summary quality",    "points": su_pts, "max": 15, "note": su_note},
    ]

    interpretation = (
        f"Confidence is {label} ({score}/100). "
        + _interpret(score, sources, findings, tool_log)
    )

    return {
        "score": score,
        "label": label,
        "icon": icon,
        "breakdown": breakdown,
        "interpretation": interpretation,
    }


def _interpret(score: int, sources: list, findings: list, tool_log: list) -> str:
    notes = []
    if len(sources) < 2:
        notes.append("very few sources were retrieved")
    else:
        low_quality = [s for s in sources if s.get("stars", 3) <= 2]
        if len(low_quality) > len(sources) / 2:
            notes.append("more than half the sources are low-credibility (blogs/community posts)")
    if "wikipedia_lookup" not in tool_log:
        notes.append("no Wikipedia background check was performed")
    if "web_search" not in tool_log:
        notes.append("no live web search was performed")
    if len(findings) < 3:
        notes.append("limited key findings were extracted")

    if not notes:
        return "The report draws from multiple credible, diverse sources with thorough coverage."
    return "Gaps detected: " + "; ".join(notes) + "."
