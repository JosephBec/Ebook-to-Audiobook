"""
TTS Engine Module

Wraps the Kokoro TTS pipeline for GPU-accelerated text-to-speech synthesis.
Processes text in chunks and returns audio data at 24kHz sample rate.
"""

import logging
import re
import time
from pathlib import Path
from typing import Dict, Optional, Generator, Tuple

import numpy as np
import torch
from kokoro import KPipeline

logger = logging.getLogger(__name__)

# Kokoro outputs audio at 24kHz
SAMPLE_RATE = 24000


def get_device() -> str:
    """Detect the best available device for inference."""
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        logger.info("CUDA available: %s (%.1f GB VRAM)", device_name, vram)
        return "cuda"
    else:
        logger.warning("CUDA not available. Falling back to CPU. This will be significantly slower.")
        return "cpu"


def list_voices(lang_code: str = "a") -> list:
    """
    Return a list of available voice names for the given language code.

    Language codes:
        'a' = American English, 'b' = British English,
        'e' = Spanish, 'f' = French, 'h' = Hindi,
        'i' = Italian, 'j' = Japanese, 'p' = Brazilian Portuguese,
        'z' = Mandarin Chinese
    """
    pipeline = KPipeline(lang_code=lang_code)
    # Kokoro voices follow naming convention: {lang_prefix}_{name}
    # Common American English voices:
    voices = []
    try:
        # Try to list voices from the pipeline if available
        if hasattr(pipeline, 'voices'):
            voices = list(pipeline.voices.keys())
    except Exception:
        pass

    if not voices:
        # Fallback: known default voices
        voices = [
            "af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica",
            "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
            "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
            "am_michael", "am_onyx", "am_puck",
            "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
            "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
        ]

    return voices


def load_phoneme_map(map_path: str) -> Dict[str, str]:
    """
    Load a phoneme map file that maps foreign words to IPA phonemes.

    The map is used to generate phonetic English spellings so the TTS
    engine pronounces foreign names and words correctly.

    Format: word | IPA phonemes | language
    Lines starting with # are comments.

    Args:
        map_path: Path to the phoneme map text file.

    Returns:
        Dictionary mapping lowercase words to phonetic respellings.
    """
    path = Path(map_path)
    if not path.exists():
        raise FileNotFoundError(f"Phoneme map not found: {map_path}")

    # IPA to English phonetic approximation mapping
    ipa_to_english = {
        # Vowels
        'ɑ': 'ah', 'a': 'ah', 'æ': 'a', 'ɛ': 'eh', 'e': 'ay',
        'i': 'ee', 'ɪ': 'ih', 'ɔ': 'aw', 'o': 'oh', 'u': 'oo',
        'ʊ': 'oo', 'y': 'oo', 'ə': 'uh', 'œ': 'ur', 'ø': 'ur',
        'ɛ̃': 'an', 'ɑ̃': 'on', 'ɔ̃': 'on', 'ɛ̃': 'an', 'ɑ̃': 'ahn',
        'ɥ': 'w', 'w': 'w', 'j': 'y',
        # Consonants
        'ʁ': 'r', 'ʒ': 'zh', 'ʃ': 'sh', 'ɲ': 'ny', 'ŋ': 'ng',
        'ɡ': 'g', 'ɣ': 'g', 'θ': 'th', 'ð': 'th',
        't͡ʃ': 'ch', 'd͡ʒ': 'j', 't͡s': 'ts',
        'ʎ': 'ly', 'ç': 'sh', 'ʔ': '',
        # Simple passthrough
        'b': 'b', 'd': 'd', 'f': 'f', 'g': 'g', 'k': 'k',
        'l': 'l', 'm': 'm', 'n': 'n', 'p': 'p', 'r': 'r',
        's': 's', 't': 't', 'v': 'v', 'z': 'z',
    }

    def ipa_to_respelling(ipa_str: str) -> str:
        """Convert IPA phoneme string to an English phonetic respelling."""
        phonemes = ipa_str.strip().split()
        parts = []
        for ph in phonemes:
            # Remove stress marks
            ph = ph.replace('ˈ', '').replace('ˌ', '')
            if ph in ipa_to_english:
                parts.append(ipa_to_english[ph])
            # Try multi-char lookups
            elif len(ph) > 1:
                # Try to match known digraphs first
                matched = False
                for digraph in ['t͡ʃ', 'd͡ʒ', 't͡s']:
                    if digraph in ph:
                        parts.append(ipa_to_english[digraph])
                        matched = True
                        break
                if not matched:
                    # Fall back to char-by-char
                    for ch in ph:
                        if ch in ipa_to_english:
                            parts.append(ipa_to_english[ch])
            else:
                parts.append(ph)
        return ''.join(parts)

    pronunciation_map = {}
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                word = parts[0].strip().lower()
                ipa = parts[1].strip()
                respelling = ipa_to_respelling(ipa)
                if respelling and respelling != word:
                    pronunciation_map[word] = respelling
                    count += 1

    logger.info("Loaded %d pronunciation overrides from %s", count, map_path)
    if count > 0:
        # Log a few examples
        examples = list(pronunciation_map.items())[:5]
        for word, respelling in examples:
            logger.info("  %s -> %s", word, respelling)

    return pronunciation_map


def apply_pronunciation_map(text: str, pmap: Dict[str, str]) -> str:
    """
    Replace words in text using the pronunciation map.

    Does case-insensitive whole-word matching, preserving
    the original capitalization pattern.

    Args:
        text: Input text.
        pmap: Dictionary mapping lowercase words to phonetic respellings.

    Returns:
        Text with pronunciation replacements applied.
    """
    if not pmap:
        return text

    def replace_word(match):
        original = match.group(0)
        lower = original.lower()
        if lower in pmap:
            replacement = pmap[lower]
            # Preserve capitalization
            if original[0].isupper():
                replacement = replacement[0].upper() + replacement[1:]
            if original.isupper():
                replacement = replacement.upper()
            return replacement
        return original

    # Build a regex pattern that matches any mapped word (whole words only)
    # Sort by length descending so longer matches take priority
    sorted_words = sorted(pmap.keys(), key=len, reverse=True)
    pattern = r'\b(' + '|'.join(re.escape(w) for w in sorted_words) + r')\b'
    return re.sub(pattern, replace_word, text, flags=re.IGNORECASE)


class TTSEngine:
    """
    Kokoro TTS engine with GPU acceleration.

    Handles text-to-speech conversion using the Kokoro-82M model
    via PyTorch with optional CUDA GPU acceleration.
    """

    def __init__(
        self,
        voice: str = "af_heart",
        speed: float = 1.0,
        lang_code: str = "a",
        device: Optional[str] = None,
        phoneme_map_path: Optional[str] = None,
    ):
        """
        Initialize the TTS engine.

        Args:
            voice: Voice name to use (e.g., 'af_heart', 'am_adam').
            speed: Speech speed multiplier (0.5 = half speed, 2.0 = double speed).
            lang_code: Language code ('a' for American English, etc.).
            device: Force a specific device ('cuda' or 'cpu'). Auto-detects if None.
            phoneme_map_path: Optional path to a phoneme map file for custom pronunciations.
        """
        self.voice = voice
        self.speed = speed
        self.lang_code = lang_code
        self.device = device or get_device()
        self.pronunciation_map = {}

        if phoneme_map_path:
            self.pronunciation_map = load_phoneme_map(phoneme_map_path)

        logger.info("Initializing Kokoro TTS pipeline (lang=%s, voice=%s, speed=%.1f, device=%s)",
                     lang_code, voice, speed, self.device)

        self.pipeline = KPipeline(lang_code=self.lang_code, device=self.device)

        logger.info("TTS engine initialized successfully.")

    def synthesize_text(self, text: str) -> Generator[Tuple[int, str, np.ndarray], None, None]:
        """
        Synthesize text to audio using Kokoro TTS.

        The pipeline automatically splits long text into manageable segments.

        Args:
            text: The text to convert to speech.

        Yields:
            Tuples of (segment_index, segment_text, audio_array).
            Audio is a numpy float32 array at 24kHz sample rate.
        """
        # Apply pronunciation overrides before synthesis
        if self.pronunciation_map:
            text = apply_pronunciation_map(text, self.pronunciation_map)

        generator = self.pipeline(
            text,
            voice=self.voice,
            speed=self.speed,
            split_pattern=r'\n+',
        )

        for i, (graphemes, phonemes, audio) in enumerate(generator):
            if audio is not None and len(audio) > 0:
                yield i, graphemes, audio

    def synthesize_chapter(self, text: str, chapter_title: str = "") -> np.ndarray:
        """
        Synthesize an entire chapter's text and return concatenated audio.

        Args:
            text: Full chapter text.
            chapter_title: Chapter title for logging.

        Returns:
            Numpy float32 array of concatenated audio at 24kHz.
        """
        logger.info("Synthesizing chapter: '%s'", chapter_title or "untitled")
        start_time = time.time()

        audio_segments = []
        segment_count = 0

        for i, graphemes, audio in self.synthesize_text(text):
            audio_segments.append(audio)
            segment_count += 1

        if not audio_segments:
            logger.warning("No audio generated for chapter: '%s'", chapter_title)
            return np.array([], dtype=np.float32)

        # Concatenate all segments with a short silence between them
        silence = np.zeros(int(SAMPLE_RATE * 0.3), dtype=np.float32)  # 300ms silence
        result_parts = []
        for idx, seg in enumerate(audio_segments):
            result_parts.append(seg)
            if idx < len(audio_segments) - 1:
                result_parts.append(silence)

        result = np.concatenate(result_parts)
        duration = len(result) / SAMPLE_RATE
        elapsed = time.time() - start_time

        logger.info("  Chapter '%s': %d segments, %.1fs audio, generated in %.1fs (%.1fx realtime)",
                     chapter_title, segment_count, duration, elapsed,
                     duration / elapsed if elapsed > 0 else 0)

        return result
