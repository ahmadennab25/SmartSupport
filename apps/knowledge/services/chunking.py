"""Split a markdown policy document into small, self-contained chunks for retrieval."""
import re
from dataclasses import dataclass

DEFAULT_MAX_CHARS = 700


@dataclass(frozen=True)
class TextChunk:
    section: str
    text: str


def parse_title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def build_chunk_text(title: str, section: str, body: str) -> str:
    """The text that is embedded and stored: the heading context makes each chunk understandable alone."""
    heading = " — ".join(part for part in (title, section) if part)
    return f"{heading}\n{body}" if heading else body


def _split_block(block: str, max_chars: int) -> list[str]:
    if len(block) <= max_chars:
        return [block]
    parts: list[str] = []
    current = ""
    for line in block.splitlines():
        while len(line) > max_chars:
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:max_chars])
            line = line[max_chars:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > max_chars:
            parts.append(current)
            current = line
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def _pack(blocks: list[str], max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for block in blocks:
        for piece in _split_block(block, max_chars):
            candidate = f"{current}\n\n{piece}" if current else piece
            if len(candidate) > max_chars and current:
                chunks.append(current)
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def chunk_markdown(markdown: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[TextChunk]:
    """Chunks never cross a `## section` boundary; paragraphs/bullets are packed up to max_chars."""
    sections: list[tuple[str, list[str]]] = []
    heading = ""
    lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            sections.append((heading, lines))
            heading, lines = line[3:].strip(), []
        elif line.startswith("# "):
            continue  # document title, stored separately
        else:
            lines.append(line)
    sections.append((heading, lines))

    chunks: list[TextChunk] = []
    for section, section_lines in sections:
        body = "\n".join(section_lines)
        blocks = [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]
        chunks.extend(TextChunk(section, text) for text in _pack(blocks, max_chars))
    return chunks
