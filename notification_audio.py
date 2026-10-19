"""Configurable notification audio shared by focus and tray notifications."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

try:
    from playsound import playsound as _playsound
except ImportError:
    _playsound = None

_BASE_DIR = Path(__file__).resolve().parent
_DEFAULT_SOUND = _BASE_DIR / "audio.mp3"
_player: QMediaPlayer | None = None
_audio: QAudioOutput | None = None
_preview_timer: QTimer | None = None
_backend = None


def set_backend(backend) -> None:
    global _backend
    _backend = backend


def _setting(key: str, fallback):
    if _backend is None:
        return fallback
    try:
        return _backend.getSetting(key, fallback)
    except Exception:
        return fallback


def resolve_sound_path() -> Path:
    configured = str(_setting("notificationSoundPath", "") or "").strip()
    candidate = Path(configured) if configured else _DEFAULT_SOUND
    if candidate.is_file():
        return candidate
    return _DEFAULT_SOUND


def _volume() -> float:
    try:
        return max(0.0, min(1.0, float(_setting("notificationSoundVolume", 0.8))))
    except (TypeError, ValueError):
        return 0.8


def is_enabled() -> bool:
    value = _setting("notificationSoundEnabled", True)
    return bool(value)


def play_notification_sound(force: bool = False) -> bool:
    """Play the configured sound without allowing audio errors to break notifications."""
    global _player, _audio
    if not force and not is_enabled():
        return False
    sound_path = resolve_sound_path()
    if not sound_path.is_file():
        return False
    volume = _volume()
    try:
        if _audio is None:
            _audio = QAudioOutput()
            _player = QMediaPlayer()
            _player.setAudioOutput(_audio)
        _audio.setVolume(volume)
        _player.setSource(QUrl.fromLocalFile(str(sound_path)))
        _player.play()
        return True
    except Exception as exc:
        # playsound has no volume API, so it is intentionally only a fallback.
        if _playsound is not None:
            try:
                _playsound(str(sound_path), block=False)
                return True
            except Exception:
                pass
        print(f"[Audio] notification sound failed: {exc}")
        return False


def preview(duration_ms: int = 4000) -> bool:
    """Preview the sound briefly, then stop playback automatically."""
    global _preview_timer
    if not play_notification_sound(force=True):
        return False
    if _player is None:
        return True
    if _preview_timer is None:
        _preview_timer = QTimer()
        _preview_timer.setSingleShot(True)
        _preview_timer.timeout.connect(_player.stop)
    _preview_timer.start(max(500, min(10000, int(duration_ms))))
    return True
