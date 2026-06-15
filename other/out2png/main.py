import json
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import List

import cairosvg
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from PIL import Image

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

    plt.rcParams.update(
        {
            "text.usetex": True,
            "font.family": "serif",
            "font.serif": ["Computer Modern Roman"],
            "font.size": 14,
        }
    )

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


def cleanup_tex_directory():
    """Clean up generated files in tex directory except .tex and .pdf files"""
    items_to_delete = [
        (f, f.is_dir())
        for f in TEX_DIR.iterdir()
        if f.is_dir() or f.suffix not in [".tex", ".pdf"]
    ]

    for item, is_dir in items_to_delete:
        print(f"Deleted: {item.name}{'/' if is_dir else ''}")
        shutil.rmtree(item) if is_dir else item.unlink()


def compile_tex():
    os.chdir(os.path.dirname(__file__))

    verify_colors_in_utils()
    create_legend_svg()

    # Copy SVG files and compile LaTeX
    for tex_file, svg_paths, prefix in [
        ("legend.tex", EXAMPLE_SVG_PATHS, ""),
        ("individual.tex", RESULT_SVG_PATHS, "individual_"),
    ]:
        copy_svg_files(svg_paths, prefix=prefix)
        for _ in range(2):
            subprocess.run(
                ["pdflatex", "--shell-escape", tex_file], check=True, cwd=TEX_DIR
            )

    cleanup_tex_directory()


def load_siteconfig(siteconfig_path: str) -> List[int]:
    with open(siteconfig_path, "r") as f:
        siteconfig = json.load(f)
        assert isinstance(siteconfig, dict), "siteconfig must be a dictionary"
        assert siteconfig.keys() == {"system", "control", "control_ancilla"}

        all_ids = sum(siteconfig.values(), [])
        assert len(all_ids) == len(set(all_ids)), "Duplicate IDs found"
        assert sorted(all_ids) == list(range(len(all_ids))), (
            "IDs must be consecutive starting from 0"
        )

        kinds = [-1] * len(all_ids)
        for kind_id, ids in enumerate(siteconfig.values()):
            for qubit_id in ids:
                kinds[qubit_id] = kind_id
    return kinds


def get_cmd(input_path: str):
    cmd = ["target/release/out2png", "../../" + input_path]
    assert os.path.exists(cmd[1])

    if input_path.startswith("out/example/demo"):
        cmd.append("--dont_show_turns")
        return cmd
    elif input_path.startswith("out/example/floorplan"):
        cmd.append("--dont_show_turns")
        cmd.append("--dont_show_ids")
        return cmd
    elif input_path.startswith("out/example/legend"):
        siteconfig_path = "../../out/example/siteconfig_legend.in"
        cmd.append("--dont_show_turns")
        cmd.append("--siteconfig")
        cmd.append("".join(map(str, load_siteconfig(siteconfig_path))))
        return cmd
    elif input_path.startswith("out/example"):
        cmd.append("--dont_show_msf")
        return cmd

    prob_name = input_path.split("/")[2].replace("result_", "")
    if "_inner" in prob_name:
        prob_name = prob_name.split("_inner")[0]
    if "_outer" in prob_name:
        prob_name = prob_name.split("_outer")[0]
    siteconfig_path = f"../../data/circuit/siteconfig_{prob_name}.in"

    cmd.append("--dont_show_turns")
    if os.path.exists(siteconfig_path):
        cmd.extend(
            ["--siteconfig", "".join(map(str, load_siteconfig(siteconfig_path)))]
        )

    return cmd


def run_rust_executable(input_path: str) -> dict[str, str] | None:
    cmd = get_cmd(input_path)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stderr:
        print(f"Stderr: {result.stderr}")
    if result.returncode != 0:
        raise RuntimeError(f"Failed: {input_path} with {result.returncode}")
    return json.loads(result.stdout)


def get_relative_path(input_path: str) -> Path:
    path = Path(input_path)
    parts = path.parts
    out_index = parts.index("out")
    assert parts[out_index] == "out"
    relative_parts = parts[out_index + 1 :]
    return Path(*relative_parts).with_suffix("")


def outline_text_in_svg(svg_content: str) -> str:
    """Convert text elements to paths using Inkscape."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".svg", delete=False
    ) as temp_input_file:
        temp_input = Path(temp_input_file.name)
        temp_input.write_text(svg_content)

    temp_output = temp_input.with_stem(f"{temp_input.stem}_output")

    try:
        cmd = [
            "inkscape",
            "--export-text-to-path",
            "--export-plain-svg",
            f"--export-filename={temp_output}",
            str(temp_input),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Inkscape error: {result.stderr}")
            return svg_content

        return temp_output.read_text()

    except Exception as e:
        print(f"Error outlining text: {e}")
        return svg_content

    finally:
        temp_input.unlink(missing_ok=True)
        temp_output.unlink(missing_ok=True)


def _process_svg_item(args):
    """Helper function for parallel processing of SVG items."""
    turn_str, svg_content, output_dir = args
    outlined_svg = outline_text_in_svg(svg_content)
    output_path = output_dir / f"{turn_str}.svg"
    with open(output_path, "w") as f:
        f.write(outlined_svg)
    return turn_str


def generate_svg_files(input_path: str) -> None:
    svg_data = run_rust_executable(input_path)
    if not svg_data:
        return

    relative_path = get_relative_path(input_path)
    output_dir = Path("svg") / relative_path
    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parallel processing of SVG items
    args_list = [
        (turn_str, svg_content, output_dir)
        for turn_str, svg_content in svg_data.items()
    ]

    with ProcessPoolExecutor() as executor:
        list(executor.map(_process_svg_item, args_list))


def create_gif(png_files: list[str], output_path: str) -> None:
    if not png_files:
        return

    images = [Image.open(png_file) for png_file in png_files]
    durations = (
        [1000] + [300] * (len(images) - 2) + [1000] if len(images) >= 2 else [1000]
    )

    images[0].save(
        output_path, save_all=True, append_images=images[1:], duration=durations, loop=0
    )
    print(f"Created: {output_path}")


def process_svg_to_png_and_gif(input_path: str) -> None:
    """Convert SVG files to PNG and create GIF for a single input path."""
    relative_path = get_relative_path(input_path)
    svg_dir = Path("svg") / relative_path

    assert svg_dir.exists(), f"SVG directory not found: {svg_dir}"
    svg_files = sorted(svg_dir.glob("*.svg"), key=lambda x: int(x.stem))
    assert svg_files, f"No SVG files found in: {svg_dir}"

    # Create figure directory and convert SVG to PNG
    figure_dir = Path("figure") / relative_path
    shutil.rmtree(figure_dir, ignore_errors=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    png_files = []
    for svg_file in svg_files:
        png_file = figure_dir / f"{svg_file.stem}.png"
        cairosvg.svg2png(url=str(svg_file), write_to=str(png_file), scale=2)
        png_files.append(str(png_file))

    # Create GIF
    if png_files:
        gif_path = Path("gif") / f"{'_'.join(relative_path.parts)}.gif"
        gif_path.parent.mkdir(parents=True, exist_ok=True)
        create_gif(png_files, str(gif_path))


def main() -> None:
    os.chdir(os.path.dirname(__file__))

    # 1. compile Rust code
    print("Compiling Rust code...")
    subprocess.run(["cargo", "build", "--release"], check=True)
    print("Compilation complete.")

    # 2. Read input paths from targets.txt
    with open("targets.txt", "r") as f:
        input_paths = [
            line.strip() for line in f if line.strip() and not line.startswith("#")
        ]
    if not input_paths:
        print("No input paths found")
        return
    print(f"Processing {len(input_paths)} files")

    # 3. Setup directories
    for directory in ["svg", "figure", "gif"]:
        Path(directory).mkdir(exist_ok=True)

    # 4. Generate SVG files
    print("Generating SVG files...")
    for input_path in input_paths:
        print(f"Processing: {input_path}")
        generate_svg_files(input_path)

    # 5. Convert SVG to PNG and create GIFs for each target
    result_paths = [
        f
        for f in input_paths
        if f.startswith("out/result/result_SELECT_10")
        or f.startswith("out/result/result_trotter_10")
    ]
    print("Converting SVG to PNG and creating GIFs...")
    for input_path in result_paths:
        process_svg_to_png_and_gif(input_path)

    print("Compiling LaTeX files...")
    compile_tex()

    print("Complete")


if __name__ == "__main__":
    main()
