from __future__ import annotations

import argparse
import json
import locale
import os
from pathlib import Path
import shutil
import subprocess
import sys


ANSI_CODES = {
    "INFO": "36",
    "OK": "32",
    "WARN": "33",
    "ERROR": "31",
    "TITLE": "1;36",
}


def wants_ansi() -> bool:
    return (
        os.environ.get("AUDION_GUI_TERMINAL") == "1"
        or os.environ.get("FORCE_COLOR") == "1"
        or os.environ.get("CLICOLOR_FORCE") == "1"
    )


def colorize(text: str, code: str) -> str:
    if not wants_ansi():
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


def emit(kind: str, message: str) -> None:
    code = ANSI_CODES.get(kind, "0")
    print(colorize(f"[{kind}] {message}", code), flush=True)


def one_line(value: object) -> str:
    return " ".join(str(value).split())


def is_python_command(command: list[str]) -> bool:
    if not command:
        return False
    executable = Path(command[0]).name.lower()
    return executable in {"python", "python.exe", "pythonw", "pythonw.exe", "py", "py.exe"}


def subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    return env


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


def run(cmd: list[str]) -> tuple[int, str]:
    try:
        if is_python_command(cmd):
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=subprocess_env(),
            )
            return process.returncode, (process.stdout or "").strip()
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=subprocess_env(),
        )
        return process.returncode, decode_subprocess_bytes(process.stdout or b"").strip()
    except Exception as exc:
        return 1, str(exc)


def resolve_powershell(root: Path) -> list[str] | None:
    candidate = root / "system_core" / "powershell" / "pwsh.exe"
    if candidate.exists():
        return [str(candidate)]

    for name in ("pwsh.exe", "pwsh", "powershell.exe", "powershell"):
        found = shutil.which(name)
        if found:
            return [found]

    return None


def import_check(module_name: str) -> dict[str, object]:
    try:
        __import__(module_name)
        return {"ok": True, "value": "available"}
    except Exception as exc:
        return {"ok": False, "value": str(exc)}


def emit_human_header(info: dict[str, object]) -> None:
    print(colorize("Audion PPTX Print to PDF Doctor", ANSI_CODES["TITLE"]), flush=True)
    emit("INFO", "Проверка окружения: UTF-8/кириллица OK")
    emit("INFO", f"Project root: {info.get('project_root', '')}")
    emit("INFO", f"Python: {info.get('python_executable', '')} ({info.get('python_version', '')})")
    emit("INFO", f"PowerShell: {info.get('powershell_executable') or 'not found'}")

    paths = info.get("paths", {})
    if isinstance(paths, dict):
        for key in ("input", "output", "logs", "state", "config"):
            emit("INFO", f"{key}: {paths.get(key, '')}")


def emit_check_result(key: str, value: dict[str, object]) -> None:
    label = str(key).replace("_", " ")
    text = one_line(value.get("value", ""))
    emit("OK" if bool(value.get("ok")) else "ERROR", f"{label}: {text}")


def print_human_report(info: dict[str, object]) -> None:
    emit_human_header(info)
    checks = info.get("checks", {})
    if not isinstance(checks, dict):
        return
    for key, value in checks.items():
        if not isinstance(value, dict):
            continue
        emit_check_result(str(key), value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Audion PPTX Print to PDF portable environment.")
    parser.add_argument("--project-root", default="")
    args = parser.parse_args()

    root = Path(args.project_root).resolve() if args.project_root else Path(__file__).resolve().parents[1]
    ps_cmd = resolve_powershell(root)
    info: dict[str, object] = {
        "project_root": str(root),
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "paths": {
            "input": str(root / "input"),
            "output": str(root / "output"),
            "logs": str(root / "logs"),
            "state": str(root / "state"),
            "config": str(root / "config" / "settings.json"),
        },
        "powershell_executable": ps_cmd[0] if ps_cmd else None,
        "checks": {},
    }

    human_output = wants_ansi()
    if human_output:
        emit_human_header(info)

    if ps_cmd is None:
        info["checks"]["powershell"] = {"ok": False, "value": "not found"}
        if human_output:
            emit_check_result("powershell", dict(info["checks"]["powershell"]))
        else:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        return 1

    info["checks"]["powershell"] = {"ok": True, "value": ps_cmd[0]}
    if human_output:
        emit_check_result("powershell", dict(info["checks"]["powershell"]))

    code, text = run([*ps_cmd, "-NoProfile", "-Command", "(Get-Printer | ? Default -eq $true | select -First 1 -ExpandProperty Name)"])
    info["checks"]["default_printer"] = {"ok": code == 0, "value": text}
    if human_output:
        emit_check_result("default_printer", dict(info["checks"]["default_printer"]))

    code, text = run([*ps_cmd, "-NoProfile", "-Command", 'if (Get-Printer -Name "Microsoft Print to PDF" -ErrorAction SilentlyContinue) { "present" } else { "missing" }'])
    info["checks"]["microsoft_print_to_pdf"] = {"ok": code == 0 and "present" in text.lower(), "value": text}
    if human_output:
        emit_check_result("microsoft_print_to_pdf", dict(info["checks"]["microsoft_print_to_pdf"]))

    code, text = run([*ps_cmd, "-NoProfile", "-Command", '$app = New-Object -ComObject PowerPoint.Application; try { $app.Quit() } catch {}; "ok"'])
    info["checks"]["powerpoint_com"] = {"ok": code == 0 and "ok" in text.lower(), "value": text}
    if human_output:
        emit_check_result("powerpoint_com", dict(info["checks"]["powerpoint_com"]))

    for key, module in (("pypdf", "pypdf"), ("nicegui", "nicegui"), ("pywebview", "webview"), ("pyyaml", "yaml")):
        info["checks"][key] = import_check(module)
        if human_output:
            emit_check_result(key, dict(info["checks"][key]))

    failed = [
        key
        for key, value in dict(info["checks"]).items()
        if isinstance(value, dict) and not bool(value.get("ok"))
    ]
    if not human_output:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
