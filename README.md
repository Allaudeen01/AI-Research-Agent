# 🔍 AI Research Agent

An autonomous research agent that takes a natural language query, plans its approach, calls multiple tools, and returns a structured report with confidence scoring.


---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Research Agent Pipeline                      │
│                                                                     │
│   User Query                                                        │
│       │                                                             │
│       ▼                                                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  1. PLANNER NODE  (agent/planner.py)                         │  │
│  │                                                              │  │
│  │  GPT-OSS 120B (via Groq) analyses the query and produces:  │  │
│  │    • research_goal                                           │  │
│  │    • sub_questions  [ Q1, Q2, Q3 ... ]                      │  │
│  │    • tool_plan      [ {tool, input, reason}, ... ]          │  │
│  │    • expected_sections                                       │  │
│  └───────────────────────────┬──────────────────────────────────┘  │
│                               │  plan injected into context         │
│                               ▼                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  2. AGENTIC TOOL-CALLING LOOP  (agent/agent.py)              │  │
│  │                                                              │  │
│  │   ┌─────────────────┐   tool calls    ┌──────────────────┐  │  │
│  │   │  GPT-OSS 120B   │ ◄────────────── │ Tool Dispatcher  │  │  │
│  │   │  via Groq API   │ ──────────────► │                  │  │  │
│  │   └─────────────────┘   tool results  └────────┬─────────┘  │  │
│  │                                                │             │  │
│  │                              ┌─────────────────┴──────────┐  │  │
│  │                              ▼                            ▼  │  │
│  │                   ┌──────────────────┐   ┌─────────────────┐ │  │
│  │                   │  🔎 web_search   │   │ 📖 wikipedia_   │ │  │
│  │                   │  (Tavily API)    │   │    lookup       │ │  │
│  │                   │  current data,  │   │  background,    │ │  │
│  │                   │  news, stats    │   │  definitions    │ │  │
│  │                   └──────────────────┘   └─────────────────┘ │  │
│  │                                                              │  │
│  │   Loop repeats until model stops requesting tools           │  │
│  └───────────────────────────┬──────────────────────────────────┘  │
│                               │                                     │
│                               ▼                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  3. SUMMARISING  — model synthesises into structured JSON    │  │
│  │     { title, summary, key_findings, sources, limitations }  │  │
│  └───────────────────────────┬──────────────────────────────────┘  │
│                               │                                     │
│                               ▼                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  4. SOURCE CREDIBILITY RANKING  (agent/credibility.py)       │  │
│  │                                                              │  │
│  │   Each source URL is pattern-matched against 80+ domain     │  │
│  │   rules to assign:                                          │  │
│  │     • Category  (Official Docs / Government / Academic /    │  │
│  │                  Research / Encyclopedia / News /           │  │
│  │                  Tech Reference / Blog / Unknown)           │  │
│  │     • Stars     (1–5, fully deterministic, no API call)     │  │
│  │                                                              │  │
│  │   Sources are sorted highest-credibility-first and an       │  │
│  │   aggregate summary (avg stars, distribution) is attached.  │  │
│  └───────────────────────────┬──────────────────────────────────┘  │
│                               │                                     │
│                               ▼                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  5. CONFIDENCE SCORING  (agent/confidence.py)                │  │
│  │                                                              │  │
│  │   Source credibility (25) + Source diversity (20)          │  │
│  │ + Finding depth (20)      + Tool coverage (20)             │  │
│  │ + Summary quality (15)    = score / 100                    │  │
│  │   → label: Very High / High / Medium / Low / Very Low      │  │
│  └───────────────────────────┬──────────────────────────────────┘  │
│                               │                                     │
│                               ▼                                     │
│          Structured Report  +  Reasoning Log  +  Confidence        │
│          saved as  outputs/<timestamp>.md  +  .json                │
└─────────────────────────────────────────────────────────────────────┘
```

### Reasoning Log stages

```
🗺️  Planning    → Planner generates research plan
🔎  Searching   → web_search tool called (Tavily)
📖  Reading     → wikipedia_lookup tool called
✍️  Summarizing → model synthesises all findings
🏅  Evaluating  → source credibility ranking applied
✅  Done        → confidence score attached, report saved
```

### Key design decisions

| Decision | Rationale |
|----------|-----------|
| **Planner node before tool execution** | Forces explicit reasoning about *what* to research before *how*. Improves coverage and reduces irrelevant tool calls. |
| **OpenAI function/tool calling** | The model autonomously decides when and which tools to call — not a hardcoded sequence. True agentic behaviour. |
| **Two complementary tools** | Tavily = current/live data. Wikipedia = stable background knowledge. Different failure modes, different freshness. |
| **Source credibility ranking** | URL pattern-matched against 80+ domain rules — no extra API call. Agents should evaluate evidence quality, not just retrieve it. |
| **Confidence scoring** | Driven by average source credibility (not just count), tool diversity, finding depth, and summary quality. Changes when sources are low-quality. |
| **Structured JSON output** | Easy to render in any UI, diff across runs, or pipe into downstream systems. |

---

## Tools

| Tool | Source | Purpose |
|------|--------|---------|
| `web_search` | Tavily API | Current news, statistics, recent events |
| `wikipedia_lookup` | Wikipedia REST API (free, no key) | Background, definitions, encyclopedic context |

---

## Source Credibility Ranking

Every source URL is classified against **80+ domain rules** — instant, deterministic, no extra API call.

| Category | Icon | Default Stars | Examples |
|----------|------|:---:|---------|
| Official Docs | 📘 | ⭐⭐⭐⭐⭐ | docs.openai.com, pytorch.org, react.dev |
| Government | 🏛️ | ⭐⭐⭐⭐⭐ | .gov, europa.eu, who.int |
| Academic | 🎓 | ⭐⭐⭐⭐⭐ | arxiv.org, .edu, nature.com, ieee.org |
| Research | 🔬 | ⭐⭐⭐⭐☆ | ourworldindata.org, pewresearch.org |
| Encyclopedia | 📖 | ⭐⭐⭐⭐☆ | wikipedia.org, britannica.com |
| News | 📰 | ⭐⭐⭐⭐☆ | reuters.com, bbc.com, wired.com |
| Tech Reference | 💻 | ⭐⭐⭐⭐☆ | stackoverflow.com, MDN |
| Blog | ✍️ | ⭐⭐☆☆☆ | medium.com, dev.to, substack.com |
| Unknown | 🔗 | ⭐⭐⭐☆☆ | unmatched domains |

The average star rating of retrieved sources also **feeds directly into the confidence score** — a report backed by arxiv papers scores higher than one backed by blog posts.

---

## Project Structure

```
ai-research-agent/
├── agent/
│   ├── __init__.py
│   ├── agent.py        # Core pipeline — planner + tool loop + scoring
│   ├── planner.py      # Planner node — generates research plan
│   ├── logger.py       # ReasoningLogger — structured stage logging
│   ├── credibility.py  # Source credibility classifier (80+ domain rules)
│   ├── confidence.py   # Confidence scoring (0-100, credibility-aware)
│   ├── tools.py        # Tool implementations + OpenAI schemas
│   └── report.py       # Markdown/JSON renderer & file saver
├── outputs/            # Generated reports (gitignored)
├── app.py              # Streamlit web UI
├── main.py             # CLI entry point
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/ai-research-agent.git
cd ai-research-agent
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
# Edit .env:
#   OPENAI_API_KEY=sk-...
#   TAVILY_API_KEY=tvly-...
```

Get keys:
- **OpenAI** → https://platform.openai.com/api-keys
- **Tavily** (free, 1000 searches/month) → https://app.tavily.com

---

## Usage

### Streamlit UI (recommended for demo)

```bash
streamlit run app.py
```

Open http://localhost:8501 — enter a query and watch the pipeline live.

### CLI

```bash
# Direct query
python main.py "What is the current state of fusion energy research?"

# With flag
python main.py --query "Impact of AI on software engineering jobs"

# Quiet mode (no step log)
python main.py --quiet "Latest quantum computing breakthroughs"

# Skip saving to disk
python main.py --no-save "Brief history of the internet"
```

---

## Output

Every run saves two files to `outputs/`:

**`<timestamp>_<slug>.md`** — human-readable report:
- Confidence score with breakdown table
- Research plan (goal + sub-questions)
- Executive summary
- Key findings
- Sources
- Limitations
- Full reasoning log table

**`<timestamp>_<slug>.json`** — machine-readable full report including:
```json
{
  "title": "...",
  "query": "...",
  "summary": "...",
  "key_findings": ["..."],
  "sources": [{"title": "...", "url": "..."}],
  "limitations": "...",
  "confidence": {
    "score": 82,
    "label": "High",
    "icon": "🟢",
    "breakdown": [...],
    "interpretation": "..."
  },
  "plan": { "research_goal": "...", "sub_questions": [...], "tool_plan": [...] },
  "tool_calls_made": 4,
  "tool_calls_log": ["wikipedia_lookup", "web_search", "web_search"],
  "reasoning_log": [{"stage": "Planning", "message": "...", "elapsed": 0.91}],
  "generated_at": "2024-06-25T12:00:00Z"
}
```

---

## Confidence Scoring

| Component | Max | Signal used |
|-----------|----:|-------------|
| Source credibility | 25 | Average star rating of ranked sources (quality over quantity) |
| Source diversity | 20 | Whether both web and Wikipedia were used |
| Finding depth | 20 | Count and average length of key findings |
| Tool coverage | 20 | Number of distinct tools × total calls |
| Summary quality | 15 | Length of executive summary |
| **Total** | **100** | |

Ratings: 🟢 Very High (90+) · 🟢 High (75+) · 🟡 Medium (55+) · 🟠 Low (35+) · 🔴 Very Low

---

## Limitations & What I'd Improve Next

**Current limitations:**
- No streaming — the UI waits for the full loop before showing any output
- Wikipedia lookup can fail on ambiguous or obscure topic names
- Confidence scoring is heuristic-based, not model-evaluated

**Next improvements:**
- **Real-time streaming** of tool results via SSE so the user sees progress as it happens
- Add a **NewsAPI tool** for time-sensitive queries with publication dates
- **Result caching** with TTL to avoid redundant API calls on repeated queries
- Multi-turn **follow-up questions** building on a prior research session
- Export to **PDF** via a headless browser renderer

---

## Demo

[Video link — see submission]
