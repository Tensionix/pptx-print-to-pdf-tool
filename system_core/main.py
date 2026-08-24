from __future__ import annotations

import argparse
import json
import locale
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PS_SCRIPT = ROOT / "system_core" / "ps_scripts" / "pptx_print_tool.ps1"
CROP_SCRIPT = ROOT / "system_core" / "crop_pdf.py"
DOCTOR_SCRIPT = ROOT / "system_core" / "doctor.py"


def input_dir() -> Path:
    return Path(os.environ.get("AUDION_SOURCE_PATH") or ROOT / "input")


def output_dir() -> Path:
    return Path(os.environ.get("AUDION_TARGET_PATH") or ROOT / "output")


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


def resolve_powershell(root: Path = ROOT) -> list[str]:
    candidates = [
        root / "system_core" / "powershell" / "pwsh.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return [str(candidate), "-NoProfile"]

    for name in ("pwsh.exe", "pwsh", "powershell.exe", "powershell"):
        found = shutil_which(name)
        if found:
            if Path(found).name.lower().startswith("powershell"):
                return [found, "-NoProfile", "-ExecutionPolicy", "Bypass"]
            return [found, "-NoProfile"]

    raise RuntimeError("PowerShell was not found.")


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


def utf8_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def terminal_subprocess_env() -> dict[str, str]:
    env = utf8_subprocess_env()
    if env.get("AUDION_GUI_TERMINAL") == "1":
        env.pop("NO_COLOR", None)
        env["CLICOLOR"] = "1"
        env["CLICOLOR_FORCE"] = "1"
        env["FORCE_COLOR"] = "1"
    return env


def is_python_command(command: list[str]) -> bool:
    if not command:
        return False
    executable = Path(command[0]).name.lower()
    return executable in {"python", "python.exe", "pythonw", "pythonw.exe", "py", "py.exe"}


def unbuffer_python_command(command: list[str]) -> list[str]:
    if not command or not is_python_command(command) or "-u" in command[1:]:
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
    if not data:
        return ""
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass

    utf16 = decode_utf16ish(data)
    if utf16 is not None:
        return utf16

    fallbacks = [
        windows_oem_encoding(),
        "cp866" if os.name == "nt" else "",
        locale.getpreferredencoding(False),
        "mbcs" if os.name == "nt" else "",
        windows_ansi_encoding(),
        "cp1251" if os.name == "nt" else "",
    ]
    seen: set[str] = set()
    for encoding in [item for item in fallbacks if item]:
        key = encoding.lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


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


def stream_process(cmd: list[str]) -> int:
    cmd = unbuffer_python_command(cmd)
    rendered = " ".join(f'"{part}"' if " " in part else part for part in cmd)
    print("RUN: " + rendered, flush=True)
    text_stream = is_python_command(cmd)
    process_kwargs: dict[str, Any] = {
        "cwd": str(ROOT),
        "stdin": None,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "env": terminal_subprocess_env(),
        **hidden_subprocess_kwargs(),
    }
    if text_stream:
        process_kwargs.update({"text": True, "encoding": "utf-8", "errors": "replace", "bufsize": 1})
    process = subprocess.Popen(cmd, **process_kwargs)

    assert process.stdout is not None
    if text_stream:
        for chunk in iter(process.stdout.readline, ""):
            if not chunk:
                break
            print(str(chunk), end="", flush=True)
    else:
        for chunk in iter(process.stdout.readline, b""):
            if not chunk:
                break
            print(decode_subprocess_bytes(bytes(chunk)), end="", flush=True)
    return int(process.wait())


def ps_action(action: str, extra: list[str] | None = None) -> int:
    cmd = [*resolve_powershell(), "-File", str(PS_SCRIPT), "-Action", action]
    if extra:
        cmd.extend(extra)
    return stream_process(cmd)


def crop_action(mode: str) -> int:
    return stream_process([sys.executable, "-u", str(CROP_SCRIPT), "--batch-output", "--mode", mode])


def count_files(folder: Path, suffixes: tuple[str, ...]) -> int:
    if not folder.exists():
        return 0
    if folder.is_file():
        return int(folder.suffix.lower() in suffixes)
    return sum(1 for item in folder.iterdir() if item.is_file() and item.suffix.lower() in suffixes)


def read_saved_printer() -> str:
    state_path = ROOT / "state" / "printer_state.json"
    if not state_path.exists():
        return ""
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8-sig"))
        return str(payload.get("previous_default_printer") or "")
    except Exception:
        return ""


def run_capture(cmd: list[str]) -> tuple[int, str]:
    try:
        text_stream = is_python_command(cmd)
        run_kwargs: dict[str, Any] = {
            "cwd": str(ROOT),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "env": terminal_subprocess_env(),
            **hidden_subprocess_kwargs(),
        }
        if text_stream:
            run_kwargs.update({"text": True, "encoding": "utf-8", "errors": "replace"})
        process = subprocess.run(cmd, **run_kwargs)
        output = (process.stdout or "") if text_stream else decode_subprocess_bytes(process.stdout or b"")
        return process.returncode, output.strip()
    except Exception as exc:
        return 1, str(exc)


def status_payload() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project_root": str(ROOT),
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "paths": {
            "input": str(input_dir()),
            "output": str(output_dir()),
            "logs": str(ROOT / "logs"),
            "state": str(ROOT / "state"),
            "config": str(ROOT / "config" / "settings.json"),
        },
        "counts": {
            "input_presentations": count_files(input_dir(), (".pptx", ".pptm")),
            "output_pdfs": count_files(output_dir(), (".pdf",)),
        },
        "checks": {},
        "saved_printer": read_saved_printer(),
    }

    try:
        ps = resolve_powershell()
        payload["powershell_executable"] = ps[0]
        payload["checks"]["powershell"] = {"ok": True, "value": ps[0]}
    except Exception as exc:
        payload["powershell_executable"] = None
        payload["checks"]["powershell"] = {"ok": False, "value": str(exc)}
        return payload

    code, text = run_capture([*ps, "-Command", "(Get-Printer | ? Default -eq $true | select -First 1 -ExpandProperty Name)"])
    payload["checks"]["default_printer"] = {"ok": code == 0, "value": text}

    code, text = run_capture([*ps, "-Command", 'if (Get-Printer -Name "Microsoft Print to PDF" -ErrorAction SilentlyContinue) { "present" } else { "missing" }'])
    payload["checks"]["microsoft_print_to_pdf"] = {"ok": code == 0 and "present" in text.lower(), "value": text}

    code, text = run_capture([*ps, "-Command", '$app = New-Object -ComObject PowerPoint.Application; try { $app.Quit() } catch {}; "ok"'])
    payload["checks"]["powerpoint_com"] = {"ok": code == 0 and "ok" in text.lower(), "value": text}

    for package in ("pypdf", "nicegui", "webview", "yaml"):
        try:
            __import__(package)
            payload["checks"][package] = {"ok": True, "value": "available"}
        except Exception as exc:
            payload["checks"][package] = {"ok": False, "value": str(exc)}

    return payload


def print_info() -> int:
    payload = status_payload()
    payload["commands"] = [
        "enable-default",
        "print-input --skip-existing",
        "crop-output-aspect --mode 16:9",
        "crop-output-a-series",
        "restore-default",
        "doctor",
    ]
    payload["message"] = "Tool is ready. Use launcher_gui.cmd for the guided GUI workflow."
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audion PPTX Print to PDF command bridge.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("info")
    sub.add_parser("status")
    sub.add_parser("enable-default")

    print_parser = sub.add_parser("print-input")
    print_parser.add_argument("--skip-existing", action="store_true")

    crop_exact = sub.add_parser("crop-output-exact")
    crop_exact.set_defaults(mode="16:9")

    crop_aspect = sub.add_parser("crop-output-aspect")
    crop_aspect.add_argument("--mode", choices=["16:9", "a-series"], default="16:9")

    sub.add_parser("crop-output-a-series")
    sub.add_parser("restore-default")
    sub.add_parser("doctor")

    args = parser.parse_args()

    if args.command == "info":
        return print_info()
    if args.command == "status":
        print(json.dumps(status_payload(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "enable-default":
        return ps_action("enable-default")
    if args.command == "print-input":
        extra = ["-SkipExisting"] if bool(args.skip_existing) else []
        return ps_action("print-input", extra)
    if args.command == "crop-output-exact":
        return crop_action("16:9")
    if args.command == "crop-output-aspect":
        return crop_action(str(args.mode))
    if args.command == "crop-output-a-series":
        return crop_action("a-series")
    if args.command == "restore-default":
        return ps_action("restore-default")
    if args.command == "doctor":
        return stream_process([sys.executable, "-u", str(DOCTOR_SCRIPT)])

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
