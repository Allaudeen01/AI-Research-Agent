"""
Research Agent — Streamlit web UI.

Run with:
    streamlit run app.py
"""

import streamlit as st
from dotenv import load_dotenv
import os

load_dotenv()

# Streamlit Cloud: inject secrets into environment if not already set
# (locally .env is used; on Streamlit Cloud st.secrets is used)
for key in ["GROQ_API_KEY", "OPENAI_API_KEY", "TAVILY_API_KEY", "LLM_PROVIDER", "GROQ_MODEL"]:
    if not os.environ.get(key) and key in st.secrets:
        os.environ[key] = st.secrets[key]

from agent.agent import ResearchAgent
from agent.logger import STAGE_ICONS
from agent.report import to_markdown, save_report
from agent.credibility import CATEGORY_ICONS
from agent.llm_client import provider_info


def icon_for(category: str) -> str:
    return CATEGORY_ICONS.get(category, "🔗")

st.set_page_config(
    page_title="AI Research Agent",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 AI Research Agent")
prov = provider_info()
st.markdown(
    f"Autonomous research powered by **{prov['icon']} {prov['provider']} / {prov['model']}** "
    f"· **Tavily Web Search** · **Wikipedia**"
)

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    prov = provider_info()
    st.markdown(f"**LLM:** {prov['icon']} {prov['provider']} `{prov['model']}`")
    st.markdown("_Set `LLM_PROVIDER` in `.env` to switch_")
    st.markdown("---")
    save_output = st.checkbox("Save report to outputs/", value=True)
    show_plan   = st.checkbox("Show research plan", value=True)
    show_log    = st.checkbox("Show reasoning log", value=True)

    st.markdown("---")
    st.markdown("**Pipeline stages**")
    for stage, icon in STAGE_ICONS.items():
        st.markdown(f"{icon} **{stage}**")

    st.markdown("---")
    st.markdown("**How it works**")
    st.markdown(
        "1. **Planning** — model generates a research plan\n"
        "2. **Searching** — Tavily web search (current data)\n"
        "3. **Reading** — Wikipedia lookup (background)\n"
        "4. **Summarizing** — synthesis into structured report\n"
        "5. **Evaluating** — source credibility ranking\n"
        "6. **Done** — confidence score computed"
    )

# ── Query input ────────────────────────────────────────────────────────────
query = st.text_input(
    "Enter your research query",
    placeholder="e.g. What is the current state of fusion energy research?",
)

if st.button("🚀 Research", type="primary") and query:

    # ── Live pipeline expander — open while running, collapsed after ──
    pipeline_expander = st.expander("🔄 Agent Pipeline", expanded=True)
    status_placeholder = pipeline_expander.empty()

    log_entries = []

    def on_log_entry(entry):
        """Called by ReasoningLogger for every new log entry."""
        log_entries.append(entry)
        rows = []
        for e in log_entries:
            icon = STAGE_ICONS.get(e.stage, "•")
            rows.append(f"| {icon} **{e.stage}** | {e.message} | `+{e.elapsed:.2f}s` |")
        md = (
            "| Stage | Message | Time |\n"
            "|-------|---------|------|\n"
            + "\n".join(rows)
        )
        status_placeholder.markdown(md)

    # ── Run agent ─────────────────────────────────────────────────────
    with st.spinner("Agent is researching..."):
        agent = ResearchAgent(verbose=False, on_log=on_log_entry)
        report = agent.run(query)

    # Collapse the pipeline table now that the report is ready
    pipeline_expander = st.expander("🔄 Agent Pipeline  ✅", expanded=False)
    with pipeline_expander:
        rows = []
        for e in log_entries:
            icon = STAGE_ICONS.get(e.stage, "•")
            rows.append(f"| {icon} **{e.stage}** | {e.message} | `+{e.elapsed:.2f}s` |")
        st.markdown(
            "| Stage | Message | Time |\n"
            "|-------|---------|------|\n"
            + "\n".join(rows)
        )

    st.success("Research complete!")

    # ── Research Plan ──────────────────────────────────────────────────
    plan = report.get("plan", {})
    if show_plan and plan:
        with st.expander("🗺️ Research Plan", expanded=False):
            st.markdown(f"**Goal:** {plan.get('research_goal', '')}")
            sub_qs = plan.get("sub_questions", [])
            if sub_qs:
                st.markdown("**Sub-questions:**")
                for q in sub_qs:
                    st.markdown(f"- {q}")
            tool_plan = plan.get("tool_plan", [])
            if tool_plan:
                st.markdown("**Tool execution plan:**")
                for step in tool_plan:
                    st.markdown(
                        f"- `{step['tool']}` ← *\"{step['input']}\"* — {step['reason']}"
                    )

    # ── Confidence Score ───────────────────────────────────────────────
    confidence = report.get("confidence", {})
    if confidence:
        st.markdown("---")
        st.markdown("### 📊 Confidence Score")

        score = confidence.get("score", 0)
        label = confidence.get("label", "N/A")
        icon  = confidence.get("icon", "")

        col1, col2, col3 = st.columns([1, 1, 2])
        col1.metric("Score", f"{score}/100")
        col2.metric("Rating", f"{icon} {label}")
        col3.markdown(f"_{confidence.get('interpretation', '')}_")

        breakdown = confidence.get("breakdown", [])
        if breakdown:
            with st.expander("Score breakdown", expanded=False):
                for row in breakdown:
                    pct = row["points"] / row["max"]
                    st.markdown(
                        f"**{row['component']}** — {row['points']}/{row['max']}  \n"
                        f"_{row.get('note', '')}_"
                    )
                    st.progress(pct)

    # ── Full Report ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📄 Report")

    # Executive summary + findings + sources
    st.markdown(f"**{report.get('title', '')}**\n")
    st.markdown(f"{report.get('summary', '')}")

    findings = report.get("key_findings", [])
    if findings:
        st.markdown("**Key Findings**")
        for i, f in enumerate(findings, 1):
            st.markdown(f"{i}. {f}")

    sources = report.get("sources", [])
    if sources:
        st.markdown("**Sources & Credibility**")
        classified = any("stars" in s for s in sources)
        if classified:
            import pandas as pd

            def _site_name(src: dict) -> str:
                """Extract a clean, human-readable site name from a classified source."""
                domain   = src.get("domain", "")
                category = src.get("category", "")
                # Strip www. / m. prefix
                host = domain.lower().replace("www.", "").replace("m.", "")

                # Well-known overrides
                KNOWN = {
                    "en.wikipedia.org":   "Wikipedia",
                    "wikipedia.org":      "Wikipedia",
                    "arxiv.org":          "arXiv",
                    "youtube.com":        "YouTube",
                    "youtu.be":           "YouTube",
                    "github.com":         "GitHub",
                    "stackoverflow.com":  "Stack Overflow",
                    "reddit.com":         "Reddit",
                    "medium.com":         "Medium",
                    "theguardian.com":    "The Guardian",
                    "nytimes.com":        "NY Times",
                    "washingtonpost.com": "Washington Post",
                    "technologyreview.com": "MIT Tech Review",
                    "scientificamerican.com": "Scientific American",
                    "thequantuminsider.com":  "Quantum Insider",
                    "bluequbit.io":           "BlueQubit",
                    "quantamagazine.org":     "Quanta Magazine",
                    "ourworldindata.org":     "Our World in Data",
                    "pewresearch.org":        "Pew Research",
                }
                for key, label in KNOWN.items():
                    if key in host:
                        return label

                # Generic: take first segment, capitalise nicely
                segment = host.split(".")[0]
                # CamelCase long segments (e.g. "thequantuminsider" → already handled above)
                return segment.capitalize()

            rows = []
            for src in sources:
                title      = src.get("title", "Untitled")
                url        = src.get("url", "")
                site       = _site_name(src)
                short_title = title if len(title) <= 45 else title[:42] + "…"
                # Only prepend site name if it isn't already in the title
                if site.lower() in short_title.lower():
                    display = short_title
                else:
                    display = f"{site} — {short_title}"

                rows.append({
                    "Source":      display,
                    "URL":         url,
                    "Type":        f"{src.get('icon','🔗')} {src.get('category','Unknown')}",
                    "Credibility": src.get("stars_display", ""),
                    "Stars":       src.get("stars", 0),
                })

            df = pd.DataFrame(rows)
            display_df = df.drop(columns=["Stars"])
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Source":      st.column_config.TextColumn("Source"),
                    "URL":         st.column_config.LinkColumn("Link"),
                    "Type":        st.column_config.TextColumn("Type"),
                    "Credibility": st.column_config.TextColumn("Credibility (/5)"),
                },
            )

            # Aggregate stats
            cred_summary = report.get("source_credibility_summary", {})
            if cred_summary:
                avg  = cred_summary.get("average_stars", 0)
                dist = cred_summary.get("distribution", {})
                ca, cb = st.columns(2)
                ca.metric("Avg Credibility", f"{avg:.1f} / 5.0")
                dist_str = "  ·  ".join(
                    f"{icon_for(cat)} {cat}: {n}"
                    for cat, n in sorted(dist.items(), key=lambda x: -x[1])
                )
                cb.markdown(f"**Source mix:** {dist_str}")
        else:
            for src in sources:
                url   = src.get("url", "")
                title = src.get("title", "Untitled")
                st.markdown(f"- [{title}]({url})" if url else f"- {title}")

    limitations = report.get("limitations", "")
    if limitations:
        st.markdown(f"**Limitations:** {limitations}")

    # ── Reasoning Log ──────────────────────────────────────────────────
    if show_log:
        with st.expander("📋 Full Reasoning Log", expanded=False):
            log = report.get("reasoning_log", [])
            for entry in log:
                stage   = entry.get("stage", "")
                message = entry.get("message", "")
                elapsed = entry.get("elapsed", 0)
                icon    = STAGE_ICONS.get(stage, "•")
                st.markdown(f"`+{elapsed:.2f}s` {icon} **{stage}** — {message}")

    # ── Stats bar ──────────────────────────────────────────────────────
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Tool Calls", report.get("tool_calls_made", 0))
    c2.metric("Sources",    len(report.get("sources", [])))
    c3.metric("Findings",   len(report.get("key_findings", [])))

    # ── Save & Download ────────────────────────────────────────────────
    if save_output:
        base, json_path, md_path = save_report(report)
        st.info(f"Saved → `{md_path}`  &  `{json_path}`")

    md_text = to_markdown(report)
    col_a, col_b = st.columns(2)
    col_a.download_button(
        label="⬇️ Download Markdown",
        data=md_text,
        file_name=f"research_{query[:30].replace(' ', '_')}.md",
        mime="text/markdown",
    )
    import json as _json
    col_b.download_button(
        label="⬇️ Download JSON",
        data=_json.dumps(report, indent=2),
        file_name=f"research_{query[:30].replace(' ', '_')}.json",
        mime="application/json",
    )
