"""Deterministic Phase 1 PPTX -> static album converter.

This is deliberately an adapter around LibreOffice. It does not inspect or
rebuild PowerPoint objects; it rasterizes the exported PDF and creates the
Album JSON contract consumed by the Viewer.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import fitz
from PIL import Image

SOFFICE = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
DEFAULT_DPI = 180
PAGE_WEBP_QUALITY = 92
THUMB_WEBP_QUALITY = 82
CJK_FONT_MARKERS = (
    "notosanssc", "notosanscjk", "sourcehansans", "simsun", "simhei",
    "deng", "microsoftyahei", "wqy", "microhei", "wenquanyi",
)
BOOK_PAGE_ASPECT = 8 / 9


def available_cjk_fonts() -> list[str]:
    """Find a CJK fallback font before LibreOffice starts rasterization."""
    if os.name == "nt":
        roots = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
                 Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"]
    else:
        roots = [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path.home() / ".fonts"]
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        for font in root.rglob("*"):
            if not font.is_file():
                continue
            normalized = "".join(character for character in font.name.lower() if character.isalnum())
            if any(marker in normalized for marker in CJK_FONT_MARKERS):
                found.append(font.name)
    return sorted(set(found))


def require_cjk_fonts() -> list[str]:
    fonts = available_cjk_fonts()
    if not fonts:
        raise RuntimeError(
            "No CJK fallback font was found. Install Noto Sans CJK or another "
            "Chinese font before converting the presentation."
        )
    return fonts


def visible_slide_numbers(pptx: Path) -> list[int]:
    """Return original 1-based slide positions, excluding p:sld show=0."""
    with zipfile.ZipFile(pptx) as archive:
        presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        slide_ids = presentation.find("p:sldIdLst", NS)
        if slide_ids is None:
            return []
        result = []
        for position, slide_id in enumerate(slide_ids, start=1):
            rel_id = slide_id.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            rels = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
            target = next((r.attrib["Target"] for r in rels if r.attrib.get("Id") == rel_id), None)
            if not target:
                continue
            slide_path = "ppt/" + target.lstrip("/")
            if slide_path not in archive.namelist():
                continue
            slide = ET.fromstring(archive.read(slide_path))
            if slide.attrib.get("show", "1") != "0":
                result.append(position)
        return result


def validate_pptx(pptx: Path, max_mb: int = 100, max_slides: int = 200) -> list[int]:
    if pptx.suffix.lower() != ".pptx":
        raise ValueError("Input must be a .pptx file")
    if not pptx.is_file():
        raise ValueError("Input file does not exist")
    if pptx.stat().st_size > max_mb * 1024 * 1024:
        raise ValueError(f"File exceeds the {max_mb} MB limit")
    if not zipfile.is_zipfile(pptx):
        raise ValueError("File is not a valid PPTX/ZIP container")
    with zipfile.ZipFile(pptx) as archive:
        names = set(archive.namelist())
        for required in ("[Content_Types].xml", "ppt/presentation.xml"):
            if required not in names:
                raise ValueError("PPTX container is missing required presentation data")
    visible = visible_slide_numbers(pptx)
    if not visible:
        raise ValueError("The presentation contains no visible slides")
    if len(visible) > max_slides:
        raise ValueError(f"Presentation exceeds the {max_slides} visible-slide limit")
    return visible


def render_pdf(pptx: Path, work: Path) -> Path:
    if not SOFFICE.exists():
        raise RuntimeError(f"LibreOffice not found at {SOFFICE}")
    result = subprocess.run(
        [str(SOFFICE), "--headless", "--convert-to", "pdf", "--outdir", str(work), str(pptx)],
        capture_output=True, text=True, timeout=180, check=False,
    )
    pdf = work / f"{pptx.stem}.pdf"
    if result.returncode != 0 or not pdf.exists():
        raise RuntimeError(f"LibreOffice conversion failed: {result.stderr or result.stdout}")
    return pdf


def save_webp(page: Image.Image, path: Path, quality: int = PAGE_WEBP_QUALITY) -> tuple[int, int]:
    page = page.convert("RGB")
    page.save(path, "WEBP", quality=quality, method=6)
    return page.width, page.height


def make_book_cover_page(image: Image.Image) -> Image.Image:
    """Keep a complete 16:9 cover inside the same 8:9 page as split interiors."""
    target_width = max(1, round(image.height * BOOK_PAGE_ASPECT))
    canvas = Image.new("RGB", (target_width, image.height), "white")
    fitted = image.convert("RGB")
    fitted.thumbnail((target_width, image.height), Image.Resampling.LANCZOS)
    offset = ((target_width - fitted.width) // 2, (image.height - fitted.height) // 2)
    canvas.paste(fitted, offset)
    return canvas


def convert(pptx: Path, output: Path, mode: str, dpi: int = DEFAULT_DPI, interval: int = 3000, transition: str = "page-curl") -> Path:
    visible = validate_pptx(pptx)
    if not 150 <= dpi <= 180:
        raise ValueError("Render DPI must be between 150 and 180")
    require_cjk_fonts()
    output.mkdir(parents=True, exist_ok=True)
    (output / "pages").mkdir(exist_ok=True)
    (output / "thumbs").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="liveslides-") as temporary:
        pdf = render_pdf(pptx, Path(temporary))
        document = fitz.open(pdf)
        if document.page_count != len(visible):
            raise RuntimeError(f"PDF page count {document.page_count} differs from visible slide count {len(visible)}")
        rendered = []
        scale = dpi / 72
        for index, page in enumerate(document):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            rendered.append(image)
            image.save(Path(temporary) / f"slide-{index + 1:03d}.png")
        document.close()

    page_items = []
    page_index = 0
    total = len(rendered)
    for slide_number, image in enumerate(rendered, start=1):
        parts = [("full", image)]
        if mode in ("split-all", "left-cover-spread") and total >= 1:
            mid = image.width // 2
            parts = [("left", image.crop((0, 0, mid, image.height))), ("right", image.crop((mid, 0, image.width, image.height)))]
        elif mode == "cover-inner-split" and total >= 3 and slide_number not in (1, total):
            mid = image.width // 2
            parts = [("left", image.crop((0, 0, mid, image.height))), ("right", image.crop((mid, 0, image.width, image.height)))]
        for part, part_image in parts:
            if mode == "cover-inner-split" and part == "full":
                part_image = make_book_cover_page(part_image)
            page_index += 1
            stem = f"p{page_index:03d}_{part}"
            src = output / "pages" / f"{stem}.webp"
            thumb = output / "thumbs" / f"{stem}.webp"
            width, height = save_webp(part_image, src)
            thumb_image = part_image.copy()
            thumb_image.thumbnail((200, 200))
            save_webp(thumb_image, thumb, quality=THUMB_WEBP_QUALITY)
            page_items.append({"id": stem, "parentSlide": slide_number, "part": part,
                               "src": f"pages/{src.name}", "thumbnail": f"thumbs/{thumb.name}",
                               "width": width, "height": height, "aspectRatio": round(width / height, 6), "bgMode": "contain"})

    cover = Image.open(output / page_items[0]["src"]).convert("RGB")
    cover.thumbnail((1200, 1200))
    cover.save(output / "cover.webp", "WEBP", quality=88, method=6)
    if interval not in (3000, 5000):
        raise ValueError("Viewer interval must be 3000ms or 5000ms")
    if transition not in ("page-curl", "slide"):
        raise ValueError("Viewer transition must be page-curl or slide")
    album = {"id": output.name, "title": pptx.stem, "pageMode": mode,
             "viewer": {"autoplay": True, "interval": interval, "flippingTime": 1000, "idleResume": 12000, "loop": True, "loopDelay": 2500, "transition": transition},
             "share": {"title": pptx.stem, "description": "点击在线查阅电子画册", "cover": "cover.webp"}, "pages": page_items}
    (output / "album.json").write_text(json.dumps(album, ensure_ascii=False, indent=2), encoding="utf-8")
    return output / "album.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert PPTX to a LiveSlides static album")
    parser.add_argument("pptx", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=("single-slide", "cover-inner-split", "split-all", "left-cover-spread"), default="single-slide")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    parser.add_argument("--interval", type=int, choices=(3000, 5000), default=3000)
    parser.add_argument("--transition", choices=("page-curl", "slide"), default="page-curl")
    args = parser.parse_args()
    manifest = convert(args.pptx, args.output, args.mode, args.dpi, args.interval, args.transition)
    print(manifest)


if __name__ == "__main__":
    main()
