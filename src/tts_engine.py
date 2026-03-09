"""
TTS Engine Module

Wraps the Kokoro TTS pipeline for GPU-accelerated text-to-speech synthesis.
Processes text in chunks and returns audio data at 24kHz sample rate.
"""

import logging
import time
from typing import Optional, Generator, Tuple

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
    ):
        """
        Initialize the TTS engine.

        Args:
            voice: Voice name to use (e.g., 'af_heart', 'am_adam').
            speed: Speech speed multiplier (0.5 = half speed, 2.0 = double speed).
            lang_code: Language code ('a' for American English, etc.).
            device: Force a specific device ('cuda' or 'cpu'). Auto-detects if None.
        """
        self.voice = voice
        self.speed = speed
        self.lang_code = lang_code
        self.device = device or get_device()

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
