"""Preserve editor structure and split Markdown without crossing screen boundaries."""
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter
from markdown_it import MarkdownIt


_MARKDOWN = MarkdownIt("commonmark").enable("table")
_SCREEN_TITLE = re.compile(r"^\[[A-Za-z0-9][A-Za-z0-9_.:/-]*\]\s*\S")
_CONTENTS_TITLES = {"목차", "contents", "table of contents"}


def _inline_markdown(content):
    if isinstance(content, str):
        return content
    pieces = []
    for item in content or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "link":
            label = _inline_markdown(item.get("content", []))
            pieces.append(f"[{label}]({item.get('href', '')})")
        elif item.get("type") == "text":
            value = item.get("text", "")
            styles = item.get("styles", {})
            for key, marker in (("code", "`"), ("bold", "**"), ("italic", "*")):
                if styles.get(key) and value:
                    value = marker + value + marker
            pieces.append(value)
    return "".join(pieces)


def blocks_to_markdown(blocks: list) -> str:
    parts = []
    number = 0
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        kind = block.get("type", "paragraph")
        props = block.get("props", {})
        content = block.get("content", [])
        if kind == "table" and isinstance(content, dict):
            rows = []
            for row in content.get("rows", []):
                cells = []
                for cell in row.get("cells", []):
                    if isinstance(cell, dict):
                        cell = cell.get("content", [])
                    value = _inline_markdown(cell).replace("|", r"\|").replace("\n", "<br>")
                    cells.append(value)
                rows.append(cells)
            if rows:
                width = max(map(len, rows))
                rows = [row + [""] * (width - len(row)) for row in rows]
                lines = ["| " + " | ".join(row) + " |" for row in rows]
                lines.insert(1, "| " + " | ".join(["---"] * width) + " |")
                parts.append("\n".join(lines))
        else:
            value = _inline_markdown(content)
            if kind == "heading":
                level = max(1, min(6, int(props.get("level", 2))))
                value = "#" * level + " " + value
            elif kind == "numberedListItem":
                number = int(props.get("start") or number + 1)
                value = f"{number}. {value}"
            elif kind in {"bulletListItem", "checkListItem"}:
                value = "- " + value
            elif kind == "codeBlock":
                fence = "`" * max(3, max((len(m.group()) + 1 for m in re.finditer(r"`+", value)), default=3))
                value = f"{fence}{props.get('language', '')}\n{value}\n{fence}"
            elif kind in {"image", "file", "video", "audio"}:
                value = f"[{props.get('caption') or props.get('name') or kind}]({props.get('url', '')})"
            if value.strip():
                parts.append(value)
        if kind != "numberedListItem":
            number = 0
        children = blocks_to_markdown(block.get("children", []))
        if children:
            parts.append("\n".join("  " + line for line in children.splitlines()))
    return "\n\n".join(parts)


def markdown_source_blocks(markdown: str) -> list:
    # Retain the canonical source, not overlapping search chunks. The client parses it.
    return [{"type": "paragraph", "content": [{"type": "text", "text": markdown, "styles": {}}]}]


def section_markdown(title: str, content: str, major_topic: str = "") -> str:
    headers = ([f"# {major_topic}"] if major_topic else []) + [f"## {title}"]
    return "\n\n".join(headers + [content.strip()])


def _headings(tokens):
    return [
        (int(token.tag[1:]), tokens[i + 1].content.strip(), token.map)
        for i, token in enumerate(tokens)
        if token.type == "heading_open" and token.level == 0
    ]


def split_markdown_sections(markdown: str, default_title: str = "") -> list[dict]:
    lines = markdown.splitlines()
    headings = _headings(_MARKDOWN.parse(markdown))
    screen_document = any(_SCREEN_TITLE.match(title) for _, title, _ in headings)
    result = []
    current = None
    major = ""

    def flush(end):
        if current is None:
            return
        title, topic, start = current
        content = "\n".join(lines[start:end]).strip()
        tokens = _MARKDOWN.parse(content)
        if tokens and tokens[-1].type == "hr":
            content = "\n".join(content.splitlines()[:tokens[-1].map[0]]).strip()
        if content and title.lower() not in _CONTENTS_TITLES:
            result.append({"title": title, "major_topic": topic, "content": content, "char_count": len(content)})

    if not screen_document:
        current = (default_title, "", 0)
    for level, title, bounds in headings:
        if screen_document:
            if level == 1:
                flush(bounds[0])
                current = None
                major = title
            elif _SCREEN_TITLE.match(title):
                flush(bounds[0])
                current = (title, major, bounds[1])
        elif level <= 2:
            flush(bounds[0])
            if level == 1:
                major = title
            current = (title, major if level > 1 else "", bounds[1])
    flush(len(lines))
    return result


def _plain_inline(token):
    return "".join(
        "\n" if child.type in {"softbreak", "hardbreak"} or child.content.lower() in {"<br>", "<br/>", "<br />"}
        else child.content if child.type in {"text", "code_inline"} else ""
        for child in token.children or []
    ).strip()


def _table_records(tokens):
    rows = []
    row = []
    for token in tokens:
        if token.type == "tr_open":
            row = []
        elif token.type == "inline":
            row.append(_plain_inline(token))
        elif token.type == "tr_close":
            rows.append(row)
    if not rows:
        return []
    headers = rows[0]
    return [
        "\n".join(f"{header or f'열 {i + 1}'}: {row[i] if i < len(row) else ''}" for i, header in enumerate(headers))
        for row in rows[1:]
    ]


def _body_units(markdown: str, parent_size: int):
    lines = markdown.splitlines()
    tokens = _MARKDOWN.parse(markdown)
    consumed = 0
    sentence_splitter = RecursiveCharacterTextSplitter(
        chunk_size=parent_size, chunk_overlap=0,
        separators=[r"\n\s*\n", r"(?<=[.!?。！？])\s+", r"\n"],
        is_separator_regex=True,
    )
    for i, token in enumerate(tokens):
        if token.level != 0 or not token.map or token.map[0] < consumed:
            continue
        start, end = token.map
        consumed = end
        if token.type == "hr":
            continue
        if token.type == "table_open":
            close = next(j for j in range(i + 1, len(tokens)) if tokens[j].type == "table_close")
            for record in _table_records(tokens[i:close + 1]):
                yield record, True
            continue
        body = "\n".join(lines[start:end]).strip()
        if not body:
            continue
        # Keep paragraphs, procedures and code intact unless prose exceeds a parent.
        if token.type == "paragraph_open" and len(body) > parent_size:
            for part in sentence_splitter.split_text(body):
                yield part, False
        else:
            yield body, token.type in {"fence", "code_block"}


def _detail_sections(markdown: str):
    lines = markdown.splitlines()
    headings = _headings(_MARKDOWN.parse(markdown))
    start = 0
    path = {}
    label = "업무 설명"
    for level, title, bounds in headings:
        body = "\n".join(lines[start:bounds[0]]).strip()
        if body:
            yield label, body
        path = {key: value for key, value in path.items() if key < level}
        path[level] = title
        label = " / ".join(path.values())
        start = bounds[1]
    body = "\n".join(lines[start:]).strip()
    if body:
        yield label, body


def _child_bodies(units, child_size):
    pending = []
    for body, atomic in units:
        if pending and (atomic or len("\n\n".join(pending + [body])) > child_size):
            yield "\n\n".join(pending)
            pending = []
        if atomic:
            yield body
        else:
            pending.append(body)
    if pending:
        yield "\n\n".join(pending)


def chunk_structured_documents(docs, parent_size=1500, child_size=300):
    parents = []
    for doc in docs:
        default_title = doc.metadata.get("section_title", "")
        for section in split_markdown_sections(doc.page_content, default_title):
            title = section["title"] or default_title or "매뉴얼"
            major = section["major_topic"]
            for label, body in _detail_sections(section["content"]):
                current_label = label
                prefix = title + "\n" + current_label + (f"\n대주제: {major}" if major else "") + "\n\n"
                children = list(_child_bodies(_body_units(body, parent_size), child_size))
                group = []

                def flush():
                    if not group:
                        return
                    parents.append({
                        "content": prefix + "\n\n".join(group),
                        "section_title": " / ".join(filter(None, (major, title, current_label))),
                        "keywords": list(dict.fromkeys(filter(None, (major, title, current_label)))),
                        "children": [{"content": prefix + part} for part in group],
                    })

                for child in children:
                    child_label = label
                    if label == "업무 설명" and child.startswith(("필드명:", "필드 ID:", "Field name:", "Field ID:")):
                        child_label = "필드 정보"
                    if group and current_label != child_label:
                        flush()
                        group = []
                    current_label = child_label
                    prefix = title + "\n" + current_label + (f"\n대주제: {major}" if major else "") + "\n\n"
                    if group and len(prefix + "\n\n".join(group + [child])) > parent_size:
                        flush()
                        group = []
                    group.append(child)
                flush()
    return parents
