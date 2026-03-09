"""
EPUB Parser Module

Extracts chapter text and metadata from EPUB files.
Handles various EPUB structures and cleans HTML content to plain text.
"""

import re
import logging
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

logger = logging.getLogger(__name__)


@dataclass
class Chapter:
    """Represents a single chapter extracted from an EPUB."""
    title: str
    text: str
    index: int
    word_count: int = 0

    def __post_init__(self):
        self.word_count = len(self.text.split())


@dataclass
class BookMetadata:
    """Metadata extracted from an EPUB file."""
    title: str = "Unknown Title"
    author: str = "Unknown Author"
    language: str = "en"
    chapters: List[Chapter] = field(default_factory=list)
    total_word_count: int = 0


def clean_html_to_text(html_content: str) -> str:
    """
    Convert HTML content to clean plain text.

    Strips all HTML tags, normalizes whitespace, and removes
    excessive blank lines while preserving paragraph breaks.
    """
    soup = BeautifulSoup(html_content, "lxml")

    # Remove script and style elements
    for element in soup(["script", "style", "head", "meta", "link"]):
        element.decompose()

    # Get text with newlines between block elements
    text = soup.get_text(separator="\n")

    # Normalize whitespace within lines
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            # Collapse multiple spaces within a line
            stripped = re.sub(r"[ \t]+", " ", stripped)
            lines.append(stripped)

    # Join with single newlines, then collapse multiple newlines to double
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_chapter_title(html_content: str, fallback_title: str) -> str:
    """
    Try to extract a chapter title from HTML content.

    Looks for heading tags (h1-h4) and uses the first one found.
    Falls back to the provided fallback title.
    """
    soup = BeautifulSoup(html_content, "lxml")

    for tag in ["h1", "h2", "h3", "h4"]:
        heading = soup.find(tag)
        if heading:
            title = heading.get_text(strip=True)
            if title and len(title) < 200:  # Sanity check on length
                return title

    return fallback_title


def parse_epub(epub_path: str, min_chapter_words: int = 20) -> BookMetadata:
    """
    Parse an EPUB file and extract all chapters with their text content.

    Args:
        epub_path: Path to the EPUB file.
        min_chapter_words: Minimum word count for a section to be considered a chapter.

    Returns:
        BookMetadata containing the book's metadata and list of chapters.

    Raises:
        FileNotFoundError: If the EPUB file doesn't exist.
        ValueError: If no chapters could be extracted.
    """
    path = Path(epub_path)
    if not path.exists():
        raise FileNotFoundError(f"EPUB file not found: {epub_path}")
    if not path.suffix.lower() == ".epub":
        raise ValueError(f"File is not an EPUB: {epub_path}")

    logger.info("Opening EPUB: %s", epub_path)
    book = epub.read_epub(str(path), options={"ignore_ncx": False})

    # Extract metadata
    metadata = BookMetadata()

    title = book.get_metadata("DC", "title")
    if title:
        metadata.title = title[0][0]

    creator = book.get_metadata("DC", "creator")
    if creator:
        metadata.author = creator[0][0]

    language = book.get_metadata("DC", "language")
    if language:
        metadata.language = language[0][0]

    logger.info("Book: '%s' by %s (language: %s)", metadata.title, metadata.author, metadata.language)

    # Extract chapters from spine order
    chapter_index = 0
    spine_items = book.get_items_of_type(ebooklib.ITEM_DOCUMENT)

    for item in spine_items:
        try:
            content = item.get_content().decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning("Failed to decode item %s: %s", item.get_name(), e)
            continue

        text = clean_html_to_text(content)

        # Skip items with very little text (likely cover pages, TOC, etc.)
        word_count = len(text.split())
        if word_count < min_chapter_words:
            logger.debug("Skipping '%s' (%d words, below threshold of %d)",
                         item.get_name(), word_count, min_chapter_words)
            continue

        # Try to get a meaningful chapter title
        fallback = f"Chapter {chapter_index + 1}"
        title = extract_chapter_title(content, fallback)

        chapter = Chapter(
            title=title,
            text=text,
            index=chapter_index,
        )
        metadata.chapters.append(chapter)
        chapter_index += 1

        logger.info("  Chapter %d: '%s' (%d words)", chapter.index + 1, chapter.title, chapter.word_count)

    if not metadata.chapters:
        raise ValueError(f"No chapters with sufficient content found in: {epub_path}")

    metadata.total_word_count = sum(ch.word_count for ch in metadata.chapters)
    logger.info("Extracted %d chapters, %d total words", len(metadata.chapters), metadata.total_word_count)

    return metadata
