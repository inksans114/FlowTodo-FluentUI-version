"""Desktop note windows inspired by PaperTodo's paper/capsule model.

The model deliberately keeps ordinary paper geometry separate from the folded
capsule presentation.  A note remains a note while folded; only its window
presentation changes and the full content is restored on expand.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtQml import QQmlComponent


class NoteManager(QObject):
    CAPSULE_WIDTH = 128
    CAPSULE_HEIGHT = 52
    notesChanged = Signal()
    visibilityChanged = Signal()
    messageRequested = Signal(str, str, str)

    def __init__(self, backend: QObject):
        super().__init__(backend)
        self.backend = backend
        self.data_dir = Path(getattr(backend, "data_dir", Path.cwd()))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.notes_file = self.data_dir / "notes.json"
        self.notes: list[dict[str, Any]] = self._load()
        self._engine = None
        self._component = None
        self._windows: dict[str, QObject] = {}

    def _defaults(self) -> dict[str, Any]:
        return {
            "version": 1,
            "notes": [],
            "settings": {
                "notesEnabled": True,
                "notesAutoShow": False,
                "notesDefaultWidth": 320,
                "notesDefaultHeight": 360,
                "notesAlwaysOnTop": False,
                "notesOpacity": 0.96,
                "notesEdgeDock": True,
                "notesCapsuleGap": 6,
                "notesCapsuleSide": "right",
                "notesRememberPosition": True,
            },
        }

    def _load(self) -> list[dict[str, Any]]:
        if not self.notes_file.exists():
            return []
        try:
            payload = json.loads(self.notes_file.read_text(encoding="utf-8"))
            values = payload.get("notes", payload) if isinstance(payload, dict) else payload
            return [self._normalize(item) for item in values if isinstance(item, dict)]
        except (OSError, ValueError, TypeError):
            return []

    def _normalize(self, source: dict[str, Any]) -> dict[str, Any]:
        note = dict(source)
        note["id"] = str(note.get("id") or uuid.uuid4().hex)
        note["title"] = str(note.get("title") or "未命名便签")
        note["content"] = str(note.get("content") or "")
        note["x"] = self._number(note.get("x"), 120)
        note["y"] = self._number(note.get("y"), 120)
        note["width"] = max(220, self._number(note.get("width"), 320))
        note["height"] = max(180, self._number(note.get("height"), 360))
        note["visible"] = bool(note.get("visible", True))
        note["alwaysOnTop"] = bool(note.get("alwaysOnTop", False))
        note["collapsed"] = bool(note.get("collapsed", False))
        note["capsuleSide"] = "left" if note.get("capsuleSide") == "left" else "right"
        note["capsuleMonitor"] = str(note.get("capsuleMonitor") or "")
        expanded = note.get("expanded") if isinstance(note.get("expanded"), dict) else {}
        note["expanded"] = {
            "x": self._number(expanded.get("x"), note["x"]),
            "y": self._number(expanded.get("y"), note["y"]),
            "width": max(220, self._number(expanded.get("width"), note["width"])),
            "height": max(180, self._number(expanded.get("height"), note["height"])),
        }
        return note

    @staticmethod
    def _number(value: Any, fallback: float) -> float:
        try:
            result = float(value)
            return result if result == result and abs(result) != float("inf") else fallback
        except (TypeError, ValueError):
            return fallback

    def _save(self) -> None:
        payload = {"version": 1, "notes": self.notes}
        temporary = self.notes_file.with_suffix(".json.tmp")
        try:
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, self.notes_file)
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def attach_engine(self, engine) -> None:
        self._engine = engine
        self._component = QQmlComponent(engine, QUrl.fromLocalFile(str(Path(__file__).parent / "qml" / "notes" / "NotePaper.qml")))
        if self._component.isError():
            for error in self._component.errors():
                print(f"[Notes] QML component error: {error}")

    def restore_visible_notes(self) -> None:
        if bool(self._settings().get("notesAutoShow", False)):
            self._sync_windows()

    @Slot()
    def refresh_settings(self) -> None:
        self._arrange_capsules()

    def _note(self, note_id: str) -> dict[str, Any] | None:
        return next((item for item in self.notes if item["id"] == str(note_id)), None)

    def _create_window(self, note: dict[str, Any]) -> QObject | None:
        if not self._component or self._component.status() == QQmlComponent.Status.Error:
            return None
        window = self._component.create()
        if window is None:
            return None
        window.setProperty("noteId", note["id"])
        window.setProperty("noteTitle", note["title"])
        window.setProperty("noteContent", note["content"])
        window.setProperty("collapsed", note["collapsed"])
        window.setProperty("alwaysOnTop", note["alwaysOnTop"])
        window.setProperty("paperX", note["x"])
        window.setProperty("paperY", note["y"])
        window.setProperty("paperWidth", note["width"])
        window.setProperty("paperHeight", note["height"])
        window.noteEdited.connect(self._on_note_edited)
        window.geometryCommitted.connect(self._on_geometry_committed)
        window.collapseRequested.connect(self.toggleCollapse)
        window.deleteRequested.connect(self.deleteNote)
        window.hideRequested.connect(self.hideNote)
        window.showRequested.connect(self.showNote)
        window.show()
        self._windows[note["id"]] = window
        self._apply_presentation(note)
        return window

    def _apply_presentation(self, note: dict[str, Any]) -> None:
        window = self._windows.get(note["id"])
        if window is None:
            return
        if note["collapsed"]:
            # Keep the remembered paper geometry intact while forcing the
            # native window itself to the small capsule dimensions.
            window.setProperty("paperWidth", note["width"])
            window.setProperty("paperHeight", note["height"])
            window.setProperty("collapsed", True)
            window.setProperty("width", self.CAPSULE_WIDTH)
            window.setProperty("height", self.CAPSULE_HEIGHT)
        else:
            window.setProperty("collapsed", False)
            window.setProperty("paperX", note["x"])
            window.setProperty("paperY", note["y"])
            window.setProperty("paperWidth", note["width"])
            window.setProperty("paperHeight", note["height"])
            window.setProperty("width", note["width"])
            window.setProperty("height", note["height"])
        window.setProperty("noteTitle", note["title"])
        window.setProperty("noteContent", note["content"])

    def _sync_windows(self) -> None:
        if not bool(self._settings().get("notesEnabled", True)):
            for window in self._windows.values():
                window.hide()
            return
        for note in self.notes:
            if note["visible"]:
                if note["id"] not in self._windows:
                    self._create_window(note)
                else:
                    self._apply_presentation(note)
            elif note["id"] in self._windows:
                self._windows[note["id"]].hide()
        self._arrange_capsules()

    def _arrange_capsules(self) -> None:
        settings = self._settings()
        if not bool(settings.get("notesEdgeDock", True)):
            return
        gap = max(0, int(self._number(settings.get("notesCapsuleGap"), 6)))
        for side in ("left", "right"):
            queue = [n for n in self.notes if n["visible"] and n["collapsed"] and n["capsuleSide"] == side]
            queue.sort(key=lambda n: (n.get("capsuleOrder", 0), n["id"]))
            y = 48
            for note in queue:
                window = self._windows.get(note["id"])
                if window is None:
                    continue
                window.setProperty("width", self.CAPSULE_WIDTH)
                window.setProperty("height", self.CAPSULE_HEIGHT)
                screen = window.screen()
                area = screen.availableGeometry() if screen else None
                if area is None:
                    continue
                x = area.left() if side == "left" else area.right() - self.CAPSULE_WIDTH + 1
                window.setProperty("paperX", x)
                window.setProperty("paperY", area.top() + y)
                y += self.CAPSULE_HEIGHT + gap

    def _settings(self) -> dict[str, Any]:
        defaults = self._defaults()["settings"]
        current = getattr(self.backend, "settings_database", {})
        return {**defaults, **{k: current[k] for k in defaults if k in current}}

    @Property(str, notify=notesChanged)
    def notesJson(self) -> str:
        return json.dumps(self.notes, ensure_ascii=False)

    @Property(int, notify=notesChanged)
    def count(self) -> int:
        return len(self.notes)

    @Slot(result=str)
    def listNotes(self) -> str:
        return self.notesJson

    @Slot(result=str)
    def createNote(self) -> str:
        settings = self._settings()
        note = self._normalize({
            "title": "新便签",
            "content": "",
            "width": settings["notesDefaultWidth"],
            "height": settings["notesDefaultHeight"],
            "alwaysOnTop": settings["notesAlwaysOnTop"],
            "capsuleSide": settings["notesCapsuleSide"],
        })
        self.notes.append(note)
        self._save()
        self._sync_windows()
        self.notesChanged.emit()
        return note["id"]

    @Slot(str)
    def showNote(self, note_id: str) -> None:
        if not bool(self._settings().get("notesEnabled", True)):
            return
        note = self._note(note_id)
        if not note:
            return
        note["visible"] = True
        self._sync_windows()
        self._save()
        self.visibilityChanged.emit()

    @Slot(str)
    def hideNote(self, note_id: str) -> None:
        note = self._note(note_id)
        if not note:
            return
        note["visible"] = False
        window = self._windows.get(note["id"])
        if window:
            window.hide()
        self._save()
        self.visibilityChanged.emit()

    @Slot(str)
    def toggleCollapse(self, note_id: str) -> None:
        note = self._note(note_id)
        if not note:
            return
        if note["collapsed"]:
            note["collapsed"] = False
            expanded = note.get("expanded", {})
            note["x"], note["y"] = expanded.get("x", note["x"]), expanded.get("y", note["y"])
            note["width"], note["height"] = expanded.get("width", note["width"]), expanded.get("height", note["height"])
        else:
            note["expanded"] = {"x": note["x"], "y": note["y"], "width": note["width"], "height": note["height"]}
            note["collapsed"] = True
        self._save()
        self._sync_windows()
        self.notesChanged.emit()

    @Slot(str)
    def deleteNote(self, note_id: str) -> None:
        note_id = str(note_id)
        window = self._windows.pop(note_id, None)
        if window:
            window.close()
            window.deleteLater()
        self.notes = [note for note in self.notes if note["id"] != note_id]
        self._save()
        self.notesChanged.emit()

    @Slot(str)
    def openNote(self, note_id: str) -> None:
        note = self._note(note_id)
        if not note:
            return
        if note["collapsed"]:
            self.toggleCollapse(note_id)
        self.showNote(note_id)

    @Slot(str, bool)
    def setAlwaysOnTop(self, note_id: str, enabled: bool) -> None:
        note = self._note(note_id)
        if not note:
            return
        note["alwaysOnTop"] = bool(enabled)
        window = self._windows.get(note_id)
        if window:
            window.setProperty("alwaysOnTop", note["alwaysOnTop"])
            window.show()
        self._save()
        self.notesChanged.emit()

    @Slot(str, str)
    def setCapsuleSide(self, note_id: str, side: str) -> None:
        note = self._note(note_id)
        if not note:
            return
        note["capsuleSide"] = "left" if str(side).lower() == "left" else "right"
        self._save()
        self._arrange_capsules()
        self.notesChanged.emit()

    @Slot()
    def showAll(self) -> None:
        if not bool(self._settings().get("notesEnabled", True)):
            return
        for note in self.notes:
            note["visible"] = True
        self._sync_windows()
        self._save()
        self.visibilityChanged.emit()

    @Slot()
    def hideAll(self) -> None:
        for note in self.notes:
            note["visible"] = False
        for window in self._windows.values():
            window.hide()
        self._save()
        self.visibilityChanged.emit()

    @Slot()
    def clear_all(self) -> None:
        """Close note windows and remove every locally stored note."""
        for window in list(self._windows.values()):
            try:
                window.close()
            except RuntimeError:
                pass
            try:
                window.deleteLater()
            except RuntimeError:
                pass
        self._windows.clear()
        self.notes = []
        self._save()
        self.notesChanged.emit()
        self.visibilityChanged.emit()

    @Slot(str, str, str)
    def _on_note_edited(self, note_id: str, title: str, content: str) -> None:
        note = self._note(note_id)
        if not note:
            return
        note["title"] = str(title or "未命名便签")
        note["content"] = str(content or "")
        self._save()
        self.notesChanged.emit()

    @Slot(str, float, float, float, float)
    def _on_geometry_committed(self, note_id: str, x: float, y: float, width: float, height: float) -> None:
        note = self._note(note_id)
        if not note:
            return
        if note["collapsed"]:
            note["capsuleSide"] = "left" if x < 200 else "right"
        else:
            note.update({"x": x, "y": y, "width": max(220, width), "height": max(180, height)})
            note["expanded"] = {"x": x, "y": y, "width": width, "height": height}
        self._save()
        self._arrange_capsules()

    @Slot()
    def showNotes(self) -> None:
        self.showAll()

    @Slot()
    def hideNotes(self) -> None:
        self.hideAll()
