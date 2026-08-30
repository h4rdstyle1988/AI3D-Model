#!/usr/bin/env python3
"""Build the R02 direct reference-versus-TRELLIS optic-gate sheet."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFile, ImageOps


ImageFile.LOAD_TRUNCATED_IMAGES = True


def panel(path: Path, label: str, size: tuple[int, int]) -> Image.Image:
    source = Image.open(path).convert("RGB")
    fitted = ImageOps.contain(source, (size[0] - 20, size[1] - 50), Image.Resampling.LANCZOS)
    result = Image.new("RGB", size, (242, 242, 242))
    result.paste(fitted, ((size[0] - fitted.width) // 2, 40 + (size[1] - 50 - fitted.height) // 2))
    draw = ImageDraw.Draw(result)
    draw.rectangle((0, 0, size[0], 38), fill=(255, 255, 255))
    draw.text((10, 12), label, fill=(20, 20, 20))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ref_clean", type=Path)
    parser.add_argument("ref_seam", type=Path)
    parser.add_argument("cutout", type=Path)
    parser.add_argument("raw_visible", type=Path)
    parser.add_argument("raw_three_quarter", type=Path)
    parser.add_argument("raw_top", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    panels = [
        panel(args.ref_clean, "SOLL: REF-CLEAN (hash exact; stream truncated)", (600, 600)),
        panel(args.ref_seam, "SOLL: REF-SEAM (Trennlinie)", (600, 600)),
        panel(args.cutout, "IST: Trellis BiRefNet cutout", (600, 600)),
        panel(args.raw_visible, "IST: Trellis raw visible view", (600, 600)),
        panel(args.raw_three_quarter, "IST: Trellis raw 3/4", (600, 600)),
        panel(args.raw_top, "IST: Trellis raw top", (600, 600)),
    ]
    sheet = Image.new("RGB", (1800, 1200), (232, 232, 232))
    for index, image in enumerate(panels):
        sheet.paste(image, ((index % 3) * 600, (index // 3) * 600))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output, optimize=True)


if __name__ == "__main__":
    main()
