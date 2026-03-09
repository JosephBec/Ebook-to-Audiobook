#!/usr/bin/env python3
"""
Ebook-to-Audiobook Converter

Convert EPUB ebooks to M4B audiobooks using Kokoro TTS with GPU acceleration.

Usage:
    python main.py input.epub
    python main.py input.epub -o output.m4b --voice af_heart --speed 1.0
    python main.py --list-voices
    python main.py --help
"""

import sys

from src.cli import run


def main():
    sys.exit(run())


if __name__ == "__main__":
    main()
