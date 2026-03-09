"""
Audiobook Builder Module

Assembles chapter audio files into a single M4B audiobook with chapter metadata.
Uses ffmpeg for audio encoding and MP4Box/ffmpeg for chapter markers.
"""

import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000


@dataclass
class ChapterMark:
    """Represents a chapter marker in the audiobook."""
    title: str
    start_time: float  # seconds
    end_time: float    # seconds


def check_ffmpeg() -> str:
    """
    Check if ffmpeg is available and return its path.

    Raises:
        RuntimeError: If ffmpeg is not found.
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise RuntimeError(
            "ffmpeg not found. Please install ffmpeg:\n"
            "  Windows: Download from https://ffmpeg.org/download.html or use 'winget install ffmpeg'\n"
            "  Or install via chocolatey: choco install ffmpeg"
        )
    # Verify it runs
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True, text=True, timeout=10
        )
        version_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
        logger.info("ffmpeg found: %s", version_line)
    except Exception as e:
        raise RuntimeError(f"ffmpeg found but failed to execute: {e}")

    return ffmpeg_path


def save_chapter_wav(audio: np.ndarray, output_path: Path) -> float:
    """
    Save a chapter's audio data to a WAV file.

    Args:
        audio: Numpy float32 array of audio samples at 24kHz.
        output_path: Path to write the WAV file.

    Returns:
        Duration of the audio in seconds.
    """
    sf.write(str(output_path), audio, SAMPLE_RATE)
    duration = len(audio) / SAMPLE_RATE
    logger.debug("Saved WAV: %s (%.1fs)", output_path.name, duration)
    return duration


def create_ffmpeg_metadata(chapters: List[ChapterMark]) -> str:
    """
    Create an ffmpeg metadata file string with chapter markers.

    This follows the ffmpeg metadata format for chapter markers,
    which can be embedded into M4B/M4A files.

    Args:
        chapters: List of ChapterMark objects.

    Returns:
        String content for the ffmpeg metadata file.
    """
    lines = [";FFMETADATA1"]

    for ch in chapters:
        start_ms = int(ch.start_time * 1000)
        end_ms = int(ch.end_time * 1000)
        # ffmpeg metadata uses timebase of 1/1000
        lines.append("[CHAPTER]")
        lines.append("TIMEBASE=1/1000")
        lines.append(f"START={start_ms}")
        lines.append(f"END={end_ms}")
        lines.append(f"title={ch.title}")

    return "\n".join(lines)


def build_m4b(
    chapter_audio: List[tuple],  # List of (title, numpy_audio_array)
    output_path: str,
    book_title: str = "Audiobook",
    book_author: str = "Unknown",
    bitrate: str = "64k",
    cover_image: Optional[bytes] = None,
    cover_image_ext: str = "jpg",
    keep_temp: bool = False,
) -> Path:
    """
    Build an M4B audiobook from chapter audio data.

    Process:
    1. Save each chapter as a temporary WAV file.
    2. Concatenate all WAVs into a single WAV.
    3. Create chapter metadata file.
    4. Encode to M4B (AAC in MP4 container) with chapter markers and cover art.

    Args:
        chapter_audio: List of (chapter_title, audio_array) tuples.
        output_path: Path for the output M4B file.
        book_title: Book title for metadata.
        book_author: Book author for metadata.
        bitrate: AAC encoding bitrate (default: '64k', good for speech).
        cover_image: Raw bytes of a cover image (JPEG/PNG), or None.
        cover_image_ext: File extension for the cover image ('jpg', 'png', etc.).
        keep_temp: If True, don't delete temporary files.

    Returns:
        Path to the created M4B file.

    Raises:
        RuntimeError: If ffmpeg is not available or encoding fails.
    """
    ffmpeg_path = check_ffmpeg()
    output = Path(output_path)

    # Ensure output has .m4b extension
    if output.suffix.lower() != ".m4b":
        output = output.with_suffix(".m4b")

    logger.info("Building M4B audiobook: %s", output)
    logger.info("  Title: %s | Author: %s | Bitrate: %s", book_title, book_author, bitrate)

    with tempfile.TemporaryDirectory(prefix="ebook_audiobook_") as temp_dir:
        temp_path = Path(temp_dir)

        # Step 1: Save chapter WAVs and track timing
        chapter_marks = []
        wav_files = []
        current_time = 0.0

        for idx, (title, audio) in enumerate(chapter_audio):
            wav_path = temp_path / f"chapter_{idx:04d}.wav"
            duration = save_chapter_wav(audio, wav_path)
            wav_files.append(wav_path)

            chapter_marks.append(ChapterMark(
                title=title,
                start_time=current_time,
                end_time=current_time + duration,
            ))
            current_time += duration

            logger.info("  Chapter %d: '%s' (%.1fs)", idx + 1, title, duration)

        total_duration = current_time
        logger.info("Total duration: %.1f seconds (%.1f minutes)", total_duration, total_duration / 60)

        # Step 2: Create concat list for ffmpeg
        concat_list_path = temp_path / "concat_list.txt"
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for wav_path in wav_files:
                # ffmpeg concat demuxer needs escaped paths
                escaped = str(wav_path).replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        # Step 3: Create metadata file with chapters
        metadata_content = create_ffmpeg_metadata(chapter_marks)
        metadata_path = temp_path / "metadata.txt"
        with open(metadata_path, "w", encoding="utf-8") as f:
            f.write(metadata_content)

        # Step 4: Concatenate WAVs and encode to M4B with chapter metadata
        # Using a two-step process for reliability:
        # First concatenate to a single WAV, then encode to M4B

        combined_wav = temp_path / "combined.wav"

        # Concatenate all WAV files
        concat_cmd = [
            ffmpeg_path,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_path),
            "-c", "copy",
            str(combined_wav),
        ]

        logger.info("Concatenating %d chapter WAV files...", len(wav_files))
        result = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logger.error("ffmpeg concat failed:\n%s", result.stderr)
            raise RuntimeError(f"Failed to concatenate WAV files: {result.stderr}")

        # Save cover image if provided
        cover_path = None
        if cover_image:
            cover_path = temp_path / f"cover.{cover_image_ext}"
            with open(cover_path, "wb") as f:
                f.write(cover_image)
            logger.info("Cover image saved: %s (%.1f KB)", cover_path.name, len(cover_image) / 1024)

        # Encode to M4B with metadata (and cover art if available)
        encode_cmd = [
            ffmpeg_path,
            "-y",
            "-i", str(combined_wav),
            "-i", str(metadata_path),
        ]

        if cover_path:
            encode_cmd += ["-i", str(cover_path)]
            # Map: 0=audio, 1=metadata, 2=cover image
            encode_cmd += [
                "-map", "0:a",
                "-map", "2:v",
                "-map_metadata", "1",
                "-c:a", "aac",
                "-b:a", bitrate,
                "-ar", str(SAMPLE_RATE),
                "-ac", "1",
                "-c:v", "copy",
                "-disposition:v", "attached_pic",
            ]
        else:
            encode_cmd += [
                "-map_metadata", "1",
                "-c:a", "aac",
                "-b:a", bitrate,
                "-ar", str(SAMPLE_RATE),
                "-ac", "1",
            ]

        encode_cmd += [
            "-metadata", f"title={book_title}",
            "-metadata", f"artist={book_author}",
            "-metadata", f"album={book_title}",
            "-metadata", "genre=Audiobook",
            "-f", "mp4",
            str(output),
        ]

        logger.info("Encoding to M4B (AAC %s)...", bitrate)
        result = subprocess.run(encode_cmd, capture_output=True, text=True, timeout=1200)
        if result.returncode != 0:
            logger.error("ffmpeg encode failed:\n%s", result.stderr)
            raise RuntimeError(f"Failed to encode M4B: {result.stderr}")

        # Verify output
        if not output.exists():
            raise RuntimeError(f"M4B file was not created: {output}")

        file_size_mb = output.stat().st_size / (1024 * 1024)
        logger.info("M4B audiobook created: %s (%.1f MB, %.1f min)",
                     output, file_size_mb, total_duration / 60)

    return output
