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
    cover_image: Optional[bytes] = None
    cover_image_ext: str = "jpg"


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


def clean_chapter_title(title: str) -> str:
    """
    Clean up a chapter title by removing redundant leading numbers.

    Some EPUBs format headings like '34 34. Problem' or '1 01. Birth'
    where the chapter number appears twice. This strips the redundant
    leading number, producing '34. Problem' or '01. Birth'.
    """
    # Match patterns like "34 34. Title" or "1 01. Title" (number, space, same-or-zeropadded number, dot)
    match = re.match(r'^(\d+)\s+(\d+[\.\):\-\s])', title)
    if match:
        leading_num = int(match.group(1))
        second_num = int(re.match(r'\d+', match.group(2)).group())
        if leading_num == second_num:
            return title[match.end(1):].lstrip()

    return title


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
                return clean_chapter_title(title)

    return fallback_title


def extract_cover_image(book: epub.EpubBook) -> tuple:
    """
    Extract the cover image from an EPUB file.

    Tries multiple strategies:
    1. Look for an item with 'cover' in its properties (EPUB3 standard).
    2. Look for metadata referencing a cover image ID.
    3. Look for image items with 'cover' in their filename.

    Args:
        book: An ebooklib EpubBook object.

    Returns:
        Tuple of (image_bytes, extension) or (None, 'jpg') if no cover found.
    """
    def _get_ext(media_type: str, filename: str) -> str:
        """Determine file extension from media type or filename."""
        if "png" in media_type or filename.lower().endswith(".png"):
            return "png"
        if "gif" in media_type or filename.lower().endswith(".gif"):
            return "gif"
        if "webp" in media_type or filename.lower().endswith(".webp"):
            return "webp"
        return "jpg"

    # Strategy 1: EPUB3 cover-image property
    for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
        props = item.get_content()
        # Check if the item has cover properties set
        if hasattr(item, 'is_chapter') and not item.is_chapter():
            pass
        item_name = item.get_name().lower()
        # Some EPUB3 books set properties="cover-image" on the cover item
        try:
            if hasattr(item, 'properties') and item.properties and 'cover-image' in item.properties:
                logger.debug("Found cover via EPUB3 properties: %s", item.get_name())
                return item.get_content(), _get_ext(item.media_type, item.get_name())
        except Exception:
            pass

    # Strategy 2: Look for cover metadata reference
    cover_meta = book.get_metadata("OPF", "cover")
    if cover_meta:
        cover_id = cover_meta[0][1].get("content", "") if len(cover_meta[0]) > 1 else ""
        if cover_id:
            for item in book.get_items():
                if item.get_id() == cover_id:
                    logger.debug("Found cover via OPF metadata (id=%s): %s", cover_id, item.get_name())
                    return item.get_content(), _get_ext(item.media_type, item.get_name())

    # Strategy 3: Look for image items with 'cover' in the name or ID
    for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
        name_lower = item.get_name().lower()
        id_lower = (item.get_id() or "").lower()
        if "cover" in name_lower or "cover" in id_lower:
            logger.debug("Found cover via filename/id match: %s", item.get_name())
            return item.get_content(), _get_ext(item.media_type, item.get_name())

    # Strategy 4: If there's a cover XHTML page, find the image inside it
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        name_lower = item.get_name().lower()
        id_lower = (item.get_id() or "").lower()
        if "cover" in name_lower or "cover" in id_lower:
            try:
                content = item.get_content().decode("utf-8", errors="replace")
                soup = BeautifulSoup(content, "lxml")
                img_tag = soup.find("img")
                if img_tag and img_tag.get("src"):
                    img_src = img_tag["src"]
                    # Find the image item matching this src
                    for img_item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
                        if img_item.get_name().endswith(img_src.split("/")[-1]):
                            logger.debug("Found cover via cover page img tag: %s", img_item.get_name())
                            return img_item.get_content(), _get_ext(img_item.media_type, img_item.get_name())
            except Exception:
                pass

    # Strategy 5: Check ALL items for EpubCover or any item with 'cover' in its ID
    # Some EPUBs use special cover types (e.g., EpubCover) that aren't ITEM_IMAGE
    for item in book.get_items():
        id_lower = (item.get_id() or "").lower()
        type_name = type(item).__name__
        if id_lower == "cover" or type_name == "EpubCover":
            try:
                content = item.get_content()
                if content and len(content) > 1000:  # Must be a real image, not just markup
                    ext = _get_ext(getattr(item, "media_type", ""), item.get_name())
                    logger.debug("Found cover via EpubCover/id match: %s (type=%s)", item.get_name(), type_name)
                    return content, ext
            except Exception:
                pass

    return None, "jpg"


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

    # Extract cover image
    metadata.cover_image, metadata.cover_image_ext = extract_cover_image(book)
    if metadata.cover_image:
        size_kb = len(metadata.cover_image) / 1024
        logger.info("Cover image found: %.1f KB (%s)", size_kb, metadata.cover_image_ext)
    else:
        logger.info("No cover image found in EPUB")

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
