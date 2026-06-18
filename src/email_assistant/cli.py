"""CLI to generate a single demo email. Powers ``make generate``.

Example:
    uv run python -m email_assistant.cli \\
        --model claude --tone "professional and warm" \\
        --intent "Follow up after a product demo" \\
        --fact "Demo was on Tuesday" --fact "Offering a 14-day trial"
"""

from __future__ import annotations

import argparse

from email_assistant.generator import EmailGenerator
from email_assistant.models import MODELS


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate a professional email.")
    parser.add_argument(
        "--model", default="claude", choices=list(MODELS), help="model to use"
    )
    parser.add_argument("--intent", required=True, help="purpose of the email")
    parser.add_argument(
        "--fact", dest="facts", action="append", default=[], help="a key fact (repeatable)"
    )
    parser.add_argument("--tone", required=True, help="desired tone")
    args = parser.parse_args(argv)

    result = EmailGenerator(args.model).generate(args.intent, args.facts, args.tone)

    print(f"# {MODELS[args.model].label}\n")
    print(result.email_text)


if __name__ == "__main__":
    main()
