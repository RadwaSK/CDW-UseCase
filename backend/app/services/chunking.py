"""Language-aware chunking: markdown by section, Python by top-level def/class,
everything else by a fixed line window. Boundaries keep each chunk a coherent unit."""

import ast
from dataclasses import dataclass
from pathlib import Path

MAX_CHUNK_LINES = 60
WINDOW_LINES = 40

EXTENSION_TO_DOC_TYPE = {
    ".py": "python",
    ".md": "markdown",
    ".txt": "text",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
}


@dataclass
class Chunk:
    content: str
    start_line: int  # 1-indexed, inclusive
    end_line: int  # 1-indexed, inclusive
    doc_type: str


def doc_type_for(path: Path) -> str | None:
    return EXTENSION_TO_DOC_TYPE.get(path.suffix.lower())


def chunk_file(path: Path) -> list[Chunk]:
    doc_type = doc_type_for(path)
    if doc_type is None:
        return []

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines:
        return []

    if doc_type == "markdown":
        spans = _markdown_spans(lines)
    elif doc_type == "python":
        spans = _python_spans(lines)
    else:
        spans = _window_spans(lines)

    chunks = []
    for start, end in spans:
        for sub_start, sub_end in _cap_span(start, end):
            content = "\n".join(lines[sub_start - 1 : sub_end])
            if content.strip():
                chunks.append(
                    Chunk(
                        content=content,
                        start_line=sub_start,
                        end_line=sub_end,
                        doc_type=doc_type,
                    )
                )
    return chunks


def _cap_span(start: int, end: int) -> list[tuple[int, int]]:
    """Split a span into MAX_CHUNK_LINES-sized pieces if it's too long."""
    if end - start + 1 <= MAX_CHUNK_LINES:
        return [(start, end)]
    spans = []
    cursor = start
    while cursor <= end:
        spans.append((cursor, min(cursor + MAX_CHUNK_LINES - 1, end)))
        cursor += MAX_CHUNK_LINES
    return spans


def _markdown_spans(lines: list[str]) -> list[tuple[int, int]]:
    header_lines = [i for i, line in enumerate(lines, start=1) if line.lstrip().startswith("#")]
    if not header_lines:
        return [(1, len(lines))]

    spans = []
    if header_lines[0] > 1:
        spans.append((1, header_lines[0] - 1))
    for i, start in enumerate(header_lines):
        end = header_lines[i + 1] - 1 if i + 1 < len(header_lines) else len(lines)
        spans.append((start, end))
    return spans


def _python_spans(lines: list[str]) -> list[tuple[int, int]]:
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return _window_spans(lines)

    top_level = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    if not top_level:
        return _window_spans(lines)

    top_level.sort(key=lambda n: n.lineno)
    spans = []
    if top_level[0].lineno > 1:
        spans.append((1, top_level[0].lineno - 1))
    for i, node in enumerate(top_level):
        start = node.lineno
        end = top_level[i + 1].lineno - 1 if i + 1 < len(top_level) else len(lines)
        spans.append((start, end))
    return spans


def _window_spans(lines: list[str]) -> list[tuple[int, int]]:
    spans = []
    cursor = 1
    total = len(lines)
    while cursor <= total:
        spans.append((cursor, min(cursor + WINDOW_LINES - 1, total)))
        cursor += WINDOW_LINES
    return spans
