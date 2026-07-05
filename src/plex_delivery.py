"""Deliver a finished M4B into the Plex audiobook folder and trigger a rescan.

Plex runs in Docker, so refresh is section-level (container paths differ from
Windows paths). Refresh is best-effort: the file move is the real deliverable.
"""

import logging
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PLEX_DIR = r"E:\Plex\Audiobooks\Audiobooks"

PLEX_UNREACHABLE_MSG = (
    "Plex is unreachable (is Docker running?) — "
    "the audiobook will appear after the next library scan."
)

_INVALID = set('<>:"/\\|?*')


def sanitize_title(title: str) -> str:
    """Make a string safe as a Windows filename component."""
    cleaned = "".join(" " if (c in _INVALID or ord(c) < 32) else c for c in title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(" .")
    return cleaned or "Untitled"


def plex_output_name(title: str, chapter_range=None) -> str:
    base = sanitize_title(title)
    if chapter_range:
        base += f" - Chapters {chapter_range[0]} - {chapter_range[1]}"
    return base + ".m4b"


def deliver(m4b_path: Path, plex_dir: str, title: str, chapter_range=None) -> Path:
    """Move the M4B into the Plex folder under its library-facing name."""
    dest_dir = Path(plex_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / plex_output_name(title, chapter_range)
    shutil.move(str(m4b_path), str(dest))
    return dest


def trigger_refresh_from_env() -> str:
    """Trigger a Plex section refresh using PLEX_URL/PLEX_TOKEN/PLEX_SECTION_ID.

    Returns a human-readable status message; never raises.
    """
    url = os.environ.get("PLEX_URL", "").rstrip("/")
    token = os.environ.get("PLEX_TOKEN", "")
    section = os.environ.get("PLEX_SECTION_ID", "")
    if not (url and token and section):
        return "Plex refresh skipped (set PLEX_URL, PLEX_TOKEN, PLEX_SECTION_ID to enable)."
    refresh_url = (f"{url}/library/sections/{urllib.parse.quote(section)}/refresh"
                   f"?X-Plex-Token={urllib.parse.quote(token)}")
    try:
        with urllib.request.urlopen(refresh_url, timeout=10):
            pass
        return "Plex library refresh triggered."
    except (urllib.error.URLError, TimeoutError):
        return PLEX_UNREACHABLE_MSG
    except Exception as e:
        return f"Plex refresh failed ({e}) — file is saved; rescan manually."
