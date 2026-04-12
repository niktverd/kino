#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable


VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

BLOCK_TAGS = {
    "article",
    "blockquote",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tbody",
    "thead",
    "tr",
    "ul",
}

SKIP_TEXT_TAGS = {
    "button",
    "mat-icon",
    "path",
    "svg",
}

SKIP_TEXT_CLASSES = {
    "action-button-container",
    "mat-focus-indicator",
    "mat-mdc-button-touch-target",
    "mat-ripple",
    "response-container-footer",
    "response-container-header",
    "response-footer",
    "response-label",
    "screen-reader-model-response-label",
    "thoughts-container",
    "user-query-label",
}

TURN_METADATA_RE = re.compile(
    r'BardVeMetadataKey:\[\["(?P<response_id>r_[^"]+)","(?P<conversation_id>c_[^"]+)"'
)


@dataclass
class Node:
    tag: str
    attrs: list[tuple[str, str | None]] = field(default_factory=list)
    starttag_text: str | None = None
    self_closing: bool = False
    children: list["Node | str"] = field(default_factory=list)
    parent: "Node | None" = None

    def attr(self, name: str, default: str | None = None) -> str | None:
        for key, value in self.attrs:
            if key == name:
                return value if value is not None else default
        return default

    @property
    def classes(self) -> set[str]:
        class_attr = self.attr("class") or ""
        return {part for part in class_attr.split() if part}


class LightweightHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.root = Node(tag="__root__")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(
            tag=tag,
            attrs=attrs,
            starttag_text=self.get_starttag_text(),
            parent=self.stack[-1],
        )
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(
            tag=tag,
            attrs=attrs,
            starttag_text=self.get_starttag_text(),
            self_closing=True,
            parent=self.stack[-1],
        )
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1].children.append(data)

    def handle_entityref(self, name: str) -> None:
        self.stack[-1].children.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.stack[-1].children.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        # Angular placeholder comments are common in these exports and are not useful
        # for either the extracted text or the optional HTML fragments.
        return


def walk(node: Node, include_self: bool = False):
    if include_self:
        yield node
    for child in node.children:
        if isinstance(child, Node):
            yield child
            yield from walk(child)


def find_first(node: Node, predicate: Callable[[Node], bool]) -> Node | None:
    for candidate in walk(node):
        if predicate(candidate):
            return candidate
    return None


def find_all(node: Node, predicate: Callable[[Node], bool]) -> list[Node]:
    return [candidate for candidate in walk(node) if predicate(candidate)]


def has_class(node: Node, class_name: str) -> bool:
    return class_name in node.classes


def node_to_html(node: Node | str) -> str:
    if isinstance(node, str):
        return node
    start = node.starttag_text or f"<{node.tag}>"
    if node.self_closing or node.tag in VOID_TAGS:
        return start
    inner = "".join(node_to_html(child) for child in node.children)
    return f"{start}{inner}</{node.tag}>"


def clean_whitespace(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t\f\r]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def node_to_text(node: Node | str) -> str:
    parts: list[str] = []

    def render(item: Node | str) -> None:
        if isinstance(item, str):
            parts.append(unescape(item))
            return

        if item.tag in SKIP_TEXT_TAGS or item.classes & SKIP_TEXT_CLASSES:
            return

        if item.tag == "br":
            parts.append("\n")
            return

        if item.tag == "li":
            parts.append("\n- ")
        elif item.tag in BLOCK_TAGS:
            parts.append("\n")

        for child in item.children:
            render(child)

        if item.tag in BLOCK_TAGS:
            parts.append("\n")

    render(node)
    return clean_whitespace("".join(parts))


def extract_turn_metadata(container: Node) -> tuple[str | None, str | None]:
    button = find_first(
        container,
        lambda node: node.tag == "button"
        and (node.attr("aria-label") or "").strip() == "Скопировать запрос",
    )
    if not button:
        return None, None

    jslog = button.attr("jslog") or ""
    match = TURN_METADATA_RE.search(jslog)
    if not match:
        return None, None
    return match.group("conversation_id"), match.group("response_id")


def extract_user_text(query_content: Node) -> str:
    lines = find_all(query_content, lambda node: has_class(node, "query-text-line"))
    if lines:
        rendered = [node_to_text(line) for line in lines]
        return clean_whitespace("\n".join(line for line in rendered if line))
    return node_to_text(query_content)


def parse_export(path: Path, include_html: bool) -> dict:
    parser = LightweightHTMLParser()
    parser.feed(path.read_text(encoding="utf-8"))

    title_node = find_first(
        parser.root,
        lambda node: node.attr("data-test-id") == "conversation-title",
    )
    title = node_to_text(title_node) if title_node else None

    containers = find_all(
        parser.root,
        lambda node: node.tag == "div" and has_class(node, "conversation-container"),
    )
    if not containers:
        raise ValueError("No conversation containers were found in the input file.")

    messages: list[dict] = []
    conversation_id: str | None = None

    for turn_index, container in enumerate(containers):
        query_content = find_first(
            container,
            lambda node: has_class(node, "query-content")
            and (node.attr("id") or "").startswith("user-query-content-"),
        )
        query_html_node = find_first(query_content, lambda node: has_class(node, "query-text")) if query_content else None

        message_content = find_first(
            container,
            lambda node: node.tag == "message-content"
            and (node.attr("id") or "").startswith("message-content-id-r_"),
        )
        response_html_node = find_first(
            message_content,
            lambda node: node.tag == "div" and has_class(node, "markdown"),
        ) if message_content else None

        if not query_content or not message_content:
            continue

        turn_conversation_id, response_id = extract_turn_metadata(container)
        if turn_conversation_id and not conversation_id:
            conversation_id = turn_conversation_id

        container_id = container.attr("id")
        if not response_id and container_id:
            response_id = f"r_{container_id}"

        has_thoughts = find_first(
            container,
            lambda node: node.attr("data-test-id") == "model-thoughts",
        ) is not None
        thoughts_toggle_node = find_first(
            container,
            lambda node: has_class(node, "thoughts-header-button-label"),
        )
        thoughts_toggle_label = node_to_text(thoughts_toggle_node) if thoughts_toggle_node else None

        user_message = {
            "message_index": len(messages),
            "turn_index": turn_index,
            "role": "user",
            "container_id": container_id,
            "conversation_id": turn_conversation_id or conversation_id,
            "response_id": response_id,
            "dom_id": query_content.attr("id"),
            "text": extract_user_text(query_content),
            "has_thoughts": has_thoughts,
        }
        if include_html and query_html_node is not None:
            user_message["html"] = node_to_html(query_html_node)
        messages.append(user_message)

        assistant_message = {
            "message_index": len(messages),
            "turn_index": turn_index,
            "role": "assistant",
            "container_id": container_id,
            "conversation_id": turn_conversation_id or conversation_id,
            "response_id": response_id,
            "dom_id": message_content.attr("id"),
            "text": node_to_text(message_content),
            "has_thoughts": has_thoughts,
            "thoughts_toggle_label": thoughts_toggle_label,
        }
        if include_html and response_html_node is not None:
            assistant_message["html"] = node_to_html(response_html_node)
        messages.append(assistant_message)

    return {
        "source_file": str(path),
        "format": "gemini-html-export",
        "conversation": {
            "title": title,
            "conversation_id": conversation_id,
            "turn_count": len(messages) // 2,
            "message_count": len(messages),
        },
        "messages": messages,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse a Gemini HTML export and extract chat messages into JSON."
    )
    parser.add_argument("input", type=Path, help="Path to the exported HTML or .md file.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Where to write JSON. Defaults to <input>.json in the same directory.",
    )
    parser.add_argument(
        "--include-html",
        action="store_true",
        help="Include the raw HTML fragment for each message.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write compact JSON without indentation.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = args.input.resolve()
    if not input_path.is_file():
        parser.error(f"Input file does not exist: {input_path}")

    output_path = args.output.resolve() if args.output else input_path.with_suffix(".json")

    try:
        payload = parse_export(input_path, include_html=args.include_html)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=None if args.compact else 2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
