"""Defaults for each selection provider.

OpenAI and DeepSeek both speak the OpenAI Chat Completions API, so they share one adapter and
differ only in base_url, the env var holding the key, and a sensible default model.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    key_env: str
    base_url: str | None
    default_model: str
    openai_compatible: bool


PROVIDER_PROFILES: dict[str, ProviderProfile] = {
    "openai": ProviderProfile(
        key_env="OPENAI_API_KEY",
        base_url=None,  # SDK default (https://api.openai.com/v1)
        default_model="gpt-4o",
        openai_compatible=True,
    ),
    "deepseek": ProviderProfile(
        key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com",
        default_model="deepseek-chat",
        openai_compatible=True,
    ),
    "claude": ProviderProfile(
        key_env="ANTHROPIC_API_KEY",
        base_url=None,
        default_model="claude-sonnet-4-6",
        openai_compatible=False,
    ),
}
