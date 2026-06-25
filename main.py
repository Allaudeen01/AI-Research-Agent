"""
Research Agent — CLI entry point.

Usage:
    python main.py "What is the current state of quantum computing?"
    python main.py --query "Latest breakthroughs in fusion energy"
    python main.py  # prompts interactively
"""

import sys
import argparse
from dotenv import load_dotenv

from agent.agent import ResearchAgent
from agent.report import to_markdown, save_report


def main():
    load_dotenv()  # loads .env if present

    parser = argparse.ArgumentParser(
        description="AI Research Agent — autonomous multi-tool research"
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Research query (wrap in quotes for multi-word queries)",
    )
    parser.add_argument(
        "--query", "-q",
        dest="query_flag",
        help="Alternative: pass query with --query flag",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip saving the report to outputs/",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the step-by-step agent log",
    )
    args = parser.parse_args()

    # Resolve query
    query = args.query or args.query_flag
    if not query:
        query = input("Enter your research query: ").strip()
    if not query:
        print("No query provided. Exiting.")
        sys.exit(1)

    agent = ResearchAgent(verbose=not args.quiet)
    report = agent.run(query)

    # Print Markdown report to console
    print("\n" + "=" * 60)
    print(to_markdown(report))
    print("=" * 60)

    # Save to outputs/
    if not args.no_save:
        base, json_path, md_path = save_report(report)
        print(f"\nReport saved:")
        print(f"  JSON -> {json_path}")
        print(f"  MD   -> {md_path}\n")


if __name__ == "__main__":
    main()
