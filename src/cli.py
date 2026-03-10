"""
CLI Module

Terminal-based interface for the Ebook-to-Audiobook converter.
Handles argument parsing, progress display, and user interaction.
"""

import argparse
import logging
import sys
import time
from pathlib import Path

from tqdm import tqdm

from src import __version__
from src.epub_parser import parse_epub
from src.tts_engine import TTSEngine, SAMPLE_RATE, list_voices
from src.audiobook_builder import build_m4b, check_ffmpeg

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False, debug: bool = False):
    """Configure logging based on verbosity level."""
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def print_banner():
    """Print the application banner with dynamically aligned box."""
    lines = [
        "Ebook-to-Audiobook Converter",
        "Powered by Kokoro TTS + CUDA GPU",
        f"v{__version__}",
    ]
    width = max(len(line) for line in lines) + 4  # padding on each side
    print()
    print(f"╔{'═' * width}╗")
    for line in lines:
        padding = width - len(line)
        left = padding // 2
        right = padding - left
        print(f"║{' ' * left}{line}{' ' * right}║")
    print(f"╚{'═' * width}╝")
    print()


def print_voices():
    """Print available voices and exit."""
    print("\nAvailable Voices (American English):")
    print("-" * 45)

    voices = list_voices("a")
    female = [v for v in voices if v.startswith("af_")]
    male = [v for v in voices if v.startswith("am_")]
    other = [v for v in voices if not v.startswith("af_") and not v.startswith("am_")]

    if female:
        print("\n  Female voices:")
        for v in sorted(female):
            print(f"    {v}")

    if male:
        print("\n  Male voices:")
        for v in sorted(male):
            print(f"    {v}")

    if other:
        print("\n  Other voices:")
        for v in sorted(other):
            print(f"    {v}")

    print("\nBritish English voices: use --lang-code b")
    print("Other languages: e (Spanish), f (French), h (Hindi), i (Italian)")
    print("                j (Japanese), p (Portuguese), z (Chinese)")
    print()


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="ebook2audiobook",
        description="Convert EPUB ebooks to M4B audiobooks using Kokoro TTS with GPU acceleration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.epub
  %(prog)s input.epub -o audiobook.m4b --voice af_heart
  %(prog)s input.epub -o audiobook.m4b --voice am_adam --speed 1.2
  %(prog)s input.epub -o audiobook.m4b --bitrate 128k --cpu
  %(prog)s --list-voices
        """,
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="Path to the input EPUB file.",
    )

    parser.add_argument(
        "-o", "--output",
        help="Path for the output M4B file. Defaults to input filename with .m4b extension.",
    )

    # TTS options
    tts_group = parser.add_argument_group("TTS Options")
    tts_group.add_argument(
        "--voice",
        default="af_heart",
        help="Voice to use for TTS (default: af_heart). Use --list-voices to see options.",
    )
    tts_group.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Speech speed multiplier (default: 1.0). Range: 0.5-2.0.",
    )
    tts_group.add_argument(
        "--lang-code",
        default="a",
        help="Language code (default: 'a' for American English). "
             "Options: a=US English, b=British, e=Spanish, f=French, "
             "h=Hindi, i=Italian, j=Japanese, p=Portuguese, z=Chinese.",
    )

    # Audio options
    audio_group = parser.add_argument_group("Audio Options")
    audio_group.add_argument(
        "--bitrate",
        default="64k",
        help="AAC encoding bitrate (default: 64k). Higher = better quality, larger file.",
    )

    # Processing options
    proc_group = parser.add_argument_group("Processing Options")
    proc_group.add_argument(
        "--cpu",
        action="store_true",
        help="Force CPU mode even if CUDA GPU is available.",
    )
    proc_group.add_argument(
        "--min-chapter-words",
        type=int,
        default=20,
        help="Minimum word count for a section to be treated as a chapter (default: 20).",
    )
    proc_group.add_argument(
        "--chapters",
        type=str,
        default=None,
        help="Comma-separated list of chapter numbers to process (e.g., '1,2,5'). "
             "Processes all chapters if not specified.",
    )
    proc_group.add_argument(
        "--phoneme-map",
        type=str,
        default=None,
        help="Path to a phoneme map file for custom pronunciation of foreign words. "
             "Format: 'word | IPA phonemes | language' per line.",
    )

    # Output options
    out_group = parser.add_argument_group("Output & Display")
    out_group.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed progress information.",
    )
    out_group.add_argument(
        "--debug",
        action="store_true",
        help="Show debug-level logging output.",
    )
    out_group.add_argument(
        "--list-voices",
        action="store_true",
        help="List available voices and exit.",
    )

    return parser


def select_chapters_interactive(chapters, total_count: int) -> list:
    """Let the user select which chapters to convert interactively."""
    print(f"\nFound {total_count} chapters:")
    print("-" * 60)

    for ch in chapters:
        print(f"  [{ch.index + 1:3d}] {ch.title} ({ch.word_count:,} words)")

    print(f"\n  Total: {sum(c.word_count for c in chapters):,} words")
    print("-" * 60)

    while True:
        selection = input("\nChapters to convert (Enter=all, e.g. '1-5', '1,3,5', 'q'=quit): ").strip()

        if selection.lower() == "q":
            print("Aborted.")
            sys.exit(0)

        if selection == "":
            return chapters

        try:
            selected_indices = set()
            for part in selection.split(","):
                part = part.strip()
                if "-" in part:
                    start, end = part.split("-", 1)
                    for i in range(int(start), int(end) + 1):
                        selected_indices.add(i)
                else:
                    selected_indices.add(int(part))

            selected = [ch for ch in chapters if (ch.index + 1) in selected_indices]
            if selected:
                return selected
            else:
                print("No valid chapters selected. Try again.")
        except ValueError:
            print("Invalid format. Use numbers like '1-5' or '1,3,5'.")


def estimate_duration(word_count: int, speed: float = 1.0) -> float:
    """Estimate audio duration in minutes from word count (~150 words/min at 1x speed)."""
    return (word_count / 150) / speed


def run(args=None):
    """Main entry point for the CLI."""
    parser = create_parser()
    opts = parser.parse_args(args)

    # Handle --list-voices
    if opts.list_voices:
        print_voices()
        return 0

    # Validate input
    if not opts.input:
        parser.print_help()
        return 1

    # Setup logging
    setup_logging(verbose=opts.verbose, debug=opts.debug)

    # Print banner
    print_banner()

    input_path = Path(opts.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {opts.input}")
        return 1

    if input_path.suffix.lower() != ".epub":
        print(f"Error: Input must be an EPUB file, got: {input_path.suffix}")
        return 1

    # Check ffmpeg availability
    print("[1/4] Checking dependencies...")
    try:
        check_ffmpeg()
        print("  ffmpeg: OK")
    except RuntimeError as e:
        print(f"  Error: {e}")
        return 1

    # Parse EPUB
    print(f"\n[2/4] Parsing EPUB: {input_path.name}")
    try:
        metadata = parse_epub(str(input_path), min_chapter_words=opts.min_chapter_words)
    except (FileNotFoundError, ValueError) as e:
        print(f"  Error: {e}")
        return 1

    print(f"  Title:    {metadata.title}")
    print(f"  Author:   {metadata.author}")
    print(f"  Language: {metadata.language}")
    print(f"  Chapters: {len(metadata.chapters)}")
    print(f"  Words:    {metadata.total_word_count:,}")
    if metadata.cover_image:
        print(f"  Cover:    Found ({len(metadata.cover_image) / 1024:.1f} KB, {metadata.cover_image_ext})")
    else:
        print(f"  Cover:    Not found")

    est_minutes = estimate_duration(metadata.total_word_count, opts.speed)
    print(f"  Est. Duration: ~{est_minutes:.0f} minutes")

    # Chapter selection
    if opts.chapters:
        # Parse explicit chapter selection
        selected_indices = set()
        for part in opts.chapters.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-", 1)
                for i in range(int(start), int(end) + 1):
                    selected_indices.add(i)
            else:
                selected_indices.add(int(part))

        chapters_to_process = [ch for ch in metadata.chapters if (ch.index + 1) in selected_indices]
        if not chapters_to_process:
            print("Error: No valid chapters found for the given selection.")
            return 1
        print(f"\n  Selected {len(chapters_to_process)} of {len(metadata.chapters)} chapters.")
    else:
        chapters_to_process = select_chapters_interactive(metadata.chapters, len(metadata.chapters))

    print(f"\n  Will process {len(chapters_to_process)} chapters "
          f"({sum(c.word_count for c in chapters_to_process):,} words)")

    # Determine output path
    if opts.output:
        output_path = Path(opts.output)
        # If -o points to a directory (or ends with a separator), place the file inside it
        if output_path.is_dir() or str(opts.output).endswith(('/', '\\')):
            output_path = output_path / input_path.with_suffix(".m4b").name
        elif output_path.suffix.lower() != ".m4b":
            output_path = output_path.with_suffix(".m4b")
    else:
        output_path = input_path.with_suffix(".m4b")

    print(f"  Output:   {output_path}")

    # Initialize TTS engine
    print(f"\n[3/4] Initializing TTS engine...")
    device = "cpu" if opts.cpu else None
    try:
        engine = TTSEngine(
            voice=opts.voice,
            speed=opts.speed,
            lang_code=opts.lang_code,
            device=device,
            phoneme_map_path=opts.phoneme_map,
        )
    except Exception as e:
        print(f"  Error initializing TTS engine: {e}")
        logger.exception("TTS init failed")
        return 1

    print(f"  Voice:    {opts.voice}")
    print(f"  Speed:    {opts.speed}x")
    print(f"  Device:   {engine.device}")
    if engine.pronunciation_map:
        print(f"  Phonemes: {len(engine.pronunciation_map)} custom pronunciations loaded")

    # Synthesize chapters
    print(f"\n[4/4] Synthesizing audio...")
    overall_start = time.time()
    chapter_audio = []

    progress_bar = tqdm(
        chapters_to_process,
        desc="Chapters",
        unit="ch",
        ncols=80,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
    )

    for chapter in progress_bar:
        progress_bar.set_postfix_str(f"{chapter.title[:30]}", refresh=True)

        try:
            audio = engine.synthesize_chapter(chapter.text, chapter.title)
            if len(audio) > 0:
                chapter_audio.append((chapter.title, audio))
            else:
                print(f"\n  Warning: No audio generated for chapter: {chapter.title}")
        except Exception as e:
            print(f"\n  Error synthesizing chapter '{chapter.title}': {e}")
            logger.exception("Chapter synthesis failed")
            continue

    progress_bar.close()

    if not chapter_audio:
        print("Error: No audio was generated for any chapter.")
        return 1

    total_synth_time = time.time() - overall_start
    total_audio_duration = sum(len(audio) / SAMPLE_RATE for _, audio in chapter_audio)

    print(f"\n  Synthesized {len(chapter_audio)} chapters")
    print(f"  Audio duration: {total_audio_duration / 60:.1f} minutes")
    print(f"  Synthesis time: {total_synth_time / 60:.1f} minutes")
    print(f"  Realtime factor: {total_audio_duration / total_synth_time:.1f}x" if total_synth_time > 0 else "")

    # Build M4B
    print(f"\nBuilding M4B audiobook...")
    try:
        result_path = build_m4b(
            chapter_audio=chapter_audio,
            output_path=str(output_path),
            book_title=metadata.title,
            book_author=metadata.author,
            bitrate=opts.bitrate,
            cover_image=metadata.cover_image,
            cover_image_ext=metadata.cover_image_ext,
        )

        file_size_mb = result_path.stat().st_size / (1024 * 1024)
        print(f"\n{'=' * 60}")
        print(f"  Audiobook created successfully!")
        print(f"  File:     {result_path}")
        print(f"  Size:     {file_size_mb:.1f} MB")
        print(f"  Duration: {total_audio_duration / 60:.1f} minutes")
        print(f"  Chapters: {len(chapter_audio)}")
        print(f"{'=' * 60}")

    except RuntimeError as e:
        print(f"  Error building M4B: {e}")
        logger.exception("M4B build failed")
        return 1

    return 0
