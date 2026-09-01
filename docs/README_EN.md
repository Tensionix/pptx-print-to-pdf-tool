# Audion PPTX Print to PDF Tool

[Русский](README_RU.md) · [User Guide](USER_GUIDE_EN.md)

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

* [User Guide](USER_GUIDE_EN.md) — step by step.

---

## Technical Reference

### Requirements

An installed PowerPoint and the "Microsoft Print to PDF" system printer set as
default. The program does not switch the printer for you: that is a system
setting, and it should not be changed silently.

### Formats

`.pptx` and `.pptm` are accepted.
