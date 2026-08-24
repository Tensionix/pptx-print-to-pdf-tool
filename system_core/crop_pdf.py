from __future__ import annotations

import argparse
from math import sqrt
import os
from pathlib import Path
from typing import Iterable

try:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import RectangleObject
except Exception as exc:  # pragma: no cover
    print("[ERROR] pypdf is not available.")
    print("[ERROR] Install it into the project runtime or system Python.")
    print(f"[DETAIL] {exc}")
    raise SystemExit(1)


ANSI_CODES = {
    "INFO": "36",
    "OK": "32",
    "WARN": "33",
    "ERROR": "31",
}


def wants_ansi() -> bool:
    return (
        os.environ.get("AUDION_GUI_TERMINAL") == "1"
        or os.environ.get("FORCE_COLOR") == "1"
        or os.environ.get("CLICOLOR_FORCE") == "1"
    )


def emit(kind: str, message: str) -> None:
    text = f"[{kind}] {message}"
    if wants_ansi():
        text = f"\x1b[{ANSI_CODES.get(kind, '0')}m{text}\x1b[0m"
    print(text, flush=True)


def target_ratio_for_page(width: float, height: float, mode: str) -> float:
    if mode == "16:9":
        return 16.0 / 9.0
    if mode == "a-series":
        ratio = sqrt(2.0)
        return ratio if width >= height else 1.0 / ratio
    raise ValueError(f"Unsupported crop mode: {mode}")


def centered_box(width: float, height: float, mode: str) -> tuple[float, float, float, float] | None:
    target = target_ratio_for_page(width, height, mode)
    current = width / height if height else 0.0
    if not current:
        return None

    if abs(current - target) < 0.0005:
        return None

    if current > target:
        new_width = height * target
        dx = (width - new_width) / 2.0
        return dx, 0.0, width - dx, height

    new_height = width / target
    dy = (height - new_height) / 2.0
    return 0.0, dy, width, height - dy


def set_page_box(page: object, x0: float, y0: float, x1: float, y1: float) -> None:
    box = RectangleObject((x0, y0, x1, y1))
    page.mediabox = box
    page.cropbox = box
    page.trimbox = box
    page.bleedbox = box
    page.artbox = box


def crop_one_pdf(src: Path, dst: Path, mode: str) -> tuple[int, int]:
    reader = PdfReader(str(src))
    writer = PdfWriter()
    changed = 0

    for page in reader.pages:
        left = float(page.mediabox.left)
        bottom = float(page.mediabox.bottom)
        right = float(page.mediabox.right)
        top = float(page.mediabox.top)
        width = right - left
        height = top - bottom
        box = centered_box(width, height, mode)

        if box is not None:
            rel_x0, rel_y0, rel_x1, rel_y1 = box
            set_page_box(page, left + rel_x0, bottom + rel_y0, left + rel_x1, bottom + rel_y1)
            changed += 1

        writer.add_page(page)

    with dst.open("wb") as fh:
        writer.write(fh)

    return len(reader.pages), changed


def iter_output_pdfs(output_dir: Path) -> Iterable[Path]:
    return sorted(path for path in output_dir.glob("*.pdf") if path.is_file())


def crop_pdf_in_place(src: Path, mode: str) -> tuple[int, int, Path]:
    temp_path = src.with_suffix(".tmp.pdf")
    if temp_path.exists():
        temp_path.unlink()

    total, changed = crop_one_pdf(src, temp_path, mode)
    temp_path.replace(src)
    return total, changed, src


def main() -> int:
    parser = argparse.ArgumentParser(description="Crop all PDFs in output folder in place.")
    parser.add_argument("--batch-output", action="store_true", help="Process all PDFs from output folder in place")
    parser.add_argument("--mode", choices=["16:9", "a-series"], default="16:9")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output_dir = Path(os.environ.get("AUDION_TARGET_PATH") or root / "output")

    if not args.batch_output:
        emit("ERROR", "Use --batch-output.")
        return 1

    files = list(iter_output_pdfs(output_dir))
    if not files:
        emit("WARN", "No PDF files were found in output.")
        return 1

    emit("INFO", f"Batch files in output: {len(files)}")
    emit("INFO", f"Mode: {args.mode}")
    emit("WARN", "Files will be overwritten in place.")

    for index, src in enumerate(files, start=1):
        total, changed, dst = crop_pdf_in_place(src, args.mode)
        emit("OK", f"[{index}/{len(files)}] {src.name} -> {dst.name} | pages={total} changed={changed}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
