"""Local speech-to-text for Telegram voice messages, using mlx-whisper
(Apple Silicon optimized, fully on-device — no API key, no per-use cost).

Needs ffmpeg on PATH to decode Telegram's Ogg/Opus voice files; installed
via the pip-bundled `imageio-ffmpeg` package rather than Homebrew (see
SETUP.md) since this machine has no Homebrew.
"""
from pathlib import Path

MODEL = "mlx-community/whisper-base.en-mlx"


def transcribe(audio_path):
    import mlx_whisper

    result = mlx_whisper.transcribe(str(audio_path), path_or_hf_repo=MODEL)
    return result["text"].strip()


if __name__ == "__main__":
    import sys

    print(transcribe(Path(sys.argv[1])))
