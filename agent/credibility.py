"""
Source Credibility Ranking

Classifies a source URL into a type category and assigns a credibility
rating (1–5 stars) based on domain pattern matching.

No API call needed — fully deterministic, instant, and explainable.

Categories (ordered by default credibility):
  Official Docs   ⭐⭐⭐⭐⭐  5  — vendor/project documentation
  Government      ⭐⭐⭐⭐⭐  5  — .gov / .gov.xx domains
  Academic        ⭐⭐⭐⭐⭐  5  — .edu, arxiv, pubmed, DOI publishers
  Research        ⭐⭐⭐⭐☆  4  — think-tanks, research institutes
  Encyclopedia    ⭐⭐⭐⭐☆  4  — Wikipedia, Britannica
  News            ⭐⭐⭐⭐☆  4  — established news outlets
  Tech Reference  ⭐⭐⭐⭐☆  4  — MDN, Stack Overflow, official RFCs
  Industry        ⭐⭐⭐☆☆  3  — reputable industry sites
  Blog / Community⭐⭐☆☆☆  2  — Medium, Dev.to, personal blogs
  Unknown         ⭐⭐⭐☆☆  3  — unclassified (default neutral)
"""

from __future__ import annotations
import re
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Domain rule tables
# Each entry: (regex_pattern, category_label, stars)
# Rules are evaluated top-to-bottom; first match wins.
# ---------------------------------------------------------------------------

_RULES: list[tuple[str, str, int]] = [

    # ── Government ────────────────────────────────────────────────────
    (r"\.gov(\.[a-z]{2})?$",            "Government",     5),
    (r"\.gov\.",                         "Government",     5),
    (r"europa\.eu",                      "Government",     5),
    (r"un\.org",                         "Government",     5),
    (r"who\.int",                        "Government",     5),
    (r"worldbank\.org",                  "Government",     5),
    (r"imf\.org",                        "Government",     5),
    (r"oecd\.org",                       "Government",     5),

    # ── Academic ──────────────────────────────────────────────────────
    (r"\.edu(\.[a-z]{2})?$",            "Academic",       5),
    (r"\.edu\.",                         "Academic",       5),
    (r"arxiv\.org",                      "Academic",       5),
    (r"pubmed\.ncbi\.nlm\.nih\.gov",     "Academic",       5),
    (r"ncbi\.nlm\.nih\.gov",             "Academic",       5),
    (r"scholar\.google\.",               "Academic",       5),
    (r"semanticscholar\.org",            "Academic",       5),
    (r"jstor\.org",                      "Academic",       5),
    (r"springer\.com",                   "Academic",       5),
    (r"nature\.com",                     "Academic",       5),
    (r"sciencedirect\.com",              "Academic",       5),
    (r"ieee\.org",                       "Academic",       5),
    (r"acm\.org",                        "Academic",       5),
    (r"doi\.org",                        "Academic",       5),

    # ── Official Documentation ────────────────────────────────────────
    (r"docs\.python\.org",               "Official Docs",  5),
    (r"docs\.openai\.com",               "Official Docs",  5),
    (r"platform\.openai\.com",           "Official Docs",  5),
    (r"openai\.com",                     "Official Docs",  5),
    (r"docs\.anthropic\.com",            "Official Docs",  5),
    (r"anthropic\.com",                  "Official Docs",  5),
    (r"docs\.google\.com",               "Official Docs",  5),
    (r"cloud\.google\.com/docs",         "Official Docs",  5),
    (r"docs\.aws\.amazon\.com",          "Official Docs",  5),
    (r"docs\.microsoft\.com",            "Official Docs",  5),
    (r"learn\.microsoft\.com",           "Official Docs",  5),
    (r"docs\.github\.com",               "Official Docs",  5),
    (r"github\.com",                     "Official Docs",  4),  # code, not always docs
    (r"pytorch\.org",                     "Official Docs",  5),
    (r"tensorflow\.org",                 "Official Docs",  5),
    (r"huggingface\.co/docs",            "Official Docs",  5),
    (r"huggingface\.co",                 "Official Docs",  4),
    (r"developer\.mozilla\.org",         "Official Docs",  5),
    (r"w3\.org",                         "Official Docs",  5),
    (r"ietf\.org",                       "Official Docs",  5),
    (r"kotlinlang\.org",                 "Official Docs",  5),
    (r"rust-lang\.org",                  "Official Docs",  5),
    (r"nodejs\.org",                     "Official Docs",  5),
    (r"reactjs\.org",                    "Official Docs",  5),
    (r"react\.dev",                      "Official Docs",  5),
    (r"vuejs\.org",                      "Official Docs",  5),
    (r"angular\.io",                     "Official Docs",  5),
    (r"djangoproject\.com",              "Official Docs",  5),
    (r"flask\.palletsprojects\.com",     "Official Docs",  5),
    (r"fastapi\.tiangolo\.com",          "Official Docs",  5),
    (r"langchain\.com",                  "Official Docs",  4),
    (r"kubernetes\.io",                  "Official Docs",  5),
    (r"docker\.com/docs",                "Official Docs",  5),
    (r"postgresql\.org",                 "Official Docs",  5),
    (r"mysql\.com/docs",                 "Official Docs",  5),

    # ── Encyclopedia ──────────────────────────────────────────────────
    (r"wikipedia\.org",                  "Encyclopedia",   4),
    (r"britannica\.com",                 "Encyclopedia",   4),
    (r"encyclopedia\.com",               "Encyclopedia",   4),

    # ── Tech Reference ────────────────────────────────────────────────
    (r"stackoverflow\.com",              "Tech Reference", 4),
    (r"stackexchange\.com",              "Tech Reference", 4),
    (r"mdn\.",                           "Tech Reference", 5),
    (r"devdocs\.io",                     "Tech Reference", 4),

    # ── Reputable News ────────────────────────────────────────────────
    (r"reuters\.com",                    "News",           4),
    (r"apnews\.com",                     "News",           4),
    (r"bbc\.(com|co\.uk)",               "News",           4),
    (r"nytimes\.com",                    "News",           4),
    (r"theguardian\.com",                "News",           4),
    (r"washingtonpost\.com",             "News",           4),
    (r"wsj\.com",                        "News",           4),
    (r"ft\.com",                         "News",           4),
    (r"economist\.com",                  "News",           4),
    (r"bloomberg\.com",                  "News",           4),
    (r"cnbc\.com",                       "News",           3),
    (r"cnn\.com",                        "News",           3),
    (r"techcrunch\.com",                 "News",           3),
    (r"wired\.com",                      "News",           4),
    (r"arstechnica\.com",                "News",           4),
    (r"theverge\.com",                   "News",           3),
    (r"venturebeat\.com",                "News",           3),
    (r"thenextweb\.com",                 "News",           3),

    # ── Research / Think-tanks ────────────────────────────────────────
    (r"brookings\.edu",                  "Research",       4),
    (r"rand\.org",                       "Research",       4),
    (r"pewresearch\.org",                "Research",       4),
    (r"mckinsey\.com",                   "Research",       4),
    (r"gartner\.com",                    "Research",       4),
    (r"forrester\.com",                  "Research",       4),
    (r"statista\.com",                   "Research",       3),
    (r"ourworldindata\.org",             "Research",       5),
    (r"gapminder\.org",                  "Research",       4),

    # ── Blogs / Community ─────────────────────────────────────────────
    (r"medium\.com",                     "Blog",           2),
    (r"substack\.com",                   "Blog",           2),
    (r"dev\.to",                         "Blog",           2),
    (r"hashnode\.com",                   "Blog",           2),
    (r"towardsdatascience\.com",         "Blog",           2),
    (r"hackernoon\.com",                 "Blog",           2),
    (r"reddit\.com",                     "Blog",           2),
    (r"quora\.com",                      "Blog",           2),
    (r"wordpress\.com",                  "Blog",           1),
    (r"blogspot\.com",                   "Blog",           1),
    (r"tumblr\.com",                     "Blog",           1),

    # ── Video / Media ─────────────────────────────────────────────────
    (r"youtube\.com",                    "Video",          3),
    (r"youtu\.be",                       "Video",          3),
    (r"vimeo\.com",                      "Video",          3),

    # ── Industry / Niche Tech ─────────────────────────────────────────
    (r"thequantuminsider\.com",          "Industry",       3),
    (r"quantamagazine\.org",             "Research",       5),
    (r"technologyreview\.com",           "News",           4),
    (r"spectrum\.ieee\.org",             "News",           4),
    (r"scientificamerican\.com",         "Research",       4),
    (r"newscientist\.com",               "News",           4),
    (r"phys\.org",                       "Research",       4),
    (r"livescience\.com",                "News",           3),
    (r"zdnet\.com",                      "News",           3),
    (r"infoq\.com",                      "Industry",       3),
    (r"towardsmachinelearning\.org",     "Blog",           2),
    (r"analytics-?vidhya\.com",          "Blog",           2),
    (r"kdnuggets\.com",                  "Industry",       3),
    (r"\.io/blog",                       "Blog",           2),
    (r"bluequbit\.io",                   "Industry",       3),
    (r"ibm\.com",                        "Official Docs",  4),
    (r"research\.ibm\.com",              "Research",       5),
    (r"microsoft\.com/en-us/research",   "Research",       5),
    (r"deepmind\.com",                   "Research",       5),
    (r"ai\.google",                      "Research",       5),
    (r"research\.google",                "Research",       5),
    (r"meta\.ai",                        "Research",       4),
    (r"ai\.facebook\.com",               "Research",       4),
]

# Pre-compile for speed
_COMPILED: list[tuple[re.Pattern, str, int]] = [
    (re.compile(pattern, re.IGNORECASE), label, stars)
    for pattern, label, stars in _RULES
]

STAR_CHAR   = "⭐"
EMPTY_STAR  = "☆"
MAX_STARS   = 5

CATEGORY_ICONS = {
    "Official Docs":  "📘",
    "Government":     "🏛️",
    "Academic":       "🎓",
    "Research":       "🔬",
    "Encyclopedia":   "📖",
    "News":           "📰",
    "Tech Reference": "💻",
    "Industry":       "🏢",
    "Video":          "🎬",
    "Blog":           "✍️",
    "Unknown":        "🔗",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_source(url: str) -> dict:
    """
    Classify a single source URL.

    Returns
    -------
    {
        "url":      str,
        "domain":   str,
        "category": str,
        "stars":    int   (1-5),
        "stars_display": str  (e.g. "⭐⭐⭐⭐☆"),
        "icon":     str,
    }
    """
    domain = _extract_domain(url)

    for pattern, label, stars in _COMPILED:
        if pattern.search(domain):
            return _build_result(url, domain, label, stars)

    # Default: unknown
    return _build_result(url, domain, "Unknown", 3)


def classify_sources(sources: list[dict]) -> list[dict]:
    """
    Classify a list of source dicts (each with 'title' and 'url' keys).
    Returns a new list with credibility fields added in-place.
    """
    result = []
    for src in sources:
        url = src.get("url", "")
        classified = classify_source(url)
        enriched = {**src, **classified}
        result.append(enriched)

    # Sort: highest stars first, then alphabetically by category
    result.sort(key=lambda s: (-s["stars"], s["category"]))
    return result


def credibility_summary(classified_sources: list[dict]) -> dict:
    """
    Compute an aggregate credibility summary for a set of classified sources.

    Returns
    -------
    {
        "average_stars": float,
        "distribution":  {category: count},
        "highest_rated": list of source dicts,
        "lowest_rated":  list of source dicts,
    }
    """
    if not classified_sources:
        return {
            "average_stars": 0.0,
            "distribution": {},
            "highest_rated": [],
            "lowest_rated": [],
        }

    stars_list = [s["stars"] for s in classified_sources]
    avg = round(sum(stars_list) / len(stars_list), 1)

    distribution: dict[str, int] = {}
    for s in classified_sources:
        cat = s["category"]
        distribution[cat] = distribution.get(cat, 0) + 1

    max_stars = max(stars_list)
    min_stars = min(stars_list)

    return {
        "average_stars": avg,
        "distribution": distribution,
        "highest_rated": [s for s in classified_sources if s["stars"] == max_stars],
        "lowest_rated":  [s for s in classified_sources if s["stars"] == min_stars],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_domain(url: str) -> str:
    """Extract hostname from a URL, falling back to the raw string."""
    try:
        parsed = urlparse(url)
        return parsed.netloc or url
    except Exception:
        return url


def _stars_display(stars: int) -> str:
    return STAR_CHAR * stars + EMPTY_STAR * (MAX_STARS - stars)


def _build_result(url: str, domain: str, category: str, stars: int) -> dict:
    return {
        "url":           url,
        "domain":        domain,
        "category":      category,
        "stars":         stars,
        "stars_display": _stars_display(stars),
        "icon":          CATEGORY_ICONS.get(category, "🔗"),
    }
