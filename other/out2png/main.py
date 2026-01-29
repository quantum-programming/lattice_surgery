import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import List

import cairosvg
from PIL import Image


def load_siteconfig(siteconfig_path: str) -> List[int]:
    kinds = []
    with open(siteconfig_path, "r") as f:
        siteconfig = json.load(f)
        assert isinstance(siteconfig, dict), "siteconfig must be a dictionary"
        assert siteconfig.keys() == {"system", "control", "control_ancilla"}
        qubit_categories = {
            "system": siteconfig["system"],
            "control": siteconfig["control"],
            "control_ancilla": siteconfig["control_ancilla"],
        }
        all_ids = sum(qubit_categories.values(), [])
        assert len(all_ids) == len(set(all_ids)), "Duplicate IDs found"
        assert sorted(all_ids) == list(range(len(all_ids))), (
            "IDs must be consecutive starting from 0"
        )
        kinds = [-1] * len(all_ids)
        for kind_id, ids in enumerate(qubit_categories.values()):
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
        cmd.append("--siteconfig")
        cmd.append("".join(map(str, load_siteconfig(siteconfig_path))))

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
    # Create temporary files
    temp_input = Path("temp_input.svg")
    temp_output = Path("temp_output.svg")

    try:
        # Write SVG content to temporary file
        with open(temp_input, "w") as f:
            f.write(svg_content)

        # Use Inkscape to convert text to paths
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
            return svg_content  # Return original content if conversion fails

        # Read the converted SVG
        with open(temp_output, "r") as f:
            return f.read()

    except Exception as e:
        print(f"Error outlining text: {e}")
        return svg_content  # Return original content if any error occurs

    finally:
        # Clean up temporary files
        for temp_file in [temp_input, temp_output]:
            if temp_file.exists():
                temp_file.unlink()


def generate_svg_files(input_path: str) -> None:
    svg_data = run_rust_executable(input_path)
    if not svg_data:
        return

    relative_path = get_relative_path(input_path)
    output_dir = Path("svg") / relative_path
    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    for turn_str, svg_content in svg_data.items():
        # Outline text in SVG before saving
        outlined_svg = outline_text_in_svg(svg_content)

        output_path = output_dir / f"{turn_str}.svg"
        with open(output_path, "w") as f:
            f.write(outlined_svg)


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
    input_paths = [
        f
        for f in input_paths
        if f.startswith("out/result/result_SELECT_10")
        or f.startswith("out/result/result_trotter_10")
    ]
    print("Converting SVG to PNG and creating GIFs...")
    for input_path in input_paths:
        relative_path = get_relative_path(input_path)
        svg_dir = Path("svg") / relative_path

        assert svg_dir.exists(), f"SVG directory not found: {svg_dir}"

        svg_files = list(svg_dir.glob("*.svg"))
        assert svg_files, f"No SVG files found in: {svg_dir}"

        # Sort SVG files by turn number
        svg_files = sorted(svg_files, key=lambda x: int(x.stem))

        # Create corresponding figure directory
        figure_dir = Path("figure") / relative_path
        shutil.rmtree(figure_dir, ignore_errors=True)
        figure_dir.mkdir(parents=True, exist_ok=True)

        # Convert SVG to PNG
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

    print("Complete")


if __name__ == "__main__":
    main()
