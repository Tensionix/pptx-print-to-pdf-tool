# Audion PPTX Print to PDF Tool

<!-- audion:release -->
<p align="center">
  <a href="https://audion.dev/downloads/pptx-print-to-pdf-tool"><img alt="Windows" src="https://img.shields.io/badge/Windows-10%20%7C%2011-0b6db8?style=flat-square&logo=windows&logoColor=white"></a>
  <a href="https://github.com/Tensionix/pptx-print-to-pdf-tool/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/Tensionix/pptx-print-to-pdf-tool?style=flat-square&label=release&color=e08a63"></a>
  <a href="https://github.com/Tensionix/pptx-print-to-pdf-tool/releases"><img alt="Downloads" src="https://img.shields.io/github/downloads/Tensionix/pptx-print-to-pdf-tool/total?style=flat-square&label=downloads&color=5fd08a"></a>
  <a href="https://github.com/Tensionix/pptx-print-to-pdf-tool/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/Tensionix/pptx-print-to-pdf-tool?style=flat-square&color=5fd08a&logo=apache&logoColor=white&cacheSeconds=3600"></a>
</p>

**Version 1.3.2** · 2026-09-04 · 78.3 MB

- [Direct download](https://audion.dev/get/pptx-print-to-pdf-tool/1.3.2/Audion_PPTX_Print_to_PDF_Tool_v1.3.2_Full.zip) — unmetered, no rate limits
- [Project page](https://audion.dev/downloads/pptx-print-to-pdf-tool) — every version and how to install

<p align="center"><img src="docs/screenshot.png" alt="The program window" width="560"></p>

`SHA-256: 63d117ef543f2d93c0774bb2fa00910837c62a1685eb74ec8d0e0ebf91b074dc`

---

An **Audion** tool, published by [Tensionix](https://github.com/Tensionix).
<!-- /audion:release -->


[Русский](docs/README_RU.md) · [User Guide](docs/USER_GUIDE_EN.md)

**Contents**

- [Why It Exists](#why-it-exists)
- [The Order of Work](#the-order-of-work)
- [Next](#next)
- [Technical Reference](#technical-reference)
  - [Requirements](#requirements)
  - [Formats](#formats)

Batch printing of presentations through the "Microsoft Print to PDF" system
printer, followed by cropping to the required format.

## Why It Exists

Exporting a presentation to PDF and printing it to PDF are **different things**,
and the results differ. Printing goes through the printer driver: page settings,
margins, and scaling all apply. Sometimes that is exactly the path required — for
instance when the receiving side expects a document that has been through print.

PowerPoint cannot batch-print. This program can.

## The Order of Work

1. Make "Microsoft Print to PDF" the default printer.
2. Put the presentations into the input folder.
3. Run the printing.
4. Crop the result to `16:9` or A4/A3.

Cropping is separate from printing: printing produces the page as it is, and
fitting to a format is done on the finished PDF.

## Next

* [User Guide](docs/USER_GUIDE_EN.md) — step by step.

---

## Technical Reference

### Requirements

An installed PowerPoint and the "Microsoft Print to PDF" system printer set as
default. The program does not switch the printer for you: that is a system
setting, and it should not be changed silently.

### Formats

`.pptx` and `.pptm` are accepted.
