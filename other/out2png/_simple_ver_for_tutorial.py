import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def read_int(words: list[str], index: int) -> tuple[int, int]:
    """Read an integer from the word list and return (value, next_index)."""
    return int(words[index]), index + 1


@dataclass
class XYZ:
    """3D coordinate (x, y, z)."""

    x: int
    y: int
    z: int

    @classmethod
    def from_words(
        cls, words: list[str], index: int, w: int, h: int, l: int
    ) -> tuple["XYZ", int]:
        """Parse XYZ from word list."""
        x, index = read_int(words, index)
        y, index = read_int(words, index)
        z, index = read_int(words, index)
        assert 0 <= x < w and 0 <= y < h and 0 <= z < l, (
            f"Coordinate out of bounds: ({x}, {y}, {z}) with bounds ({w}, {h}, {l})"
        )
        return cls(x, y, z), index

    def svg_x(self, w: int, block_size: int, dw: int = 50) -> int:
        """Calculate SVG x-coordinate."""
        return (self.x + self.z * w) * block_size + dw * self.z

    def svg_y(self, block_size: int) -> int:
        """Calculate SVG y-coordinate."""
        return self.y * block_size

    def is_adjacent(self, other: "XYZ") -> bool:
        """Check if two coordinates are adjacent."""
        dx = abs(self.x - other.x)
        dy = abs(self.y - other.y)
        dz = abs(self.z - other.z)
        return (dx + dy + dz) == 1


@dataclass
class RenderConfig:
    """Configuration for rendering."""

    dont_show_msf: bool = False
    dont_show_turns: bool = False
    dont_show_ids: bool = False


@dataclass
class ColorScheme:
    """Color scheme for visualization."""

    grid_fill: str = "#dae3f3"
    grid_stroke: str = "#1f77b4"
    system_qubit: str = "#1f77b4"
    control_qubit: str = "#ff7f0e"
    control_ancilla: str = "#2ca02c"
    magic_state: str = "#12527C"
    separator: str = "#111111"
    path_colors: tuple[str, ...] = (
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    )


def get_qubit_color(config_char: str, colors: ColorScheme) -> str:
    """Get color based on qubit configuration."""
    assert config_char.isdigit(), f"Config char must be digit: {config_char}"
    assert config_char in "012", f"Config char must be 0, 1, or 2: {config_char}"

    if config_char == "0":
        return colors.system_qubit
    elif config_char == "1":
        return colors.control_qubit
    elif config_char == "2":
        return colors.control_ancilla
    else:
        return "unknown"


class SVGBuilder:
    """Helper class to build SVG documents."""

    DW = 50  # Distance between layers

    def __init__(self):
        self.elements = []

    def add_rectangle(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        fill: str,
        stroke: str = "",
        stroke_width: int = 0,
        rx: int = 0,
        ry: int = 0,
        title: str = "",
    ):
        """Add a rectangle to the SVG."""
        rect = f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        rect += f'fill="{fill}" '
        if stroke:
            rect += f'stroke="{stroke}" '
        if stroke_width:
            rect += f'stroke-width="{stroke_width}" '
        if rx:
            rect += f'rx="{rx}" '
        if ry:
            rect += f'ry="{ry}" '
        rect += ">"
        if title:
            rect += f"<title>{title}</title>"
        rect += "</rect>"
        self.elements.append(rect)

    def add_text(
        self,
        text: str,
        x: int,
        y: int,
        font_size: int,
        fill: str = "black",
        text_anchor: str = "middle",
        zorder: int = 0,
    ):
        """Add text to the SVG."""
        text_elem = (
            f'<text x="{x}" y="{y}" font-size="{font_size}" '
            f'fill="{fill}" text-anchor="{text_anchor}">{text}</text>'
        )
        self.elements.append(text_elem)

    def build(self, l: int, width: int, height: int) -> str:
        """Build the final SVG document."""
        total_width = l * width + (l - 1) * self.DW + 10
        total_height = height + 10

        svg = f'''<svg id="vis" viewBox="{-5} {-5} {total_width} {total_height}" '''
        svg += f'width="{total_width}" height="{total_height}" '
        svg += 'style="background-color:white" xmlns="http://www.w3.org/2000/svg">\n'
        svg += "<style>text {text-anchor: middle; dominant-baseline: central; user-select: none;}</style>\n"

        for element in self.elements:
            svg += element + "\n"

        svg += "</svg>"
        return svg


def add_qubit_text(
    builder: SVGBuilder,
    text: str,
    xyz: XYZ,
    w: int,
    block_size: int,
    font_size: int,
    offset: tuple[int, int],
):
    """Add qubit label text."""
    builder.add_text(
        text,
        xyz.svg_x(w, block_size) + offset[0],
        xyz.svg_y(block_size) + offset[1],
        font_size,
        "black",
    )


def add_qubit_id_texts(
    builder: SVGBuilder, w: int, n1: int, n2: int, xyzs: list[XYZ], block_size: int
):
    """Add ID labels for all qubits."""
    font_size = block_size * 2 // 3 if n1 < 100 else block_size // 2

    # System and control qubits
    for i in range(n1):
        add_qubit_text(
            builder,
            str(i + 1),
            xyzs[i],
            w,
            block_size,
            font_size,
            (block_size // 2, block_size // 2),
        )

    # Magic state qubits
    for i in range(n2):
        add_qubit_text(
            builder,
            "M",
            xyzs[n1 + i],
            w,
            block_size,
            font_size // 2,
            (block_size // 4, block_size // 4),
        )


def add_grid(
    builder: SVGBuilder, l: int, w: int, h: int, block_size: int, colors: ColorScheme
):
    """Add grid background."""
    for d2 in range(l):
        for w2 in range(w):
            for h2 in range(h):
                builder.add_rectangle(
                    (w2 + d2 * w) * block_size + SVGBuilder.DW * d2,
                    h2 * block_size,
                    block_size,
                    block_size,
                    colors.grid_fill,
                    colors.grid_stroke,
                    2,
                    title=f"(l, w, h) = ({d2}, {w2}, {h2})",
                )


def add_logical_qubits(
    builder: SVGBuilder,
    xyzs: list[XYZ],
    n1: int,
    w: int,
    block_size: int,
    siteconfig: Optional[str],
    colors: ColorScheme,
):
    """Add logical qubit rectangles."""
    for i in range(n1):
        if siteconfig and i < len(siteconfig):
            color = get_qubit_color(siteconfig[i], colors)
        else:
            color = colors.system_qubit

        xyz = xyzs[i]
        builder.add_rectangle(
            xyz.svg_x(w, block_size) + 1,
            xyz.svg_y(block_size) + 1,
            block_size - 2,
            block_size - 2,
            color,
            "",
            0,
            title=f"Qubit {i + 1}, (l, w, h) = ({xyz.z}, {xyz.x}, {xyz.y})",
        )


def add_magic_state_qubits(
    builder: SVGBuilder,
    xyzs: list[XYZ],
    n1: int,
    n2: int,
    w: int,
    block_size: int,
    colors: ColorScheme,
):
    """Add magic state qubit rectangles."""
    for i in range(n1, n1 + n2):
        xyz = xyzs[i]
        builder.add_rectangle(
            xyz.svg_x(w, block_size) + 1,
            xyz.svg_y(block_size) + 1,
            block_size - 2,
            block_size - 2,
            colors.magic_state,
            "",
            0,
            title=f"Qubit {i + 1}, (l, w, h) = ({xyz.z}, {xyz.x}, {xyz.y})",
        )


def add_layer_separators(
    builder: SVGBuilder, l: int, w: int, h: int, block_size: int, colors: ColorScheme
):
    """Add separators between layers."""
    for d2 in range(1, l):
        x = d2 * w * block_size + (d2 - 1 + 0.45) * SVGBuilder.DW
        y = -0.02 * h * block_size
        width = 0.1 * SVGBuilder.DW
        height = 1.04 * h * block_size

        builder.add_rectangle(
            int(x), int(y), int(width), int(height), colors.separator, "", 0
        )


def make_doc_base(
    l: int,
    w: int,
    h: int,
    n1: int,
    n2: int,
    xyzs: list[XYZ],
    block_size: int,
    is_first: bool,
    siteconfig: Optional[str],
    dont_show_ids: bool,
) -> str:
    """Create base SVG document with grid and qubits."""
    colors = ColorScheme()
    builder = SVGBuilder()

    add_grid(builder, l, w, h, block_size, colors)
    add_logical_qubits(builder, xyzs, n1, w, block_size, siteconfig, colors)
    add_magic_state_qubits(builder, xyzs, n1, n2, w, block_size, colors)
    add_layer_separators(builder, l, w, h, block_size, colors)

    if is_first and not dont_show_ids:
        add_qubit_id_texts(builder, w, n1, n2, xyzs, block_size)

    return builder.build(l, w * block_size, h * block_size)


@dataclass
class Output:
    """Parsed output data."""

    l: int
    w: int
    h: int
    n1: int
    n2: int
    xyzs: list[XYZ]
    targets: list[list[int]]
    paths: list[list[tuple[int, XYZ, XYZ]]]
    max_turn: int
    doc_base: str
    siteconfig: Optional[str]


def validate_siteconfig(siteconfig: Optional[str], n1: int):
    """Validate site configuration string."""
    if siteconfig is not None:
        if len(siteconfig) != n1:
            print(
                f"Error: siteconfig length ({len(siteconfig)}) "
                f"does not match qubit count ({n1})",
                file=sys.stderr,
            )
            sys.exit(1)
        if not all(c.isdigit() for c in siteconfig):
            print("Error: siteconfig must contain only digits", file=sys.stderr)
            sys.exit(1)


def parse_path_data(
    words: list[str], index: int
) -> tuple[list[tuple[int, int, int, int]], int]:
    """Parse path data from word list."""
    path_len, index = read_int(words, index)
    path = []

    for _ in range(path_len):
        t, index = read_int(words, index)
        x, index = read_int(words, index)
        y, index = read_int(words, index)
        z, index = read_int(words, index)
        path.append((t, x, y, z))

    return path, index


def process_path_segment(
    paths: list[list[tuple[int, XYZ, XYZ]]],
    id: int,
    current: tuple[int, int, int, int],
    next_seg: tuple[int, int, int, int],
):
    """Process a single path segment."""
    t_0 = current[0]
    t_1 = next_seg[0]
    u = XYZ(current[1], current[2], current[3])
    v = XYZ(next_seg[1], next_seg[2], next_seg[3])

    if t_0 != t_1:
        assert u.x == v.x and u.y == v.y and u.z == v.z, (
            "Time slice movement must be at same position"
        )
        if t_0 > t_1:
            paths[t_0 + 1].append((id, u, v))
            paths[t_1 + 1].append((~id, u, v))  # Bitwise NOT for negative ID
        else:
            paths[t_0 + 1].append((~id, u, v))
            paths[t_1 + 1].append((id, u, v))
    else:
        assert u.is_adjacent(v), "Same-turn movement must be adjacent"
        paths[t_0 + 1].append((id, u, v))


def apply_msf_transform(
    w: int,
    h: int,
    n1: int,
    xyzs: list[XYZ],
    paths: list[list[tuple[int, XYZ, XYZ]]],
    max_turn: int,
) -> tuple[int, int, int, list[XYZ], list[list[tuple[int, XYZ, XYZ]]]]:
    """Apply MSF (Magic State Factory) transform by removing border."""
    new_w = max(w - 2, w)
    new_h = max(h - 2, h)
    new_n2 = 0

    new_xyzs = []
    for i in range(n1):
        old_xyz = xyzs[i]
        assert old_xyz.x >= 1 and old_xyz.y >= 1, (
            "MSF transform requires border coordinates"
        )
        new_xyzs.append(XYZ(old_xyz.x - 1, old_xyz.y - 1, old_xyz.z))

    new_paths = [[] for _ in range(max_turn + 1)]
    for turn in range(max_turn + 1):
        for id, u, v in paths[turn]:
            assert u.x >= 1 and u.y >= 1 and v.x >= 1 and v.y >= 1, (
                "MSF transform requires border coordinates in paths"
            )
            new_u = XYZ(u.x - 1, u.y - 1, u.z)
            new_v = XYZ(v.x - 1, v.y - 1, v.z)
            new_paths[turn].append((id, new_u, new_v))

    return new_w, new_h, new_n2, new_xyzs, new_paths


def parse_output(
    content: str, siteconfig: Optional[str], config: RenderConfig
) -> Output:
    """Parse output file content."""
    words = content.split()
    index = 0

    w, index = read_int(words, index)
    h, index = read_int(words, index)
    l, index = read_int(words, index)
    n1, index = read_int(words, index)
    n2, index = read_int(words, index)
    total = n1 + n2

    validate_siteconfig(siteconfig, n1)

    # Parse qubit positions
    xyzs = []
    for _ in range(total):
        xyz, index = XYZ.from_words(words, index, w, h, l)
        xyzs.append(xyz)

    m, index = read_int(words, index)
    max_turn_raw, index = read_int(words, index)
    max_turn = max_turn_raw + 1

    targets = []
    paths = [[] for _ in range(max_turn + 1)]

    # Parse instructions and paths
    for id in range(m):
        cnt, index = read_int(words, index)
        target_inst = []
        for _ in range(cnt):
            t_id, index = read_int(words, index)
            assert t_id < total, f"Target ID {t_id} out of bounds (total={total})"
            target_inst.append(t_id)
        targets.append(target_inst)

        path_data, index = parse_path_data(words, index)
        for i in range(len(path_data) - 1):
            process_path_segment(paths, id, path_data[i], path_data[i + 1])

    # Apply MSF transform if requested
    if config.dont_show_msf:
        final_w, final_h, final_n2, final_xyzs, final_paths = apply_msf_transform(
            w, h, n1, xyzs, paths, max_turn
        )
    else:
        final_w, final_h, final_n2, final_xyzs, final_paths = w, h, n2, xyzs, paths

    block_size = 600 // max(final_w, final_h)
    doc_base = make_doc_base(
        l,
        final_w,
        final_h,
        n1,
        final_n2,
        final_xyzs,
        block_size,
        False,
        siteconfig,
        config.dont_show_ids,
    )

    return Output(
        l=l,
        w=final_w,
        h=final_h,
        n1=n1,
        n2=final_n2,
        xyzs=final_xyzs,
        targets=targets,
        paths=final_paths,
        max_turn=max_turn,
        doc_base=doc_base,
        siteconfig=siteconfig,
    )


def add_rounded_rect(
    builder: SVGBuilder,
    x: int,
    y: int,
    width: int,
    height: int,
    color: str,
    block_size: int,
    title: str,
):
    """Add rounded rectangle for path visualization."""
    rx = ry = block_size // 6
    builder.add_rectangle(x, y, width, height, color, "", 0, rx, ry, title)


def add_path_cross_layer(
    builder: SVGBuilder,
    texts: list[tuple[str, int, int, int]],
    u: XYZ,
    v: XYZ,
    color: str,
    block_size: int,
    output: Output,
    title: str,
):
    """Add cross-layer path visualization."""
    x1 = u.svg_x(output.w, block_size) + block_size // 3
    x2 = v.svg_x(output.w, block_size) + block_size // 3
    y = u.svg_y(block_size) + block_size // 3
    size = block_size // 3

    add_rounded_rect(builder, x1, y, size, size, color, block_size, title)
    add_rounded_rect(builder, x2, y, size, size, color, block_size, title)

    # Add circle symbols
    texts.append(
        (
            "◉",
            u.svg_x(output.w, block_size) + block_size // 2,
            u.svg_y(block_size) + block_size // 2,
            block_size // 3,
        )
    )
    texts.append(
        (
            "◉",
            v.svg_x(output.w, block_size) + block_size // 2,
            v.svg_y(block_size) + block_size // 2,
            block_size // 3,
        )
    )


def add_path_same_layer(
    builder: SVGBuilder,
    u: XYZ,
    v: XYZ,
    color: str,
    block_size: int,
    output: Output,
    title: str,
):
    """Add same-layer path visualization."""
    x = (
        (min(u.x, v.x) + u.z * output.w) * block_size
        + block_size // 3
        + SVGBuilder.DW * u.z
    )
    y = min(u.y, v.y) * block_size + block_size // 3

    if u.x == v.x:
        width = block_size // 3
        height = block_size * 4 // 3
    else:
        width = block_size * 4 // 3
        height = block_size // 3

    add_rounded_rect(builder, x, y, width, height, color, block_size, title)


def add_path_time_slice(
    builder: SVGBuilder,
    texts: list[tuple[str, int, int, int]],
    u: XYZ,
    color: str,
    block_size: int,
    output: Output,
    title: str,
    is_positive_id: bool,
    is_drawn: set[tuple[int, int]],
):
    """Add time-slice path visualization."""
    x = u.svg_x(output.w, block_size) + block_size // 3
    y = u.svg_y(block_size) + block_size // 3
    coord_key = (x, y)

    if coord_key in is_drawn:
        return
    is_drawn.add(coord_key)

    size = block_size // 3
    add_rounded_rect(builder, x, y, size, size, color, block_size, title)

    text_x = u.svg_x(output.w, block_size) + block_size // 2
    text_y = u.svg_y(block_size) + block_size // 2

    if is_positive_id:
        symbol = "⊗"
        font_size = round(block_size / 2.5)
        text_y += block_size // 30
    else:
        symbol = "⨀"
        font_size = round(block_size / 3.1)

    texts.append((symbol, text_x, text_y, font_size))


def add_path(
    builder: SVGBuilder,
    texts: list[tuple[str, int, int, int]],
    i: int,
    u: XYZ,
    v: XYZ,
    block_size: int,
    output: Output,
    colors: ColorScheme,
    is_positive_id: bool,
    is_drawn: set[tuple[int, int]],
):
    """Add path visualization based on path type."""
    color = colors.path_colors[i % len(colors.path_colors)]
    title = f"Inst {i} ({output.targets[i][0] + 1} - {output.targets[i][1] + 1})"

    # Determine path type
    if u.z != v.z:
        # Cross-layer
        add_path_cross_layer(builder, texts, u, v, color, block_size, output, title)
    elif u.x != v.x or u.y != v.y:
        # Same layer
        add_path_same_layer(builder, u, v, color, block_size, output, title)
    else:
        # Time slice
        add_path_time_slice(
            builder,
            texts,
            u,
            color,
            block_size,
            output,
            title,
            is_positive_id,
            is_drawn,
        )


def vis(output: Output, turn: int, config: RenderConfig) -> tuple[int, str, str, str]:
    """Visualize a specific turn."""
    colors = ColorScheme()
    score = output.max_turn
    block_size = 600 // max(output.w, output.h)

    if turn == 0:
        # First turn - show base with IDs
        doc_base = make_doc_base(
            output.l,
            output.w,
            output.h,
            output.n1,
            output.n2,
            output.xyzs,
            block_size,
            True,
            output.siteconfig,
            config.dont_show_ids,
        )
        builder = SVGBuilder()
        builder.elements = [doc_base[doc_base.find("<rect") : doc_base.rfind("</svg>")]]
    else:
        # Parse base document and add paths
        builder = SVGBuilder()
        # Copy base elements
        doc_base_content = output.doc_base
        start = doc_base_content.find("<rect")
        end = doc_base_content.rfind("</svg>")
        if start >= 0 and end >= 0:
            base_content = doc_base_content[start:end]
            builder.elements.append(base_content)

        texts: list[tuple[str, int, int, int]] = []
        is_drawn = set()

        for id, u, v in output.paths[turn]:
            actual_id = id if id >= 0 else ~id
            is_positive = id >= 0
            add_path(
                builder,
                texts,
                actual_id,
                u,
                v,
                block_size,
                output,
                colors,
                is_positive,
                is_drawn,
            )

        # Add text elements
        for text, x, y, font_size in texts:
            builder.add_text(text, x, y, font_size)

        if not config.dont_show_ids:
            add_qubit_id_texts(
                builder, output.w, output.n1, output.n2, output.xyzs, block_size
            )

    # Add turn label if needed
    if not config.dont_show_msf and not config.dont_show_turns:
        builder.add_text(f"Turn {turn}", 60, 10, 20, "gray", "start")

    svg_string = builder.build(output.l, output.w * block_size, output.h * block_size)
    return (score, "", "", svg_string)


def main():
    """Main entry point."""
    args = sys.argv[1:]

    if len(args) < 1:
        print(
            "Usage: out2png <input_file> [--siteconfig <config_string>] "
            "[--dont_show_msf] [--dont_show_ids]",
            file=sys.stderr,
        )
        print("No input file provided. Exiting.", file=sys.stderr)
        return

    input_path = Path(args[0])

    if not input_path.is_file():
        print(f"Error: File not found or not accessible: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Parse optional arguments
    siteconfig: Optional[str] = None
    dont_show_msf = False
    dont_show_turns = False
    dont_show_ids = False

    i = 1
    while i < len(args):
        if args[i] == "--siteconfig":
            if i + 1 >= len(args):
                print(
                    "Error: --siteconfig requires a config string argument.",
                    file=sys.stderr,
                )
                sys.exit(1)
            siteconfig = args[i + 1]
            i += 2
        elif args[i] == "--dont_show_msf":
            dont_show_msf = True
            i += 1
        elif args[i] == "--dont_show_turns":
            dont_show_turns = True
            i += 1
        elif args[i] == "--dont_show_ids":
            dont_show_ids = True
            i += 1
        else:
            print(f"Error: Unknown argument: {args[i]}", file=sys.stderr)
            print(
                "Usage: out2png <input_file> [--siteconfig <config_string>] "
                "[--dont_show_msf] [--dont_show_ids]",
                file=sys.stderr,
            )
            sys.exit(1)

    # Read input file
    try:
        content = input_path.read_text()
    except Exception as e:
        print(f"Error: Unable to read file {input_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Configure rendering
    config = RenderConfig(
        dont_show_msf=dont_show_msf,
        dont_show_turns=dont_show_turns,
        dont_show_ids=dont_show_ids,
    )

    # Parse output
    output = parse_output(content, siteconfig, config)

    # Generate SVG data
    step = 1
    svg_data = {}

    max_turn = min(output.max_turn, 100)
    for turn in range(0, max_turn + 1, step):
        _, _, _, svg_string = vis(output, turn, config)
        svg_data[f"{turn:03d}"] = svg_string

    print(json.dumps(svg_data))


if __name__ == "__main__":
    main()
