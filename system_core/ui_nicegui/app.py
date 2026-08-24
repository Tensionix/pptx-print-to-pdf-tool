from __future__ import annotations

from pathlib import Path
from typing import Any
import atexit
import argparse
import ctypes
from ctypes import wintypes
import ipaddress
import json
import locale
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser

from nicegui import app as nicegui_app, run, ui  # type: ignore

AUDION_CANONICAL_TOOLTIP_DELAY_MS = 1500
AUDION_CANONICAL_TOOLTIP_HIDE_DELAY_MS = 100
AUDION_CANONICAL_TOOLTIP_TRANSITION_MS = 100


def install_audion_canonical_tooltip_defaults() -> None:
    try:
        from nicegui.elements.tooltip import Tooltip as NiceGuiTooltip  # type: ignore
    except Exception:
        return
    if getattr(NiceGuiTooltip, "_audion_canonical_tooltip_defaults", False):
        return
    original_init = NiceGuiTooltip.__init__

    def audion_tooltip_init(self: Any, text: str = "") -> None:
        original_init(self, text)
        self.props["delay"] = AUDION_CANONICAL_TOOLTIP_DELAY_MS
        self.props["hide-delay"] = AUDION_CANONICAL_TOOLTIP_HIDE_DELAY_MS
        self.props["transition-duration"] = AUDION_CANONICAL_TOOLTIP_TRANSITION_MS
        self.classes("audion-tooltip")

    NiceGuiTooltip.__init__ = audion_tooltip_init  # type: ignore[method-assign]
    NiceGuiTooltip._audion_canonical_tooltip_defaults = True  # type: ignore[attr-defined]


install_audion_canonical_tooltip_defaults()


AUDION_CANONICAL_UI_CSS = """
<style id="audion-canonical-tooltip-icon-style">
  html body .q-tooltip,
  html body .audion-tooltip {
    background: rgb(23, 33, 43) !important;
    background-color: rgb(23, 33, 43) !important;
    color: #f4f8fb !important;
    border: 1px solid rgba(88, 166, 255, 0.24) !important;
    border-radius: 8px !important;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.34) !important;
  }
  html body .q-icon.material-icons,
  html body .q-icon.material-symbols-outlined,
  html body .q-icon.material-symbols-rounded,
  html body i.material-icons,
  html body i.material-symbols-outlined,
  html body i.material-symbols-rounded,
  html body .q-btn .q-icon,
  html body .q-btn .material-icons,
  html body .q-btn .material-symbols-outlined,
  html body .q-btn .material-symbols-rounded,
  html body .q-field .q-field__append .q-icon,
  html body .q-field .q-field__prepend .q-icon,
  html body .q-item .q-icon,
  html body .q-menu .q-icon,
  html body .audion-label-icon,
  html body .audion-path-option-pin,
  html body .audion-select-option-pin {
    font-size: 14px !important;
    width: 14px !important;
    min-width: 14px !important;
    height: 14px !important;
    line-height: 14px !important;
  }
  html body .material-icons,
  html body .q-icon.material-icons {
    font-family: "Material Icons" !important;
  }
  html body .material-symbols-outlined,
  html body .q-icon.material-symbols-outlined {
    font-family: "Material Symbols Outlined" !important;
  }
  html body .material-symbols-rounded,
  html body .q-icon.material-symbols-rounded {
    font-family: "Material Symbols Rounded" !important;
  }
</style>
"""


def add_audion_canonical_ui_styles() -> None:
    ui.add_head_html(AUDION_CANONICAL_UI_CSS)



def audion_tooltip_path_text(path_value: Any) -> str:
    raw = str(path_value or "").strip()
    if not raw:
        return ""
    try:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        return str(path)
    except Exception:
        return raw


def audion_folder_button_tooltip(folder_id: str, path_value: Any) -> str:
    key = str(folder_id or "folder").strip().lower()
    path_text = audion_tooltip_path_text(path_value)
    if getattr(settings, "language", "ru") == "ru":
        descriptions = {
            "logs": "папку логов запусков и вывода терминала",
            "report": "папку отчётов и результатов операций",
            "reports": "папку отчётов и результатов операций",
            "config": "папку конфигурации проекта: manifest, GUI-настройки и кэши",
            "state": "папку рабочего состояния GUI",
            "project": "корневую папку проекта",
            "root": "корневую папку проекта",
            "data": "папку данных проекта",
            "pipeline": "папку pipeline-артефактов и промежуточных результатов",
            "github": "папку GitHub-артефактов проекта",
            "install": "папку install/runtime-артефактов проекта",
        }
        description = descriptions.get(key, f"папку {folder_id}")
        return f"Открыть {description}: {path_text}" if path_text else f"Открыть {description}."
    descriptions = {
        "logs": "the logs folder with run and terminal output",
        "report": "the reports/results folder",
        "reports": "the reports/results folder",
        "config": "the project config folder with manifest, GUI settings, and caches",
        "state": "the GUI state folder",
        "project": "the project root folder",
        "root": "the project root folder",
        "data": "the project data folder",
        "pipeline": "the pipeline artifacts and intermediate results folder",
        "github": "the project GitHub artifacts folder",
        "install": "the project install/runtime artifacts folder",
    }
    description = descriptions.get(key, f"the {folder_id} folder")
    return f"Open {description}: {path_text}" if path_text else f"Open {description}."


def audion_terminal_action_tooltip(action: str) -> str:
    key = str(action or "").strip().lower()
    if getattr(settings, "language", "ru") == "ru":
        tips = {
            "clear_terminal_window": "Очистить только видимое окно терминала. Файлы логов, отчёты и результаты операций не удаляются.",
            "expand": "Открыть терминал в большом окне, чтобы читать длинный вывод без тесной панели.",
            "expand_log": "Открыть терминал в большом окне, чтобы читать длинный вывод без тесной панели.",
            "pin_command": "Закрепить текущую команду в истории терминала для быстрого повторного запуска.",
            "unpin_command": "Открепить текущую команду от верхней части истории терминала.",
            "clear_history": "Очистить историю команд терминала. Закреплённые команды и файлы логов не удаляются.",
            "terminal_shell": "Выбрать оболочку, в которой будут запускаться команды терминала.",
            "terminal_history": "Выбрать ранее сохранённую или закреплённую команду терминала.",
            "terminal_command": "Команда, которая будет выполнена из выбранной рабочей папки.",
            "terminal_cwd": "Рабочая папка терминала. Команда будет запущена именно отсюда.",
            "pick_folder": "Выбрать рабочую папку терминала через системный диалог.",
            "terminal_run": "Запустить введённую команду в выбранной оболочке и рабочей папке.",
            "latest_report": "Открыть последний созданный отчёт, если он уже есть.",
            "command_preview": "Показать команду, которая будет запущена с текущими параметрами, без выполнения операции.",
            "report_view": "Открыть встроенный список отчётов без перехода в проводник.",
            "close": "Закрыть большое окно терминала и вернуться к основной панели.",
        }
    else:
        tips = {
            "clear_terminal_window": "Clear only the visible terminal window. Log files, reports, and operation results are not deleted.",
            "expand": "Open the terminal in a large window for reading long output comfortably.",
            "expand_log": "Open the terminal in a large window for reading long output comfortably.",
            "pin_command": "Pin the current terminal command for quick reuse.",
            "unpin_command": "Remove the current command from the pinned command list.",
            "clear_history": "Clear terminal command history. Pinned commands and log files are not deleted.",
            "terminal_shell": "Choose the shell used to run terminal commands.",
            "terminal_history": "Pick a saved or pinned terminal command.",
            "terminal_command": "Command to run from the selected working folder.",
            "terminal_cwd": "Terminal working folder. Commands are started from here.",
            "pick_folder": "Choose the terminal working folder with the system dialog.",
            "terminal_run": "Run the entered command in the selected shell and working folder.",
            "latest_report": "Open the latest generated report, if one exists.",
            "command_preview": "Show the command that would run with the current settings, without executing it.",
            "report_view": "Open the built-in reports list without switching to the file explorer.",
            "close": "Close the large terminal window and return to the main panel.",
        }
    return tips.get(key, key.replace("_", " ").strip())


UI_DIR = Path(__file__).resolve().parent
if str(UI_DIR) not in sys.path:
    sys.path.insert(0, str(UI_DIR))
CORE_DIR = UI_DIR.parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

try:
    from .ansi import strip_ansi
    from .ansi import terminal_html as build_terminal_html
    from .ansi import terminal_lines_html
    from .output_decode import decode_process_bytes
    from .workbench import (
        WorkbenchAdapter,
        WorkbenchConfig,
        WorkbenchHandlers,
        WorkbenchRenderer,
        WorkbenchRole,
        WORKBENCH_FEEDBACK_CSS,
        WORKBENCH_LAYOUT_CSS,
        WORKBENCH_OVERRIDE_CSS,
        canonical_role,
    )
except ImportError:  # pragma: no cover - direct script execution
    from ansi import strip_ansi  # type: ignore
    from ansi import terminal_html as build_terminal_html  # type: ignore
    from ansi import terminal_lines_html  # type: ignore
    from output_decode import decode_process_bytes  # type: ignore
    from workbench import (  # type: ignore
        WorkbenchAdapter,
        WorkbenchConfig,
        WorkbenchHandlers,
        WorkbenchRenderer,
        WorkbenchRole,
        WORKBENCH_FEEDBACK_CSS,
        WORKBENCH_LAYOUT_CSS,
        WORKBENCH_OVERRIDE_CSS,
        canonical_role,
    )

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


ROOT = Path(__file__).resolve().parents[2]
MAIN_PY = ROOT / "system_core" / "main.py"
GUI_SETTINGS_PATH = ROOT / "config" / "gui_settings.yaml"
PATH_HISTORY_PATH = ROOT / "config" / "path_history.json"
UI_COLORS_PATH = ROOT / "config" / "ui_colors.yaml"
PROGRESS_RE = re.compile(r"\[(\d+)/(\d+)\]")

FOLDERS = {
    "input": ROOT / "input",
    "output": ROOT / "output",
    "logs": ROOT / "logs",
    "config": ROOT / "config",
    "report": ROOT / "report",
    "state": ROOT / "state",
}

DEFAULT_THEME_ID = "code_dark"
MAX_TERMINAL_LINES = 2000
PATH_HISTORY_LIMIT = 100
PLAIN_TERMINAL_LOG = FOLDERS["logs"] / "gui_terminal_plain.log"

state: dict[str, Any] = {
    "running": False,
    "cancel": False,
    "progress": 0.0,
    "status": "",
    "lines": [],
    "raw_lines": [],
    "log_first_id": 0,
    "log_next_id": 0,
    "log_version": 0,
    "exit_code": None,
    "active_screen": "root",
    "process": None,
    "status_data": {},
    "source_path": str(FOLDERS["input"]),
    "destination_path": str(FOLDERS["output"]),
}

settings: dict[str, Any] = {
    "language": "ru",
    "theme": DEFAULT_THEME_ID,
    "emoji": False,
    "source_path": "",
    "destination_path": "",
}


def display_path(path_value: Any) -> str:
    text = str(path_value or "").strip()
    if not text:
        return ""
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(ROOT)
    except (OSError, ValueError):
        return str(path)
    return str(relative) or "."

LABELS = {
    "ru": {
        "title": "Audion PPTX Print to PDF",
        "workspace": "Рабочие папки",
        "operations": "Операции",
        "add_files": "ДОБАВИТЬ ФАЙЛЫ",
        "add_folder": "ДОБАВИТЬ ПАПКУ",
        "file_list": "File List",
        "file_list_button": "СПИСОК",
        "file_list_empty": "INPUT has no files.",
        "file_list_missing": "INPUT was not found: {path}",
        "clear_io": "СБРОСИТЬ I/O",
        "input": "INPUT",
        "output": "OUTPUT",
        "source_folder": "Источник",
        "target_folder": "Назначение",
        "clear_io_short": "Сбросить",
        "delete_io": "УДАЛИТЬ",
        "delete_io_short": "Удалить",
        "status": "Статус",
        "idle": "Ожидание",
        "running": "Выполняется",
        "done": "Готово",
        "error": "Ошибка",
        "ready": "Готов к запуску",
        "log": "Журнал операции",
        "logs": "LOGS",
        "config": "CONFIG",
        "report": "REPORT",
        "state": "STATE",
        "expand": "РАЗВЕРНУТЬ",
        "clear_terminal_window": "Очистить окно терминала",
        "close": "Закрыть",
        "back": "НАЗАД",
        "run": "ЗАПУСТИТЬ",
        "refresh": "ОБНОВИТЬ",
        "cancel": "ОТМЕНИТЬ",
        "prepare": "ПОДГОТОВИТЬ ПРИНТЕР",
        "print": "ПЕЧАТАТЬ PPTX ИЗ INPUT",
        "crop": "ОБРЕЗАТЬ OUTPUT",
        "restore": "ВЕРНУТЬ ПРЕЖНИЙ ПРИНТЕР",
        "doctor": "DOCTOR",
        "prepare_title": "Подготовка принтера",
        "print_title": "Печать через Microsoft Print to PDF",
        "crop_title": "Обрезка PDF",
        "restore_title": "Возврат принтера",
        "doctor_title": "Проверка окружения",
        "skip_existing": "Пропускать PDF, которые уже есть",
        "post_crop": "Обрезка после печати",
        "crop_mode": "Режим обрезки",
        "crop_none": "Не обрезать",
        "crop_16_9": "Обрезать 16:9",
        "crop_a_series": "Обрезать A4/A3",
        "pdf_saved": "PDF СОХРАНЁН",
        "awaiting_print": "Ожидание запуска",
        "confirm_hint": "Когда появится диалог Microsoft Print to PDF, вставьте путь из буфера обмена и сохраните PDF. Затем вернитесь сюда и подтвердите.",
        "queue": "Очередь input",
        "workflow": "Рабочий порядок",
        "workflow_1": "Подготовить Microsoft Print to PDF как принтер по умолчанию.",
        "workflow_2": "Запустить guided-печать PPTX/PPTM из input.",
        "workflow_3": "В каждом диалоге сохранения вставить путь из буфера и подтвердить.",
        "workflow_4": "После сохранения нажать в GUI «PDF сохранён».",
        "workflow_5": "Обрезать готовые PDF и вернуть прежний принтер.",
        "prepare_desc": "Сохранить текущий принтер, включить Microsoft Print to PDF и выставить Legal landscape.",
        "print_desc": "GUI показывает ход, а кнопка подтверждает сохранение каждого PDF.",
        "crop_desc": "Обрезать все PDF в output на месте: 16:9 или A4/A3.",
        "restore_desc": "Восстановить принтер по умолчанию из сохранённого состояния.",
        "doctor_desc": "Проверить PowerShell, Microsoft Print to PDF, PowerPoint COM и зависимости.",
        "input_count": "PPTX/PPTM в input",
        "output_count": "PDF в output",
        "default_printer": "Принтер по умолчанию",
        "mptpdf": "Microsoft Print to PDF",
        "saved_printer": "Сохранённый принтер",
        "another_running": "Другая операция уже выполняется.",
        "operation_done": "Операция завершилась успешно",
        "operation_failed": "Операция завершилась с кодом {code}",
        "picker_cancelled": "Выбор отменён",
        "folder_only": "Нужна папка",
        "path_required": "Нужен путь",
        "path_pinned": "Путь закреплён",
        "path_unpinned": "Закрепление снято",
        "source_selected": "Источник выбран",
        "target_selected": "Назначение выбрано",
        "lang_switch": "EN",
        "theme_saved": "Тема сохранена",
        "empty_queue": "В input пока нет PPTX/PPTM.",
    },
    "en": {
        "title": "Audion PPTX Print to PDF",
        "workspace": "Workspace folders",
        "operations": "Operations",
        "add_files": "ADD FILES",
        "add_folder": "ADD FOLDER",
        "file_list": "File List",
        "file_list_button": "LIST",
        "file_list_empty": "INPUT has no files.",
        "file_list_missing": "INPUT was not found: {path}",
        "clear_io": "CLEAR I/O",
        "input": "INPUT",
        "output": "OUTPUT",
        "source_folder": "Source",
        "target_folder": "Target",
        "clear_io_short": "Reset",
        "delete_io": "CLEAR",
        "delete_io_short": "Delete",
        "status": "Status",
        "idle": "Idle",
        "running": "Running",
        "done": "Done",
        "error": "Error",
        "ready": "Ready to run",
        "log": "Operation log",
        "logs": "LOGS",
        "config": "CONFIG",
        "report": "REPORT",
        "state": "STATE",
        "expand": "EXPAND",
        "clear_terminal_window": "Clear terminal window",
        "close": "Close",
        "back": "BACK",
        "run": "RUN",
        "refresh": "REFRESH",
        "cancel": "CANCEL",
        "prepare": "PREPARE PRINTER",
        "print": "PRINT PPTX FROM INPUT",
        "crop": "CROP OUTPUT",
        "restore": "RESTORE PREVIOUS PRINTER",
        "doctor": "DOCTOR",
        "prepare_title": "Prepare Printer",
        "print_title": "Print via Microsoft Print to PDF",
        "crop_title": "Crop PDF",
        "restore_title": "Restore Printer",
        "doctor_title": "Environment Check",
        "skip_existing": "Skip PDFs that already exist",
        "post_crop": "Post-print crop",
        "crop_mode": "Crop mode",
        "crop_none": "Do not crop",
        "crop_16_9": "Crop 16:9",
        "crop_a_series": "Crop A4/A3",
        "pdf_saved": "PDF SAVED",
        "awaiting_print": "Waiting to start",
        "confirm_hint": "When Microsoft Print to PDF opens, paste the path from clipboard and save the PDF. Then return here and confirm.",
        "queue": "Input queue",
        "workflow": "Workflow",
        "workflow_1": "Prepare Microsoft Print to PDF as the default printer.",
        "workflow_2": "Start guided printing for PPTX/PPTM from input.",
        "workflow_3": "Paste the clipboard path in every save dialog and confirm.",
        "workflow_4": "After saving, click PDF saved in the GUI.",
        "workflow_5": "Crop finished PDFs and restore the previous printer.",
        "prepare_desc": "Save the current printer, enable Microsoft Print to PDF, and set Legal landscape.",
        "print_desc": "Guided printing: GUI shows progress and the button confirms each saved PDF.",
        "crop_desc": "Crop all PDFs in output in place: 16:9 or A4/A3.",
        "restore_desc": "Restore the default printer from saved state.",
        "doctor_desc": "Check PowerShell, Microsoft Print to PDF, PowerPoint COM, and dependencies.",
        "input_count": "PPTX/PPTM in input",
        "output_count": "PDF in output",
        "default_printer": "Default printer",
        "mptpdf": "Microsoft Print to PDF",
        "saved_printer": "Saved printer",
        "another_running": "Another operation is already running.",
        "operation_done": "Operation completed successfully",
        "operation_failed": "Operation finished with code {code}",
        "picker_cancelled": "Selection cancelled",
        "folder_only": "Folder required",
        "path_required": "Path required",
        "path_pinned": "Path pinned",
        "path_unpinned": "Path unpinned",
        "source_selected": "Source selected",
        "target_selected": "Target selected",
        "lang_switch": "RU",
        "theme_saved": "Theme saved",
        "empty_queue": "No PPTX/PPTM in input yet.",
    },
}


def tr(key: str, **kwargs: Any) -> str:
    text = LABELS.get(settings["language"], LABELS["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text


def ensure_dirs() -> None:
    for folder in FOLDERS.values():
        folder.mkdir(parents=True, exist_ok=True)


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists() or yaml is None:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _yaml_string(value: Any) -> str:
    return "'" + str(value or "").replace("'", "''") + "'"


def load_settings() -> None:
    payload = load_yaml_file(GUI_SETTINGS_PATH)
    gui = payload.get("gui", payload) if isinstance(payload, dict) else {}
    if isinstance(gui, dict):
        language = str(gui.get("language", settings["language"])).lower()
        if language in {"ru", "en"}:
            settings["language"] = language
        settings["theme"] = str(gui.get("theme", settings["theme"]) or DEFAULT_THEME_ID)
        settings["emoji"] = bool(gui.get("emoji", settings["emoji"]))
    settings["source_path"] = ""
    settings["destination_path"] = ""
    if not state.get("_workspace_initialized"):
        state["source_path"] = ""
        state["destination_path"] = ""
        state["_workspace_initialized"] = True


def save_settings() -> None:
    GUI_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "gui:\n"
        f"  language: \"{settings['language']}\"\n"
        f"  theme: \"{settings['theme']}\"\n"
        f"  emoji: {str(bool(settings['emoji'])).lower()}\n"
        "  allow_runtime_switching: true\n"
        "  advanced_open: false\n"
        f"  source_path: {_yaml_string("")}\n"
        f"  destination_path: {_yaml_string("")}\n"
    )
    GUI_SETTINGS_PATH.write_text(text, encoding="utf-8", newline="\n")


def current_source_path() -> Path:
    return Path(str(state.get("source_path") or FOLDERS["input"]))


def current_target_path() -> Path:
    return Path(str(state.get("destination_path") or FOLDERS["output"]))


def presentation_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source] if source.suffix.casefold() in {".pptx", ".pptm"} else []
    if source.is_dir():
        return sorted(source.glob("*.pptx")) + sorted(source.glob("*.pptm"))
    return []


def save_workspace_path(role: str, path_text: Any) -> None:
    normalized = str(path_text or "").strip().strip('"')
    if normalized:
        selected = Path(normalized).expanduser()
        if canonical_role(role) == "target":
            selected.mkdir(parents=True, exist_ok=True)
        normalized = str(selected)
    if canonical_role(role) == "target":
        state["destination_path"] = normalized
    else:
        state["source_path"] = normalized
def themes() -> dict[str, dict[str, Any]]:
    data = load_yaml_file(UI_COLORS_PATH)
    items = data.get("themes", {}) if isinstance(data, dict) else {}
    return items if isinstance(items, dict) else {}


def theme_data() -> dict[str, Any]:
    catalog = themes()
    return dict(catalog.get(settings["theme"]) or catalog.get(DEFAULT_THEME_ID) or {})


def theme_options() -> dict[str, str]:
    result: dict[str, str] = {}
    for theme_id, data in themes().items():
        label_key = "label_ru" if settings["language"] == "ru" else "label"
        result[theme_id] = str(data.get(label_key) or data.get("label") or theme_id)
    return result or {DEFAULT_THEME_ID: "Code Dark"}


def theme_tokens() -> dict[str, str]:
    data = theme_data()
    tokens = data.get("tokens", {}) if isinstance(data, dict) else {}
    result = {str(key): str(value) for key, value in dict(tokens).items()} if isinstance(tokens, dict) else {}
    defaults = {
        "color-background-primary": "#141413",
        "color-background-secondary": "#1f1e1a",
        "color-background-tertiary": "#0f0f0e",
        "color-text-primary": "#faf9f5",
        "color-text-secondary": "#e8e6dc",
        "color-text-tertiary": "#b0aea5",
        "color-border-tertiary": "rgba(250, 249, 245, 0.18)",
        "color-border-secondary": "rgba(250, 249, 245, 0.36)",
        "color-accent-primary": "#d97757",
        "font-sans": "Inter, Segoe UI, Arial, sans-serif",
        "font-mono": "Cascadia Mono, Consolas, monospace",
        "border-radius-md": "8px",
    }
    return {**defaults, **result}


def add_log(message: str, *, preserve_empty: bool = False) -> None:
    text = str(message)
    if text == "":
        if preserve_empty:
            _append_log_line("")
        return
    if not preserve_empty and not text.strip():
        return
    lines = text.rstrip("\r\n").splitlines()
    if not lines and preserve_empty:
        _append_log_line("")
        return
    for raw_line in lines:
        _append_log_line(raw_line)


def _append_log_line(raw_line: str) -> None:
    plain_line = strip_ansi(raw_line).rstrip("\r\n")
    state["log_next_id"] = int(state["log_next_id"]) + 1
    state["raw_lines"].append(raw_line.rstrip("\r\n"))
    state["lines"].append(plain_line)
    excess = max(0, len(state["raw_lines"]) - MAX_TERMINAL_LINES)
    if excess:
        state["raw_lines"] = state["raw_lines"][excess:]
        state["lines"] = state["lines"][excess:]
        state["log_first_id"] = int(state["log_first_id"]) + excess
    _append_plain_terminal_log(plain_line)
    state["log_version"] = int(state["log_version"]) + 1
    match = PROGRESS_RE.search(plain_line)
    if match and plain_line.startswith(("[OK]", "[WARN]", "[INFO]")):
        index = int(match.group(1))
        total = max(1, int(match.group(2)))
        state["progress"] = max(float(state["progress"]), min(0.98, index / total))


def _append_plain_terminal_log(line: str) -> None:
    try:
        PLAIN_TERMINAL_LOG.parent.mkdir(parents=True, exist_ok=True)
        with PLAIN_TERMINAL_LOG.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
    except Exception as exc:
        logging.warning("Could not append GUI terminal plain log: %s", exc)


def reset_log_history() -> None:
    state["lines"] = []
    state["raw_lines"] = []
    state["log_first_id"] = 0
    state["log_next_id"] = 0
    state["log_version"] = int(state["log_version"]) + 1
    try:
        PLAIN_TERMINAL_LOG.parent.mkdir(parents=True, exist_ok=True)
        PLAIN_TERMINAL_LOG.write_text("", encoding="utf-8")
    except Exception as exc:
        logging.warning("Could not reset GUI terminal plain log: %s", exc)


def terminal_html() -> str:
    return build_terminal_html(list(state["raw_lines"]), start_id=int(state["log_first_id"]))


def terminal_inner_html() -> str:
    return terminal_lines_html(list(state["raw_lines"]), start_id=int(state["log_first_id"]))


def terminal_append_html(from_line_id: int) -> str:
    first_id = int(state["log_first_id"])
    start_index = max(0, from_line_id - first_id)
    return terminal_lines_html(
        list(state["raw_lines"]),
        leading_newline=start_index > 0,
        start_id=first_id,
        skip=start_index,
    )


def terminal_update_js(mode: str, html: str) -> str:
    payload = json.dumps({"mode": mode, "html": html, "maxLines": MAX_TERMINAL_LINES}, ensure_ascii=False)
    return f"""
    (() => {{
      const payload = {payload};
      const removeLine = (line) => {{
        const next = line.nextSibling;
        const previous = line.previousSibling;
        line.remove();
        if (next && next.nodeType === Node.TEXT_NODE) {{
          next.textContent = next.textContent.replace(/^\\n/, '');
          if (next.textContent === '') next.remove();
        }} else if (previous && previous.nodeType === Node.TEXT_NODE) {{
          previous.textContent = previous.textContent.replace(/\\n$/, '');
          if (previous.textContent === '') previous.remove();
        }}
      }};
      document.querySelectorAll('.audion-terminal').forEach((terminal) => {{
        const pre = terminal.querySelector('.audion-terminal-pre');
        if (!pre) return;
        const distanceToBottom = terminal.scrollHeight - terminal.scrollTop - terminal.clientHeight;
        const wasAtBottom = distanceToBottom <= 4;
        if (payload.mode === 'replace') {{
          pre.innerHTML = payload.html;
        }} else if (payload.html) {{
          pre.insertAdjacentHTML('beforeend', payload.html);
        }}
        const lines = pre.querySelectorAll('[data-terminal-line]');
        const excess = lines.length - payload.maxLines;
        for (let index = 0; index < excess; index += 1) {{
          removeLine(lines[index]);
        }}
        if (wasAtBottom) {{
          terminal.scrollTop = terminal.scrollHeight;
        }}
      }});
    }})();
    """


def utf8_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def gui_terminal_env() -> dict[str, str]:
    env = utf8_subprocess_env()
    env.pop("NO_COLOR", None)
    env["CLICOLOR"] = "1"
    env["CLICOLOR_FORCE"] = "1"
    env["FORCE_COLOR"] = "1"
    env["AUDION_GUI_TERMINAL"] = "1"
    env["AUDION_SOURCE_PATH"] = str(current_source_path())
    env["AUDION_TARGET_PATH"] = str(current_target_path())
    return env


def is_python_command(command: list[str]) -> bool:
    if not command:
        return False
    executable = Path(command[0]).name.lower()
    return executable in {"python", "python.exe", "pythonw", "pythonw.exe", "py", "py.exe"}


def unbuffer_python_command(command: list[str]) -> list[str]:
    if not command:
        return command
    if not is_python_command(command):
        return command
    if "-u" in command[1:]:
        return command
    return [command[0], "-u", *command[1:]]


def windows_oem_encoding() -> str:
    if os.name != "nt":
        return ""
    try:
        import ctypes

        return f"cp{int(ctypes.windll.kernel32.GetOEMCP())}"
    except Exception:
        return ""


def windows_ansi_encoding() -> str:
    if os.name != "nt":
        return ""
    try:
        import ctypes

        return f"cp{int(ctypes.windll.kernel32.GetACP())}"
    except Exception:
        return ""


def decode_subprocess_bytes(data: bytes) -> str:
    return decode_process_bytes(data)


SPINNER_FRAME_CHARS = set("-\\|/ \t")


def _is_spinner_only_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and all(char in SPINNER_FRAME_CHARS for char in line)


def decoded_process_lines(raw_line: bytes | str) -> list[str]:
    text = str(raw_line) if isinstance(raw_line, str) else decode_process_bytes(raw_line)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for part in text.split("\n"):
        line = part.rstrip()
        if not line or _is_spinner_only_line(line):
            continue
        lines.append(line)
    return lines


def decode_utf16ish(data: bytes) -> str | None:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            return None
    sample = data[:200]
    if len(sample) < 4:
        return None
    even_nuls = sample[0::2].count(0) / max(1, len(sample[0::2]))
    odd_nuls = sample[1::2].count(0) / max(1, len(sample[1::2]))
    candidates: list[str] = []
    if odd_nuls > 0.25 and odd_nuls > even_nuls * 2:
        candidates.append("utf-16le")
    if even_nuls > 0.25 and even_nuls > odd_nuls * 2:
        candidates.append("utf-16be")
    for encoding in candidates:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def safe_notify(message: str, kind: str = "info", **notify_kwargs: Any) -> None:
    notify_type = str(notify_kwargs.pop("type", kind))
    options = {"message": str(message), "type": notify_type, **notify_kwargs}
    delivered = False
    for client in list(nicegui_app.clients()):
        if getattr(client, "_deleted", False) or not client.has_socket_connection:
            continue
        try:
            client.outbox.enqueue_message("notify", options, client.id)
            delivered = True
        except Exception as exc:
            logging.warning("Notification delivery failed: %s", exc)
    if delivered:
        return
    try:
        ui.notify(message, type=notify_type, **notify_kwargs)
    except RuntimeError as exc:
        message_text = str(exc)
        if "slot belongs to has been deleted" not in message_text and "current slot cannot be determined" not in message_text:
            raise
        logging.warning("NiceGUI notification skipped because no live client slot was available: %s", message)


def progress_text() -> str:
    return f"{round(max(0.0, min(1.0, float(state['progress']))) * 100):.0f}%"


def status_dot_classes() -> str:
    base = "audion-status-dot text-lg leading-none"
    if bool(state["running"]):
        return f"{base} text-sky-400 animate-pulse"
    if state.get("exit_code") is None:
        return f"{base} text-gray-500"
    return f"{base} {'text-green-400' if int(state.get('exit_code') or 0) == 0 else 'text-red-400'}"


def hidden_startupinfo() -> subprocess.STARTUPINFO | None:
    if os.name != "nt" or not hasattr(subprocess, "STARTUPINFO"):
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo


def hidden_creationflags() -> int:
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return int(subprocess.CREATE_NO_WINDOW)
    return 0


def hidden_subprocess_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    startupinfo = hidden_startupinfo()
    if startupinfo is not None:
        kwargs["startupinfo"] = startupinfo
    flags = hidden_creationflags()
    if flags:
        kwargs["creationflags"] = flags
    return kwargs


def run_command_sync(cmd: list[str]) -> int:
    cmd = unbuffer_python_command(cmd)
    rendered = " ".join(f'"{part}"' if " " in part else part for part in cmd)
    add_log("RUN: " + rendered)
    text_stream = is_python_command(cmd)
    process_kwargs: dict[str, Any] = {
        "cwd": str(ROOT),
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "env": gui_terminal_env(),
        **hidden_subprocess_kwargs(),
    }
    if text_stream:
        process_kwargs.update({"text": True, "encoding": "utf-8", "errors": "replace", "bufsize": 1})
    process = subprocess.Popen(cmd, **process_kwargs)
    state["process"] = process
    assert process.stdout is not None
    if text_stream:
        for chunk in iter(process.stdout.readline, ""):
            if state["cancel"]:
                process.terminate()
                add_log("Cancellation requested.")
                break
            if not chunk:
                break
            for line in decoded_process_lines(str(chunk)):
                add_log(line, preserve_empty=True)
    else:
        for chunk in iter(process.stdout.readline, b""):
            if state["cancel"]:
                process.terminate()
                add_log("Cancellation requested.")
                break
            if not chunk:
                break
            for line in decoded_process_lines(bytes(chunk)):
                add_log(line, preserve_empty=True)
    exit_code = int(process.wait())
    state["process"] = None
    return exit_code


def load_status_data_sync() -> dict[str, Any]:
    process = subprocess.run(
        [sys.executable, "-u", str(MAIN_PY), "status"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=gui_terminal_env(),
        **hidden_subprocess_kwargs(),
    )
    return json.loads(process.stdout) if process.stdout.strip() else {}


async def refresh_status_data() -> None:
    try:
        state["status_data"] = await run.io_bound(load_status_data_sync)
    except Exception as exc:
        add_log(f"STATUS ERROR: {exc}")


def get_status_value(path: list[str], default: str = "-") -> str:
    current: Any = state.get("status_data") or {}
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    value = str(current or "").strip()
    return value or default


def notify_result(exit_code: int) -> None:
    safe_notify(
        tr("operation_done") if exit_code == 0 else tr("operation_failed", code=exit_code),
        "positive" if exit_code == 0 else "negative",
    )


async def start_command(title: str, cmd: list[str], after: list[str] | None = None) -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return
    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {title}",
            "log_version": int(state["log_version"]) + 1,
            "exit_code": None,
        }
    )
    reset_log_history()
    started = time.perf_counter()
    try:
        exit_code = await run.io_bound(run_command_sync, cmd)
        if exit_code == 0 and after:
            state["status"] = f"{tr('running')}: {tr('crop')}"
            state["progress"] = 0.02
            exit_code = await run.io_bound(run_command_sync, after)
        elapsed = time.perf_counter() - started
        state["exit_code"] = exit_code
        state["progress"] = 1.0
        state["status"] = f"{tr('done') if exit_code == 0 else tr('error')}: {title} [{exit_code}] {elapsed:.1f}s"
        notify_result(exit_code)
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")
    finally:
        state["running"] = False
        await refresh_status_data()


def confirm_pdf_saved() -> None:
    process = state.get("process")
    if process is None or getattr(process, "stdin", None) is None:
        safe_notify(tr("awaiting_print"), "warning")
        return
    try:
        try:
            process.stdin.write("\n")
        except TypeError:
            process.stdin.write(b"\n")
        process.stdin.flush()
        add_log("[GUI] PDF saved confirmation sent.")
    except Exception as exc:
        safe_notify(str(exc), "negative")


PICKER_BOOTSTRAP = r"""
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class AudionDpiAwareness {
  [DllImport("user32.dll")]
  public static extern bool SetProcessDpiAwarenessContext(IntPtr dpiContext);
  [DllImport("shcore.dll")]
  public static extern int SetProcessDpiAwareness(int value);
}
"@
  try { [AudionDpiAwareness]::SetProcessDpiAwarenessContext([IntPtr](-4)) | Out-Null }
  catch { [AudionDpiAwareness]::SetProcessDpiAwareness(2) | Out-Null }
} catch {}
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
"""


def resolve_dialog_powershell() -> list[str]:
    candidates = [
        [str(ROOT / "system_core" / "powershell" / "pwsh.exe"), "-NoLogo", "-NoProfile", "-STA", "-Command"],
        ["pwsh.exe", "-NoLogo", "-NoProfile", "-STA", "-Command"],
        ["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command"],
    ]
    for candidate in candidates:
        if Path(candidate[0]).exists() or shutil.which(candidate[0]):
            return candidate
    raise RuntimeError("PowerShell was not found for the Windows picker.")


_PICKER_RUN_LOCK = threading.Lock()
_PICKER_JOB_LOCK = threading.Lock()
_PICKER_JOB_HANDLE: int | None = None


class _JobObjectBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JobObjectExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobObjectBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def close_picker_job() -> None:
    global _PICKER_JOB_HANDLE
    with _PICKER_JOB_LOCK:
        handle = _PICKER_JOB_HANDLE
        _PICKER_JOB_HANDLE = None
    if os.name == "nt" and handle:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(wintypes.HANDLE(handle))


def _picker_job_handle() -> int | None:
    global _PICKER_JOB_HANDLE
    if os.name != "nt":
        return None
    with _PICKER_JOB_LOCK:
        if _PICKER_JOB_HANDLE:
            return _PICKER_JOB_HANDLE
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            logging.warning("Could not create the Windows picker job: %s", ctypes.get_last_error())
            return None
        info = _JobObjectExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = 0x00002000
        configured = kernel32.SetInformationJobObject(
            wintypes.HANDLE(job),
            9,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not configured:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(wintypes.HANDLE(job))
            logging.warning("Could not configure the Windows picker job: %s", error)
            return None
        _PICKER_JOB_HANDLE = int(job)
        return _PICKER_JOB_HANDLE


def _assign_picker_to_job(process: subprocess.Popen[str]) -> None:
    handle = _picker_job_handle()
    if os.name != "nt" or not handle:
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    assigned = kernel32.AssignProcessToJobObject(
        wintypes.HANDLE(handle),
        wintypes.HANDLE(int(process._handle)),  # type: ignore[attr-defined]
    )
    if not assigned:
        logging.warning("Could not attach picker PID %s to its Windows job: %s", process.pid, ctypes.get_last_error())


def run_picker_script(script: str, failure_message: str) -> str:
    if not _PICKER_RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("A Windows picker is already open.")
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            [*resolve_dialog_powershell(), script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=hidden_creationflags(),
            startupinfo=hidden_startupinfo(),
        )
        _assign_picker_to_job(process)
        try:
            stdout, stderr = process.communicate(timeout=3600)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.communicate()
            raise RuntimeError("Windows picker timed out.") from exc
        if process.returncode != 0:
            raise RuntimeError(stderr.strip() or failure_message)
        return stdout
    finally:
        if process is not None and process.poll() is None:
            process.kill()
        _PICKER_RUN_LOCK.release()


atexit.register(close_picker_job)
nicegui_app.on_shutdown(close_picker_job)


def parse_picker_paths(text: str) -> list[Path]:
    payload = text.strip()
    if not payload:
        return []
    data = json.loads(payload)
    if isinstance(data, str):
        data = [data]
    return [Path(str(item)).resolve() for item in data if str(item).strip()]


def pick_single_file() -> list[Path]:
    script = PICKER_BOOTSTRAP + r"""
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'Choose one PowerPoint source file'
$dialog.Multiselect = $false
$dialog.Filter = 'PowerPoint (*.pptx;*.pptm)|*.pptx;*.pptm|All files (*.*)|*.*'
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  $dialog.FileName | ConvertTo-Json -Compress
}
"""
    return parse_picker_paths(run_picker_script(script, "File picker failed."))


def pick_folder(description: str = "Choose workspace folder", show_new_folder_button: bool = True) -> list[Path]:
    title = str(description).replace("'", "''")
    allow_new = "$true" if show_new_folder_button else "$false"
    script = PICKER_BOOTSTRAP + f"""
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '{title}'
$dialog.ShowNewFolderButton = {allow_new}
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
  @($dialog.SelectedPath) | ConvertTo-Json -Compress
}}
"""
    return parse_picker_paths(run_picker_script(script, "Folder picker failed."))


def input_file_list_lines(source: Path) -> list[str]:
    if not source.exists():
        return [tr("file_list_missing", path=source)]
    if source.is_file():
        names = [source.name]
    elif source.is_dir():
        names = sorted(
            (path.name for path in source.rglob("*") if path.is_file()),
            key=lambda item: item.casefold(),
        )
    else:
        return [f"Unsupported source path: {source}"]
    if not names:
        return [tr("file_list_empty")]

    number_width = max(3, len(str(len(names))))
    lines = [
        f"{'No.':>{number_width}}  List",
        f"{'-' * number_width}  ----",
    ]
    lines.extend(f"{index:0{number_width}d}. {name}" for index, name in enumerate(names, start=1))
    return lines


def show_input_file_list() -> int:
    lines = input_file_list_lines(current_source_path())
    for line in lines:
        add_log(line)
    return 0


async def show_input_file_list_click() -> None:
    await start_callable(tr("file_list"), show_input_file_list)


async def start_callable(title: str, func: Any) -> None:
    if state["running"]:
        safe_notify(tr("another_running"), "warning")
        return
    state.update({"running": True, "cancel": False, "progress": 0.02, "status": f"{tr('running')}: {title}", "log_version": int(state["log_version"]) + 1, "exit_code": None})
    reset_log_history()
    try:
        exit_code = await run.io_bound(func)
        state["exit_code"] = exit_code
        state["progress"] = 1.0
        state["status"] = f"{tr('done')}: {title} [{exit_code}]"
        notify_result(exit_code)
    except Exception as exc:
        state["exit_code"] = 1
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), "negative")
    finally:
        state["running"] = False
        await refresh_status_data()


def open_folder(folder_id: str) -> None:
    folder = FOLDERS[folder_id]
    folder.mkdir(parents=True, exist_ok=True)
    open_path(folder)


def absolute_project_path(path_value: Any) -> Path:
    path = Path(str(path_value or "")).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


def normalized_absolute_path(path_value: Any) -> Path:
    return absolute_project_path(path_value).resolve(strict=False)


def paths_equal(left: Any, right: Any) -> bool:
    return os.path.normcase(str(normalized_absolute_path(left))) == os.path.normcase(str(normalized_absolute_path(right)))


def open_path(path_value: Any) -> None:
    path = absolute_project_path(path_value)
    if path.is_file():
        if os.name == "nt":
            subprocess.Popen(
                ["explorer.exe", f"/select,{path}"],
                **hidden_subprocess_kwargs(),
            )
        else:
            webbrowser.open(path.parent.as_uri())
        return
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        webbrowser.open(path.as_uri())


def remove_path_tree(path: Path) -> int:
    is_junction = bool(getattr(os.path, "isjunction", lambda _path: False)(path))
    if path.is_symlink() or is_junction:
        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()
        return 1
    if path.is_file():
        path.unlink()
        return 1
    if path.is_dir():
        shutil.rmtree(path)
        return 1
    return 0


def clear_directory_contents(folder: Path) -> int:
    removed = 0
    if not folder.exists():
        return removed
    for child in sorted(folder.iterdir(), key=lambda item: item.name.casefold()):
        # .gitkeep is not spared: input and output must be genuinely empty after
        # a clear, so nobody has to wonder what the leftover file is or whether it
        # is safe to delete. The folders come from install/init_folders.cmd.
        removed += remove_path_tree(child)
    return removed


def validate_workspace_delete_target(path_value: Any) -> Path:
    target = normalized_absolute_path(path_value)
    if target.parent == target:
        raise RuntimeError(f"Refusing to delete a filesystem root: {target}")
    if paths_equal(target, ROOT):
        raise RuntimeError(f"Refusing to delete the project root: {target}")
    return target


def delete_workspace_path_contents(path_value: Any) -> dict[str, Any]:
    target = validate_workspace_delete_target(path_value)
    if not target.exists() and not target.is_symlink():
        return {"path": str(target), "kind": "missing", "removed": 0}
    is_junction = bool(getattr(os.path, "isjunction", lambda _path: False)(target))
    if target.is_file() or target.is_symlink() or is_junction:
        return {"path": str(target), "kind": "file", "removed": remove_path_tree(target)}
    if not target.is_dir():
        raise RuntimeError(f"Unsupported workspace path: {target}")
    return {"path": str(target), "kind": "folder", "removed": clear_directory_contents(target)}


def delete_workspace_io_contents(source: Path, target: Path) -> dict[str, Any]:
    source_result = delete_workspace_path_contents(source)
    target_result = (
        {"path": str(normalized_absolute_path(target)), "kind": "same", "removed": 0}
        if paths_equal(source, target)
        else delete_workspace_path_contents(target)
    )
    return {"source": source_result, "target": target_result}


def reload_ui(delay_ms: int = 0) -> None:
    delay = max(0, int(delay_ms))
    if delay:
        ui.run_javascript(f"window.setTimeout(() => window.location.reload(), {delay})")
    else:
        ui.run_javascript("window.location.reload()")


def open_workspace_folder(role: str) -> None:
    role_key = canonical_role(role)
    path = current_target_path() if role_key == "target" else current_source_path()
    if role_key == "source" and not path.exists():
        raise FileNotFoundError(f"Source path does not exist: {path}")
    open_path(path)


def mark_workspace_feedback(role: str, action: str) -> None:
    state["workspace_feedback"] = {"role": canonical_role(role), "action": str(action or "path")}


def _workspace_feedback() -> dict[str, str]:
    value = state.get("workspace_feedback")
    return dict(value) if isinstance(value, dict) else {}


def _clear_workspace_feedback() -> None:
    state["workspace_feedback"] = {}


WORKBENCH_CONFIG = WorkbenchConfig(
    root=ROOT,
    input_path=FOLDERS["input"],
    output_path=FOLDERS["output"],
    history_path=PATH_HISTORY_PATH,
    history_limit=PATH_HISTORY_LIMIT,
)
WORKBENCH_ADAPTER = WorkbenchAdapter(
    config=WORKBENCH_CONFIG,
    current_path_callback=lambda role: current_target_path() if role == "target" else current_source_path(),
    save_path_callback=save_workspace_path,
    language_callback=lambda: str(settings["language"]),
    translate_callback=tr,
    log_callback=add_log,
    notify_callback=safe_notify,
    reload_callback=reload_ui,
    busy_callback=lambda: bool(state.get("running")),
    feedback_callback=_workspace_feedback,
    set_feedback_callback=mark_workspace_feedback,
    clear_feedback_callback=_clear_workspace_feedback,
)
WORKBENCH_ADAPTER.validate()
WORKBENCH_ADAPTER.ensure_initial_history()


def workspace_pin_click_handler(role: str, pinned: bool):
    async def handler() -> None:
        path_value = str(current_target_path() if canonical_role(role) == "target" else current_source_path())
        if not path_value:
            safe_notify(WORKBENCH_ADAPTER.translate("path_required"), "warning")
            return
        try:
            await run.io_bound(WORKBENCH_ADAPTER.set_path_pinned, role, path_value, pinned)
            mark_workspace_feedback(role, "pin" if pinned else "unpin")
            add_log(f"{'Pinned' if pinned else 'Unpinned'} {canonical_role(role)} path: {path_value}")
            reload_ui(150)
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")

    return handler


def workspace_delete_path_click_handler(role: str):
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        role_key = canonical_role(role)
        path = current_target_path() if role_key == "target" else current_source_path()
        path_value = str(path)
        if not path_value:
            safe_notify(WORKBENCH_ADAPTER.translate("path_required"), "warning")
            return
        external_source = role_key == "source" and not paths_equal(path, FOLDERS["input"])
        if external_source:
            is_file = path.is_file()
            with ui.dialog() as dialog, ui.card().classes("audion-dialog rounded-lg"):
                title = "Удалить исходный файл?" if is_file else "Очистить внешний Источник?"
                warning = (
                    "Будет удалён исходный файл. Другой копии может не существовать."
                    if is_file
                    else "Будут безвозвратно удалены все файлы и вложенные папки."
                )
                if settings["language"] != "ru":
                    title = "Delete the source file?" if is_file else "Clear the external Source?"
                    warning = (
                        "The source file will be deleted. Another copy may not exist."
                        if is_file
                        else "All files and nested folders will be permanently deleted."
                    )
                ui.label(title).classes("text-base font-semibold")
                ui.label(warning).classes("text-sm text-gray-300")
                ui.label(str(normalized_absolute_path(path))).classes("max-w-3xl break-all font-mono text-xs text-gray-400")
                with ui.row().classes("gap-2"):
                    ui.button(tr("cancel"), on_click=dialog.close).props("dense flat")
                    ui.button(WORKBENCH_ADAPTER.translate("delete_io_short"), on_click=lambda: dialog.submit(True)).props("dense color=negative")
            if not await dialog:
                return
        try:
            result = await run.io_bound(delete_workspace_path_contents, path)
            if result.get("kind") == "file":
                await run.io_bound(WORKBENCH_ADAPTER.delete_path_history, role_key, path_value)
                save_workspace_path(role_key, "")
            mark_workspace_feedback(role_key, "delete")
            add_log(
                f"Cleared {'TARGET' if role_key == 'target' else 'SOURCE'}: {result.get('path')} "
                f"[kind={result.get('kind')}, removed={result.get('removed', 0)}]"
            )
            reload_ui(150)
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")

    return handler


def workspace_single_file_click_handler():
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        try:
            selected = await run.io_bound(pick_single_file)
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")
            return
        if not selected:
            add_log(tr("picker_cancelled"))
            return
        path_value = str(selected[0])
        save_workspace_path("source", path_value)
        await run.io_bound(WORKBENCH_ADAPTER.remember_path, "source", path_value)
        mark_workspace_feedback("source", "path")
        add_log(f"SOURCE FILE -> {path_value}")
        reload_ui(150)

    return handler


def workspace_open_click_handler(role: str):
    async def handler() -> None:
        try:
            await run.io_bound(open_workspace_folder, role)
            role_key = canonical_role(role)
            path = current_target_path() if role_key == "target" else current_source_path()
            add_log(f"Opened {role_key} path: {path}")
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")

    return handler


def reset_workspace_paths_click_handler():
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        result = await run.io_bound(WORKBENCH_ADAPTER.clear_path_history_cache_keep_pins)
        save_workspace_path("source", "")
        save_workspace_path("target", "")
        add_log(f"Workspace route reset: SOURCE -> {FOLDERS['input']}")
        add_log(f"Workspace route reset: TARGET -> {FOLDERS['output']}")
        add_log(
            "Workspace path cache cleared: "
            f"sources={result.get('removed_sources', 0)}, targets={result.get('removed_targets', 0)}, "
            f"pins kept={result.get('kept_pins', 0)}"
        )
        safe_notify(tr("operation_done"), "positive")
        reload_ui()

    return handler


def workspace_path_select_handler(role: str):
    async def handler(event: Any) -> None:
        path_value = str(getattr(event, "value", "") or "").strip()
        if not path_value:
            return
        role_key = canonical_role(role)
        current = current_target_path() if role_key == "target" else current_source_path()
        if paths_equal(current, path_value):
            return
        save_workspace_path(role_key, path_value)
        await run.io_bound(WORKBENCH_ADAPTER.remember_path, role_key, path_value)
        mark_workspace_feedback(role_key, "path")
        add_log(f"{'TARGET' if role_key == 'target' else 'SOURCE'} -> {path_value}")
        reload_ui(150)

    return handler


def workspace_delete_both_click_handler():
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        source = current_source_path()
        target = current_target_path()
        external_source = not paths_equal(source, FOLDERS["input"])
        with ui.dialog() as dialog, ui.card().classes("audion-dialog rounded-lg"):
            title = "Удалить содержимое Источника и Назначения?"
            warning = (
                "Внешний Источник может быть единственным экземпляром. Операция необратима."
                if external_source
                else "Все файлы Источника и Назначения будут удалены. Операция необратима."
            )
            if settings["language"] != "ru":
                title = "Delete Source and Target contents?"
                warning = (
                    "The external Source may be the only copy. This cannot be undone."
                    if external_source
                    else "All Source and Target files will be deleted. This cannot be undone."
                )
            ui.label(title).classes("text-base font-semibold")
            ui.label(warning).classes("text-sm text-gray-300")
            ui.label(f"SOURCE: {normalized_absolute_path(source)}").classes("max-w-3xl break-all font-mono text-xs text-gray-400")
            ui.label(f"TARGET: {normalized_absolute_path(target)}").classes("max-w-3xl break-all font-mono text-xs text-gray-400")
            with ui.row().classes("gap-2"):
                ui.button(tr("cancel"), on_click=dialog.close).props("dense flat")
                ui.button(WORKBENCH_ADAPTER.translate("delete_io_short"), on_click=lambda: dialog.submit(True)).props("dense color=negative")
        if not await dialog:
            return
        state["running"] = True
        try:
            result = await run.io_bound(delete_workspace_io_contents, source, target)
            source_result = result.get("source", {})
            target_result = result.get("target", {})
            if source_result.get("kind") == "file":
                await run.io_bound(WORKBENCH_ADAPTER.delete_path_history, "source", str(source))
                save_workspace_path("source", "")
            if target_result.get("kind") == "file":
                await run.io_bound(WORKBENCH_ADAPTER.delete_path_history, "target", str(target))
                save_workspace_path("target", "")
            add_log(f"Cleared SOURCE: {source_result.get('path')} [removed={source_result.get('removed', 0)}]")
            add_log(f"Cleared TARGET: {target_result.get('path')} [removed={target_result.get('removed', 0)}]")
            mark_workspace_feedback("source", "delete")
            reload_ui(150)
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")
        finally:
            state["running"] = False

    return handler


def workspace_pick_click_handler(role: str):
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), "warning")
            return
        role_key = canonical_role(role)
        try:
            selected = await run.io_bound(
                pick_folder,
                WORKBENCH_ADAPTER.translate("target_folder" if role_key == "target" else "source_folder"),
                True,
            )
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), "negative")
            return
        if not selected:
            add_log(tr("picker_cancelled"))
            return
        path_value = str(selected[0])
        save_workspace_path(role_key, path_value)
        await run.io_bound(WORKBENCH_ADAPTER.remember_path, role_key, path_value)
        mark_workspace_feedback(role_key, "path")
        add_log(f"{'TARGET' if role_key == 'target' else 'SOURCE'} -> {path_value}")
        safe_notify(
            WORKBENCH_ADAPTER.translate("target_selected" if role_key == "target" else "source_selected"),
            "positive",
        )
        reload_ui(150)

    return handler


WORKBENCH_RENDERER = WorkbenchRenderer(
    adapter=WORKBENCH_ADAPTER,
    handlers=WorkbenchHandlers(
        delete_path=workspace_delete_path_click_handler,
        pin_path=workspace_pin_click_handler,
        select_path=workspace_path_select_handler,
        pick_path=workspace_pick_click_handler,
        open_path=workspace_open_click_handler,
        add_file=workspace_single_file_click_handler,
        reset_paths=reset_workspace_paths_click_handler,
        delete_io=workspace_delete_both_click_handler,
        list_files=show_input_file_list_click,
    ),
    display_path_callback=display_path,
)
def set_screen(screen: str) -> None:
    state["active_screen"] = screen
    operations_area.refresh()


def child_header(title: str, run_handler: Any | None = None) -> None:
    with ui.row().classes("w-full items-center gap-2 pb-1"):
        ui.button(tr("back"), on_click=lambda: set_screen("root")).props("dense flat no-wrap").classes("audion-action w-28 rounded-lg")
        ui.label(title).classes("min-w-0 flex-1 text-center text-base font-bold")
        if run_handler:
            ui.button(tr("run"), on_click=run_handler).props("dense flat no-wrap").classes("audion-action w-36 rounded-lg")
        else:
            ui.element("div").classes("w-36")


def command_row(label: str, description: str, screen: str) -> None:
    with ui.element("div").classes("audion-operation-row"):
        ui.button(label, on_click=lambda: set_screen(screen)).props("dense flat no-wrap").classes("audion-action audion-operation-button rounded-lg")
        ui.label(description).classes("audion-operation-description")


def direct_command(label: str, description: str, title: str, command: list[str]) -> None:
    async def handler() -> None:
        await start_command(title, command)

    with ui.element("div").classes("audion-operation-row"):
        ui.button(label, on_click=handler).props("dense flat no-wrap").classes("audion-action audion-operation-button rounded-lg")
        ui.label(description).classes("audion-operation-description")


@ui.refreshable
def operations_area() -> None:
    screen = str(state.get("active_screen") or "root")

    if screen == "prepare":
        async def submit() -> None:
            await start_command(tr("prepare_title"), [sys.executable, "-u", str(MAIN_PY), "enable-default"])
        with ui.column().classes("w-full gap-3"):
            child_header(tr("prepare_title"), submit)
            ui.label(tr("prepare_desc")).classes("text-sm text-gray-300")
        return

    if screen == "print":
        async def submit() -> None:
            cmd = [sys.executable, "-u", str(MAIN_PY), "print-input"]
            if bool(skip_existing.value):
                cmd.append("--skip-existing")
            after = None
            if str(post_crop.value) == "16:9":
                after = [sys.executable, "-u", str(MAIN_PY), "crop-output-aspect", "--mode", "16:9"]
            elif str(post_crop.value) == "a-series":
                after = [sys.executable, "-u", str(MAIN_PY), "crop-output-aspect", "--mode", "a-series"]
            await start_command(tr("print_title"), cmd, after)

        with ui.column().classes("w-full gap-3"):
            child_header(tr("print_title"), submit)
            with ui.column().classes("audion-panel w-full gap-3 p-3"):
                skip_existing = ui.checkbox(tr("skip_existing"), value=True).props("dense").classes("audion-checkbox-item")
                ui.label(tr("post_crop")).classes("text-sm font-semibold")
                post_crop = ui.radio(
                    {"none": tr("crop_none"), "16:9": tr("crop_16_9"), "a-series": tr("crop_a_series")},
                    value="16:9",
                ).props("inline dense").classes("audion-radio")
            with ui.column().classes("audion-panel w-full gap-2 p-3"):
                ui.label(tr("confirm_hint")).classes("text-sm text-gray-300")
                with ui.row().classes("w-full items-center gap-2"):
                    ui.button(tr("pdf_saved"), on_click=confirm_pdf_saved).props("dense flat no-wrap").classes("audion-action audion-confirm-button rounded-lg")
                    ui.label(tr("awaiting_print")).classes("text-xs text-gray-400")
            with ui.column().classes("audion-panel w-full gap-2 p-3"):
                ui.label(f"{tr('queue')}: {get_status_value(['counts', 'input_presentations'], '0')}").classes("text-sm font-semibold")
                files = presentation_files(current_source_path())
                if not files:
                    ui.label(tr("empty_queue")).classes("text-sm text-gray-400")
                for item in files[:10]:
                    ui.label(item.name).classes("text-xs font-mono text-gray-300")
        return

    if screen == "crop":
        async def submit() -> None:
            mode = str(crop_mode.value)
            await start_command(
                tr("crop_title"),
                [sys.executable, "-u", str(MAIN_PY), "crop-output-aspect", "--mode", mode],
            )
        with ui.column().classes("w-full gap-3"):
            child_header(tr("crop_title"), submit)
            with ui.column().classes("audion-panel w-full gap-3 p-3"):
                ui.label(tr("crop_mode")).classes("text-sm font-semibold text-center")
                crop_mode = ui.radio(
                    {"16:9": tr("crop_16_9"), "a-series": tr("crop_a_series")},
                    value="16:9",
                ).props("inline dense").classes("audion-radio")
        return

    if screen == "restore":
        async def submit() -> None:
            await start_command(tr("restore_title"), [sys.executable, "-u", str(MAIN_PY), "restore-default"])
        with ui.column().classes("w-full gap-3"):
            child_header(tr("restore_title"), submit)
            ui.label(tr("restore_desc")).classes("text-sm text-gray-300")
        return

    if screen == "doctor":
        async def submit() -> None:
            await start_command(tr("doctor_title"), [sys.executable, "-u", str(MAIN_PY), "doctor"])
        with ui.column().classes("w-full gap-3"):
            child_header(tr("doctor_title"), submit)
            ui.label(tr("doctor_desc")).classes("text-sm text-gray-300")
        return

    with ui.column().classes("w-full gap-3"):
        with ui.column().classes("audion-panel w-full gap-2 p-3"):
            ui.label(tr("workflow")).classes("text-base font-semibold")
            for index in range(1, 6):
                with ui.row().classes("audion-step-row w-full items-center gap-3"):
                    ui.label(str(index)).classes("audion-step-num")
                    ui.label(tr(f"workflow_{index}")).classes("text-sm text-gray-300")
        with ui.column().classes("audion-panel w-full gap-1 p-3"):
            direct_command(tr("prepare"), tr("prepare_desc"), tr("prepare_title"), [sys.executable, "-u", str(MAIN_PY), "enable-default"])
            command_row(tr("print"), tr("print_desc"), "print")
            command_row(tr("crop"), tr("crop_desc"), "crop")
            direct_command(tr("restore"), tr("restore_desc"), tr("restore_title"), [sys.executable, "-u", str(MAIN_PY), "restore-default"])
            command_row(tr("doctor"), tr("doctor_desc"), "doctor")


_application_css_cache: dict[str, str] = {}


def application_css(name: str) -> str:
    """A stylesheet that lives next to this module rather than inside it."""
    if name not in _application_css_cache:
        path = Path(__file__).resolve().with_name(name)
        _application_css_cache[name] = path.read_text(encoding="utf-8")
    return _application_css_cache[name]


def add_styles() -> None:
    add_audion_canonical_ui_styles()
    ui.add_head_html("<style>" + WORKBENCH_LAYOUT_CSS + WORKBENCH_OVERRIDE_CSS + "</style>")
    ui.add_head_html(WORKBENCH_FEEDBACK_CSS)
    variables = "\n".join(f"  --{key}: {value};" for key, value in sorted(theme_tokens().items()))
    ui.add_head_html(
        "<style>\n"
        ":root {\n"
        f"{variables}\n"
        "}\n"
        + application_css("theme.css")
        + "\n</style>\n"
    )


def status_card(label: str, value: str) -> Any:
    with ui.column().classes("audion-status-card gap-1"):
        ui.label(label).classes("text-xs text-gray-400")
        return ui.label(value).classes("text-sm font-bold")


def toggle_language() -> None:
    settings["language"] = "en" if settings["language"] == "ru" else "ru"
    save_settings()
    ui.run_javascript("window.location.reload()")


def set_theme(event: Any) -> None:
    settings["theme"] = str(getattr(event, "value", None) or DEFAULT_THEME_ID)
    save_settings()
    safe_notify(tr("theme_saved"), "positive")
    ui.run_javascript("window.location.reload()")


def build_ui() -> None:
    ensure_dirs()
    load_settings()
    state["status"] = state["status"] or tr("idle")
    if str(theme_data().get("mode", "dark")) == "dark":
        ui.dark_mode().enable()
    else:
        ui.dark_mode().disable()
    add_styles()

    with ui.header().classes("audion-header h-[42px] items-center justify-between px-4"):
        ui.label(tr("title")).classes("audion-header-title text-lg font-bold")
        with ui.row().classes("audion-header-controls items-center gap-2"):
            ui.icon("palette").classes("text-lg")
            ui.select(theme_options(), value=settings["theme"], on_change=set_theme).props("dense outlined options-dense").classes("audion-theme-select")
            ui.button(tr("lang_switch"), on_click=toggle_language).props("dense flat").classes("audion-button rounded-lg")
            cancel_button = ui.button(tr("cancel"), on_click=lambda: state.update({"cancel": True})).props("dense flat color=negative")
            cancel_button.visible = False

    with ui.element("div").classes("audion-shell"):
        with ui.column().classes("audion-pane audion-scroll gap-3"):
            with ui.column().classes("audion-panel audion-workspace-panel w-full gap-2 p-2"):
                WORKBENCH_RENDERER.render_address_rows()
                WORKBENCH_RENDERER.render_action_bar()
            ui.label(tr("operations")).classes("text-lg font-bold")
            operations_area()

        with ui.element("div").classes("audion-pane audion-right"):
            with ui.column().classes("audion-panel w-full gap-2 p-3"):
                with ui.element("div").classes("audion-status-grid"):
                    input_count = status_card(tr("input_count"), "0")
                    output_count = status_card(tr("output_count"), "0")
                    default_printer = status_card(tr("default_printer"), "-")
                    mptpdf = status_card(tr("mptpdf"), "-")
                    saved_printer = status_card(tr("saved_printer"), "-")

            with ui.column().classes("audion-panel w-full gap-2 p-3"):
                with ui.row().classes("w-full items-center gap-3"):
                    ui.label(tr("status")).classes("text-base font-semibold")
                    status_label = ui.label(str(state["status"])).classes("min-w-0 flex-1 text-sm text-gray-300")
                with ui.row().classes("w-full items-center gap-3"):
                    progress = ui.linear_progress(value=0.0, show_value=False).classes("min-w-0 flex-1")
                    progress_label = ui.label(progress_text()).classes("w-12 text-right text-sm")

            with ui.column().classes("audion-terminal-panel w-full gap-2 p-3"):
                with ui.row().classes("w-full items-center gap-2"):
                    ui.label(tr("log")).classes("text-base font-semibold")
                    ui.space()
                    ui.button(tr("logs"), on_click=lambda: open_folder("logs")).props("dense flat").classes("audion-action rounded-lg").tooltip(audion_folder_button_tooltip("logs", FOLDERS.get("logs", "logs") if "FOLDERS" in globals() else "logs"))
                    ui.button(tr("config"), on_click=lambda: open_folder("config")).props("dense flat").classes("audion-action rounded-lg").tooltip(audion_folder_button_tooltip("config", FOLDERS.get("config", "config") if "FOLDERS" in globals() else "config"))
                    ui.button(tr("report"), on_click=lambda: open_folder("report")).props("dense flat").classes("audion-action rounded-lg").tooltip(audion_folder_button_tooltip("report", FOLDERS.get("report", "report") if "FOLDERS" in globals() else "report"))
                    ui.button(tr("state"), on_click=lambda: open_folder("state")).props("dense flat").classes("audion-action rounded-lg").tooltip(audion_folder_button_tooltip("state", FOLDERS.get("state", "state") if "FOLDERS" in globals() else "state"))
                    clear_log_button = ui.button(icon="delete_sweep", on_click=reset_log_history).props("dense flat round").classes("audion-action audion-log-icon-button")
                    clear_log_button.tooltip(audion_terminal_action_tooltip("clear_terminal_window"))
                    expand_log_button = ui.button(icon="open_in_full", on_click=lambda: log_dialog.open()).props("dense flat round").classes("audion-action audion-log-icon-button")
                    expand_log_button.tooltip(audion_terminal_action_tooltip("expand"))
                log_view = ui.html(terminal_html(), sanitize=False).classes("audion-terminal w-full")
                with ui.row().classes("audion-terminal-footer w-full items-center gap-2 px-1 pt-1"):
                    status_dot = ui.label("●").classes(status_dot_classes())
                    terminal_status_label = ui.label(str(state["status"])).classes("min-w-0 flex-1 truncate text-xs")

    with ui.dialog() as log_dialog:
        with ui.card().classes("h-[92vh] w-[92vw] rounded-lg p-3").style("background: var(--audion-terminal-bg);"):
            with ui.row().classes("w-full items-center gap-2"):
                ui.label(tr("log")).classes("text-base font-semibold")
                ui.space()
                clear_dialog_log_button = ui.button(icon="delete_sweep", on_click=reset_log_history).props("dense flat round").classes("audion-action audion-log-icon-button")
                clear_dialog_log_button.tooltip(audion_terminal_action_tooltip("clear_terminal_window"))
                ui.button(tr("close"), on_click=log_dialog.close).props("dense flat").classes("audion-action rounded-lg").tooltip(audion_terminal_action_tooltip("close"))
            expanded_log_view = ui.html(terminal_html(), sanitize=False).classes("audion-terminal w-full h-full")

    last_terminal_state = {"first_id": -1, "next_id": -1}
    refresh_timer: Any | None = None

    def refresh() -> None:
        nonlocal refresh_timer
        try:
            status_label.text = str(state["status"])
            terminal_status_label.text = str(state["status"])
            status_dot.classes(replace=status_dot_classes())
            progress.value = float(state["progress"])
            progress_label.text = progress_text()
            data = state.get("status_data") or {}
            input_count.text = str(data.get("counts", {}).get("input_presentations", 0)) if isinstance(data, dict) else "0"
            output_count.text = str(data.get("counts", {}).get("output_pdfs", 0)) if isinstance(data, dict) else "0"
            default_printer.text = get_status_value(["checks", "default_printer", "value"])
            mptpdf.text = "OK" if get_status_value(["checks", "microsoft_print_to_pdf", "value"]).lower() == "present" else get_status_value(["checks", "microsoft_print_to_pdf", "value"])
            saved_printer.text = get_status_value(["saved_printer"])
            first_id = int(state["log_first_id"])
            next_id = int(state["log_next_id"])
            if first_id != last_terminal_state["first_id"] or next_id != last_terminal_state["next_id"]:
                previous_next_id = int(last_terminal_state["next_id"])
                replace_terminal = (
                    previous_next_id < first_id
                    or previous_next_id > next_id
                    or last_terminal_state["first_id"] < 0
                )
                if replace_terminal:
                    ui.run_javascript(terminal_update_js("replace", terminal_inner_html()))
                else:
                    ui.run_javascript(terminal_update_js("append", terminal_append_html(previous_next_id)))
                last_terminal_state["first_id"] = first_id
                last_terminal_state["next_id"] = next_id
            cancel_button.visible = bool(state["running"])
        except RuntimeError as exc:
            message = str(exc)
            if "slot belongs to has been deleted" not in message and "current slot cannot be determined" not in message:
                raise
            logging.warning("NiceGUI refresh timer stopped because the client slot was deleted.")
            if refresh_timer is not None:
                refresh_timer.deactivate()

    refresh_timer = ui.timer(0.5, refresh)
    ui.timer(0.2, refresh_status_data, once=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audion PPTX Print to PDF NiceGUI shell.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8094)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args()


def port_is_open(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in str(host or "") else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            return sock.connect_ex((host, port)) == 0
    except OSError:
        return False


def env_flag_enabled(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def assert_gui_host_allowed(host: str) -> None:
    normalized = str(host or "").strip().lower().strip("[]")
    try:
        is_loopback = normalized == "localhost" or ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        is_loopback = normalized == "localhost"
    if is_loopback or env_flag_enabled("AUDION_ALLOW_REMOTE_GUI"):
        return
    raise SystemExit(
        "Refusing non-loopback host for a GUI with process execution. "
        "Use 127.0.0.1/localhost/::1, or set AUDION_ALLOW_REMOTE_GUI=1 explicitly."
    )


def build_ui_once() -> dict[str, int]:
    """Build the whole page once, headlessly, and report what came of it.

    `--smoke` used to print a line and return, so an app could ship a `build_ui`
    that raised on its first statement and still pass — twice in this fleet it did.
    Here the page is actually built: no browser and no HTTP request, so whatever
    the app defers until a client attaches is skipped, but every widget is
    constructed and the stylesheet has to arrive.
    """
    import asyncio
    import logging
    import re

    from nicegui import core
    from nicegui.client import Client
    from nicegui.page import page as page_definition

    async def build() -> tuple[int, str]:
        core.loop = asyncio.get_running_loop()
        # Work deferred to a connected browser fails here and says nothing about
        # the build. An exception raised by build_ui itself still propagates.
        core.loop.set_exception_handler(lambda _loop, _context: None)
        logging.getLogger("nicegui").setLevel(logging.CRITICAL)
        client = Client(page_definition("/__smoke__"))
        with client:
            build_ui()
        report = len(client.elements), client.shared_head_html + client.head_html
        # The page starts work that waits for a browser to attach. Nothing will
        # attach, so stop it deliberately instead of letting the loop close on it.
        pending = asyncio.all_tasks(core.loop) - {asyncio.current_task()}
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        return report

    element_count, head = asyncio.run(build())
    if element_count < 2:
        raise RuntimeError("build_ui produced no widgets")
    # Token prefixes differ between apps, so look for any custom property rather
    # than for one project's naming.
    if not re.search(r"--[\w-]+\s*:", head):
        raise RuntimeError("the stylesheet never reached the page")
    return {"elements": element_count, "stylesheet_bytes": len(head)}


def main() -> int:
    args = parse_args()
    assert_gui_host_allowed(args.host)
    ensure_dirs()
    if args.smoke:
        try:
            report = build_ui_once()
        except Exception as error:  # noqa: BLE001
            print(f"FAIL nicegui shell: {ROOT}: {error}")
            return 1
        print(
            f"OK nicegui shell: {ROOT}"
            f" | widgets={report['elements']}"
            f" | stylesheet={report['stylesheet_bytes']} bytes"
        )
        return 0
    if port_is_open(args.host, args.port):
        url = f"http://{args.host}:{args.port}/"
        print(f"Audion PPTX Print to PDF GUI already appears to be running: {url}")
        if not args.no_browser:
            webbrowser.open(url)
        return 0
    ui.run(
        root=build_ui,
        title="Audion PPTX Print to PDF",
        host=args.host,
        port=args.port,
        reload=False,
        native=False,
        show=not args.no_browser,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
