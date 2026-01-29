import os
import shutil
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# Constants
LEGEND_LABELS = [
    "magic state factory",
    "ancilla",
    "data (System)",
    "data (QPE ancilla)",
    "data (Block Encoding Ancilla)",
]
LEGEND_COLORS = ["#808080", "#dae3f3", "tab:blue", "tab:orange", "tab:green"]

EXAMPLE_SVG_PATHS = [
    "svg/example/legend_inner/001.svg",
    "svg/example/legend_outer/001.svg",
]

RESULT_SVG_PATHS = [
    "svg/result/result_SELECT_10_FermiHubbard2D_cylinder_0_0_1_outer_projective_CareKinkParity_1__/001.svg",
    "svg/result/result_SELECT_10_FermiHubbard2D_cylinder_0_0_1_outer_double_CareKinkParity_1__/001.svg",
    "svg/result/result_SELECT_10_FermiHubbard2D_cylinder_0_0_1_outer_projective_CareKinkParity_1__/002.svg",
    "svg/result/result_SELECT_10_FermiHubbard2D_cylinder_0_0_1_outer_double_CareKinkParity_1__/002.svg",
    "svg/result/result_SELECT_10_FermiHubbard2D_cylinder_0_0_1_outer_projective_CareKinkParity_1__/003.svg",
    "svg/result/result_SELECT_10_FermiHubbard2D_cylinder_0_0_1_outer_double_CareKinkParity_1__/003.svg",
]

TEX_DIR = Path("tex")


def verify_colors_in_utils():
    """Verify that colors are defined in src/util.rs"""
    with open("src/util.rs", "r") as f:
        utils = f.read()
        assert LEGEND_COLORS[0] in utils, (
            "magic state factory color not found in utils.rs"
        )
        assert LEGEND_COLORS[1] in utils, "ancilla color not found in utils.rs"


def create_legend_svg():
    """Create legend SVG file"""
    legend_elements = [
        Patch(facecolor=color, label=label)
        for color, label in zip(LEGEND_COLORS, LEGEND_LABELS)
    ]

    fig, ax = plt.subplots()
    legend = ax.legend(handles=legend_elements, frameon=False, loc="center")
    ax.axis("off")

    fig.canvas.draw()
    bbox = legend.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    fig.savefig(TEX_DIR / "legend_only.svg", bbox_inches=bbox)
    plt.close(fig)


def copy_svg_files(svg_paths, prefix=""):
    """Copy SVG files to tex directory with renamed filenames"""
    for path in svg_paths:
        path_main = "_".join(path.split("/")[-2:])
        dst_filename = f"{prefix}{path_main}" if prefix else path_main
        shutil.copy(path, TEX_DIR / dst_filename)


def compile_latex(tex_file):
    """Compile LaTeX file with shell escape enabled"""
    for _ in range(2):
        subprocess.run(
            ["pdflatex", "--shell-escape", tex_file],
            check=True,
            cwd=TEX_DIR,
        )


def cleanup_tex_directory():
    """Clean up generated files in tex directory except .tex and .pdf files"""
    print("\n=== Files to be deleted from tex/ directory ===")
    files_to_delete = []
    folders_to_delete = []

    for file in TEX_DIR.iterdir():
        if file.is_file() and file.suffix not in [".tex", ".pdf"]:
            files_to_delete.append(file)
            print(f"  - {file.name}")
        elif file.is_dir():
            folders_to_delete.append(file)
            print(f"  - {file.name}/")

    response = input("\nDelete these files? (y/n): ").strip().lower()
    if response == "y":
        for file in files_to_delete:
            file.unlink()
        for folder in folders_to_delete:
            shutil.rmtree(folder)
        print("Deleted successfully.")
    else:
        print("Cancelled.")


def main():
    os.chdir(os.path.dirname(__file__))

    verify_colors_in_utils()
    create_legend_svg()
    copy_svg_files(EXAMPLE_SVG_PATHS)
    compile_latex("legend.tex")
    copy_svg_files(RESULT_SVG_PATHS, prefix="individual_")
    compile_latex("individual.tex")

    cleanup_tex_directory()


if __name__ == "__main__":
    main()
