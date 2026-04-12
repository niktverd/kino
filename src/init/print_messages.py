#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print message text from a parsed chat JSON file."
    )
    parser.add_argument(
        "start",
        nargs="?",
        type=int,
        help="First message_index to print (inclusive).",
    )
    parser.add_argument(
        "end",
        nargs="?",
        type=int,
        help="Last message_index to print (inclusive). If omitted, prints from start onward.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=Path(__file__).with_name("parsed-chat.json"),
        help="Path to the parsed chat JSON file.",
    )
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Print only message text without index and role headers.",
    )
    return parser.parse_args()


def load_messages(path: Path) -> list[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"File not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")

    if not isinstance(payload, dict):
        raise SystemExit(f"Expected top-level JSON object in {path}")

    messages = payload.get("messages")
    if not isinstance(messages, list):
        raise SystemExit(f"Expected a top-level 'messages' array in {path}")

    return messages


def select_messages(
    messages: list[dict], start: int | None, end: int | None
) -> list[tuple[int, dict]]:
    if start is not None and end is not None and end < start:
        raise SystemExit("End index must be greater than or equal to start index.")

    selected: list[tuple[int, dict]] = []
    for position, message in enumerate(messages):
        if not isinstance(message, dict):
            continue

        message_index = message.get("message_index", position)
        if not isinstance(message_index, int):
            message_index = position

        if start is not None and message_index < start:
            continue
        if end is not None and message_index > end:
            continue

        selected.append((message_index, message))

    return selected


def format_message(message_index: int, message: dict, text_only: bool) -> str:
    text = message.get("text")
    if not isinstance(text, str):
        text = ""

    if text_only:
        return text

    role = message.get("role")
    if not isinstance(role, str):
        role = "unknown"

    return f"[{message_index}] {role}\n{text}"


def main() -> int:
    args = parse_args()
    messages = load_messages(args.file)
    selected = select_messages(messages, args.start, args.end)

    if not selected:
        print("No messages matched the requested range.", file=sys.stderr)
        return 1

    for index, (message_index, message) in enumerate(selected):
        if index > 0:
            print()
            print()
        print(format_message(message_index, message, args.text_only))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
