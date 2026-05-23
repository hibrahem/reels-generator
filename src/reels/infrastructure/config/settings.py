"""Configuration schema and loader (spec §7).

Single ``config.yaml`` validated with pydantic. Secrets (API keys) are NEVER read from here — they
come from environment variables, resolved in the relevant infrastructure adapter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class PathsConfig(BaseModel):
    input_dir: Path
    output_dir: Path
    work_dir: Path = Path("./work")
    intro: Path | None = None
    outro: Path | None = None
    logo: Path | None = None
    font: Path


class TranscriptionConfig(BaseModel):
    backend: Literal["faster-whisper", "whisperx"] = "faster-whisper"
    model_size: str = "large-v3"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    compute_type: str = "auto"
    language: str = "ar"
    beam_size: int = 5


class SelectionConfig(BaseModel):
    # 'deepseek' and 'openai' share one OpenAI-compatible adapter (they differ only by base_url
    # and which env var holds the key). 'claude' uses the Anthropic SDK.
    provider: Literal["openai", "deepseek", "claude"] = "openai"
    model: str = "gpt-4o"
    base_url: str | None = None  # override the API endpoint (OpenAI-compatible providers)
    api_key_env: str | None = None  # override which env var holds the key
    temperature: float = 0.2
    min_clip_seconds: float = 20.0
    max_clip_seconds: float = 90.0
    max_retries: int = 1


class LayoutConfig(BaseModel):
    mode_b_split_ratio: float = Field(default=0.5, gt=0.0, lt=1.0)
    detection_sample_interval_seconds: float = 2.0
    default_fallback_crop: Literal["right", "center", "left"] = "right"
    presenter_anchor: Literal["right", "center", "left"] = "right"


class CaptionsConfig(BaseModel):
    font_family: str = "Noto Naskh Arabic"
    base_font_size: int = 64
    active_font_size: int = 72
    base_color: str = "&H00FFFFFF"
    active_color: str = "&H0000D7FF"
    position: Literal["bottom", "center"] = "bottom"
    safe_margin_v: int = 220
    safe_margin_h: int = 80
    max_words_per_line: int = 5
    outline: int = 3
    shadow: int = 1


class OutputConfig(BaseModel):
    width: int = 1080
    height: int = 1920
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    video_bitrate: str = "8M"
    audio_bitrate: str = "192k"
    faststart: bool = True


class Settings(BaseModel):
    paths: PathsConfig
    transcription: TranscriptionConfig = TranscriptionConfig()
    selection: SelectionConfig = SelectionConfig()
    layout: LayoutConfig = LayoutConfig()
    captions: CaptionsConfig = CaptionsConfig()
    output: OutputConfig = OutputConfig()


def load_settings(config_path: Path) -> Settings:
    """Read and validate a YAML config file into a :class:`Settings` instance."""
    if not config_path.exists():
        raise FileNotFoundError(f"config file not found: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return Settings.model_validate(raw)
