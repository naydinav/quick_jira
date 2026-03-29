"""
QuickJira Tray – lightning-fast Jira task entry from the system tray.

Features
- Tray icon app (Windows-friendly, cross‑platform) built with PySide6.
- Quick input window: type multiple lines, each line is one task.
  Syntax (inspired by MyLifeOrganized Quick Input):
    Summary text @prj <project> @type <issuetype> @asg <assignee|me> @due <natural date>
  Examples:
    Новая задача для работы @prj myproject @type issue @asg me @due next week
    Fix crash on boot @prj MOBILE @type Bug @asg ivanov @due 2025-09-01

- Ctrl+Enter: parse all lines → review table → edit if needed → Create in Jira.
- Smart parsing:
    • @prj fuzzy‑matches Jira projects by key or name (best match is used).
    • @type picks best‑matching issue type (project‑aware when possible).
    • @asg "me" => current user; otherwise searches users by display/displayName/email.
    • @due accepts dates and natural language (via dateparser), stored as YYYY‑MM‑DD.

- Settings dialog: Jira URL, email/username, API token, defaults. Saved at:
    Windows: %APPDATA%/QuickJira/config.json

Dependencies (install once):
    pip install -r requirements.txt

Tested with Python 3.10+.
"""
from __future__ import annotations
import dateparser
from rapidfuzz import fuzz, process as rfprocess

from pathlib import Path
import json
import os
import sys
import base64
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from html import escape
from datetime import date, timedelta
import re

from appdirs import user_config_dir, user_cache_dir
from PySide6.QtCore import Qt, QEvent, QSize, QDate, QObject, QThread, Signal, QPoint, QTimer, QPoint, QAbstractNativeEventFilter
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPainter, QPixmap, QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QDateEdit,
    QScrollArea,
    QFrame,
    QCheckBox,
    QTabWidget,
)

try:
    import yaml
except ImportError:
    yaml = None


# Fuzzy matching

# Natural language dates

# Lazy Jira import in JiraClient to keep module import time low

APP_NAME = "QuickJira"
APP_VERSION = "1.1"
CONFIG_NAME = "config.json"

APP_ICON_B64 = (
    "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"
)


DEFAULT_UI_TEXT = {
    "en": {

        # ---- MainWindow ----
        "main_title": "QuickJira – Quick task entry",

        "main_placeholder": (
            "Enter one task per line.\n"
            "Example:\n"
            "New task for work @prj naidzin @type issue @asg me @due next week\n\n"
            "Supported tags: @prj/@project, @type, @asg/@assignee, @due"
        ),
        "main_placeholder_single": (
            "Enter one task in free form.\n"
            "First line — summary.  Remaining lines — description (newlines preserved).\n"
            "Tags (@prj, @type, @asg, @due) can appear on any line.\n\n"
            "Example:\n"
            "Fix crash on login\n"
            "  Steps to reproduce:\n"
            "  1. Open the app and wait 30 min\n"
            "  2. Try to log in\n"
            "  @prj MOBILE @type Bug @asg me @due next week"
        ),

        "main_parse": "Parse  [Ctrl+Enter]",
        "main_settings": "Settings...",
        "main_cancel": "Cancel",
        "main_multi_task": "Multiple task entry (1 task per line)",

        # ---- ReviewDialog ----
        "review_title": "Review tasks",
        "review_create": "Create in Jira  [Ctrl+Enter]",
        "review_cancel": "Cancel  [Esc]",
        "review_add_to_jira": "Add to Jira",
        "review_project": "Project",
        "review_type": "Type",
        "review_assignee": "Assignee",
        "review_estimate": "Estimate",
        "review_due": "Due",
        "review_labels": "Labels",
        "review_status_after_create": "Status after create",

        # ---- messages ----
        "msg_empty_title": "Empty",
        "msg_empty_text": "Enter at least one line.",

        "msg_parse_failed_title": "Parse failed",
        "msg_parse_failed_text": "Check the line format.",

        "msg_no_settings_title": "No settings",
        "msg_no_settings_text": "Fill Jira settings before creating issues.",

        # ---- result dialog ----
        "result_title": "Result",
        "result_created": "Created:",
        "result_errors": "Errors:",
        "result_no_actions": "No actions",

        # ---- SettingsDialog ----
        "settings_title": "QuickJira – Settings",

        "jira_url": "Jira URL:",
        "user": "User (email/login):",
        "token": "API Token:",
        "default_project": "Default project:",
        "default_issue_type": "Default issue type:",
        "default_assignee": "Default assignee:",
        "default_due_workdays": "Default workdays (@due):",
        "default_estimate": "Default estimate:",
        "language": "Language:",

        "settings_tab_task": "Task settings",
        "settings_tab_app": "Application settings",
        "settings_default_labels": "Default labels:",
        "settings_default_status": "Default status:",
        "settings_stay_on_top": "Stay on top:",
        "settings_inactivity_transparency": "Inactivity transparency:",
        "settings_global_hotkey": "Global hotkey:",
        "settings_hotkey_enable": "Enable global hotkey",
        "settings_hotkey_shortcut": "Shortcut:",
        "settings_autostart": "Run at Windows startup",

        "check_connection": "Check connection",
        "save": "Save",
        "cancel": "Cancel",

        "connection_fill_required": "Fill Jira URL, User and API Token first.",

        "connection_ok_title": "Connection OK",
        "connection_ok_message": "Connected successfully.\nUser: {user}",

        "connection_failed_title": "Connection failed",

        # ---- TrayApp ----
        "tray_tooltip": "QuickJira – quick Jira entry",
        "tray_open": "Open input…",
        "tray_settings": "Settings…",
        "tray_history": "Task history…",
        "tray_about": "About…",
        "tray_quit": "Quit",

        # ---- TaskHistoryDialog ----
        "history_title": "Created task history",
        "history_empty": "No tasks created in the last 30 days.",
        "history_close": "Close",

        # ---- About dialog ----
        "about_title": f"About QuickJira v{APP_VERSION}",
        "about_text": (
            f"QuickJira v{APP_VERSION}\n\n"
            "QuickJira is a lightweight Windows system-tray app for creating "
            "Jira issues at lightning speed.\n\n"
            "Type one task per line (or a multi-line single task), attach inline "
            "tags, review the parsed result, and bulk-create everything in Jira — "
            "without ever opening a browser."
        ),
    }
}

# Per-language tag definitions: primary token, all aliases, UI description
DEFAULT_TAG_DEFINITIONS: Dict[str, Dict[str, dict]] = {
    "en": {
        "project":  {"primary": "prj",    "aliases": ["prj", "project"],          "description": "set project"},
        "type":     {"primary": "type",   "aliases": ["type", "issue"],           "description": "set issue type"},
        "assignee": {"primary": "asg",    "aliases": ["asg", "assignee"],         "description": "set assignee"},
        "due":      {"primary": "due",    "aliases": ["due"],                     "description": "set due date"},
        "estimate": {"primary": "est",    "aliases": ["est", "estimate"],         "description": "set estimate"},
        "label":    {"primary": "label",  "aliases": ["label", "labels", "lbl"], "description": "set labels"},
        "status":   {"primary": "status", "aliases": ["status"],                 "description": "set status after create"},
    },
    "ru": {
        "project":  {"primary": "проект", "aliases": ["проект", "про"],           "description": "указать проект"},
        "type":     {"primary": "тип",    "aliases": ["тип"],                    "description": "тип задачи"},
        "assignee": {"primary": "исп",    "aliases": ["исп", "на"],              "description": "исполнитель"},
        "due":      {"primary": "срок",   "aliases": ["срок", "когда"],          "description": "срок выполнения"},
        "estimate": {"primary": "оценка", "aliases": ["оценка"],                 "description": "оценка времени"},
        "label":    {"primary": "метка",  "aliases": ["метка", "метки"],         "description": "метки"},
        "status":   {"primary": "статус", "aliases": ["статус"],                 "description": "статус после создания"},
    },
}


def translations_file_path() -> Path:
    return Path(__file__).resolve().parent / "translations.yaml"


def _cache_file_path() -> Path:
    cache_dir = user_cache_dir(APP_NAME)
    os.makedirs(cache_dir, exist_ok=True)
    return Path(cache_dir) / "cache.json"


def ensure_translations_file():
    path = translations_file_path()

    if yaml is None:
        return

    if path.exists():
        return

    data = {
        "default_language": "en",
        "languages": sorted(DEFAULT_UI_TEXT.keys()),
        "translations": DEFAULT_UI_TEXT,
        "tags": DEFAULT_TAG_DEFINITIONS,
    }

    try:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                data,
                f,
                allow_unicode=True,
                sort_keys=False,
            )
        print(f"Created default translations file: {path}")
    except Exception as e:
        print(f"Failed to create translations file: {e}")


def load_translations() -> dict:
    data = {
        "default_language": "en",
        "languages": ["en"],
        "translations": DEFAULT_UI_TEXT.copy(),
    }

    path = translations_file_path()

    if yaml is None:
        print("YAML library not available, using defaults.")
        return data

    if not path.exists():
        ensure_translations_file()

    if not path.exists():
        print("translations.yaml not found, using defaults.")
        return data

    try:
        print(f"Loading translations from: {path}")
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        translations = raw.get("translations", {})
        languages = raw.get("languages")
        default_lang = raw.get("default_language", "en")

        merged = {}
        for lang, values in DEFAULT_UI_TEXT.items():
            merged[lang] = dict(values)

        for lang, values in translations.items():
            base = dict(DEFAULT_UI_TEXT.get("en", {}))
            if lang in merged:
                base.update(merged[lang])
            if isinstance(values, dict):
                base.update(values)
            merged[lang] = base

        if not languages:
            languages = sorted(merged.keys())

        if default_lang not in merged:
            default_lang = "en"

        print("Available translations:", languages)

        return {
            "default_language": default_lang,
            "languages": languages,
            "translations": merged,
        }

    except Exception as e:
        print(f"Failed to load translations: {e}")
        return data


TRANSLATION_DATA = load_translations()


def load_tag_definitions() -> Dict[str, Dict[str, dict]]:
    """Load tag definitions from translations.yaml (tags: section), merging with defaults."""
    result: Dict[str, Dict[str, dict]] = {}
    for lang, families in DEFAULT_TAG_DEFINITIONS.items():
        result[lang] = {f: dict(v) for f, v in families.items()}

    if yaml is None:
        return result

    path = translations_file_path()
    if not path.exists():
        return result

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        for lang, families in raw.get("tags", {}).items():
            if not isinstance(families, dict):
                continue
            if lang not in result:
                result[lang] = {
                    f: dict(v) for f, v in DEFAULT_TAG_DEFINITIONS.get("en", {}).items()}
            for family, defn in families.items():
                if not isinstance(defn, dict):
                    continue
                entry = result[lang].setdefault(family, {})
                if "primary" in defn:
                    entry["primary"] = defn["primary"]
                if "aliases" in defn and isinstance(defn["aliases"], list):
                    entry["aliases"] = defn["aliases"]
                if "description" in defn:
                    entry["description"] = defn["description"]
    except Exception as e:
        print(f"Failed to load tag definitions: {e}")

    return result


TAG_DEFINITIONS = load_tag_definitions()


def supported_languages() -> list[str]:
    return list(TRANSLATION_DATA.get("languages", ["en"]))


def default_language() -> str:
    return TRANSLATION_DATA.get("default_language", "en")


def tr(lang: str, key: str) -> str:

    translations = TRANSLATION_DATA.get("translations", {})
    lang_map = translations.get(lang) or translations.get("en", {})
    return lang_map.get(key, key)


_TAG_FAMILIES = ("project", "type", "assignee",
                 "due", "estimate", "label", "status")

# Base English aliases that are always recognized regardless of language settings
_BASE_ALIASES: Dict[str, set] = {
    "project":  {"prj", "project"},
    "type":     {"type", "issue"},
    "assignee": {"asg", "assignee"},
    "due":      {"due"},
    "estimate": {"est", "estimate"},
    "label":    {"label", "labels", "lbl"},
    "status":   {"status"},
}


def _build_supported_tags() -> Dict[str, set]:
    """Build SUPPORTED_TAGS from all language tag definitions + base English aliases."""
    result: Dict[str, set] = {f: set(v) for f, v in _BASE_ALIASES.items()}
    for lang_defs in TAG_DEFINITIONS.values():
        for family, defn in lang_defs.items():
            result.setdefault(family, set())
            for alias in defn.get("aliases", []):
                result[family].add(alias.lower())
    return result


SUPPORTED_TAGS = _build_supported_tags()
DEFAULT_LANGUAGES = ['ru', 'en']


def _build_tag_pattern(family: str) -> str:
    """Regex alternation pattern matching any alias of a tag family."""
    aliases = sorted(SUPPORTED_TAGS.get(family, set()), key=len, reverse=True)
    return r'@(' + '|'.join(re.escape(a) for a in aliases) + r')\s+([^@]*)$'


TAG_PATTERNS: Dict[str, str] = {
    f: _build_tag_pattern(f) for f in SUPPORTED_TAGS}


def tag_completion_items(lang: str) -> List[str]:
    """Return language-aware tag completion list formatted as '<aliases> — description'."""
    lang_defs = TAG_DEFINITIONS.get(lang) or TAG_DEFINITIONS.get("en", {})
    items = []
    for family in _TAG_FAMILIES:
        defn = lang_defs.get(family, {})
        aliases = defn.get("aliases", None)
        if not aliases:
            # get primar
            aliases = defn.get("primary", None)
        if not aliases:
            continue
        if isinstance(aliases, str):
            aliases = [aliases]
        aliases_str = ", @".join(aliases)
        description = defn.get("description", "")
        if aliases_str:
            label = f"@{aliases_str}"
            if description:
                label = f"@{aliases_str} \u2014 {description}"
            items.append(label)
    return items


def tag_primary(lang: str, family: str) -> str:
    """Return the primary tag token (without @) for the given language and family."""
    lang_defs = TAG_DEFINITIONS.get(lang) or TAG_DEFINITIONS.get("en", {})
    return lang_defs.get(family, {}).get("primary", family)


ESTIMATE_SUGGESTIONS = [
    "30m",
    "1h",
    "2h",
    "4h",
    "1d",
    "2d",
    "1w",
]

DUE_SUGGESTIONS = [
    "today",
    "tomorrow",
    "next week",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

# --------------------------- Config ---------------------------
DEFAULT_ESTIMATE = "1h"


@dataclass
class AppConfig:
    """All user-configurable settings persisted to JSON.

    Serialized to/from ``%APPDATA%/QuickJira/config.json`` via
    :class:`ConfigManager`.  New fields with defaults are backwards-compatible
    because ``ConfigManager.load`` merges the JSON dict into a fresh dataclass.
    """

    jira_url: str = ""
    jira_user: str = ""
    jira_token: str = ""
    default_project: str = ""
    default_issue_type: str = "Task"
    default_assignee: str = "me"
    default_due_workdays: int = 3
    language: str = default_language()
    default_estimate: str = DEFAULT_ESTIMATE
    default_labels: str = ""
    default_status: str = ""
    stay_on_top: bool = False
    inactivity_transparency: int = 30
    global_hotkey_enabled: bool = False
    global_hotkey: str = "Alt+Shift+M"
    multi_task_mode: bool = True
    autostart: bool = False
    main_window_geometry: str = ""

    def is_complete(self) -> bool:
        return bool(self.jira_url and self.jira_user and self.jira_token)


class ConfigManager:
    """Loads and saves :class:`AppConfig` as JSON on disk.

    The config file location is platform-aware (via *appdirs*):

    * **Windows** – ``%APPDATA%\\QuickJira\\config.json``
    * **macOS**   – ``~/Library/Application Support/QuickJira/config.json``
    * **Linux**   – ``~/.config/QuickJira/config.json``
    """

    def __init__(self):
        cfg_dir = user_config_dir(APP_NAME, roaming=True)
        os.makedirs(cfg_dir, exist_ok=True)
        self.path = os.path.join(cfg_dir, CONFIG_NAME)
        self.config = AppConfig()
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.config = AppConfig(**{**AppConfig().__dict__, **data})
            except Exception:
                pass

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.config.__dict__, f, ensure_ascii=False, indent=2)


# --------------------------- Global Hotkey (Windows) ---------------------------

_HOTKEY_ID = 9001
MOD_ALT = 0x0001
MOD_CTRL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

try:
    import ctypes
    import ctypes.wintypes
    _ctypes_ok = sys.platform == "win32"
except Exception:
    _ctypes_ok = False


class GlobalHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, _, message):
        try:
            if _ctypes_ok:
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                    self._callback()
                    return True, 0
        except Exception:
            pass
        return False, 0


class HotkeyManager:
    def __init__(self):
        self._registered = False
        self._filter: Optional[GlobalHotkeyFilter] = None

    @staticmethod
    def _parse(hotkey_str: str):
        modifiers = 0
        vk = 0
        for part in hotkey_str.split("+"):
            p = part.strip().upper()
            if p == "ALT":
                modifiers |= MOD_ALT
            elif p in ("CTRL", "CONTROL"):
                modifiers |= MOD_CTRL
            elif p == "SHIFT":
                modifiers |= MOD_SHIFT
            elif p in ("WIN", "WINDOWS", "META"):
                modifiers |= MOD_WIN
            elif len(p) == 1:
                vk = ord(p)
        return modifiers, vk

    def register(self, app, hotkey_str: str, callback) -> bool:
        if not _ctypes_ok:
            return False
        self.unregister(app)
        modifiers, vk = self._parse(hotkey_str)
        if not vk:
            return False
        ok = bool(ctypes.windll.user32.RegisterHotKey(
            None, _HOTKEY_ID, modifiers | MOD_NOREPEAT, vk))
        if ok:
            self._registered = True
            self._filter = GlobalHotkeyFilter(callback)
            app.installNativeEventFilter(self._filter)
        return ok

    def unregister(self, app=None):
        if self._registered and _ctypes_ok:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, _HOTKEY_ID)
            except Exception:
                pass
            self._registered = False
        if app and self._filter:
            try:
                app.removeNativeEventFilter(self._filter)
            except Exception:
                pass
            self._filter = None


try:
    import winreg as _winreg
    _winreg_ok = True
except ImportError:
    _winreg_ok = False


def _set_autostart(enabled: bool, app_name: str = "QuickJira") -> bool:
    """Register or unregister the app in the Windows startup registry key.

    Uses ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``.
    When running as a compiled exe the exe path is used directly; when
    running from source the current Python interpreter + script path is used.
    Returns True on success, False if the operation failed (e.g. on non-Windows).
    """
    if not _winreg_ok:
        return False
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = _winreg.OpenKey(
            _winreg.HKEY_CURRENT_USER, key_path, 0, _winreg.KEY_SET_VALUE)
        if enabled:
            exe = sys.executable
            script = os.path.abspath(sys.argv[0])
            # If running as a PyInstaller bundle, sys.executable IS the exe
            if getattr(sys, "frozen", False):
                cmd = f'"{exe}"'
            else:
                # Running from source: use pythonw.exe so no console window
                pythonw = exe.replace("python.exe", "pythonw.exe")
                cmd = f'"{pythonw}" "{script}"'
            _winreg.SetValueEx(key, app_name, 0, _winreg.REG_SZ, cmd)
        else:
            try:
                _winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        _winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Autostart registry error: {e}")
        return False


class KeyCaptureEdit(QLineEdit):
    """Read-only field that captures a single keystroke on click."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._key = ""
        self.setReadOnly(True)
        self.setPlaceholderText("click…")
        self.setFixedWidth(52)
        self.setAlignment(Qt.AlignCenter)

    def key(self) -> str:
        return self._key

    def set_key(self, key: str):
        self._key = key
        self.setText(key)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.setStyleSheet("border: 2px solid #4285f4;")

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.clearFocus()
            self.setStyleSheet("")
            return
        if key in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta,
                   Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
            return
        text = event.text().upper().strip()
        if not text:
            text = QKeySequence(key).toString().upper()
        if text:
            self._key = text
            self.setText(text)
            self.setStyleSheet("")
            self.clearFocus()
        event.accept()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.setStyleSheet("")


class HotkeyWidget(QWidget):
    """Compact hotkey configurator: key capture + modifier checkboxes."""

    def __init__(self, hotkey_str: str = "Alt+Shift+M", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._key_edit = KeyCaptureEdit(self)
        layout.addWidget(self._key_edit)

        self._chk_shift = QCheckBox("Shift")
        self._chk_alt = QCheckBox("Alt")
        self._chk_ctrl = QCheckBox("Ctrl")
        self._chk_win = QCheckBox("Win")
        for chk in (self._chk_shift, self._chk_alt, self._chk_ctrl, self._chk_win):
            layout.addWidget(chk)
        layout.addStretch()

        self.set_hotkey(hotkey_str)

    def set_hotkey(self, hotkey_str: str):
        parts = [p.strip().upper() for p in hotkey_str.split("+")]
        self._chk_ctrl.setChecked("CTRL" in parts or "CONTROL" in parts)
        self._chk_shift.setChecked("SHIFT" in parts)
        self._chk_alt.setChecked("ALT" in parts)
        self._chk_win.setChecked(
            any(p in parts for p in ("WIN", "WINDOWS", "META")))
        key = next(
            (p for p in parts
             if p not in ("CTRL", "CONTROL", "SHIFT", "ALT", "WIN", "WINDOWS", "META")),
            ""
        )
        self._key_edit.set_key(key)

    def get_hotkey(self) -> str:
        parts = []
        if self._chk_ctrl.isChecked():
            parts.append("Ctrl")
        if self._chk_shift.isChecked():
            parts.append("Shift")
        if self._chk_alt.isChecked():
            parts.append("Alt")
        if self._chk_win.isChecked():
            parts.append("Win")
        key = self._key_edit.key()
        if key:
            parts.append(key)
        return "+".join(parts)


class SuggestionPopup(QListWidget):
    """Frameless floating list that shows autocomplete suggestions.

    Rendered as a ``Qt.ToolTip`` window so it floats above all other widgets
    without stealing keyboard focus.  Callers drive navigation via
    :meth:`keyPressEvent` forwarding and connect :signal:`itemClicked`.
    """

    def __init__(self, parent=None):
        super().__init__(None)
        self._owner = parent

        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.setFocusPolicy(Qt.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSelectionMode(QListWidget.SingleSelection)
        self.hide()

    def show_items(self, items: List[str], global_pos: QPoint):
        self.clear()

        if not items:
            self.hide()
            return

        for text in items:
            QListWidgetItem(text, self)

        self.setCurrentRow(0)

        row_h = max(22, self.sizeHintForRow(0))
        visible_rows = min(len(items), 8)
        height = row_h * visible_rows + 8
        width = 380

        self.resize(width, height)
        self.move(global_pos)
        self.show()
        self.raise_()

    def selected_text(self) -> Optional[str]:
        item = self.currentItem()
        return item.text() if item else None


class SmartTaskEdit(QPlainTextEdit):
    """Multi-line task input with inline tag autocomplete.

    Watches every keystroke and shows a :class:`SuggestionPopup` for:

    * Tag names after ``@`` (project, type, assignee, due, estimate, …)
    * Project key/name values after ``@prj``
    * Issue-type names after ``@type`` (project-aware)
    * Estimate shorthands after ``@est`` (``1h``, ``2d``, …)
    * Natural-language due dates after ``@due``
    * Assignee display names after ``@asg`` (searches Jira API with debounce)
    * Label names after ``@label`` (semicolon-separated, token-aware)
    * Status names after ``@status``

    ``owner`` must expose a ``cfg: AppConfig`` and optionally ``jira: JiraClient``.
    """

    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self.owner = owner
        self.popup = SuggestionPopup(self)
        self.popup.itemClicked.connect(self.on_item_clicked)

        self._suggestion_timer = QTimer(self)
        self._suggestion_timer.setSingleShot(True)
        self._suggestion_timer.timeout.connect(self.update_suggestions)

        self._assignee_cache: Dict[str, List[str]] = {}

    def on_item_clicked(self, item):
        self.apply_suggestion(item.text())

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        QTimer.singleShot(150, self.popup.hide)

    def keyPressEvent(self, event):
        if self.popup.isVisible():
            if event.key() in (Qt.Key_Down, Qt.Key_Up):
                self.popup.keyPressEvent(event)
                return

            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                text = self.popup.selected_text()
                if text:
                    self.apply_suggestion(text)
                    return

            if event.key() == Qt.Key_Escape:
                self.popup.hide()
                return

        super().keyPressEvent(event)

        line = self.current_line_before_cursor()

        # show suggestions immediately after typing "@"
        if line.endswith("@"):
            self.update_suggestions()
            return

        if re.search(r'@(asg|assignee|исп|на)\s+([^@]*)$', line, flags=re.IGNORECASE):
            self._suggestion_timer.start(250)
        else:
            self._suggestion_timer.start(80)

    def current_line_before_cursor(self) -> str:
        tc = self.textCursor()
        block_text = tc.block().text()
        pos_in_block = tc.positionInBlock()
        return block_text[:pos_in_block]

    def popup_global_pos(self) -> QPoint:
        cr = self.cursorRect()
        return self.mapToGlobal(cr.bottomRight())

    def update_suggestions(self):
        line = self.current_line_before_cursor()

        # 1) tag completion: "@", "@p", "@ti"  — language-aware
        m_tag = re.search(r'@([A-Za-zА-Яа-я_0-9]*)$', line)
        if m_tag:
            lang = getattr(getattr(self.owner, "cfg", None), "language", "en")
            prefix = "@" + m_tag.group(1)
            all_items = tag_completion_items(lang)
            items = [it for it in all_items if it.lower(
            ).startswith(prefix.lower())]

            # if the tag is fully typed and is the only match — hide popup
            if len(items) == 1:
                item_tag = items[0].split(" \u2014 ", 1)[0].strip()
                if item_tag.lower() == prefix.lower():
                    self.popup.hide()
                    return

            self.popup.show_items(items, self.popup_global_pos())
            return

        # 2) project values
        value_prefix = self.should_suggest_tag_value(
            line, TAG_PATTERNS["project"])
        if value_prefix is not None:
            items = self.project_suggestions(value_prefix)
            if self.should_hide_on_exact_match(value_prefix, items):
                self.popup.hide()
                return
            self.popup.show_items(items, self.popup_global_pos())
            return

        # 3) issue type values
        value_prefix = self.should_suggest_tag_value(
            line, TAG_PATTERNS["type"])
        if value_prefix is not None:
            items = self.issue_type_suggestions(value_prefix, line)
            if self.should_hide_on_exact_match(value_prefix, items):
                self.popup.hide()
                return
            self.popup.show_items(items, self.popup_global_pos())
            return

        # 4) estimate values
        value_prefix = self.should_suggest_tag_value(
            line, TAG_PATTERNS["estimate"])
        if value_prefix is not None:
            items = [
                x for x in ESTIMATE_SUGGESTIONS
                if x.lower().startswith(value_prefix.lower())
            ]
            if self.should_hide_on_exact_match(value_prefix, items):
                self.popup.hide()
                return
            self.popup.show_items(items, self.popup_global_pos())
            return

        # 5) due values
        value_prefix = self.should_suggest_tag_value(line, TAG_PATTERNS["due"])
        if value_prefix is not None:
            items = self.due_suggestions(value_prefix.lower())
            if self.should_hide_on_exact_match(value_prefix, items):
                self.popup.hide()
                return
            self.popup.show_items(items, self.popup_global_pos())
            return

        # 6) assignee values
        value_prefix = self.should_suggest_tag_value(
            line, TAG_PATTERNS["assignee"])
        if value_prefix is not None:
            items = self.assignee_suggestions(value_prefix)
            if self.should_hide_on_exact_match(value_prefix, items):
                self.popup.hide()
                return
            self.popup.show_items(items, self.popup_global_pos())
            return

        # 7) label values — semicolon-aware: complete each token after a semicolon
        m_label = re.search(TAG_PATTERNS["label"], line, flags=re.IGNORECASE)
        if m_label:
            full_value = m_label.group(2)
            parts = full_value.split(";")
            current_token = parts[-1].strip()
            items = self.label_suggestions(current_token)
            if self.should_hide_on_exact_match(current_token, items):
                self.popup.hide()
                return
            self.popup.show_items(items, self.popup_global_pos())
            return

        # 8) status values
        value_prefix = self.should_suggest_tag_value(
            line, TAG_PATTERNS["status"])
        if value_prefix is not None:
            items = self.status_suggestions(value_prefix, line)
            if self.should_hide_on_exact_match(value_prefix, items):
                self.popup.hide()
                return
            self.popup.show_items(items, self.popup_global_pos())
            return

        self.popup.hide()

    def project_suggestions(self, prefix: str) -> List[str]:
        jira = getattr(self.owner, "jira", None)
        if not jira:
            return []

        try:
            pairs = jira.project_keys_and_names()
        except Exception:
            return []

        prefix_low = (prefix or "").strip().lower()
        pair_map = {key: name for key, name in pairs}

        def matches(key, name):
            if not prefix_low:
                return True
            return prefix_low in key.lower() or prefix_low in name.lower()

        seen_keys = set()
        results = []

        # favorites first (MRU order)
        for fav_key in jira._favorite_projects:
            name = pair_map.get(fav_key, "")
            if matches(fav_key, name):
                results.append(f"{fav_key} \u2014 {name}" if name else fav_key)
                seen_keys.add(fav_key)

        # remaining projects (no duplicates)
        for key, name in pairs:
            if key not in seen_keys and matches(key, name):
                results.append(f"{key} \u2014 {name}")

        return results[:30]

    def extract_project_from_line(self, line: str) -> Optional[str]:
        m_prj = re.search(
            r'@(prj|project|проект)\s+([^@\s]+)', line, flags=re.IGNORECASE)
        if not m_prj:
            return None

        raw_project = m_prj.group(2).strip()
        jira = getattr(self.owner, "jira", None)
        if not jira:
            return raw_project

        try:
            pairs = jira.project_keys_and_names()
        except Exception:
            return raw_project

        raw_low = raw_project.lower()

        for key, name in pairs:
            if raw_low == key.lower():
                return key
            if raw_low == name.lower():
                return key

        for key, name in pairs:
            if raw_low in key.lower() or raw_low in name.lower():
                return key

        return raw_project

    def issue_type_suggestions(self, prefix: str, line: str) -> List[str]:
        jira = getattr(self.owner, "jira", None)
        if not jira:
            return []

        project_key = self.extract_project_from_line(line)
        if not project_key:
            try:
                project_key = getattr(self.owner.cfg, "default_project", "")
            except Exception:
                project_key = ""

        try:
            if project_key:
                types = jira.issue_types_for_project(project_key)
            else:
                types = []
        except Exception:
            types = []

        if not types:
            default_type = getattr(
                self.owner.cfg, "default_issue_type", "Task")
            types = [default_type, "Task", "Bug", "Story", "Epic"]

        seen = []
        for t in types:
            if t not in seen:
                seen.append(t)

        prefix_low = (prefix or "").strip().lower()
        if not prefix_low:
            return seen[:20]

        return [t for t in seen if prefix_low in t.lower()][:20]

    def due_suggestions(self, prefix: str) -> List[str]:
        prefix = (prefix or "").strip()
        prefix_low = prefix.lower()

        # base text suggestions
        items = []

        if not prefix_low:
            return DUE_SUGGESTIONS

        for x in DUE_SUGGESTIONS:
            if x.lower().startswith(prefix_low):
                items.append(x)

        # YYYY-MM-DD or partial ISO date
        if re.match(r'^\d{4}(-\d{0,2})?(-\d{0,2})?$', prefix):
            if prefix not in items:
                items.insert(0, prefix)

        # Text dates:
        # "15 december 2026"
        if re.match(r'^\d{1,2}\s+[A-Za-zА-Яа-яЁё]+(?:\s+\d{4})?$', prefix, flags=re.IGNORECASE):
            if prefix not in items:
                items.insert(0, prefix)

        return items[:20]

    def label_suggestions(self, prefix: str) -> List[str]:
        jira = getattr(self.owner, "jira", None)
        if not jira:
            return []
        try:
            return jira.get_labels(prefix)
        except Exception:
            return []

    def status_suggestions(self, prefix: str, line: str) -> List[str]:
        jira = getattr(self.owner, "jira", None)
        if not jira:
            return []
        project_key = self.extract_project_from_line(line)
        if not project_key:
            try:
                project_key = getattr(self.owner.cfg, "default_project", "")
            except Exception:
                project_key = ""
        if not project_key:
            return []
        try:
            statuses = jira.get_statuses_for_project(project_key)
            prefix_low = (prefix or "").strip().lower()
            if not prefix_low:
                return statuses[:20]
            return [s for s in statuses if prefix_low in s.lower()][:20]
        except Exception:
            return []

    def assignee_suggestions(self, prefix: str) -> List[str]:
        jira = getattr(self.owner, "jira", None)
        if not jira:
            return []

        prefix = (prefix or "").strip()
        prefix_low = prefix.lower()

        if not prefix:
            # Show me + all hand-picked cached users
            results = ["me"]
            for dn, aid, email in jira._cached_users:
                label = jira._format_user_label(dn, aid, email)
                if label not in results:
                    results.append(label)
            return results[:20]

        if prefix_low in self._assignee_cache:
            return self._assignee_cache[prefix_low]

        results = ["me"] if "me".startswith(prefix_low) else []

        try:
            users = jira.search_users_names(prefix)
        except Exception:
            users = []

        for dn, aid, email in users:
            label = jira._format_user_label(dn, aid, email)
            if label not in results:
                results.append(label)

        self._assignee_cache[prefix_low] = results[:20]
        return results[:20]

    def apply_suggestion(self, text: str):
        tc = self.textCursor()
        line = self.current_line_before_cursor()

        # replace tag prefix — strip " — description" suffix from display string
        m_tag = re.search(r'@([A-Za-zА-Яа-я_0-9]*)$', line)
        if m_tag:
            # strip description, then take only the first alias (before comma)
            insert_text = text.split(" \u2014 ", 1)[
                0].strip().split(",")[0].strip()
            start = tc.position() - len(m_tag.group(0))
            tc.setPosition(start)
            tc.setPosition(start + len(m_tag.group(0)),
                           QTextCursor.MoveMode.KeepAnchor)
            tc.insertText(insert_text + " ")
            self.setTextCursor(tc)
            self.popup.hide()
            return

        # replace project value
        m_prj = re.search(TAG_PATTERNS["project"], line, flags=re.IGNORECASE)
        if m_prj:
            prefix_text = m_prj.group(2)
            key = text.split("—", 1)[0].strip()
            start = tc.position() - len(prefix_text)
            tc.setPosition(start)
            tc.setPosition(start + len(prefix_text),
                           QTextCursor.MoveMode.KeepAnchor)
            tc.insertText(key)
            self.setTextCursor(tc)
            self.popup.hide()
            return

        # replace issue type value
        m_type = re.search(TAG_PATTERNS["type"], line, flags=re.IGNORECASE)
        if m_type:
            prefix_text = m_type.group(2)
            start = tc.position() - len(prefix_text)
            tc.setPosition(start)
            tc.setPosition(start + len(prefix_text),
                           QTextCursor.MoveMode.KeepAnchor)
            tc.insertText(text)
            self.setTextCursor(tc)
            self.popup.hide()
            return

        # replace estimate value
        m_est = re.search(TAG_PATTERNS["estimate"], line, flags=re.IGNORECASE)
        if m_est:
            prefix_text = m_est.group(2)
            start = tc.position() - len(prefix_text)
            tc.setPosition(start)
            tc.setPosition(start + len(prefix_text),
                           QTextCursor.MoveMode.KeepAnchor)
            tc.insertText(text)
            self.setTextCursor(tc)
            self.popup.hide()
            return

        # replace due value
        m_due = re.search(TAG_PATTERNS["due"], line, flags=re.IGNORECASE)
        if m_due:
            prefix_text = m_due.group(2)
            start = tc.position() - len(prefix_text)
            tc.setPosition(start)
            tc.setPosition(start + len(prefix_text),
                           QTextCursor.MoveMode.KeepAnchor)
            tc.insertText(text)
            self.setTextCursor(tc)
            self.popup.hide()
            return

        # replace assignee value
        m_asg = re.search(TAG_PATTERNS["assignee"], line, flags=re.IGNORECASE)
        if m_asg:
            prefix_text = m_asg.group(2)
            value = text.split(" \u2014 ", 1)[0].strip()
            start = tc.position() - len(prefix_text)
            tc.setPosition(start)
            tc.setPosition(start + len(prefix_text),
                           QTextCursor.MoveMode.KeepAnchor)
            tc.insertText(value)
            self.setTextCursor(tc)
            self.popup.hide()
            # Persist selected user to cache
            jira = getattr(self.owner, "jira", None)
            if jira and text.lower() != "me":
                jira.add_user_to_cache(text)
            return

        # replace label value — semicolon-aware: only replace the current token after last semicolon
        m_label = re.search(TAG_PATTERNS["label"], line, flags=re.IGNORECASE)
        if m_label:
            full_value = m_label.group(2)
            parts = full_value.split(";")
            current_token = parts[-1]  # raw (may have leading space)
            start = tc.position() - len(current_token)
            tc.setPosition(start)
            tc.setPosition(start + len(current_token),
                           QTextCursor.MoveMode.KeepAnchor)
            tc.insertText(text + "; ")
            self.setTextCursor(tc)
            self.popup.hide()
            return

        # replace status value
        m_status = re.search(TAG_PATTERNS["status"], line, flags=re.IGNORECASE)
        if m_status:
            prefix_text = m_status.group(2)
            start = tc.position() - len(prefix_text)
            tc.setPosition(start)
            tc.setPosition(start + len(prefix_text),
                           QTextCursor.MoveMode.KeepAnchor)
            tc.insertText(text)
            self.setTextCursor(tc)
            self.popup.hide()
            return

    def should_suggest_tag_value(self, line: str, pattern: str) -> Optional[str]:
        m = re.search(pattern, line, flags=re.IGNORECASE)
        if not m:
            return None

        value_prefix = m.group(2)

        # if value ends with a space — no suggestion
        if value_prefix and value_prefix.endswith(" "):
            return None

        return value_prefix.strip()

    def should_hide_on_exact_match(self, prefix: str, items: List[str]) -> bool:
        prefix = (prefix or "").strip().lower()
        if not prefix or not items:
            return False

        normalized = []
        for item in items:
            value = item.split("—", 1)[0].strip().lower()
            normalized.append(value)

        return len(normalized) == 1 and normalized[0] == prefix
# --------------------------- Jira Client ---------------------------


class JiraWarmupWorker(QObject):
    finished = Signal()
    failed = Signal(str)

    def __init__(self, jira_client: "JiraClient"):
        super().__init__()
        self.jira_client = jira_client

    def run(self):
        try:
            self.jira_client.warmup_cache()
            self.finished.emit()
        except Exception as e:
            self.failed.emit(str(e))


class JiraClient:
    """Thin wrapper around the ``jira`` library with caching and fuzzy matching.

    The underlying :class:`jira.JIRA` connection is created lazily on first use
    so that importing this module is fast even if the Jira SDK is heavy.

    Caches (in memory and on disk via :func:`_cache_file_path`):

    * Project list (key + display name pairs)
    * Issue types per project
    * Available statuses per project
    * All labels (fetched in bulk during warmup)
    * Recently searched users (persisted hand-picked set)
    * Favourite/MRU project keys (most-recently created issues)
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._jira = None
        self._me = None
        self._warmup_done = False
        self._projects_cache = None
        self._projects_pairs: Optional[List[Tuple[str, str]]] = None
        self._issuetypes_cache: Dict[str, List[str]] = {}
        self._statuses_cache: Dict[str, List[str]] = {}
        self._labels_all_cache: List[str] = []
        # hand-picked persistent users
        self._cached_users: List[Tuple[str, str, str]] = []
        # label → user tuple
        self._user_label_map: Dict[str, Tuple[str, str, str]] = {}
        # most-recently-used project keys (most recent first, max 10)
        self._favorite_projects: List[str] = []
        self._load_disk_cache()

    def _ensure(self):
        if self._jira is None:
            try:
                from jira import JIRA  # type: ignore
            except Exception as e:
                raise RuntimeError(
                    "Не установлен пакет 'jira'. Запустите: pip install jira"
                ) from e
            options = {"server": self.cfg.jira_url}
            self._jira = JIRA(options=options, basic_auth=(
                self.cfg.jira_user, self.cfg.jira_token))

    def me(self) -> dict:
        if self._me is not None:
            return self._me
        self._ensure()
        self._me = self._jira.myself()
        return self._me

    def projects(self) -> List[dict]:
        self._ensure()
        if self._projects_cache is None:
            self._projects_cache = self._jira.projects()
        return self._projects_cache

    def project_keys_and_names(self) -> List[Tuple[str, str]]:
        if self._projects_pairs is not None:
            return self._projects_pairs
        out = []
        for p in self.projects():
            key = getattr(p, "key", "")
            name = getattr(p, "name", "")
            out.append((key, name))
        self._projects_pairs = out
        return out

    def issue_types_for_project(self, project_key: str) -> List[str]:
        if project_key in self._issuetypes_cache:
            return self._issuetypes_cache[project_key]
        self._ensure()
        # Using createmeta to get project-specific types
        meta = self._jira.createmeta(
            projectKeys=project_key, expand="projects.issuetypes")
        types = []
        for proj in meta.get("projects", []):
            for t in proj.get("issuetypes", []):
                if not t.get("subtask", False):
                    types.append(t["name"])  # keep only standard issue types
        if not types:
            # Fallback to global types
            types = [it.name for it in self._jira.issue_types(
            ) if not getattr(it, "subtask", False)]
        self._issuetypes_cache[project_key] = types
        return types

    def find_assignee(self, query: str) -> Optional[str]:
        """Return accountId for assignee, or None."""
        self._ensure()
        if query.lower() in ("me", "я", "сам", "self"):
            me = self.me()
            return me.get("accountId") or me.get("name")
        try:
            users = self._jira.search_users(
                query=query, maxResults=20, includeInactive=False)
        except Exception:
            users = []
        # Prefer exact-ish displayName match, else first
        best = None
        best_score = 0
        for u in users:
            dn = getattr(u, "displayName", "")
            em = getattr(u, "emailAddress", "")
            score = max(
                fuzz.partial_ratio(query.lower(), dn.lower()),
                fuzz.partial_ratio(query.lower(), em.lower()),
            )
            if score > best_score:
                best = u
                best_score = score
        if best is None:
            return None
        return getattr(best, "accountId", None) or getattr(best, "name", None)

    @staticmethod
    def _format_user_label(dn: str, aid: str, email: str) -> str:
        label = dn or email or aid
        if email and email != label:
            label = f"{label} \u2014 {email}"
        return label

    def search_users_names(self, query: str) -> List[Tuple[str, str, str]]:
        """Return top candidates as (displayName, accountId, email).

        Empty query → returns only hand-picked cached users.
        Non-empty  → calls Jira API /user/search and merges result with
                     cached users that match; also populates _user_label_map
                     so add_user_to_cache() can resolve the selection later.
        """
        query_low = (query or "").strip().lower()

        if not query_low:
            return list(self._cached_users[:10])

        # Cached users that match the query
        cached_hits = [
            (dn, aid, email) for dn, aid, email in self._cached_users
            if query_low in dn.lower() or query_low in email.lower()
        ]
        cached_aids = {u[1] for u in cached_hits}

        # API search
        self._ensure()
        try:
            users = self._jira.search_users(
                query=query, maxResults=10, includeInactive=False)
        except Exception:
            users = []

        api_results: List[Tuple[str, str, str]] = []
        for u in users:
            dn = getattr(u, "displayName", "")
            aid = getattr(u, "accountId", None) or getattr(u, "name", "")
            email = getattr(u, "emailAddress", "")
            item = (dn, aid, email)
            # Store in label map so add_user_to_cache can later resolve it
            self._user_label_map[self._format_user_label(
                dn, aid, email)] = item
            if aid not in cached_aids:
                api_results.append(item)

        return (cached_hits + api_results)[:10]

    def add_favorite_project(self, key: str):
        """Record a project key as recently used (MRU, most recent first, max 10)."""
        if not key:
            return
        if key in self._favorite_projects:
            self._favorite_projects.remove(key)
        self._favorite_projects.insert(0, key)
        self._favorite_projects = self._favorite_projects[:10]
        self._save_disk_cache()

    def add_user_to_cache(self, label: str):
        """Persist a user (identified by their display label) to the cache."""
        if label.strip().lower() == "me":
            return
        user = self._user_label_map.get(label)
        if user is None:
            return
        _, aid, _ = user
        if any(u[1] == aid for u in self._cached_users):
            return  # already cached
        self._cached_users.append(user)
        self._save_disk_cache()

    def create_issue(self, project_key: str, summary: str, issue_type: str,
                     assignee_account_id: Optional[str], due_date: Optional[str],
                     description: Optional[str] = None,
                     estimate_text: Optional[str] = None,
                     labels: Optional[List[str]] = None) -> str:
        self._ensure()
        fields = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if assignee_account_id:
            fields["assignee"] = {"id": assignee_account_id}
        if due_date:
            fields["duedate"] = due_date  # yyyy-mm-dd
        if description:
            fields["description"] = description
        if estimate_text:
            fields["timetracking"] = {
                "originalEstimate": estimate_text
            }
        if labels:
            fields["labels"] = labels
        issue = self._jira.create_issue(fields=fields)
        return issue.key

    def get_labels(self, prefix: str = "") -> List[str]:
        """Return label suggestions from the warmup cache."""
        prefix_low = (prefix or "").strip().lower()
        if not prefix_low:
            return self._labels_all_cache[:20]
        return [lb for lb in self._labels_all_cache if prefix_low in lb.lower()][:20]

    def get_statuses_for_project(self, project_key: str) -> List[str]:
        """Return sorted list of unique status names available in the project."""
        if project_key in self._statuses_cache:
            return self._statuses_cache[project_key]
        self._ensure()
        try:
            statuses_raw = self._jira._get_json(
                f"project/{project_key}/statuses")
            status_names: set = set()
            for entry in statuses_raw:
                for s in entry.get("statuses", []):
                    status_names.add(s["name"])
            result = sorted(status_names)
        except Exception:
            result = []
        self._statuses_cache[project_key] = result
        return result

    def transition_issue(self, issue_key: str, target_status: str) -> bool:
        """Transition issue to the named status (exact or fuzzy match)."""
        self._ensure()
        try:
            transitions = self._jira.transitions(issue_key)
            # exact match first
            for t in transitions:
                if t["to"]["name"].lower() == target_status.lower():
                    self._jira.transition_issue(issue_key, t["id"])
                    return True
            # fuzzy fallback
            best, best_score = None, 0
            for t in transitions:
                score = fuzz.ratio(target_status.lower(),
                                   t["to"]["name"].lower())
                if score > best_score:
                    best_score = score
                    best = t
            if best and best_score >= 60:
                self._jira.transition_issue(issue_key, best["id"])
                return True
        except Exception:
            pass
        return False

    def warmup_cache(self):
        if self._warmup_done:
            return

        self._ensure()

        try:
            self.me()
        except Exception as e:
            print(f"Warmup: failed to load current user: {e}")

        try:
            projects = self.projects()
            self._projects_pairs = [
                (getattr(p, "key", ""), getattr(p, "name", ""))
                for p in projects
            ]
        except Exception as e:
            print(f"Warmup: failed to load projects: {e}")
            return

        for p in projects:
            key = getattr(p, "key", "")
            if not key:
                continue
            try:
                self.issue_types_for_project(key)
            except Exception as e:
                print(f"Warmup: failed to load issue types for {key}: {e}")

        try:
            all_labels: List[str] = []
            start_at = 0
            max_results = 1000
            while True:
                result = self._jira._get_json(
                    f"label?startAt={start_at}&maxResults={max_results}"
                )
                values = result.get("values", [])
                all_labels.extend(values)
                if result.get("isLast", True) or len(values) < max_results:
                    break
                start_at += max_results
            self._labels_all_cache = all_labels
            print(
                f"Warmup: loaded {len(self._labels_all_cache)} labels via /rest/api/3/label")
        except Exception as e:
            print(f"Warmup: failed to load labels via /rest/api/3/label: {e}")
            # fallback to suggest API
            try:
                result = self._jira._get_json(
                    "label/suggest?query=&maxResults=100")
                self._labels_all_cache = [
                    item["label"] for item in result.get("suggestions", [])
                ]
                print(
                    f"Warmup: loaded {len(self._labels_all_cache)} labels via suggest fallback")
            except Exception as e2:
                print(f"Warmup: failed to load labels (fallback): {e2}")

        self._warmup_done = True
        self._save_disk_cache()

    def _load_disk_cache(self):
        """Load cached Jira data from disk on startup."""
        path = _cache_file_path()
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "me" in data:
                self._me = data["me"]
            if "projects" in data:
                self._projects_pairs = [tuple(p) for p in data["projects"]]
            if "issue_types" in data:
                self._issuetypes_cache = data["issue_types"]
            if "statuses" in data:
                self._statuses_cache = data["statuses"]
            if "labels_all" in data:
                self._labels_all_cache = data["labels_all"]
            if "cached_users" in data:
                self._cached_users = [tuple(u) for u in data["cached_users"]]
                # Pre-populate label map for cached users
                for u in self._cached_users:
                    self._user_label_map[self._format_user_label(*u)] = u
            if "favorite_projects" in data:
                self._favorite_projects = data["favorite_projects"]
            print(
                f"Loaded disk cache: {len(self._projects_pairs or [])} projects, "
                f"{len(self._cached_users)} cached users, {len(self._labels_all_cache)} labels"
            )
        except Exception as e:
            print(f"Failed to load disk cache: {e}")

    def _save_disk_cache(self):
        """Persist cached Jira data to disk after warmup."""
        path = _cache_file_path()
        try:
            data: Dict = {}
            if self._me:
                data["me"] = self._me
            if self._projects_pairs is not None:
                data["projects"] = [list(p) for p in self._projects_pairs]
            if self._issuetypes_cache:
                data["issue_types"] = self._issuetypes_cache
            if self._statuses_cache:
                data["statuses"] = self._statuses_cache
            if self._labels_all_cache:
                data["labels_all"] = self._labels_all_cache
            if self._cached_users:
                data["cached_users"] = [list(u) for u in self._cached_users]
            if self._favorite_projects:
                data["favorite_projects"] = self._favorite_projects
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Saved disk cache to: {path}")
        except Exception as e:
            print(f"Failed to save disk cache: {e}")

# --------------------------- Parsing ---------------------------


@dataclass
class ParsedTask:
    raw_line: str
    summary: str
    description: str
    project: str
    issue_type: str
    assignee_query: str
    assignee_account_id: Optional[str]
    due_str: str
    due_date: Optional[str]
    estimate_str: str
    labels: List[str] = field(default_factory=list)
    target_status: str = ""
    due_parse_failed: bool = False
    project_fallback_used: bool = False
    issue_type_fallback_used: bool = False
    assignee_fallback_used: bool = False
    estimate_fallback_used: bool = False


class QuickParser:
    """Parse free-text task lines into :class:`ParsedTask` objects.

    Supports two modes:

    * **Multi-task** (:meth:`parse_many`) – each non-empty line is one task.
      The first ``.`` in a line separates *summary* from *description*.
    * **Single-task** (:meth:`parse_single_task`) – the entire text block is
      one task; the first non-empty line (after tag stripping) is the summary,
      remaining lines become the description (newlines preserved).

    Tags are scanned with :attr:`TAG_START_RE` and resolved via
    :data:`SUPPORTED_TAGS`.  Unknown tags are silently removed from the text.
    Project / issue-type resolution uses fuzzy matching (:mod:`rapidfuzz`)
    against the Jira cache when a :class:`JiraClient` is available.
    """

    TAG_START_RE = re.compile(r'@(\w+)')

    def __init__(self, jira: Optional[JiraClient], defaults: AppConfig):
        self.jira = jira
        self.defaults = defaults

    def _extract_supported_tags(self, text: str) -> Tuple[Dict[str, str], str]:
        """
        Extract all supported tags and return:
        - dict with normalized values by family
        - remaining text with all recognized tags removed
        """
        matches = list(self.TAG_START_RE.finditer(text))
        if not matches:
            return {}, text.strip()

        tags: Dict[str, str] = {}
        remaining_parts = []
        last_pos = 0

        for i, m in enumerate(matches):
            tag_name = m.group(1).strip().lower()
            start = m.start()
            value_start = m.end()

            next_start = matches[i + 1].start() if i + \
                1 < len(matches) else len(text)
            value = text[value_start:next_start].strip()

            # text before current tag stays in remaining text
            if start > last_pos:
                remaining_parts.append(text[last_pos:start])

            family = self._tag_family(tag_name)
            if family:
                tags[family] = value
            else:
                # unknown tag: do not keep it in text either
                pass

            last_pos = next_start

        # tail after last tag is already consumed as part of last tag value
        remaining_text = "".join(remaining_parts).strip()
        return tags, remaining_text

    def _strip_any_tags(self, text: str) -> str:
        """
        Remove any remaining @tag value fragments, even if tag is unknown.
        This guarantees that tags never end up in summary/description.
        """
        matches = list(self.TAG_START_RE.finditer(text))
        if not matches:
            return text.strip()

        remaining_parts = []
        last_pos = 0

        for i, m in enumerate(matches):
            start = m.start()
            next_start = matches[i + 1].start() if i + \
                1 < len(matches) else len(text)

            if start > last_pos:
                remaining_parts.append(text[last_pos:start])

            last_pos = next_start

        cleaned = "".join(remaining_parts).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _tag_family(self, tag: str) -> Optional[str]:
        tag = tag.lower()
        for family, aliases in SUPPORTED_TAGS.items():
            if tag in aliases:
                return family
        return None

    @staticmethod
    def _nl_date_to_iso(date_text: str) -> Optional[str]:
        if not date_text:
            return None

        text = date_text.strip()
        if not text:
            return None

        # 1) try ISO format directly
        if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
            return text

        # 2) try dateparser for natural language dates
        dt = dateparser.parse(
            text,
            languages=["ru", "en"],
            settings={
                "PREFER_DATES_FROM": "future",
                "RETURN_AS_TIMEZONE_AWARE": False,
                "DATE_ORDER": "DMY",
            },
        )

        if not dt:
            return None

        return dt.strftime("%Y-%m-%d")

    @staticmethod
    def _heuristic_date(text: str) -> Optional[str]:
        t = (text or "").strip().lower()
        if not t:
            return None
        today = date.today()
        if "next week" in t:
            return (today + timedelta(days=7)).strftime("%Y-%m-%d")
        weekdays = {
            "monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
        }
        for name, idx in weekdays.items():
            if f"next {name}" in t:
                delta = (idx - today.weekday()) % 7
                if delta == 0:
                    delta = 7
                return (today + timedelta(days=delta)).strftime("%Y-%m-%d")
        return None

    @staticmethod
    def _add_business_days(start: Optional[date], days: int) -> date:
        d = start or date.today()
        step = 1 if days >= 0 else -1
        remaining = abs(days)
        while remaining > 0:
            d += timedelta(days=step)
            if d.weekday() < 5:
                remaining -= 1
        return d

    def _best_project(self, text: str) -> str:
        if not self.jira:
            return text or self.defaults.default_project or ""
        pairs = self.jira.project_keys_and_names()
        if not pairs:
            return text or self.defaults.default_project or ""
        candidates = {k: k for k, _ in pairs}
        candidates.update({name: k for k, name in pairs})
        choices = list(candidates.keys())
        match, score, _ = rfprocess.extractOne(
            text, choices, scorer=fuzz.WRatio
        ) if text else (None, 0, None)
        if match and score >= 55:
            return candidates[match]
        return self.defaults.default_project or (pairs[0][0] if pairs else "")

    def _best_issue_type(self, project_key: str, text: str) -> str:
        fallback = self.defaults.default_issue_type or "Task"
        if not self.jira or not project_key:
            return text or fallback
        types = self.jira.issue_types_for_project(project_key)
        if not types:
            return text or fallback
        if not text:
            return fallback if fallback in types else types[0]
        match, score, _ = rfprocess.extractOne(text, types, scorer=fuzz.WRatio)
        if match and score >= 60:
            return match

        synonyms = {
            "issue": "Task",
            "bug": "Bug",
            "story": "Story",
            "task": "Task",
            "epic": "Epic",
        }
        low = text.strip().lower()
        if low in synonyms and synonyms[low] in types:
            return synonyms[low]
        return fallback if fallback in types else types[0]

    def _assignee(self, text: str) -> Tuple[str, Optional[str]]:
        if not text:
            return self.defaults.default_assignee or "", None
        if self.jira:
            acc = self.jira.find_assignee(text)
            return text, acc
        return text, None

    @staticmethod
    def validate_estimate(text: str) -> bool:
        if not text:
            return False
        pattern = r"^\d+\s*(m|h|d|w)$"
        return bool(re.match(pattern, text.strip().lower()))

    def parse_line(self, line: str) -> ParsedTask:
        raw = line.strip()
        if not raw:
            return ParsedTask(
                raw_line=raw,
                summary="",
                description="",
                project=self.defaults.default_project,
                issue_type=self.defaults.default_issue_type,
                assignee_query="",
                assignee_account_id=None,
                due_str="",
                due_date=None,
                estimate_str=getattr(
                    self.defaults, "default_estimate", DEFAULT_ESTIMATE),
            )

        extracted, rest = self._extract_supported_tags(raw)

        # extra safety: remove any remaining @... fragments from text
        rest = self._strip_any_tags(rest)

        # rule 1: first dot splits summary / description
        summary = ""
        description = ""

        if rest:
            pos = rest.find(".")
            if pos != -1:
                summary = rest[:pos].strip()
                description = rest[pos + 1:].strip()
            else:
                summary = rest.strip()
                description = ""

        project_text = extracted.get("project", "").strip()
        type_text = extracted.get("type", "").strip()
        assignee_text = extracted.get("assignee", "").strip()
        due_text = extracted.get("due", "").strip()
        estimate_text = extracted.get("estimate", "").strip()
        label_text = extracted.get("label", "").strip()
        status_text = extracted.get("status", "").strip()

        project_fallback_used = False
        project = self._best_project(project_text)

        if not project_text:
            project_fallback_used = True
        elif self.defaults.default_project and project == self.defaults.default_project and project_text != project:
            project_fallback_used = True

        issue_type_fallback_used = False
        issue_type = self._best_issue_type(project, type_text)

        if not type_text:
            issue_type_fallback_used = True
        elif self.defaults.default_issue_type and issue_type == self.defaults.default_issue_type and type_text.lower() != issue_type.lower():
            issue_type_fallback_used = True

        assignee_fallback_used = False

        effective_assignee = assignee_text or self.defaults.default_assignee
        asg_query, asg_id = self._assignee(effective_assignee)

        if not assignee_text:
            assignee_fallback_used = True
        elif assignee_text and not asg_id:
            assignee_fallback_used = True
            asg_query = self.defaults.default_assignee
            asg_id = None

        due_parse_failed = False

        due_iso = self._nl_date_to_iso(due_text)

        if due_text and not due_iso:
            due_iso = self._heuristic_date(due_text)

        # date was provided but could not be parsed
        if due_text and not due_iso:
            due_parse_failed = True

        # no date or failed to parse — fall back to default_due_workdays
        if (not due_text or due_parse_failed) and getattr(self.defaults, "default_due_workdays", 0):
            d = self._add_business_days(
                date.today(),
                int(getattr(self.defaults, "default_due_workdays", 0))
            )
            due_iso = d.strftime("%Y-%m-%d")

        estimate_fallback_used = False

        estimate_text = (estimate_text or getattr(
            self.defaults, "default_estimate", DEFAULT_ESTIMATE
        )).strip()

        if not self.validate_estimate(estimate_text):
            estimate_text = getattr(
                self.defaults, "default_estimate", DEFAULT_ESTIMATE)
            estimate_fallback_used = True
        elif not extracted.get("estimate", "").strip():
            estimate_fallback_used = True

        # labels
        labels: List[str] = [l.strip() for l in label_text.split(
            ";") if l.strip()] if label_text else []
        if not labels:
            default_labels_str = getattr(self.defaults, "default_labels", "")
            if default_labels_str:
                labels = [l.strip()
                          for l in default_labels_str.split(";") if l.strip()]

        # status
        target_status = status_text or getattr(
            self.defaults, "default_status", "")

        return ParsedTask(
            raw_line=raw,
            summary=summary,
            description=description,
            project=project,
            issue_type=issue_type,
            assignee_query=asg_query,
            assignee_account_id=asg_id,
            due_str=due_text,
            due_date=due_iso,
            estimate_str=estimate_text,
            labels=labels,
            target_status=target_status,
            due_parse_failed=due_parse_failed,
            project_fallback_used=project_fallback_used,
            issue_type_fallback_used=issue_type_fallback_used,
            assignee_fallback_used=assignee_fallback_used,
            estimate_fallback_used=estimate_fallback_used,
        )

    def parse_many(self, text: str) -> List[ParsedTask]:
        lines = [l for l in text.splitlines() if l.strip()]
        return [self.parse_line(l) for l in lines]

    def parse_single_task(self, text: str) -> List[ParsedTask]:
        """Parse the entire text as one task.

        First non-empty line after tag removal → summary.
        Remaining lines → description (newlines preserved).
        Tags are scanned across all lines.
        """
        if not text.strip():
            return []

        # Collect all tags from every line
        merged_tags: Dict[str, str] = {}
        clean_lines: List[str] = []

        for line in text.splitlines():
            extracted, rest = self._extract_supported_tags(line)
            rest = self._strip_any_tags(rest).strip()
            for family, value in extracted.items():
                if value and family not in merged_tags:
                    merged_tags[family] = value
            clean_lines.append(rest)

        # First non-empty line = summary; the rest = description
        summary = ""
        desc_lines: List[str] = []
        summary_found = False
        for cl in clean_lines:
            if not summary_found and cl:
                summary = cl
                summary_found = True
            elif summary_found:
                desc_lines.append(cl)

        # Trim trailing blank lines from description
        while desc_lines and not desc_lines[-1].strip():
            desc_lines.pop()
        description = "\n".join(desc_lines)

        project_text = merged_tags.get("project", "").strip()
        type_text = merged_tags.get("type", "").strip()
        assignee_text = merged_tags.get("assignee", "").strip()
        due_text = merged_tags.get("due", "").strip()
        estimate_text = merged_tags.get("estimate", "").strip()
        label_text = merged_tags.get("label", "").strip()
        status_text = merged_tags.get("status", "").strip()

        project_fallback_used = False
        project = self._best_project(project_text)
        if not project_text:
            project_fallback_used = True

        issue_type_fallback_used = False
        issue_type = self._best_issue_type(project, type_text)
        if not type_text:
            issue_type_fallback_used = True

        assignee_fallback_used = False
        effective_assignee = assignee_text or self.defaults.default_assignee
        asg_query, asg_id = self._assignee(effective_assignee)
        if not assignee_text:
            assignee_fallback_used = True

        due_parse_failed = False
        due_iso = self._nl_date_to_iso(due_text)
        if due_text and not due_iso:
            due_iso = self._heuristic_date(due_text)
        if due_text and not due_iso:
            due_parse_failed = True
        if (not due_text or due_parse_failed) and getattr(self.defaults, "default_due_workdays", 0):
            d = self._add_business_days(
                date.today(), int(getattr(self.defaults, "default_due_workdays", 0)))
            due_iso = d.strftime("%Y-%m-%d")

        estimate_fallback_used = False
        estimate_text = (estimate_text or getattr(
            self.defaults, "default_estimate", DEFAULT_ESTIMATE)).strip()
        if not self.validate_estimate(estimate_text):
            estimate_text = getattr(
                self.defaults, "default_estimate", DEFAULT_ESTIMATE)
            estimate_fallback_used = True
        elif not merged_tags.get("estimate", "").strip():
            estimate_fallback_used = True

        labels: List[str] = [lb.strip() for lb in label_text.split(
            ";") if lb.strip()] if label_text else []
        if not labels:
            default_labels_str = getattr(self.defaults, "default_labels", "")
            if default_labels_str:
                labels = [lb.strip()
                          for lb in default_labels_str.split(";") if lb.strip()]

        target_status = status_text or getattr(
            self.defaults, "default_status", "")

        return [ParsedTask(
            raw_line=text.strip(),
            summary=summary,
            description=description,
            project=project,
            issue_type=issue_type,
            assignee_query=asg_query,
            assignee_account_id=asg_id,
            due_str=due_text,
            due_date=due_iso,
            estimate_str=estimate_text,
            labels=labels,
            target_status=target_status,
            due_parse_failed=due_parse_failed,
            project_fallback_used=project_fallback_used,
            issue_type_fallback_used=issue_type_fallback_used,
            assignee_fallback_used=assignee_fallback_used,
            estimate_fallback_used=estimate_fallback_used,
        )]


# --------------------------- UI: Settings ---------------------------


class SettingsDialog(QDialog):

    def __init__(self, cfg: AppConfig, jira: Optional["JiraClient"] = None, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._jira = jira
        self.resize(720, 520)
        self.setWindowTitle(tr(cfg.language, "settings_title"))

        outer = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        outer.addWidget(self.tabs)

        # ── Tab 1: Task settings ──────────────────────────────────────────
        task_tab = QWidget()
        task_form = QFormLayout(task_tab)

        self.url = QLineEdit(cfg.jira_url)
        self.user = QLineEdit(cfg.jira_user)
        self.token = QLineEdit(cfg.jira_token)
        self.token.setEchoMode(QLineEdit.Password)

        self.def_proj = AutocompleteLineEdit(
            cfg.default_project, suggestion_fn=self._project_suggestions, parent=self)
        self.def_type = AutocompleteLineEdit(
            cfg.default_issue_type, suggestion_fn=self._issue_type_suggestions, parent=self)
        self.def_asg = QLineEdit(cfg.default_assignee)

        self.def_due_days = QSpinBox()
        self.def_due_days.setRange(0, 30)
        try:
            self.def_due_days.setValue(
                int(getattr(cfg, "default_due_workdays", 3)))
        except Exception:
            self.def_due_days.setValue(3)

        self.def_estimate = QLineEdit(
            getattr(cfg, "default_estimate", DEFAULT_ESTIMATE))
        self.def_labels = AutocompleteLineEdit(
            getattr(cfg, "default_labels", ""),
            suggestion_fn=self._label_suggestions, separator=";", parent=self)
        self.def_labels.setPlaceholderText("label1; label2")
        self.def_status = AutocompleteLineEdit(
            getattr(cfg, "default_status", ""),
            suggestion_fn=self._status_suggestions, parent=self)
        self.def_status.setPlaceholderText("e.g. In Progress")

        self.lbl_url = QLabel()
        self.lbl_user = QLabel()
        self.lbl_token = QLabel()
        self.lbl_proj = QLabel()
        self.lbl_type = QLabel()
        self.lbl_asg = QLabel()
        self.lbl_due = QLabel()
        self.lbl_est = QLabel()

        task_form.addRow(self.lbl_url, self.url)
        task_form.addRow(self.lbl_user, self.user)
        task_form.addRow(self.lbl_token, self.token)

        self.btn_check = QPushButton()
        self.btn_check.clicked.connect(self.on_check_connection)
        check_row = QHBoxLayout()
        check_row.addWidget(self.btn_check)
        check_row.addStretch()
        task_form.addRow("", check_row)

        task_form.addRow(self.lbl_proj, self.def_proj)
        task_form.addRow(self.lbl_type, self.def_type)
        task_form.addRow(self.lbl_asg, self.def_asg)
        task_form.addRow(self.lbl_due, self.def_due_days)
        task_form.addRow(self.lbl_est, self.def_estimate)
        self.lbl_def_labels = QLabel()
        self.lbl_def_status = QLabel()
        task_form.addRow(self.lbl_def_labels, self.def_labels)
        task_form.addRow(self.lbl_def_status, self.def_status)

        self.tabs.addTab(task_tab, "")

        # ── Tab 2: Application settings ───────────────────────────────────
        app_tab = QWidget()
        app_form = QFormLayout(app_tab)

        self.lbl_lang = QLabel()
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(supported_languages())
        current_lang = getattr(cfg, "language", default_language())
        idx = self.combo_lang.findText(current_lang)
        if idx >= 0:
            self.combo_lang.setCurrentIndex(idx)
        elif self.combo_lang.count() > 0:
            self.combo_lang.setCurrentIndex(0)
        app_form.addRow(self.lbl_lang, self.combo_lang)

        self.chk_stay_on_top = QCheckBox()
        self.chk_stay_on_top.setChecked(getattr(cfg, "stay_on_top", False))
        self.lbl_stay_on_top = QLabel()
        app_form.addRow(self.lbl_stay_on_top, self.chk_stay_on_top)

        self.spin_transparency = QSpinBox()
        self.spin_transparency.setRange(5, 95)
        self.spin_transparency.setSuffix(" %")
        self.spin_transparency.setValue(
            getattr(cfg, "inactivity_transparency", 30))
        self.spin_transparency.setToolTip(
            "Transparency when stay-on-top is active and the window loses focus")
        self.lbl_transparency = QLabel()
        app_form.addRow(self.lbl_transparency, self.spin_transparency)

        self.chk_hotkey = QCheckBox()
        self.chk_hotkey.setChecked(
            getattr(cfg, "global_hotkey_enabled", False))
        self.lbl_hotkey = QLabel()
        app_form.addRow(self.lbl_hotkey, self.chk_hotkey)

        self.hotkey_widget = HotkeyWidget(
            getattr(cfg, "global_hotkey", "Alt+Shift+M"), self)
        self.hotkey_widget.setEnabled(self.chk_hotkey.isChecked())
        self.chk_hotkey.toggled.connect(self.hotkey_widget.setEnabled)
        self.lbl_hotkey_shortcut = QLabel()
        app_form.addRow(self.lbl_hotkey_shortcut, self.hotkey_widget)

        self.chk_autostart = QCheckBox()
        self.chk_autostart.setChecked(getattr(cfg, "autostart", False))
        self.chk_autostart.setEnabled(_winreg_ok)
        self.lbl_autostart = QLabel()
        app_form.addRow(self.lbl_autostart, self.chk_autostart)

        self.tabs.addTab(app_tab, "")

        # ── Bottom buttons ────────────────────────────────────────────────
        btns = QHBoxLayout()
        self.btn_save = QPushButton()
        self.btn_cancel = QPushButton()
        btns.addStretch()
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_cancel)
        outer.addLayout(btns)

        self.btn_save.clicked.connect(self.on_save)
        self.btn_cancel.clicked.connect(self.reject)
        self.combo_lang.currentTextChanged.connect(self.apply_language)
        self.apply_language()

    def current_lang(self) -> str:
        return self.combo_lang.currentText().strip() or "en"

    def apply_language(self, *_):
        lang = self.current_lang()
        self.setWindowTitle(tr(lang, "settings_title"))
        self.tabs.setTabText(0, tr(lang, "settings_tab_task"))
        self.tabs.setTabText(1, tr(lang, "settings_tab_app"))
        self.lbl_url.setText(tr(lang, "jira_url"))
        self.lbl_user.setText(tr(lang, "user"))
        self.lbl_token.setText(tr(lang, "token"))
        self.lbl_proj.setText(tr(lang, "default_project"))
        self.lbl_type.setText(tr(lang, "default_issue_type"))
        self.lbl_asg.setText(tr(lang, "default_assignee"))
        self.lbl_due.setText(tr(lang, "default_due_workdays"))
        self.lbl_est.setText(tr(lang, "default_estimate"))
        self.lbl_def_labels.setText(tr(lang, "settings_default_labels"))
        self.lbl_def_status.setText(tr(lang, "settings_default_status"))
        self.lbl_lang.setText(tr(lang, "language"))
        self.lbl_stay_on_top.setText(tr(lang, "settings_stay_on_top"))
        self.lbl_transparency.setText(
            tr(lang, "settings_inactivity_transparency"))
        self.lbl_hotkey.setText(tr(lang, "settings_global_hotkey"))
        self.chk_hotkey.setText(tr(lang, "settings_hotkey_enable"))
        self.lbl_hotkey_shortcut.setText(tr(lang, "settings_hotkey_shortcut"))
        self.lbl_autostart.setText(tr(lang, "settings_autostart"))
        self.btn_check.setText(tr(lang, "check_connection"))
        self.btn_save.setText(tr(lang, "save"))
        self.btn_cancel.setText(tr(lang, "cancel"))

    # ── suggestion helpers ─────────────────────────────────────────────────

    def _project_suggestions(self, prefix: str) -> List[str]:
        if not self._jira:
            return []
        try:
            pairs = self._jira.project_keys_and_names()
        except Exception:
            return []
        prefix_low = (prefix or "").strip().lower()
        pair_map = {key: name for key, name in pairs}
        seen_keys: set = set()
        results: List[str] = []
        for fav_key in self._jira._favorite_projects:
            name = pair_map.get(fav_key, "")
            if not prefix_low or prefix_low in fav_key.lower() or prefix_low in name.lower():
                results.append(f"{fav_key} \u2014 {name}" if name else fav_key)
                seen_keys.add(fav_key)
        for key, name in pairs:
            if key not in seen_keys:
                if not prefix_low or prefix_low in key.lower() or prefix_low in name.lower():
                    results.append(f"{key} \u2014 {name}")
        return results[:30]

    def _issue_type_suggestions(self, prefix: str) -> List[str]:
        if not self._jira:
            return []
        proj_text = self.def_proj.text().strip()
        proj_key = proj_text.split("\u2014")[0].strip(
        ) if "\u2014" in proj_text else proj_text
        try:
            types = self._jira.issue_types_for_project(
                proj_key) if proj_key else []
        except Exception:
            types = []
        if not types:
            types = ["Task", "Bug", "Story", "Epic"]
        prefix_low = (prefix or "").strip().lower()
        if not prefix_low:
            return types[:20]
        return [t for t in types if prefix_low in t.lower()][:20]

    def _label_suggestions(self, prefix: str) -> List[str]:
        if not self._jira:
            return []
        try:
            return self._jira.get_labels(prefix or "")
        except Exception:
            return []

    def _status_suggestions(self, prefix: str) -> List[str]:
        if not self._jira:
            return []
        proj_text = self.def_proj.text().strip()
        proj_key = proj_text.split("\u2014")[0].strip(
        ) if "\u2014" in proj_text else proj_text
        if not proj_key:
            return []
        try:
            statuses = self._jira.get_statuses_for_project(proj_key)
            prefix_low = (prefix or "").strip().lower()
            if not prefix_low:
                return statuses[:20]
            return [s for s in statuses if prefix_low in s.lower()][:20]
        except Exception:
            return []

    def on_save(self):
        self.cfg.jira_url = self.url.text().strip()
        self.cfg.jira_user = self.user.text().strip()
        self.cfg.jira_token = self.token.text().strip()

        proj_text = self.def_proj.text().strip()
        if "\u2014" in proj_text:
            proj_text = proj_text.split("\u2014")[0].strip()
        self.cfg.default_project = proj_text

        self.cfg.default_issue_type = self.def_type.text().strip() or "Task"
        self.cfg.default_assignee = self.def_asg.text().strip() or "me"
        self.cfg.default_due_workdays = int(self.def_due_days.value())
        self.cfg.default_estimate = self.def_estimate.text().strip() or DEFAULT_ESTIMATE
        self.cfg.default_labels = self.def_labels.text().strip()
        self.cfg.default_status = self.def_status.text().strip()

        self.cfg.language = self.combo_lang.currentText()
        self.cfg.stay_on_top = self.chk_stay_on_top.isChecked()
        self.cfg.inactivity_transparency = self.spin_transparency.value()
        self.cfg.global_hotkey_enabled = self.chk_hotkey.isChecked()
        self.cfg.global_hotkey = self.hotkey_widget.get_hotkey()
        self.cfg.autostart = self.chk_autostart.isChecked()
        _set_autostart(self.cfg.autostart)

        self.accept()

    def on_check_connection(self):
        url = self.url.text().strip()
        user = self.user.text().strip()
        token = self.token.text().strip()

        if not url or not user or not token:
            QMessageBox.warning(self, "Connection",
                                "Fill Jira URL, User and API Token first.")
            return

        try:
            from jira import JIRA
            jira = JIRA(options={"server": url}, basic_auth=(user, token))
            me = jira.myself()
            name = me.get("displayName") or me.get("name") or "unknown"
            QMessageBox.information(self, "Connection OK",
                                    f"Connected successfully.\nUser: {name}")
        except Exception as e:
            QMessageBox.critical(self, "Connection failed", str(e))


# --------------------------- UI: Review Table ---------------------------

class AutocompleteLineEdit(QLineEdit):
    """QLineEdit with popup autocomplete.

    suggestion_fn: Callable[[str], List[str]] — returns suggestions for current token.
    on_select_fn:  Callable[[str], None]       — called with the raw selected label
                   when user picks from the popup (for side-effects like caching).
    separator:     if set (e.g. ';'), supports multi-value input — completes the token
                   after the last separator.
    """

    def __init__(self, text: str = "", suggestion_fn=None,
                 on_select_fn=None,
                 separator: Optional[str] = None, parent=None):
        super().__init__(text, parent)
        self._suggestion_fn = suggestion_fn
        self._on_select_fn = on_select_fn
        self._separator = separator
        self._popup = SuggestionPopup(self)
        self._popup.itemClicked.connect(self._on_item_clicked)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._update_suggestions)
        self.textEdited.connect(lambda: self._timer.start(200))

    def set_suggestion_fn(self, fn):
        self._suggestion_fn = fn

    def _on_item_clicked(self, item):
        self._apply_suggestion(item.text())

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        QTimer.singleShot(150, self._popup.hide)

    def keyPressEvent(self, event):
        if self._popup.isVisible():
            if event.key() in (Qt.Key_Down, Qt.Key_Up):
                self._popup.keyPressEvent(event)
                return
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                text = self._popup.selected_text()
                if text:
                    self._apply_suggestion(text)
                    return
            if event.key() == Qt.Key_Escape:
                self._popup.hide()
                return
        super().keyPressEvent(event)

    def _current_token(self) -> str:
        if not self._separator:
            return self.text()
        cursor_pos = self.cursorPosition()
        text_before = self.text()[:cursor_pos]
        return text_before.split(self._separator)[-1].strip()

    def _popup_pos(self) -> QPoint:
        return self.mapToGlobal(QPoint(0, self.height()))

    def _update_suggestions(self):
        if not self._suggestion_fn:
            self._popup.hide()
            return
        token = self._current_token()
        items = self._suggestion_fn(token)
        if not items:
            self._popup.hide()
            return
        self._popup.show_items(items, self._popup_pos())

    def _apply_suggestion(self, text: str):
        if not self._separator:
            # Single-value (e.g. assignee): strip display suffix after ' — '
            value = text.split(" \u2014 ", 1)[0].strip()
            self.setText(value)
            self.setCursorPosition(len(value))
            self._popup.hide()
        else:
            # Multi-value: replace current token and add separator + space
            cursor_pos = self.cursorPosition()
            full_text = self.text()
            text_before = full_text[:cursor_pos]
            text_after = full_text[cursor_pos:]
            parts = text_before.split(self._separator)
            parts[-1] = text
            new_before = (self._separator + " ").join(
                p.strip() for p in parts
            ) + self._separator + " "
            new_text = new_before + text_after.lstrip(self._separator).lstrip()
            self.setText(new_text)
            self.setCursorPosition(len(new_before))
            self._popup.hide()
        # Notify caller (e.g. to persist selection to cache)
        if self._on_select_fn:
            try:
                self._on_select_fn(text)
            except Exception:
                pass


class ReviewTaskCard(QFrame):
    """Editable card representing a single parsed task in the review dialog.

    Displays all task fields as editable widgets (summary, description, project
    combo, issue-type combo, assignee, estimate, due date, labels, status).
    Fields that were resolved via fallback are highlighted in amber.
    The "Add to Jira" checkbox disables the whole card when unchecked so the
    task is skipped during creation.
    """

    def __init__(self, task: ParsedTask, jira: Optional[JiraClient], cfg, parent=None):
        super().__init__(parent)
        self.task = task
        self.jira = jira
        self.cfg = cfg
        lang = getattr(cfg, "language", "en")
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("taskCard")
        self.setStyleSheet("""
            QFrame#taskCard {
                border: 1px solid #d8d8d8;
                border-radius: 8px;
                background: white;
                padding: 6px;
            }
            QLabel.title {
                font-weight: bold;
                font-size: 13px;
            }
            QLabel.meta {
                color: #666;
                font-size: 11px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # --- include checkbox ---
        self.chk_add_to_jira = QCheckBox(tr(lang, "review_add_to_jira"))
        self.chk_add_to_jira.setChecked(True)
        root.addWidget(self.chk_add_to_jira)

        # Summary
        self.edit_summary = QLineEdit(task.summary)
        self.edit_summary.setPlaceholderText("Summary")
        root.addWidget(self.edit_summary)

        # Description
        self.edit_description = QPlainTextEdit(
            getattr(task, "description", "") or ""
        )
        self.edit_description.setPlaceholderText("Description")
        self.edit_description.setFixedHeight(70)
        root.addWidget(self.edit_description)

        # --- Project row (full width) ---
        project_row = QHBoxLayout()

        self.project_combo = QComboBox()
        if self.jira:
            pairs = self.jira.project_keys_and_names()
            for key, name in pairs:
                self.project_combo.addItem(f"{key} — {name}", key)

            idx = next(
                (i for i in range(self.project_combo.count())
                 if self.project_combo.itemData(i) == task.project),
                0
            )
            self.project_combo.setCurrentIndex(idx)
        else:
            self.project_combo.addItem(task.project)

        project_row.addWidget(QLabel(tr(lang, "review_project")))
        project_row.addWidget(self.project_combo)
        root.addLayout(project_row)

        # --- Meta row (Type / Assignee / Due) ---
        meta = QHBoxLayout()

        self.type_combo = QComboBox()
        if getattr(task, "issue_type_fallback_used", False):
            self._mark_fallback(
                self.type_combo,
                "Issue type was not recognized, default value was applied"
            )
        if self.jira and task.project:
            types = self.jira.issue_types_for_project(task.project)
            if not types:
                types = [task.issue_type] if task.issue_type else ["Task"]
        else:
            types = [task.issue_type] if task.issue_type else ["Task"]

        self.type_combo.addItems(types)

        if task.issue_type in types:
            self.type_combo.setCurrentText(task.issue_type)

        meta.addWidget(QLabel(tr(lang, "review_type")))
        meta.addWidget(self.type_combo)

        self.assignee_edit = AutocompleteLineEdit(
            task.assignee_query or "",
            suggestion_fn=self._assignee_suggestions,
            on_select_fn=self._on_assignee_selected,
            parent=self,
        )
        if getattr(task, "assignee_fallback_used", False):
            self._mark_fallback(
                self.assignee_edit,
                "Assignee was not recognized, default value was applied"
            )
        meta.addWidget(QLabel(tr(lang, "review_assignee")))
        meta.addWidget(self.assignee_edit)

        self.estimate_edit = QLineEdit(
            getattr(task, "estimate_str", "") or getattr(
                self.task, "estimate_str", "") or DEFAULT_ESTIMATE
        )
        if getattr(task, "estimate_fallback_used", False):
            self._mark_fallback(
                self.estimate_edit,
                "Estimate was invalid, default value was applied"
            )
        self.estimate_edit.setPlaceholderText("30m / 2h / 1d / 1w")
        meta.addWidget(QLabel(tr(lang, "review_estimate")))
        meta.addWidget(self.estimate_edit)

        self.due_edit = QLineEdit(task.due_date or "")
        if getattr(task, "due_parse_failed", False):
            self._mark_fallback(
                self.due_edit,
                "Date was not recognized, default due date was applied"
            )
        self.due_edit.setPlaceholderText(
            "YYYY-MM-DD / tomorrow / 15 december 2026 / 15 декабря 2026")
        meta.addWidget(QLabel(tr(lang, "review_due")))
        meta.addWidget(self.due_edit)

        meta.setSpacing(10)
        meta.setStretch(1, 1)
        meta.setStretch(3, 1)
        meta.setStretch(5, 1)

        root.addLayout(meta)

        # --- Labels & Status row ---
        ls_row = QHBoxLayout()

        self.labels_edit = AutocompleteLineEdit(
            "; ".join(task.labels) if task.labels else "",
            suggestion_fn=self._label_suggestions,
            separator=";",
            parent=self,
        )
        self.labels_edit.setPlaceholderText("label1; label2")
        ls_row.addWidget(QLabel(tr(lang, "review_labels")))
        ls_row.addWidget(self.labels_edit, 2)

        self.status_edit = QLineEdit(getattr(task, "target_status", "") or "")
        self.status_edit.setPlaceholderText("e.g. In Progress")
        ls_row.addWidget(QLabel(tr(lang, "review_status_after_create")))
        ls_row.addWidget(self.status_edit, 1)

        root.addLayout(ls_row)

        # Raw line
        self.raw_label = QLabel(task.raw_line)
        self.raw_label.setWordWrap(True)
        self.raw_label.setProperty("class", "meta")
        self.raw_label.setStyleSheet("color: #777; font-size: 11px;")
        root.addWidget(self.raw_label)

        if self.jira:
            self.project_combo.currentIndexChanged.connect(
                self.refresh_issue_types)

        self.chk_add_to_jira.toggled.connect(self.on_include_toggled)
        self.on_include_toggled(self.chk_add_to_jira.isChecked())

    def on_include_toggled(self, checked: bool):
        self.edit_summary.setEnabled(checked)
        self.edit_description.setEnabled(checked)
        self.project_combo.setEnabled(checked)
        self.type_combo.setEnabled(checked)
        self.assignee_edit.setEnabled(checked)
        self.due_edit.setEnabled(checked)
        self.raw_label.setEnabled(checked)
        self.estimate_edit.setEnabled(checked)
        self.labels_edit.setEnabled(checked)
        self.status_edit.setEnabled(checked)

    def is_selected(self) -> bool:
        return self.chk_add_to_jira.isChecked()

    def refresh_issue_types(self):
        if not self.jira:
            return
        key = self.project_combo.currentData() or self.project_combo.currentText()
        current = self.type_combo.currentText()
        types = self.jira.issue_types_for_project(key) if key else []
        if not types:
            return
        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        self.type_combo.addItems(types)
        if current in types:
            self.type_combo.setCurrentText(current)
        self.type_combo.blockSignals(False)

    def to_task(self) -> ParsedTask:
        project = self.project_combo.currentData() or self.project_combo.currentText()
        issue_type = self.type_combo.currentText()
        summary = self.edit_summary.text().strip()
        description = self.edit_description.toPlainText().strip()
        assignee = self.assignee_edit.text().strip()
        due = self.due_edit.text().strip()
        raw = self.raw_label.text()
        estimate = self.estimate_edit.text().strip()

        if estimate and not QuickParser.validate_estimate(estimate):
            estimate = self.cfg.default_estimate
            self.estimate_edit.setStyleSheet("background:#fff3cd;")
        else:
            self.estimate_edit.setStyleSheet("")

        labels_text = self.labels_edit.text().strip()
        labels = [lb.strip() for lb in labels_text.split(";") if lb.strip()]
        target_status = self.status_edit.text().strip()

        return ParsedTask(
            raw_line=raw,
            summary=summary,
            description=description,
            project=project,
            issue_type=issue_type,
            assignee_query=assignee,
            assignee_account_id=None,
            due_str=due,
            due_date=due,
            estimate_str=estimate,
            labels=labels,
            target_status=target_status,
        )

    def _assignee_suggestions(self, prefix: str) -> List[str]:
        prefix_low = (prefix or "").strip().lower()

        if not prefix_low:
            # me + all hand-picked cached users
            results = ["me"]
            if self.jira:
                for dn, aid, email in self.jira._cached_users:
                    label = self.jira._format_user_label(dn, aid, email)
                    if label not in results:
                        results.append(label)
            return results[:20]

        results = ["me"] if "me".startswith(prefix_low) else []
        if not self.jira:
            return results
        try:
            users = self.jira.search_users_names(prefix)
        except Exception:
            users = []
        for dn, aid, email in users:
            label = self.jira._format_user_label(dn, aid, email)
            if label not in results:
                results.append(label)
        return results[:20]

    def _on_assignee_selected(self, label: str):
        if self.jira and label.strip().lower() != "me":
            self.jira.add_user_to_cache(label)

    def _label_suggestions(self, prefix: str) -> List[str]:
        if not self.jira:
            return []
        try:
            return self.jira.get_labels(prefix or "")
        except Exception:
            return []

    def _mark_fallback(self, widget, tooltip: str):
        widget.setStyleSheet("background:#fff3cd;")
        widget.setToolTip(tooltip)


class ReviewDialog(QDialog):
    """Scrollable dialog showing one :class:`ReviewTaskCard` per parsed task.

    The user can edit any field before clicking *Create in Jira* (Ctrl+Enter).
    Unchecked cards are excluded from creation.  Accepted via :meth:`as_rows`.
    """

    def __init__(self, items: List[ParsedTask], jira: Optional[JiraClient], cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.jira = jira
        self.cards: List[ReviewTaskCard] = []
        self.resize(900, 700)

        lang = getattr(cfg, "language", "en")

        root = QVBoxLayout(self)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(8, 8, 8, 8)
        self.container_layout.setSpacing(10)

        for item in items:
            card = ReviewTaskCard(item, jira, cfg, self.container)
            self.cards.append(card)
            self.container_layout.addWidget(card)

        self.container_layout.addStretch()
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll)

        btns = QHBoxLayout()
        self.btn_create = QPushButton(tr(lang, "review_create"))
        self.btn_cancel = QPushButton(tr(lang, "review_cancel"))
        btns.addStretch()
        btns.addWidget(self.btn_create)
        btns.addWidget(self.btn_cancel)
        root.addLayout(btns)

        self.setWindowTitle(tr(lang, "review_title"))
        self.btn_create.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        # keyboard shortcuts
        _act_create = QAction(self)
        _act_create.setShortcut(QKeySequence("Ctrl+Return"))
        _act_create.triggered.connect(self.accept)
        self.addAction(_act_create)
        _act_create2 = QAction(self)
        _act_create2.setShortcut(QKeySequence("Ctrl+Enter"))
        _act_create2.triggered.connect(self.accept)
        self.addAction(_act_create2)

    def as_rows(self) -> List[ParsedTask]:
        return [card.to_task() for card in self.cards if card.is_selected()]


# --------------------------- UI: Main Window ---------------------------
class MainWindow(QMainWindow):
    """The primary input window shown when the user opens the app.

    Contains a :class:`SmartTaskEdit` for typing tasks, a *Parse* button
    (Ctrl+Enter) that opens :class:`ReviewDialog`, and a *Settings* button.

    The window hides (rather than closes) on the X button and the Cancel button
    so the tray icon remains the sole exit point.  If *Stay on top* is enabled
    in settings the window floats above other windows and becomes semi-transparent
    when it loses focus (configurable transparency level).
    """

    def __init__(self, cfg_mgr: ConfigManager):
        super().__init__()
        self.cfg_mgr = cfg_mgr
        self.cfg = cfg_mgr.config
        self._warmup_thread = None
        self._warmup_worker = None
        self._hotkey_manager = HotkeyManager()

        self.jira = JiraClient(self.cfg) if self.cfg.is_complete() else None
        if self.jira:
            self.start_jira_warmup()

        self.setWindowTitle(
            f"{tr(self.cfg.language, 'main_title')} v{APP_VERSION}")
        self.resize(750, 420)
        saved_geom = getattr(self.cfg, "main_window_geometry", "")
        if saved_geom:
            try:
                from PySide6.QtCore import QByteArray
                self.restoreGeometry(
                    QByteArray.fromBase64(saved_geom.encode()))
            except Exception:
                pass

        central = QWidget()
        v = QVBoxLayout(central)
        self.setCentralWidget(central)

        self.input = SmartTaskEdit(self, self)
        v.addWidget(self.input, 1)

        h = QHBoxLayout()
        self.chk_multi_task = QCheckBox()
        self.chk_multi_task.setChecked(
            getattr(self.cfg, "multi_task_mode", True))
        self.btn_parse = QPushButton()
        self.btn_settings = QPushButton()
        self.btn_quit = QPushButton()
        h.addWidget(self.chk_multi_task)
        h.addWidget(self.btn_parse)
        h.addStretch(1)
        h.addWidget(self.btn_settings)
        h.addWidget(self.btn_quit)
        v.addLayout(h)

        self.addAction(self._mk_shortcut("Ctrl+Return", self.on_parse))
        self.addAction(self._mk_shortcut("Ctrl+Enter", self.on_parse))

        self.btn_parse.clicked.connect(self.on_parse)
        self.btn_settings.clicked.connect(self.on_settings)
        self.btn_quit.clicked.connect(self.hide)
        self.chk_multi_task.toggled.connect(self._on_multi_task_changed)

        self.apply_language()
        self._apply_window_flags()
        self._apply_hotkey()

    def _mk_shortcut(self, seq: str, slot):
        act = QAction(self)
        act.setShortcut(QKeySequence(seq))
        act.triggered.connect(slot)
        return act

    def closeEvent(self, event):
        self._save_geometry()
        event.ignore()
        self.hide()

    def _save_geometry(self):
        try:
            geom_bytes = self.saveGeometry().toBase64().data().decode()
            self.cfg.main_window_geometry = geom_bytes
            self.cfg_mgr.save()
        except Exception:
            pass

    def hideEvent(self, event):
        self._save_geometry()
        super().hideEvent(event)

    def _on_multi_task_changed(self, checked: bool):
        self.cfg.multi_task_mode = checked
        self.cfg_mgr.save()
        self._update_placeholder()

    def _update_placeholder(self):
        lang = getattr(self.cfg, "language", "en")
        multi = getattr(self.cfg, "multi_task_mode", True)
        key = "main_placeholder" if multi else "main_placeholder_single"
        self.input.setPlaceholderText(tr(lang, key))

    def apply_language(self):
        lang = getattr(self.cfg, "language", "en")

        self.setWindowTitle(f"{tr(lang, 'main_title')} v{APP_VERSION}")
        self.chk_multi_task.setText(tr(lang, "main_multi_task"))
        self._update_placeholder()

        self.btn_parse.setText(tr(lang, "main_parse"))
        self.btn_settings.setText(tr(lang, "main_settings"))
        self.btn_quit.setText(tr(lang, "main_cancel"))

    # --- Window flags / transparency / hotkey ---

    def _apply_window_flags(self):
        flags = self.windowFlags()
        if getattr(self.cfg, "stay_on_top", False):
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        if was_visible:
            self.show()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange:
            if getattr(self.cfg, "stay_on_top", False):
                if self.isActiveWindow():
                    self.setWindowOpacity(1.0)
                else:
                    pct = getattr(self.cfg, "inactivity_transparency", 30)
                    self.setWindowOpacity(max(0.05, (100 - pct) / 100.0))

    def _apply_hotkey(self):
        app = QApplication.instance()
        self._hotkey_manager.unregister(app)
        if getattr(self.cfg, "global_hotkey_enabled", False):
            hotkey = getattr(self.cfg, "global_hotkey", "Alt+Shift+M")
            self._hotkey_manager.register(app, hotkey, self._on_hotkey)

    def _on_hotkey(self):
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()
        self.activateWindow()

    # --- Actions ---
    def on_settings(self):
        dlg = SettingsDialog(self.cfg, self.jira, self)
        if dlg.exec() == QDialog.Accepted:
            self.cfg_mgr.save()

            self.cfg = self.cfg_mgr.config
            self.jira = JiraClient(
                self.cfg) if self.cfg.is_complete() else None

            self.apply_language()
            self._apply_window_flags()
            self._apply_hotkey()

            if self.jira:
                self.start_jira_warmup()

    def on_parse(self):
        lang = getattr(self.cfg, "language", "en")

        text = self.input.toPlainText().strip()
        if not text:
            QMessageBox.information(
                self,
                tr(lang, "msg_empty_title"),
                tr(lang, "msg_empty_text"),
            )
            return

        parser = QuickParser(self.jira, self.cfg)
        multi = getattr(self.cfg, "multi_task_mode", True)
        items = parser.parse_many(
            text) if multi else parser.parse_single_task(text)
        if not any(i.summary for i in items):
            QMessageBox.warning(
                self,
                tr(lang, "msg_parse_failed_title"),
                tr(lang, "msg_parse_failed_text"),
            )
            return

        # Pre-resolve assignees to accountId when possible
        if self.jira:
            for it in items:
                if not it.assignee_account_id and it.assignee_query:
                    it.assignee_account_id = self.jira.find_assignee(
                        it.assignee_query)

        review = ReviewDialog(items, self.jira, self.cfg, self)
        if review.exec() == QDialog.Accepted:
            rows = review.as_rows()
            self._create_in_jira(rows)
            self.input.clear()

    def _create_in_jira(self, rows: List[ParsedTask]):
        lang = getattr(self.cfg, "language", "en")

        if not self.cfg.is_complete():
            QMessageBox.critical(
                self,
                tr(lang, "msg_no_settings_title"),
                tr(lang, "msg_no_settings_text"),
            )
            return

        if self.jira is None:
            self.jira = JiraClient(self.cfg)

        ok, failed = [], []
        for r in rows:
            assignee_id = self.jira.find_assignee(
                r.assignee_query) if r.assignee_query else None
            due_iso = r.due_date
            if due_iso and len(due_iso) != 10:
                due_iso = QuickParser._nl_date_to_iso(r.due_date) or None

            estimate_text = (r.estimate_str or "").strip()
            if estimate_text and not QuickParser.validate_estimate(estimate_text):
                estimate_text = getattr(
                    self.cfg, "default_estimate", DEFAULT_ESTIMATE)

            labels = list(getattr(r, "labels", []) or [])
            if not labels:
                default_labels_str = getattr(self.cfg, "default_labels", "")
                if default_labels_str:
                    labels = [lb.strip()
                              for lb in default_labels_str.split(";") if lb.strip()]

            target_status = (getattr(r, "target_status", "") or "").strip()
            if not target_status:
                target_status = getattr(self.cfg, "default_status", "").strip()

            try:
                key = self.jira.create_issue(
                    r.project, r.summary, r.issue_type, assignee_id, due_iso,
                    r.description, estimate_text, labels or None
                )
                if target_status:
                    self.jira.transition_issue(key, target_status)
                ok.append((r.summary, key))
                self.jira.add_favorite_project(r.project)
                append_history(key, r.summary, self.cfg.jira_url)
            except Exception as e:
                failed.append((r.summary, str(e)))

        base = self.cfg.jira_url.rstrip("/")
        parts = []
        if ok:
            parts.append(f"<b>{tr(lang, 'result_created')}</b><br>")
            for s, k in ok:
                url = f"{base}/browse/{k}"
                parts.append(
                    f"&nbsp;&nbsp;<a href=\"{url}\">{k}</a> — {escape(s)}<br>")
        if failed:
            parts.append(f"<br><b>{tr(lang, 'result_errors')}</b><br>")
            for s, err in failed:
                parts.append(f"&nbsp;&nbsp;{escape(s)} — {escape(err)}<br>")

        html_msg = "<html><body>" + \
            ("".join(parts) or tr(lang, "result_no_actions")) + "</body></html>"
        mb = QMessageBox(self)
        mb.setWindowTitle(tr(lang, "result_title"))
        mb.setTextFormat(Qt.RichText)
        mb.setText(html_msg)

        for lbl in mb.findChildren(QLabel):
            try:
                lbl.setOpenExternalLinks(True)
                lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
            except Exception:
                pass
        mb.exec()

    def start_jira_warmup(self):
        if not self.jira:
            return

        # skip if warmup thread is already running
        if hasattr(self, "_warmup_thread") and self._warmup_thread is not None:
            if self._warmup_thread.isRunning():
                return

        self._warmup_thread = QThread(self)
        self._warmup_worker = JiraWarmupWorker(self.jira)
        self._warmup_worker.moveToThread(self._warmup_thread)

        self._warmup_thread.started.connect(self._warmup_worker.run)
        self._warmup_worker.finished.connect(self.on_jira_warmup_finished)
        self._warmup_worker.failed.connect(self.on_jira_warmup_failed)

        self._warmup_worker.finished.connect(self._warmup_thread.quit)
        self._warmup_worker.failed.connect(self._warmup_thread.quit)

        self._warmup_thread.finished.connect(self._warmup_worker.deleteLater)
        self._warmup_thread.finished.connect(self._warmup_thread.deleteLater)

        self._warmup_thread.start()

    def on_jira_warmup_finished(self):
        print("Jira warmup completed")

        self._warmup_thread = None
        self._warmup_worker = None

    def on_jira_warmup_failed(self, error: str):
        print(f"Jira warmup failed: {error}")

        self._warmup_thread = None
        self._warmup_worker = None
# --------------------------- Tray ---------------------------


def build_app_icon() -> QIcon:
    """Build the application icon from the embedded base64 PNG.

    Falls back to a simple painted "J" glyph if decoding fails.
    The icon is used for the system tray, main window, and all dialogs.
    """
    try:
        raw = base64.b64decode(APP_ICON_B64)
        pm = QPixmap()
        pm.loadFromData(raw, "PNG")
        if not pm.isNull():
            return QIcon(pm)
    except Exception as e:
        print(f"Icon load failed: {e}")

    # Fallback: painted circle with "J"
    pm = QPixmap(32, 32)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(Qt.gray)
    p.drawEllipse(0, 0, 31, 31)
    p.setPen(Qt.white)
    f = QFont()
    f.setBold(True)
    f.setPointSize(14)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, "J")
    p.end()
    return QIcon(pm)


# --------------------------- Task History ---------------------------

HISTORY_FILE = os.path.join(user_config_dir(
    APP_NAME, roaming=True), "history.json")


def load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(entries: list):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def append_history(key: str, summary: str, jira_url: str):
    entries = load_history()
    entries.insert(0, {
        "key": key,
        "summary": summary,
        "url": f"{jira_url.rstrip('/')}/browse/{key}",
        "created_at": date.today().isoformat(),
    })
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    entries = [e for e in entries if e.get("created_at", "") >= cutoff]
    save_history(entries)


class TaskHistoryDialog(QDialog):
    """Shows tasks created in the last 30 days, newest first, with clickable links."""

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        lang = getattr(cfg, "language", "en")
        self.setWindowTitle(tr(lang, "history_title"))
        self.resize(700, 500)

        layout = QVBoxLayout(self)

        entries = load_history()
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        entries = [e for e in entries if e.get("created_at", "") >= cutoff]

        if not entries:
            lbl = QLabel(tr(lang, "history_empty"))
            lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl)
        else:
            from PySide6.QtWidgets import QTextBrowser
            browser = QTextBrowser()
            browser.setOpenExternalLinks(True)
            lines = []
            for e in entries:
                key = escape(e.get("key", ""))
                summary = escape(e.get("summary", ""))
                url = e.get("url", "")
                created = e.get("created_at", "")
                lines.append(
                    f'<p>{created} &nbsp; <a href="{url}">{key}</a> — {summary}</p>'
                )
            browser.setHtml("<html><body>" + "".join(lines) + "</body></html>")
            layout.addWidget(browser)

        btn_close = QPushButton(tr(lang, "history_close"))
        btn_close.clicked.connect(self.accept)
        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(btn_close)
        layout.addLayout(h)


class TrayApp:
    """System-tray controller that owns the :class:`MainWindow` lifecycle.

    Creates the tray icon, context menu, and wires global hotkey / autostart.
    The application quits only via the tray menu *Quit* action or
    :meth:`QApplication.quit` — closing :class:`MainWindow` merely hides it.
    """

    def __init__(self, app: QApplication, cfg_mgr: ConfigManager):
        self.app = app
        self.cfg_mgr = cfg_mgr
        self.window = MainWindow(cfg_mgr)
        # Build a guaranteed non-null tray icon
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(self.window, "QuickJira",
                                 "System tray is not available on this system.")
        tray_icon = build_app_icon()
        self.tray = QSystemTrayIcon(tray_icon, self.window)
        self.tray.setIcon(tray_icon)
        self.app.setWindowIcon(tray_icon)
        self.window.setWindowIcon(tray_icon)

        menu = QMenu()
        self.act_open = QAction(menu)
        self.act_settings = QAction(menu)
        self.act_history = QAction(menu)
        self.act_about = QAction(menu)
        self.act_quit = QAction(menu)
        menu.addAction(self.act_open)
        menu.addAction(self.act_settings)
        menu.addAction(self.act_history)
        menu.addSeparator()
        menu.addAction(self.act_about)
        menu.addSeparator()
        menu.addAction(self.act_quit)
        self.tray.setContextMenu(menu)

        self.tray.activated.connect(self.on_tray_activated)
        self.act_open.triggered.connect(self.show_window)
        self.act_settings.triggered.connect(self._on_settings)
        self.act_history.triggered.connect(self._on_history)
        self.act_about.triggered.connect(self._on_about)
        self.act_quit.triggered.connect(self.app.quit)
        self.app.aboutToQuit.connect(self._on_quit)
        self.tray.show()

        self.apply_language()

    def apply_language(self):
        lang = getattr(self.cfg_mgr.config, "language", "en")
        self.tray.setToolTip(tr(lang, "tray_tooltip"))
        self.act_open.setText(tr(lang, "tray_open"))
        self.act_settings.setText(tr(lang, "tray_settings"))
        self.act_history.setText(tr(lang, "tray_history"))
        self.act_about.setText(tr(lang, "tray_about"))
        self.act_quit.setText(tr(lang, "tray_quit"))

    def _on_history(self):
        dlg = TaskHistoryDialog(self.cfg_mgr.config, self.window)
        dlg.exec()

    def _on_about(self):
        lang = getattr(self.cfg_mgr.config, "language", "en")
        QMessageBox.information(
            self.window,
            tr(lang, "about_title"),
            tr(lang, "about_text"),
        )

    def _on_settings(self):
        self.window.on_settings()
        self.apply_language()

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window()

    def _on_quit(self):
        self.window._hotkey_manager.unregister(self.app)

    def show_window(self):
        self.window.setWindowOpacity(1.0)
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()


# --------------------------- Entry ---------------------------
def main():
    # HiDPI friendly
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    cfg_mgr = ConfigManager()
    tray = TrayApp(app, cfg_mgr)

    # Optional: auto-open on first run (no config)
    if not cfg_mgr.config.is_complete():
        tray.show_window()
        tray.window.on_settings()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
