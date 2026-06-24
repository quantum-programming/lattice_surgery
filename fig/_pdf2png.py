from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image


def main():
    base_dir = Path(__file__).resolve().parent

    input_pdf = base_dir / "double_schematic_v2.pdf"
    output_png = base_dir / "_README_fig.png"

    doc = fitz.open(input_pdf)

    try:
        page = doc[0]  # 最初のページ
        zoom = 0.8
        matrix = fitz.Matrix(zoom, zoom)

        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        image.save(output_png, format="PNG", optimize=True, compress_level=9)

        print(f"Saved: {output_png}")

    finally:
        doc.close()


if __name__ == "__main__":
    main()
