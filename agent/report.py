"""
Report renderer — converts a report dict into a readable Markdown document
and saves both Markdown and JSON to the outputs/ folder.
"""

import os
import json
import datetime


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def _confidence_bar(score: int, max_score: int = 100) -> str:
    """Render a simple text progress bar for a score."""
    filled = round((score / max_score) * 20)
    return "█" * filled + "░" * (20 - filled)


def to_markdown(report: dict) -> str:
    """Render a research report dict as a Markdown string."""
    lines = []

    # ── Header ────────────────────────────────────────────────────────
    title = report.get("title", "Research Report")
    lines.append(f"# {title}\n")
    lines.append(
        f"**Query:** {report.get('query', '')}  \n"
        f"**Generated:** {report.get('generated_at', 'N/A')}  \n"
        f"**Tool calls:** {report.get('tool_calls_made', 'N/A')}"
    )
    lines.append("")

    # ── Confidence Score ──────────────────────────────────────────────
    confidence = report.get("confidence")
    if confidence:
        score  = confidence.get("score", 0)
        label  = confidence.get("label", "N/A")
        icon   = confidence.get("icon", "")
        interp = confidence.get("interpretation", "")
        bar    = _confidence_bar(score)

        lines.append("---\n")
        lines.append("## Confidence Score\n")
        lines.append(f"**{icon} {label}  —  {score}/100**\n")
        lines.append(f"`{bar}`\n")
        lines.append(f"{interp}\n")

        breakdown = confidence.get("breakdown", [])
        if breakdown:
            lines.append("| Component | Score | Max |")
            lines.append("|-----------|------:|----:|")
            for row in breakdown:
                lines.append(
                    f"| {row['component']} | {row['points']} | {row['max']} |"
                    + (f" _{row['note']}_" if row.get("note") else "")
                )
            lines.append("")

    # ── Research Plan ─────────────────────────────────────────────────
    plan = report.get("plan")
    if plan:
        lines.append("---\n")
        lines.append("## Research Plan\n")
        lines.append(f"**Goal:** {plan.get('research_goal', '')}\n")

        sub_qs = plan.get("sub_questions", [])
        if sub_qs:
            lines.append("**Sub-questions explored:**")
            for q in sub_qs:
                lines.append(f"- {q}")
            lines.append("")

    # ── Executive Summary ─────────────────────────────────────────────
    lines.append("---\n")
    lines.append("## Executive Summary\n")
    lines.append(f"{report.get('summary', '')}\n")

    # ── Key Findings ──────────────────────────────────────────────────
    findings = report.get("key_findings", [])
    if findings:
        lines.append("## Key Findings\n")
        for i, finding in enumerate(findings, 1):
            lines.append(f"{i}. {finding}")
        lines.append("")

    # ── Sources with Credibility Ranking ─────────────────────────────
    sources = report.get("sources", [])
    if sources:
        lines.append("## Sources & Credibility\n")

        # Check if sources have been credibility-classified
        classified = any("stars" in s for s in sources)
        if classified:
            lines.append("| # | Source | Type | Credibility |")
            lines.append("|---|--------|------|-------------|")
            for i, src in enumerate(sources, 1):
                src_title = src.get("title", "Untitled")
                url       = src.get("url", "")
                category  = src.get("category", "Unknown")
                icon      = src.get("icon", "🔗")
                stars_str = src.get("stars_display", "")
                link = f"[{src_title}]({url})" if url else src_title
                lines.append(f"| {i} | {link} | {icon} {category} | {stars_str} |")
            lines.append("")

            # Aggregate summary
            cred_summary = report.get("source_credibility_summary", {})
            if cred_summary:
                avg = cred_summary.get("average_stars", 0)
                dist = cred_summary.get("distribution", {})
                dist_str = ", ".join(f"{cat}: {n}" for cat, n in sorted(dist.items()))
                lines.append(f"**Average credibility:** {avg:.1f}/5.0  \n")
                lines.append(f"**Source mix:** {dist_str}\n")
        else:
            # Fallback: plain list
            for src in sources:
                src_title = src.get("title", "Untitled")
                url = src.get("url", "")
                if url:
                    lines.append(f"- [{src_title}]({url})")
                else:
                    lines.append(f"- {src_title}")
        lines.append("")

    # ── Limitations ───────────────────────────────────────────────────
    limitations = report.get("limitations", "")
    if limitations:
        lines.append("## Limitations & Caveats\n")
        lines.append(limitations)
        lines.append("")

    # ── Reasoning Log ─────────────────────────────────────────────────
    log = report.get("reasoning_log", [])
    if log:
        lines.append("---\n")
        lines.append("## Agent Reasoning Log\n")
        lines.append("| Stage | Message | Elapsed |")
        lines.append("|-------|---------|--------:|")
        for entry in log:
            stage   = entry.get("stage", "")
            message = entry.get("message", "").replace("|", "\\|")
            elapsed = entry.get("elapsed", 0)
            lines.append(f"| {stage} | {message} | +{elapsed:.2f}s |")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Save to disk
# ---------------------------------------------------------------------------

def save_report(report: dict, output_dir: str = "outputs") -> tuple[str, str, str]:
    """
    Save the report as both JSON (.json) and Markdown (.md).

    Returns
    -------
    (base_name, json_path, md_path)
    """
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    slug = (
        report.get("query", "report")[:40]
        .replace(" ", "_")
        .replace("/", "-")
        .replace("\\", "-")
        .replace("?", "")
        .replace(":", "")
        .replace("*", "")
        .replace('"', "")
        .replace("<", "")
        .replace(">", "")
        .replace("|", "")
    )
    base = f"{timestamp}_{slug}"

    json_path = os.path.join(output_dir, f"{base}.json")
    md_path   = os.path.join(output_dir, f"{base}.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(report))

    return base, json_path, md_path
