# Ebook-to-Audiobook

Convert EPUB ebooks into M4B audiobooks using [Kokoro TTS](https://github.com/hexgrad/kokoro) with NVIDIA GPU acceleration.

Kokoro is an open-weight text-to-speech model with 82 million parameters that delivers high-quality, natural-sounding speech. This tool parses EPUB files, synthesizes speech chapter-by-chapter on your GPU, and packages everything into a single M4B audiobook file with embedded chapter markers.

---

## Features

- **GPU-accelerated TTS** — Uses PyTorch + CUDA for fast synthesis on NVIDIA GPUs
- **EPUB parsing** — Automatically extracts chapters, titles, and metadata
- **Cover art extraction** — Automatically extracts the cover image from the EPUB and embeds it in the M4B file
- **M4B output** — Produces audiobook files with embedded chapter markers, compatible with Apple Books, VLC, and other audiobook players
- **Custom pronunciation** — Optional phoneme map files to correct pronunciation of foreign names and words (e.g., French names in *The Count of Monte Cristo*)
- **Multiple voices** — 20+ built-in voices (male and female) across multiple languages
- **Adjustable speed** — Control speech rate from 0.5x to 2.0x
- **Interactive chapter selection** — Choose which chapters to convert, or convert the whole book
- **Progress display** — Real-time progress bars with time estimates
- **Fully terminal-based** — No GUI required, works entirely from the command line

## Requirements

- **Python 3.9–3.12** (Python 3.13+ is not supported by Kokoro)
- **NVIDIA GPU** with CUDA support (tested on RTX 2070; CPU fallback available)
- **ffmpeg** — Required for M4B encoding
- **espeak-ng** — Required by Kokoro for phoneme generation

## Installation

### 1. Install System Dependencies

#### ffmpeg

- **Windows (winget):**
  ```
  winget install ffmpeg
  ```
- **Windows (Chocolatey):**
  ```
  choco install ffmpeg
  ```
- **Windows (manual):** Download from [ffmpeg.org](https://ffmpeg.org/download.html), extract, and add the `bin` folder to your system PATH.

#### espeak-ng

- **Windows:** Download the `.msi` installer from [espeak-ng releases](https://github.com/espeak-ng/espeak-ng/releases) (e.g., `espeak-ng-20191129-b702b03-x64.msi`) and run it.

### 2. Clone the Repository

```bash
git clone https://github.com/YourUser/Ebook-to-Audiobook.git
cd Ebook-to-Audiobook
```

### 3. Create a Virtual Environment

```bash
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (cmd)
.venv\Scripts\activate.bat

# Linux / macOS
source .venv/bin/activate
```

### 4. Install PyTorch with CUDA

Install PyTorch with CUDA support **first**, before other dependencies. Visit [pytorch.org](https://pytorch.org/get-started/locally/) to find the right command for your CUDA version.

For CUDA 12.1:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

For CUDA 12.4:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

### 5. Install Project Dependencies

```bash
pip install -r requirements.txt
```

### 6. Verify Installation

```bash
python main.py --list-voices
```

If this prints a list of voices without errors, you're good to go.

## Usage

### Basic Conversion

```bash
python main.py mybook.epub
```

This will:
1. Parse the EPUB and display chapter information
2. Prompt you to select which chapters to convert (Enter = all)
3. Synthesize speech for each chapter using your GPU
4. Package everything into `mybook.m4b` with chapter markers

### Specify Output File and Voice

```bash
python main.py mybook.epub -o audiobook.m4b --voice af_heart
```

### Use a Male Voice at 1.2x Speed

```bash
python main.py mybook.epub --voice am_adam --speed 1.2
```

### Convert Specific Chapters Only

```bash
python main.py mybook.epub --chapters 1,2,3,5-10
```

### Force CPU Mode (No GPU)

```bash
python main.py mybook.epub --cpu
```

### Higher Audio Quality

```bash
python main.py mybook.epub --bitrate 128k
```

### Verbose Output (Detailed Progress)

```bash
python main.py mybook.epub -v
```

### Debug Mode (Full Logging)

```bash
python main.py mybook.epub --debug
```

### Custom Pronunciation with Phoneme Maps

For books with foreign names and words (e.g., French names in classic literature), you can provide a phoneme map file to improve pronunciation:

```bash
python main.py mybook.epub --phoneme-map phoneme_maps/monte_cristo.txt -v
```

A phoneme map is a text file where each line maps a word to its IPA phonemes:

```
# Format: word | IPA phonemes | language
dantès | d ɑ̃ t ɛ | fr
mercédès | m ɛ ʁ s e d ɛ | fr
villefort | v i l f ɔ ʁ | fr
```

The tool converts IPA phonemes into English phonetic respellings so the TTS engine pronounces them correctly. Pre-built maps are available in the `phoneme_maps/` directory:

- **`phoneme_maps/monte_cristo.txt`** — 897 French/Italian/Latin words from *The Count of Monte Cristo*

The `--phoneme-map` flag is entirely optional — omit it for books that don't need custom pronunciation.

### Output to a Directory

If `-o` points to a directory, the output file is automatically named after the EPUB:

```bash
python main.py mybook.epub -o "E:\Plex\Audiobooks\"
# Creates: E:\Plex\Audiobooks\mybook.m4b
```

## Real-World Example: Full Walkthrough

Below is a complete, real example converting a light novel EPUB into an M4B audiobook — from start to finish.

### Source File

```
D:\Desktop\My Stuff\Books\Books\Light Novels\Birth of The Demonic Sword\Birth of the Demonic Sword 1 ~ 60.epub
```

### Step 1: Activate the Virtual Environment

```powershell
cd D:\Projects\Ebook-to-Audiobook
.venv\Scripts\Activate.ps1
```

### Step 2: Run the Conversion

Convert all 60 chapters, saving the M4B to the same directory as the EPUB:

```powershell
python main.py "D:\Desktop\My Stuff\Books\Books\Light Novels\Birth of The Demonic Sword\Birth of the Demonic Sword 1 ~ 60.epub" -o "D:\Desktop\My Stuff\Books\Books\Light Novels\Birth of The Demonic Sword\Birth of the Demonic Sword 1 ~ 60.m4b" --chapters 1-60 -v
```

**Breaking down the command:**
- **`"D:\Desktop\...\Birth of the Demonic Sword 1 ~ 60.epub"`** — Input EPUB file (quotes needed for paths with spaces)
- **`-o "D:\Desktop\...\Birth of the Demonic Sword 1 ~ 60.m4b"`** — Output M4B path in the same folder
- **`--chapters 1-60`** — Process all 60 chapters (skips the interactive chapter selection prompt)
- **`-v`** — Verbose output to see detailed progress

### Step 3: What Happens

The tool prints progress as it works through each stage:

```
╔══════════════════════════════════════════════════════════╗
║              Ebook-to-Audiobook Converter                ║
║           Powered by Kokoro TTS + CUDA GPU               ║
║                     v1.0.0                               ║
╚══════════════════════════════════════════════════════════╝

[1/4] Checking dependencies...
  ffmpeg: OK

[2/4] Parsing EPUB: Birth of the Demonic Sword 1 ~ 60.epub
  Title:    Birth of the Demonic Sword 1 ~ 60
  Author:   Eveofchaos
  Language: en
  Chapters: 60
  Words:    73,223
  Est. Duration: ~488 minutes

  Selected 60 of 60 chapters.
  Will process 60 chapters (73,223 words)
  Output:   D:\Desktop\...\Birth of the Demonic Sword 1 ~ 60.m4b

[3/4] Initializing TTS engine...
  Voice:    af_heart
  Speed:    1.0x
  Device:   cuda

[4/4] Synthesizing audio...
Chapters: 100%|████████████████████████████████████████| 60/60 [12:52<00:00]

  Synthesized 60 chapters
  Audio duration: 423.8 minutes
  Synthesis time: 12.9 minutes
  Realtime factor: 32.9x

Building M4B audiobook...

============================================================
  Audiobook created successfully!
  File:     D:\Desktop\...\Birth of the Demonic Sword 1 ~ 60.m4b
  Size:     193.8 MB
  Duration: 423.8 minutes
  Chapters: 60
============================================================
```

### Results Summary

| Metric | Value |
|---|---|
| **Input** | 60 chapters, 73,223 words |
| **Audio Duration** | 423.8 minutes (~7 hours) |
| **Synthesis Time** | ~13 minutes |
| **Realtime Factor** | ~33x (on RTX 2070) |
| **Output File Size** | 193.8 MB |
| **Voice** | `af_heart` (default female) |
| **Bitrate** | 64k AAC (default) |

### Variations

To convert only the first 5 chapters as a test:
```powershell
python main.py "D:\Desktop\My Stuff\Books\Books\Light Novels\Birth of The Demonic Sword\Birth of the Demonic Sword 1 ~ 60.epub" -o "D:\Desktop\My Stuff\Books\Books\Light Novels\Birth of The Demonic Sword\Birth of the Demonic Sword 1 ~ 60.m4b" --chapters 1-5 -v
```

To use a male voice at 1.1x speed with higher quality audio:
```powershell
python main.py "D:\Desktop\My Stuff\Books\Books\Light Novels\Birth of The Demonic Sword\Birth of the Demonic Sword 1 ~ 60.epub" -o "D:\Desktop\My Stuff\Books\Books\Light Novels\Birth of The Demonic Sword\Birth of the Demonic Sword 1 ~ 60.m4b" --voice am_adam --speed 1.1 --bitrate 128k --chapters 1-60 -v
```

To let the tool auto-name the output (defaults to same name with `.m4b` extension in the same directory as the input):
```powershell
python main.py "D:\Desktop\My Stuff\Books\Books\Light Novels\Birth of The Demonic Sword\Birth of the Demonic Sword 1 ~ 60.epub" --chapters 1-60 -v
```

## All Options

```
usage: ebook2audiobook [-h] [-o OUTPUT] [--voice VOICE] [--speed SPEED]
                       [--lang-code LANG_CODE] [--bitrate BITRATE] [--cpu]
                       [--min-chapter-words MIN_CHAPTER_WORDS]
                       [--chapters CHAPTERS] [--phoneme-map PHONEME_MAP]
                       [-v] [--debug] [--list-voices]
                       [input]

positional arguments:
  input                 Path to the input EPUB file.

TTS Options:
  --voice VOICE         Voice to use (default: af_heart)
  --speed SPEED         Speech speed multiplier (default: 1.0, range: 0.5-2.0)
  --lang-code LANG_CODE Language code (default: 'a' for American English)

Audio Options:
  --bitrate BITRATE     AAC encoding bitrate (default: 64k)

Processing Options:
  --cpu                 Force CPU mode
  --min-chapter-words N Minimum words to treat a section as a chapter (default: 20)
  --chapters CHAPTERS   Comma-separated chapter numbers (e.g., '1,2,5-10')
  --phoneme-map FILE    Path to a phoneme map for custom pronunciation

Output & Display:
  -o, --output OUTPUT   Output M4B file path (or directory)
  -v, --verbose         Show detailed progress
  --debug               Show debug logging
  --list-voices         List available voices and exit
```

## Available Voices

### American English (`--lang-code a`)

| Female Voices | Male Voices |
|---|---|
| `af_heart` (default) | `am_adam` |
| `af_alloy` | `am_echo` |
| `af_aoede` | `am_eric` |
| `af_bella` | `am_fenrir` |
| `af_jessica` | `am_liam` |
| `af_kore` | `am_michael` |
| `af_nicole` | `am_onyx` |
| `af_nova` | `am_puck` |
| `af_river` | |
| `af_sarah` | |
| `af_sky` | |

### British English (`--lang-code b`)

| Female Voices | Male Voices |
|---|---|
| `bf_alice` | `bm_daniel` |
| `bf_emma` | `bm_fable` |
| `bf_isabella` | `bm_george` |
| `bf_lily` | `bm_lewis` |

### Other Languages

| Code | Language | Flag |
|---|---|---|
| `e` | Spanish | 🇪🇸 |
| `f` | French | 🇫🇷 |
| `h` | Hindi | 🇮🇳 |
| `i` | Italian | 🇮🇹 |
| `j` | Japanese | 🇯🇵 |
| `p` | Brazilian Portuguese | 🇧🇷 |
| `z` | Mandarin Chinese | 🇨🇳 |

## Project Structure

```
Ebook-to-Audiobook/
├── main.py                 # Entry point
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── phoneme_maps/           # Custom pronunciation maps (optional)
│   ├── monte_cristo.txt    # French/Italian/Latin words for Monte Cristo
│   └── monte_cristo_words.txt  # Source word list
└── src/
    ├── __init__.py          # Package init
    ├── cli.py               # CLI argument parsing and orchestration
    ├── epub_parser.py       # EPUB file parsing and chapter extraction
    ├── tts_engine.py        # Kokoro TTS engine with GPU support + phoneme maps
    └── audiobook_builder.py # M4B assembly with ffmpeg + cover art
```

## How It Works

1. **EPUB Parsing** (`epub_parser.py`): Reads the EPUB file, extracts chapters in spine order, strips HTML to clean text, and identifies chapter titles from heading tags.

2. **TTS Synthesis** (`tts_engine.py`): Initializes the Kokoro-82M model on your GPU via PyTorch. If a phoneme map is provided, foreign words are replaced with phonetic respellings before synthesis. Each chapter's text is fed through the pipeline, which handles text segmentation, phoneme conversion (via [misaki](https://github.com/hexgrad/misaki)), and audio generation at 24kHz.

3. **M4B Assembly** (`audiobook_builder.py`): Chapter audio is saved as temporary WAV files, concatenated, then encoded to AAC audio in an MP4 container (M4B) using ffmpeg. Chapter markers with titles and timestamps are embedded in the file metadata. If a cover image is found in the EPUB, it is embedded as cover art in the M4B.

## Performance

On an NVIDIA RTX 2070 (8 GB VRAM), expect roughly **10-30x realtime** synthesis speed. A typical 80,000-word novel (~9 hours of audio) can be converted in approximately 20-50 minutes depending on content complexity.

CPU mode is available but significantly slower (~1-3x realtime).

## Troubleshooting

### "espeak-ng not found"
Make sure espeak-ng is installed and on your PATH. On Windows, the MSI installer should handle this automatically. If not, add the espeak-ng installation directory to your system PATH.

### "CUDA not available"
- Verify your NVIDIA drivers are up to date
- Ensure you installed the CUDA-enabled PyTorch build (not the CPU-only version)
- Check with: `python -c "import torch; print(torch.cuda.is_available())"`

### "ffmpeg not found"
Make sure ffmpeg is installed and on your PATH. Test with: `ffmpeg -version`

### Out of GPU Memory
The Kokoro-82M model is small (82M params), so it should work on most GPUs. If you still run into issues, use `--cpu` mode.

### EPUB Chapters Not Detected
Some EPUBs have unusual structures. Try lowering `--min-chapter-words` to include shorter sections, or use `--debug` to see what's being parsed.

## Credits

- [Kokoro](https://github.com/hexgrad/kokoro) — The Kokoro-82M TTS model and inference library by hexgrad
- [misaki](https://github.com/hexgrad/misaki) — G2P (grapheme-to-phoneme) library used by Kokoro
- [nazdridoy/kokoro-tts](https://github.com/nazdridoy/kokoro-tts) — Inspiration for CLI design and EPUB handling
- [espeak-ng](https://github.com/espeak-ng/espeak-ng) — Phonemizer backend
- [ffmpeg](https://ffmpeg.org/) — Audio encoding and M4B assembly

## License

MIT
