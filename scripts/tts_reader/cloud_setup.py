"""Interactive cloud-voice setup wizard.

Walks through provider (or disable), the env var that holds the API key, and
Azure region when needed. The key itself is never written to config.json.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Callable, List, Optional, Tuple

from tts_reader import config
from tts_reader.engine.cloud import (
    DEFAULT_API_KEY_ENV,
    api_key_env_name,
    valid_env_name,
)
from tts_reader.ui import BACK, EXIT, prompt_line, radio_select

CUSTOM = "__custom__"
OFF = "off"

NOT_TTY = (
    "Cloud setup needs an interactive terminal.\n"
    "Run `tts cloud setup` in a terminal, or set values directly:\n"
    "  tts backend cloud\n"
    "  tts cloud provider openai\n"
    "  tts cloud env YOUR_API_KEY_VAR"
)

AZURE_REGIONS = (
    "eastus",
    "eastus2",
    "westus",
    "westus2",
    "westus3",
    "centralus",
    "northeurope",
    "westeurope",
    "uksouth",
    "southeastasia",
    "eastasia",
    "japaneast",
    "australiaeast",
    "canadacentral",
)

SelectFn = Callable[..., str]
PromptFn = Callable[..., str]
Choice = Tuple[str, str]


def _is_interactive() -> bool:
    return bool(
        getattr(sys.stdin, "isatty", lambda: False)()
        and getattr(sys.stdout, "isatty", lambda: False)()
    )


def _mark_env(name: str) -> str:
    state = "set" if os.environ.get(name) else "unset"
    return f"{name}  [{state}]"


def env_choices(provider: str) -> List[Choice]:
    """Provider default plus a prompt for any other name. Do not list env vars."""
    default = DEFAULT_API_KEY_ENV.get(provider) or "API_KEY"
    return [
        (default, f"{_mark_env(default)}  (provider default)"),
        (CUSTOM, "Type a custom name…"),
    ]


def apply_setup(
    *,
    provider: Optional[str],
    api_key_env: Optional[str] = None,
    region: Optional[str] = None,
) -> str:
    """Persist wizard results. ``provider=None`` turns cloud voices off."""
    if not provider or provider == OFF:
        config.set_values(backend="auto")
        return "Cloud voices disabled. Backend set to auto (OS voice)."

    config.set_values(backend="cloud")
    updates = {"provider": provider}
    if api_key_env:
        updates["api_key_env"] = api_key_env
    if region:
        updates["region"] = region
    config.set_cloud_values(**updates)

    cloud = config.load_config()["cloud"]
    env_name = api_key_env_name(provider, cloud)
    lines = [
        "Cloud voices enabled.",
        f"  provider: {provider}",
        f"  api key env: {env_name}",
    ]
    if env_name and os.environ.get(env_name):
        lines.append(f"  {env_name}: set")
    else:
        lines.append(f"  warning: {env_name} is not set in this environment.")
        lines.append(f"  export {env_name}=<your-key>")
    if provider == "azure":
        lines.append(f"  region: {cloud.get('region') or '(required)'}")
    voice = cloud.get("voice") or "(provider default)"
    lines.append(f"  voice: {voice}")
    lines.append("Change voice later with: tts cloud voice <id>")
    return "\n".join(lines)


def _provider_choices() -> List[Choice]:
    return [
        (OFF, "Off — use OS voice (disable cloud)"),
        ("elevenlabs", "ElevenLabs"),
        ("openai", "OpenAI"),
        ("azure", "Azure Speech"),
    ]


def _current_provider_id(cfg: dict) -> str:
    if cfg.get("backend") != "cloud":
        return OFF
    provider = (cfg.get("cloud") or {}).get("provider") or "elevenlabs"
    return provider if provider in DEFAULT_API_KEY_ENV else OFF


def _ask_custom_env(prompt: PromptFn) -> Optional[str]:
    name = prompt("Env var name: ")
    if not name:
        return None
    if not valid_env_name(name):
        sys.stderr.write(
            f"Invalid env var name {name!r}. "
            "Use letters, digits, and underscores.\n"
        )
        return None
    return name


def _ask_custom_region(prompt: PromptFn) -> Optional[str]:
    name = prompt("Azure region (e.g. eastus): ")
    if not name:
        return None
    if not re.fullmatch(r"[A-Za-z0-9-]+", name):
        sys.stderr.write(f"Invalid Azure region {name!r}.\n")
        return None
    return name.lower()


def run_wizard(
    *,
    select: Optional[SelectFn] = None,
    prompt: Optional[PromptFn] = None,
) -> str:
    """Run the setup wizard. Returns a one-block summary string."""
    select_fn = select or radio_select
    prompt_fn = prompt or prompt_line
    if select is None and not _is_interactive():
        return NOT_TTY

    cfg = config.load_config()
    cloud = cfg.get("cloud") or {}
    draft_provider = _current_provider_id(cfg)
    draft_env = cloud.get("api_key_env") or None
    draft_region = cloud.get("region") or None
    step = "provider"

    while True:
        if step == "provider":
            picked = select_fn(
                "Cloud voice setup\nWhich provider?",
                _provider_choices(),
                selected_id=draft_provider,
                allow_back=True,
            )
            if picked in (EXIT, BACK):
                return "Cloud setup cancelled."
            draft_provider = picked
            if picked == OFF:
                return apply_setup(provider=None)
            defaults = set(DEFAULT_API_KEY_ENV.values())
            if not draft_env or draft_env in defaults:
                draft_env = DEFAULT_API_KEY_ENV.get(picked)
            step = "env"
            continue

        if step == "env":
            choices = env_choices(draft_provider)
            default = DEFAULT_API_KEY_ENV.get(draft_provider)
            selected = default if (not draft_env or draft_env == default) else CUSTOM
            picked = select_fn(
                "Cloud voice setup\nWhich environment variable holds the API key?",
                choices,
                selected_id=selected,
                allow_back=True,
            )
            if picked == EXIT:
                return "Cloud setup cancelled."
            if picked == BACK:
                step = "provider"
                continue
            if picked == CUSTOM:
                name = _ask_custom_env(prompt_fn)
                if not name:
                    continue
                draft_env = name
            else:
                draft_env = picked
            step = "region" if draft_provider == "azure" else "done"
            continue

        if step == "region":
            rows: List[Choice] = [(r, r) for r in AZURE_REGIONS]
            if draft_region and draft_region not in AZURE_REGIONS:
                rows.insert(0, (draft_region, f"{draft_region}  (current)"))
            rows.append((CUSTOM, "Type a custom region…"))
            selected = draft_region if any(c[0] == draft_region for c in rows) else "eastus"
            picked = select_fn(
                "Cloud voice setup\nAzure region?",
                rows,
                selected_id=selected,
                allow_back=True,
            )
            if picked == EXIT:
                return "Cloud setup cancelled."
            if picked == BACK:
                step = "env"
                continue
            if picked == CUSTOM:
                name = _ask_custom_region(prompt_fn)
                if not name:
                    continue
                draft_region = name
            else:
                draft_region = picked
            step = "done"
            continue

        if step == "done":
            return apply_setup(
                provider=draft_provider,
                api_key_env=draft_env,
                region=draft_region if draft_provider == "azure" else None,
            )
