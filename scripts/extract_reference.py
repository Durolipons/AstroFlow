"""Extract text from the reference astrology library.

Extracts plain text from the PDFs and the EPUB in
``Reference/Astrology`` into ``Reference/Astrology/_extracted`` so the
material can be consulted when authoring interpretation-library wording.

Usage (from the repo root):
    .venv\\Scripts\\python.exe scripts\\extract_reference.py

Known-unreadable files (binary/corrupt ".txt" notes) are reported and
skipped rather than failing the run.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

try:
    import pymupdf as _pymupdf

    def _pdf_text(path: Path) -> tuple[int, str]:
        doc = _pymupdf.open(path)
        parts = [page.get_text() or "" for page in doc]
        n = len(parts)
        doc.close()
        return n, "\n".join(parts)
except ImportError:  # pragma: no cover - fallback path
    from pypdf import PdfReader

    def _pdf_text(path: Path) -> tuple[int, str]:
        reader = PdfReader(str(path))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception as exc:  # individual page failures are non-fatal
                parts.append(f"\n[page extraction failed: {exc}]\n")
        return len(reader.pages), "\n".join(parts)

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "Reference" / "Astrology"
OUT = SRC / "_extracted"


def extract_pdf(path: Path, out_dir: Path) -> tuple[int, str]:
    pages, text = _pdf_text(path)
    target = out_dir / (path.stem + ".txt")
    target.write_text(text, encoding="utf-8")
    return pages, text


def extract_epub(path: Path, out_dir: Path) -> tuple[int, str]:
    parts: list[str] = []
    with zipfile.ZipFile(path) as zf:
        names = sorted(n for n in zf.namelist()
                       if n.lower().endswith((".html", ".htm", ".xhtml")))
        for name in names:
            html = zf.read(name).decode("utf-8", errors="replace")
            # crude but dependency-free: strip tags, keep line breaks
            body = (
                html.replace("</p>", "\n").replace("<br/>", "\n")
                .replace("<br>", "\n").replace("</h1>", "\n")
                .replace("</h2>", "\n").replace("</h3>", "\n")
                .replace("</li>", "\n").replace("</div>", "\n")
            )
            stripped = []
            inside = False
            for ch in body:
                if ch == "<":
                    inside = True
                elif ch == ">":
                    inside = False
                elif not inside:
                    stripped.append(ch)
            parts.append("".join(stripped))
    text = "\n\n".join(parts)
    target = out_dir / (path.stem + ".txt")
    target.write_text(text, encoding="utf-8")
    return len(names), text


def main() -> int:
    OUT.mkdir(exist_ok=True)
    print(f"Extracting into: {OUT}\n")
    ok, failed = 0, 0
    for pdf in sorted(SRC.rglob("*.pdf")):
        rel = pdf.relative_to(SRC)
        try:
            pages, text = extract_pdf(pdf, OUT)
            words = len(text.split())
            print(f"  OK   {rel}: {pages} pages, {words:,} words")
            ok += 1
        except Exception as exc:
            print(f"  FAIL {rel}: {exc}")
            failed += 1
    for epub in sorted(SRC.rglob("*.epub")):
        rel = epub.relative_to(SRC)
        try:
            chapters, text = extract_epub(epub, OUT)
            words = len(text.split())
            print(f"  OK   {rel}: {chapters} chapters, {words:,} words")
            ok += 1
        except Exception as exc:
            print(f"  FAIL {rel}: {exc}")
            failed += 1
    corrupt = [p.name for p in (SRC / "Jeff Green bits and pieces").glob("*.txt")]
    if corrupt:
        print(f"\n  SKIPPED (not plain text / corrupt): {len(corrupt)} files:")
        for name in corrupt:
            print(f"         - {name}")
    print(f"\nDone: {ok} extracted, {failed} failed, {len(corrupt)} skipped.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())