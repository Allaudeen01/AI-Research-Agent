"""
Offline verification script — tests every module without making any API calls.
Run with:  python verify.py
"""

import sys
import json

PASS = "✅"
FAIL = "❌"
results = []

def check(name, fn):
    try:
        fn()
        results.append((PASS, name))
        print(f"  {PASS}  {name}")
    except Exception as e:
        results.append((FAIL, name))
        print(f"  {FAIL}  {name}")
        print(f"       {e}")

print("\n" + "="*55)
print("  Research Agent — Offline Verification")
print("="*55 + "\n")

# ── 1. Imports ─────────────────────────────────────────────────
print("[ Imports ]")

def test_import_tools():
    from agent.tools import TOOLS, TOOL_FUNCTIONS
    assert "web_search" in TOOL_FUNCTIONS
    assert "wikipedia_lookup" in TOOL_FUNCTIONS
    assert len(TOOLS) == 2

def test_import_planner():
    from agent.planner import make_plan

def test_import_logger():
    from agent.logger import ReasoningLogger, STAGE_ICONS
    assert "Planning" in STAGE_ICONS
    assert "Evaluating" in STAGE_ICONS
    assert "Done" in STAGE_ICONS

def test_import_credibility():
    from agent.credibility import classify_source, classify_sources, credibility_summary, CATEGORY_ICONS

def test_import_confidence():
    from agent.confidence import compute_confidence

def test_import_report():
    from agent.report import to_markdown, save_report

def test_import_agent():
    from agent.agent import ResearchAgent

check("tools.py imports", test_import_tools)
check("planner.py imports", test_import_planner)
check("logger.py imports", test_import_logger)
check("credibility.py imports", test_import_credibility)
check("confidence.py imports", test_import_confidence)
check("report.py imports", test_import_report)
check("agent.py imports", test_import_agent)

# ── 2. Credibility classifier ──────────────────────────────────
print("\n[ Source Credibility Classifier ]")
from agent.credibility import classify_source, classify_sources, credibility_summary

EXPECTED = [
    ("https://docs.openai.com/overview",              "Official Docs",  5),
    ("https://arxiv.org/abs/2303.08774",               "Academic",       5),
    ("https://www.nist.gov/ai",                        "Government",     5),
    ("https://en.wikipedia.org/wiki/AI",               "Encyclopedia",   4),
    ("https://www.reuters.com/technology",             "News",           4),
    ("https://stackoverflow.com/questions/123",        "Tech Reference", 4),
    ("https://medium.com/@user/some-post",             "Blog",           2),
    ("https://blogspot.com/post",                      "Blog",           1),
    ("https://www.nature.com/articles/s41586",         "Academic",       5),
    ("https://www.bbc.com/news/technology",            "News",           4),
    ("https://pytorch.org/docs/stable/index.html",     "Official Docs",  5),
    ("https://learn.microsoft.com/en-us/azure",        "Official Docs",  5),
    ("https://www.pewresearch.org/topic/ai",           "Research",       4),
    ("https://some-random-blog.io/post",               "Unknown",        3),
]

def make_classifier_test(url, expected_cat, expected_stars):
    def test():
        result = classify_source(url)
        assert result["category"] == expected_cat, \
            f"URL: {url}\n       Expected category '{expected_cat}', got '{result['category']}'"
        assert result["stars"] == expected_stars, \
            f"URL: {url}\n       Expected {expected_stars} stars, got {result['stars']}"
        assert len(result["stars_display"]) == 5, "stars_display should be 5 chars"
        assert result["domain"] != "", "domain should not be empty"
    return test

for url, cat, stars in EXPECTED:
    short = url.replace("https://", "").split("/")[0]
    check(f"classify {short} → {cat} ({stars}★)", make_classifier_test(url, cat, stars))

# Test sort order (highest stars first)
def test_sort_order():
    sources = [
        {"title": "Blog",    "url": "https://medium.com/post"},
        {"title": "arXiv",   "url": "https://arxiv.org/abs/123"},
        {"title": "Reuters", "url": "https://reuters.com/tech"},
    ]
    ranked = classify_sources(sources)
    assert ranked[0]["stars"] >= ranked[1]["stars"] >= ranked[2]["stars"], \
        "Sources should be sorted by stars descending"

check("classify_sources sorts highest-first", test_sort_order)

# Test credibility summary
def test_credibility_summary():
    sources = classify_sources([
        {"title": "A", "url": "https://arxiv.org/abs/1"},       # 5★ Academic
        {"title": "B", "url": "https://reuters.com/news"},      # 4★ News
        {"title": "C", "url": "https://medium.com/@x/post"},    # 2★ Blog
    ])
    summary = credibility_summary(sources)
    assert summary["average_stars"] == 3.7, f"Expected 3.7, got {summary['average_stars']}"
    assert summary["distribution"]["Academic"] == 1
    assert summary["distribution"]["Blog"] == 1
    assert len(summary["highest_rated"]) == 1
    assert summary["highest_rated"][0]["category"] == "Academic"

check("credibility_summary averages and distribution", test_credibility_summary)

# ── 3. Logger ──────────────────────────────────────────────────
print("\n[ ReasoningLogger ]")
from agent.logger import ReasoningLogger, STAGE_ICONS

def test_logger_stages():
    log = ReasoningLogger()
    log.planning("test plan")
    log.searching("test search", detail="query: AI")
    log.reading("test read")
    log.summarizing("test summarize")
    log.log("Evaluating", "classifying sources")
    log.done("finished")
    assert len(log.entries) == 6
    assert log.entries[0].stage == "Planning"
    assert log.entries[4].stage == "Evaluating"
    assert log.entries[5].stage == "Done"

def test_logger_callback():
    received = []
    log = ReasoningLogger(on_entry=lambda e: received.append(e.stage))
    log.planning("p")
    log.searching("s")
    assert received == ["Planning", "Searching"]

def test_logger_text_output():
    log = ReasoningLogger()
    log.planning("step one")
    text = log.to_text()
    assert "Planning" in text
    assert "step one" in text

def test_logger_stage_summary():
    log = ReasoningLogger()
    log.planning("p")
    log.done("d")
    summary = log.stage_summary()
    assert isinstance(summary, list)
    assert summary[0]["stage"] == "Planning"
    assert "elapsed" in summary[0]

check("logger records all stages", test_logger_stages)
check("logger callback fires", test_logger_callback)
check("logger to_text output", test_logger_text_output)
check("logger stage_summary format", test_logger_stage_summary)

# ── 4. Confidence scoring ──────────────────────────────────────
print("\n[ Confidence Scoring ]")
from agent.confidence import compute_confidence
from agent.credibility import classify_sources

def test_confidence_high_cred():
    sources = classify_sources([
        {"title": "arXiv", "url": "https://arxiv.org/abs/1"},
        {"title": "Gov",   "url": "https://nist.gov/ai"},
        {"title": "Docs",  "url": "https://docs.openai.com"},
    ])
    report = {
        "sources": sources,
        "key_findings": ["F1 detail here extensive", "F2 detail here extensive", "F3"],
        "summary": "A " * 80,  # long summary
        "tool_calls_made": 4,
        "tool_calls_log": ["wikipedia_lookup", "web_search", "web_search", "web_search"],
    }
    conf = compute_confidence(report)
    assert conf["score"] >= 75, f"High-cred report should score >= 75, got {conf['score']}"
    assert conf["label"] in ("High", "Very High")

def test_confidence_low_cred():
    sources = classify_sources([
        {"title": "Blog 1", "url": "https://medium.com/p1"},
        {"title": "Blog 2", "url": "https://blogspot.com/p2"},
    ])
    report = {
        "sources": sources,
        "key_findings": ["Short"],
        "summary": "Brief.",
        "tool_calls_made": 1,
        "tool_calls_log": ["web_search"],
    }
    conf = compute_confidence(report)
    assert conf["score"] < 75, f"Low-cred report should score < 75, got {conf['score']}"

def test_confidence_score_drops_for_blogs():
    sources_good = classify_sources([{"title": "arXiv", "url": "https://arxiv.org/abs/1"}])
    sources_bad  = classify_sources([{"title": "Blog",  "url": "https://medium.com/post"}])
    base = {
        "key_findings": ["F1", "F2"],
        "summary": "Summary " * 20,
        "tool_calls_made": 3,
        "tool_calls_log": ["wikipedia_lookup", "web_search"],
    }
    score_good = compute_confidence({**base, "sources": sources_good})["score"]
    score_bad  = compute_confidence({**base, "sources": sources_bad })["score"]
    assert score_good > score_bad, "Academic sources should score higher than blogs"

def test_confidence_breakdown_keys():
    conf = compute_confidence({
        "sources": [], "key_findings": [], "summary": "",
        "tool_calls_made": 0, "tool_calls_log": [],
    })
    assert "score" in conf
    assert "label" in conf
    assert "icon" in conf
    assert "breakdown" in conf
    assert "interpretation" in conf
    components = [row["component"] for row in conf["breakdown"]]
    assert "Source credibility" in components   # not "Source quantity" anymore

check("high-cred sources → High/Very High score", test_confidence_high_cred)
check("low-cred sources → lower score", test_confidence_low_cred)
check("academic scores higher than blogs", test_confidence_score_drops_for_blogs)
check("confidence breakdown has 'Source credibility'", test_confidence_breakdown_keys)

# ── 5. Report rendering ────────────────────────────────────────
print("\n[ Report Rendering ]")
from agent.report import to_markdown, save_report
import tempfile, os

def _make_mock_report():
    sources = classify_sources([
        {"title": "OpenAI Docs", "url": "https://docs.openai.com"},
        {"title": "Wikipedia",   "url": "https://en.wikipedia.org/wiki/AI"},
        {"title": "Medium",      "url": "https://medium.com/@u/post"},
    ])
    report = {
        "title": "Test Report: AI Overview",
        "query": "What is artificial intelligence?",
        "summary": "AI is the simulation of human intelligence in machines. " * 3,
        "key_findings": [
            "AI encompasses machine learning, NLP, and computer vision.",
            "Large language models have transformed the field since 2020.",
            "Regulation of AI is actively being developed worldwide.",
        ],
        "limitations": "This report may not reflect the very latest research.",
        "sources": sources,
        "source_credibility_summary": credibility_summary(sources),
        "tool_calls_made": 3,
        "tool_calls_log": ["wikipedia_lookup", "web_search", "web_search"],
        "generated_at": "2024-06-25T12:00:00Z",
        "plan": {
            "research_goal": "Understand AI",
            "sub_questions": ["What is AI?", "What are its applications?"],
            "tool_plan": [
                {"tool": "wikipedia_lookup", "input": "Artificial intelligence", "reason": "background"},
                {"tool": "web_search", "input": "AI latest news 2024", "reason": "current info"},
            ],
        },
        "reasoning_log": [
            {"stage": "Planning",    "message": "Generated plan",           "elapsed": 0.9},
            {"stage": "Reading",     "message": "wikipedia_lookup called",  "elapsed": 1.8},
            {"stage": "Searching",   "message": "web_search called",        "elapsed": 3.2},
            {"stage": "Evaluating",  "message": "Classified 3 sources",     "elapsed": 3.3},
            {"stage": "Done",        "message": "Report ready",             "elapsed": 4.1},
        ],
    }
    report["confidence"] = compute_confidence(report)
    return report

def test_markdown_contains_credibility_table():
    report = _make_mock_report()
    md = to_markdown(report)
    assert "Sources & Credibility" in md,    "Missing credibility section heading"
    assert "Official Docs" in md,            "Missing category in table"
    assert "Encyclopedia" in md,             "Missing Wikipedia category"
    assert "Blog" in md,                     "Missing Blog category"
    assert "⭐" in md,                        "Missing star characters"
    assert "Average credibility" in md,      "Missing aggregate line"

def test_markdown_contains_confidence():
    md = to_markdown(_make_mock_report())
    assert "Confidence Score" in md
    assert "Source credibility" in md        # new component name

def test_markdown_contains_reasoning_log():
    md = to_markdown(_make_mock_report())
    assert "Agent Reasoning Log" in md
    assert "Evaluating" in md

def test_save_report_writes_both_files():
    report = _make_mock_report()
    with tempfile.TemporaryDirectory() as tmpdir:
        base, json_path, md_path = save_report(report, output_dir=tmpdir)
        assert os.path.exists(json_path), "JSON file not written"
        assert os.path.exists(md_path),   "Markdown file not written"
        # Verify JSON is valid
        with open(json_path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["query"] == report["query"]
        assert "confidence" in loaded
        assert "source_credibility_summary" in loaded
        # Verify Markdown has content
        with open(md_path, encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 500

check("markdown has credibility table",  test_markdown_contains_credibility_table)
check("markdown has confidence section", test_markdown_contains_confidence)
check("markdown has reasoning log",      test_markdown_contains_reasoning_log)
check("save_report writes .json + .md", test_save_report_writes_both_files)

# ── 6. Summary ────────────────────────────────────────────────
print()
print("="*55)
passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
total  = len(results)
print(f"  Results: {passed}/{total} passed", end="")
if failed:
    print(f"  |  {failed} FAILED ← fix these before demo")
else:
    print("  — all good, ready for live test!")
print("="*55 + "\n")

if failed:
    sys.exit(1)
