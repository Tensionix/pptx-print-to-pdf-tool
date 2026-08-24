from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest

from pypdf import PdfReader, PdfWriter


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "system_core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import crop_pdf  # noqa: E402
import main as backend  # noqa: E402


class CropGeometryTests(unittest.TestCase):
    def test_centered_16_9_crop(self) -> None:
        box = crop_pdf.centered_box(400.0, 300.0, "16:9")
        self.assertIsNotNone(box)
        assert box is not None
        x0, y0, x1, y1 = box
        self.assertAlmostEqual(x0, 0.0)
        self.assertAlmostEqual(x1, 400.0)
        self.assertAlmostEqual(y0, 37.5)
        self.assertAlmostEqual(y1, 262.5)
        self.assertAlmostEqual((x1 - x0) / (y1 - y0), 16.0 / 9.0)

    def test_matching_ratio_is_unchanged(self) -> None:
        self.assertIsNone(crop_pdf.centered_box(1600.0, 900.0, "16:9"))

    def test_a_series_orientation(self) -> None:
        landscape = crop_pdf.target_ratio_for_page(842.0, 595.0, "a-series")
        portrait = crop_pdf.target_ratio_for_page(595.0, 842.0, "a-series")
        self.assertAlmostEqual(landscape * portrait, 1.0)
        self.assertGreater(landscape, 1.0)
        self.assertLess(portrait, 1.0)

    def test_unsupported_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            crop_pdf.target_ratio_for_page(100.0, 100.0, "square")


class PdfPipelineTests(unittest.TestCase):
    @staticmethod
    def _write_pdf(path: Path, width: float, height: float, pages: int = 2) -> None:
        writer = PdfWriter()
        for _ in range(pages):
            writer.add_blank_page(width=width, height=height)
        with path.open("wb") as handle:
            writer.write(handle)

    def test_crop_one_pdf_keeps_source_and_crops_every_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source = folder / "source.pdf"
            target = folder / "target.pdf"
            self._write_pdf(source, 400.0, 300.0)
            source_before = source.read_bytes()

            total, changed = crop_pdf.crop_one_pdf(source, target, "16:9")

            self.assertEqual((total, changed), (2, 2))
            self.assertEqual(source.read_bytes(), source_before)
            reader = PdfReader(str(target))
            self.assertEqual(len(reader.pages), 2)
            for page in reader.pages:
                width = float(page.mediabox.right) - float(page.mediabox.left)
                height = float(page.mediabox.top) - float(page.mediabox.bottom)
                self.assertAlmostEqual(width / height, 16.0 / 9.0, places=5)

    def test_crop_in_place_replaces_pdf_without_temp_residue(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.pdf"
            self._write_pdf(source, 1000.0, 1000.0, pages=1)

            total, changed, returned = crop_pdf.crop_pdf_in_place(source, "a-series")

            self.assertEqual((total, changed, returned), (1, 1, source))
            self.assertFalse(source.with_suffix(".tmp.pdf").exists())
            page = PdfReader(str(source)).pages[0]
            width = float(page.mediabox.right) - float(page.mediabox.left)
            height = float(page.mediabox.top) - float(page.mediabox.bottom)
            self.assertAlmostEqual(width / height, 2 ** 0.5, places=5)


class RoutingContractTests(unittest.TestCase):
    def test_count_files_accepts_single_presentation_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "one.pptx"
            source.touch()
            self.assertEqual(backend.count_files(source, (".pptx", ".pptm")), 1)
            self.assertEqual(backend.count_files(source, (".pdf",)), 0)

    def test_cli_paths_follow_workbench_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            target = Path(temp) / "target"
            old_source = os.environ.get("AUDION_SOURCE_PATH")
            old_target = os.environ.get("AUDION_TARGET_PATH")
            try:
                os.environ["AUDION_SOURCE_PATH"] = str(source)
                os.environ["AUDION_TARGET_PATH"] = str(target)
                self.assertEqual(backend.input_dir(), source)
                self.assertEqual(backend.output_dir(), target)
            finally:
                if old_source is None:
                    os.environ.pop("AUDION_SOURCE_PATH", None)
                else:
                    os.environ["AUDION_SOURCE_PATH"] = old_source
                if old_target is None:
                    os.environ.pop("AUDION_TARGET_PATH", None)
                else:
                    os.environ["AUDION_TARGET_PATH"] = old_target

    def test_gui_and_powershell_share_workbench_route_contract(self) -> None:
        app_text = (CORE / "ui_nicegui" / "app.py").read_text(encoding="utf-8")
        ps_text = (CORE / "ps_scripts" / "pptx_print_tool.ps1").read_text(encoding="utf-8-sig")
        self.assertIn('env["AUDION_SOURCE_PATH"] = str(current_source_path())', app_text)
        self.assertIn('env["AUDION_TARGET_PATH"] = str(current_target_path())', app_text)
        self.assertIn("$env:AUDION_SOURCE_PATH", ps_text)
        self.assertIn("$env:AUDION_TARGET_PATH", ps_text)
        self.assertIn("if ($source.PSIsContainer)", ps_text)
        self.assertIn("elseif ($source.Extension -in '.pptx', '.pptm')", ps_text)


if __name__ == "__main__":
    unittest.main()
