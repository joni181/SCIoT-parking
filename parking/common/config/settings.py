"""Runtime configuration - where the broker lives and who this node is.

Resolution order (later wins):

  1. built-in defaults (localhost:1883)
  2. config/config.yaml          <- the normal knob; copy from config.example.yaml
  3. environment variables       <- handy one-off overrides (PARKING_BROKER_*)

So in everyday use you set the broker IP/port once in config/config.yaml. The
same `Settings` is read identically by both nodes; only the values differ.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


@dataclass
class Settings:
    broker_host: str = "localhost"
    broker_port: int = 1883
    node_name: str = "node"  # free-form label used in client ids / log lines
    parking_spots: Tuple[str, ...] = ("P1", "P2", "P3")
    buffer_spots: Tuple[str, ...] = ("B1",)
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8050
    dashboard_open_browser: bool = True


def _as_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("0", "false", "no", "off")


def _repo_root() -> Path:
    # parking/common/config/settings.py -> repo root is four levels up.
    return Path(__file__).resolve().parents[3]


def _default_config_path() -> Optional[Path]:
    env = os.environ.get("PARKING_CONFIG")
    if env:
        return Path(env)
    candidate = _repo_root() / "config" / "config.yaml"
    return candidate if candidate.exists() else None


def _apply_yaml(base: Settings, path: Path) -> Settings:
    import yaml  # lazy: only needed when a config file is actually present

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Settings(
        broker_host=raw.get("broker_host", base.broker_host),
        broker_port=int(raw.get("broker_port", base.broker_port)),
        node_name=raw.get("node_name", base.node_name),
        parking_spots=tuple(raw.get("parking_spots", base.parking_spots)),
        buffer_spots=tuple(raw.get("buffer_spots", base.buffer_spots)),
        dashboard_host=raw.get("dashboard_host", base.dashboard_host),
        dashboard_port=int(raw.get("dashboard_port", base.dashboard_port)),
        dashboard_open_browser=_as_bool(raw.get("dashboard_open_browser"), base.dashboard_open_browser),
    )


def _apply_env(base: Settings) -> Settings:
    parking_spots = os.environ.get("PARKING_SPOTS")
    buffer_spots = os.environ.get("PARKING_BUFFER_SPOTS")
    return Settings(
        broker_host=os.environ.get("PARKING_BROKER_HOST", base.broker_host),
        broker_port=int(os.environ.get("PARKING_BROKER_PORT", base.broker_port)),
        node_name=os.environ.get("PARKING_NODE_NAME", base.node_name),
        parking_spots=tuple(parking_spots.split(",")) if parking_spots else base.parking_spots,
        buffer_spots=tuple(buffer_spots.split(",")) if buffer_spots else base.buffer_spots,
        dashboard_host=os.environ.get("PARKING_DASHBOARD_HOST", base.dashboard_host),
        dashboard_port=int(os.environ.get("PARKING_DASHBOARD_PORT", base.dashboard_port)),
        dashboard_open_browser=_as_bool(
            os.environ.get("PARKING_DASHBOARD_OPEN_BROWSER"), base.dashboard_open_browser
        ),
    )


def load_settings(path: Optional[str] = None) -> Settings:
    """Build Settings from defaults, then config.yaml, then environment."""
    settings = Settings()
    cfg = Path(path) if path else _default_config_path()
    if cfg and cfg.exists():
        settings = _apply_yaml(settings, cfg)
    return _apply_env(settings)


# Backwards-compatible alias.
def load_settings_from_yaml(path: str) -> Settings:
    return load_settings(path)
