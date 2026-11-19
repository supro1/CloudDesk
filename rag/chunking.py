from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from backend.app.schemas.common import TicketCategory

DEFAULT_ARTICLES_DIR = Path(__file__).resolve().parent.parent / "sample_data" / "knowledge_base"
DEFAULT_CHUNK_SIZE = 900
DEFAULT_CHUNK_OVERLAP = 150
_HEADING_PATTERN = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_ANCHOR_PATTERN = re.compile(r"[^\w-]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class KnowledgeArticle:
    slug: str
    title: str
    category: TicketCategory | None
    tags: tuple[str, ...]
    summary: str
    content: str
    source_path: Path


@dataclass(frozen=True, slots=True)
class ArticleChunk:
    id: str
    page_content: str
    metadata: dict[str, Any]


def load_article_files(directory: Path = DEFAULT_ARTICLES_DIR) -> list[KnowledgeArticle]:
    """Load Markdown articles with validated YAML front matter from a directory."""
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Knowledge article directory does not exist: {directory}")

    articles = [_load_article(path) for path in sorted(directory.glob("*.md"))]
    slugs = [article.slug for article in articles]
    if len(slugs) != len(set(slugs)):
        raise ValueError(f"Knowledge article slugs must be unique in {directory}")
    return articles


def _load_article(path: Path) -> KnowledgeArticle:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path} must start with YAML front matter delimited by '---'")

    try:
        closing_index = next(
            index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration as error:
        raise ValueError(f"{path} has unterminated YAML front matter") from error

    try:
        metadata = yaml.safe_load("\n".join(lines[1:closing_index]))
    except yaml.YAMLError as error:
        raise ValueError(f"{path} has invalid YAML front matter: {error}") from error
    if not isinstance(metadata, dict):
        raise TypeError(f"{path} front matter must be a YAML mapping")

    title = _required_text(metadata, "title", path)
    summary = _required_text(metadata, "summary", path)
    category_value = _required_text(metadata, "category", path)
    try:
        category = TicketCategory(category_value)
    except ValueError as error:
        choices = ", ".join(item.value for item in TicketCategory)
        raise ValueError(
            f"{path} has unknown category {category_value!r}; expected one of: {choices}"
        ) from error

    tags = metadata.get("tags")
    if not isinstance(tags, list) or not all(
        isinstance(tag, str) and tag.strip() for tag in tags
    ):
        raise ValueError(f"{path} front matter field 'tags' must be a list of non-empty strings")

    content = "\n".join(lines[closing_index + 1 :]).strip()
    if not content:
        raise ValueError(f"{path} article body must not be empty")

    return KnowledgeArticle(
        slug=path.stem,
        title=title,
        category=category,
        tags=tuple(tag.strip() for tag in tags),
        summary=summary,
        content=content,
        source_path=path,
    )


def _required_text(metadata: dict[str, Any], key: str, path: Path) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} front matter field {key!r} must be a non-empty string")
    return value.strip()


def chunk_article(
    article: KnowledgeArticle,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[ArticleChunk]:
    """Split an article by Markdown headings and then into overlapping character windows."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and less than chunk_size")

    chunks: list[ArticleChunk] = []
    section_counts: dict[str, int] = {}
    for section_index, (heading, body) in enumerate(_split_sections(article)):
        anchor_base = _anchor(heading)
        section_counts[anchor_base] = section_counts.get(anchor_base, 0) + 1
        occurrence = section_counts[anchor_base]
        anchor = anchor_base if occurrence == 1 else f"{anchor_base}-{occurrence}"

        for chunk_index, window in enumerate(_windows(body, chunk_size, overlap)):
            chunk_id = f"{article.slug}:{section_index}:{chunk_index}"
            chunks.append(
                ArticleChunk(
                    id=chunk_id,
                    page_content=f"{article.title} - {heading}\n{window}",
                    metadata={
                        "article_slug": article.slug,
                        "title": article.title,
                        "category": (
                            article.category.value if article.category is not None else None
                        ),
                        "tags": list(article.tags),
                        "summary": article.summary,
                        "heading": heading,
                        "section": anchor,
                        "source": f"kb://{article.slug}#{anchor}",
                        "source_path": article.source_path.name,
                    },
                )
            )
    return chunks


def _split_sections(article: KnowledgeArticle) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current_heading = article.title
    current_lines: list[str] = []

    for line in article.content.splitlines():
        match = _HEADING_PATTERN.match(line)
        if match:
            if "\n".join(current_lines).strip():
                sections.append((current_heading, current_lines))
            current_heading = match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if "\n".join(current_lines).strip():
        sections.append((current_heading, current_lines))
    return [(heading, "\n".join(lines).strip()) for heading, lines in sections]


def _windows(text: str, chunk_size: int, overlap: int) -> list[str]:
    windows: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        windows.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return windows


def _anchor(heading: str) -> str:
    anchor = _ANCHOR_PATTERN.sub("-", heading.casefold()).strip("-")
    return anchor or "section"
