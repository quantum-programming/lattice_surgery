#![allow(non_snake_case, unused_macros)]

use std::collections::HashSet;
use svg::{
    node::element::{Rectangle, Style, Text},
    Node,
};

fn read_int(iter: &mut std::str::SplitWhitespace) -> isize {
    iter.next().unwrap().parse().unwrap()
}

#[derive(Clone, Copy, Debug)]
pub struct XYZ {
    pub x: usize,
    pub y: usize,
    pub z: usize,
}

const DW: usize = 50;
impl XYZ {
    pub fn new(x: usize, y: usize, z: usize) -> XYZ {
        XYZ { x, y, z }
    }

    pub fn from(iter: &mut std::str::SplitWhitespace, w: usize, h: usize, l: usize) -> XYZ {
        let x = read_int(iter) as usize;
        let y = read_int(iter) as usize;
        let z = read_int(iter) as usize;
        assert!(x < w && y < h && z < l);
        XYZ { x, y, z }
    }

    pub fn svg_x(&self, w: usize, block_size: usize) -> usize {
        (self.x + self.z * w) * block_size + DW * self.z
    }

    pub fn svg_y(&self, block_size: usize) -> usize {
        self.y * block_size
    }

    pub fn is_adjacent(&self, other: &XYZ) -> bool {
        let dx = (self.x as isize - other.x as isize).abs();
        let dy = (self.y as isize - other.y as isize).abs();
        let dz = (self.z as isize - other.z as isize).abs();
        (dx + dy + dz) == 1
    }
}

pub struct RenderConfig {
    pub dont_show_msf: bool,
    pub dont_show_turns: bool,
    pub dont_show_ids: bool,
}

pub struct ColorScheme {
    pub grid_fill: &'static str,
    pub grid_stroke: &'static str,
    pub system_qubit: &'static str,
    pub control_qubit: &'static str,
    pub control_ancilla: &'static str,
    pub magic_state: &'static str,
    pub separator: &'static str,
    pub path_colors: &'static [&'static str],
}

impl Default for ColorScheme {
    fn default() -> Self {
        Self {
            grid_fill: "#dae3f3",
            grid_stroke: "#1f77b4",
            system_qubit: "#1f77b4",
            control_qubit: "#ff7f0e",
            control_ancilla: "#2ca02c",
            magic_state: "#808080",
            separator: "#111111",
            path_colors: &[
                "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
            ],
        }
    }
}

fn get_qubit_color(config_char: char, colors: &ColorScheme) -> String {
    assert!(config_char.is_ascii_digit());
    assert!('0' <= config_char && config_char <= '2');
    match config_char {
        '0' => colors.system_qubit.to_string(),
        '1' => colors.control_qubit.to_string(),
        '2' => colors.control_ancilla.to_string(),
        _ => "unknown".to_string(), // This case should not happen
    }
}

fn add_qubit_text(
    doc: &mut svg::Document,
    text: &str,
    xyz: &XYZ,
    w: usize,
    block_size: usize,
    font_size: usize,
    offset: (usize, usize),
) {
    doc.append(
        Text::new(text)
            .set("x", xyz.svg_x(w, block_size) + offset.0)
            .set("y", xyz.svg_y(block_size) + offset.1)
            .set("fill", "black")
            .set("font-size", font_size),
    );
}

pub fn add_qubit_id_texts(
    doc: &mut svg::Document,
    w: usize,
    n1: usize,
    n2: usize,
    xyzs: &[XYZ],
    block_size: usize,
) {
    let font_size = if n1 < 100 {
        block_size * 2 / 3
    } else {
        block_size / 2
    };

    for i in 0..n1 {
        add_qubit_text(
            doc,
            &format!("{}", i + 1),
            &xyzs[i],
            w,
            block_size,
            font_size,
            (block_size / 2, block_size / 2),
        );
    }

    for i in 0..n2 {
        add_qubit_text(
            doc,
            "M",
            &xyzs[n1 + i],
            w,
            block_size,
            font_size / 2,
            (block_size / 4, block_size / 4),
        );
    }
}

fn add_rectangle(
    doc: &mut svg::Document,
    x: usize,
    y: usize,
    width: usize,
    height: usize,
    fill: &str,
    stroke: &str,
    stroke_width: usize,
    title: &str,
) {
    doc.append(
        Rectangle::new()
            .set("x", x)
            .set("y", y)
            .set("width", width)
            .set("height", height)
            .set("fill", fill)
            .set("stroke", stroke)
            .set("stroke-width", stroke_width)
            .add(svg::node::element::Title::new(title)),
    );
}

fn create_svg_document(l: usize, w: usize, h: usize) -> svg::Document {
    let width = l * w + (l - 1) * DW + 10;
    let height = h + 10;
    svg::Document::new()
        .set("id", "vis")
        .set("viewBox", (-5, -5, width, height))
        .set("width", width)
        .set("height", height)
        .set("style", "background-color:white")
        .add(Style::new(
            "text {text-anchor: middle; dominant-baseline: central; user-select: none;}",
        ))
}

fn add_grid(
    doc: &mut svg::Document,
    l: usize,
    w: usize,
    h: usize,
    block_size: usize,
    colors: &ColorScheme,
) {
    for d2 in 0..l {
        for w2 in 0..w {
            for h2 in 0..h {
                add_rectangle(
                    doc,
                    (w2 + d2 * w) * block_size + DW * d2,
                    h2 * block_size,
                    block_size,
                    block_size,
                    colors.grid_fill,
                    colors.grid_stroke,
                    2,
                    &format!("(l, w, h) = ({}, {}, {})", d2, w2, h2),
                );
            }
        }
    }
}

fn add_logical_qubits(
    doc: &mut svg::Document,
    xyzs: &[XYZ],
    n1: usize,
    w: usize,
    block_size: usize,
    siteconfig: Option<&str>,
    colors: &ColorScheme,
) {
    for i in 0..n1 {
        let color = if let Some(config_str) = siteconfig {
            let config_char = config_str.chars().nth(i).unwrap_or('0');
            get_qubit_color(config_char, colors)
        } else {
            colors.system_qubit.to_string()
        };

        let xyz = &xyzs[i];
        add_rectangle(
            doc,
            xyz.svg_x(w, block_size) + 1,
            xyz.svg_y(block_size) + 1,
            block_size - 2,
            block_size - 2,
            &color,
            "",
            0,
            &format!(
                "Qubit {}, (l, w, h) = ({}, {}, {})",
                i + 1,
                xyz.z,
                xyz.x,
                xyz.y
            ),
        );
    }
}

fn add_magic_state_qubits(
    doc: &mut svg::Document,
    xyzs: &[XYZ],
    n1: usize,
    n2: usize,
    w: usize,
    block_size: usize,
    colors: &ColorScheme,
) {
    for i in n1..n1 + n2 {
        let xyz = &xyzs[i];
        add_rectangle(
            doc,
            xyz.svg_x(w, block_size) + 1,
            xyz.svg_y(block_size) + 1,
            block_size - 2,
            block_size - 2,
            colors.magic_state,
            "",
            0,
            &format!(
                "Qubit {}, (l, w, h) = ({}, {}, {})",
                i + 1,
                xyz.z,
                xyz.x,
                xyz.y
            ),
        );
    }
}

fn add_layer_separators(
    doc: &mut svg::Document,
    l: usize,
    w: usize,
    h: usize,
    block_size: usize,
    colors: &ColorScheme,
) {
    for d2 in 1..l {
        doc.append(
            Rectangle::new()
                .set(
                    "x",
                    (d2 as f64) * (w as f64 * block_size as f64)
                        + (d2 as f64 - 1.0 + 0.45) * (DW as f64),
                )
                .set("y", -0.02 * h as f64 * block_size as f64)
                .set("width", 0.1 * (DW as f64))
                .set("height", 1.04 * h as f64 * block_size as f64)
                .set("fill", colors.separator),
        );
    }
}

pub fn make_doc_base(
    l: usize,
    w: usize,
    h: usize,
    n1: usize,
    n2: usize,
    xyzs: &[XYZ],
    block_size: usize,
    is_first: bool,
    siteconfig: Option<&str>,
    dont_show_ids: bool,
) -> svg::Document {
    let colors = ColorScheme::default();
    let mut doc = create_svg_document(l, w * block_size, h * block_size);

    add_grid(&mut doc, l, w, h, block_size, &colors);
    add_logical_qubits(&mut doc, xyzs, n1, w, block_size, siteconfig, &colors);
    add_magic_state_qubits(&mut doc, xyzs, n1, n2, w, block_size, &colors);
    add_layer_separators(&mut doc, l, w, h, block_size, &colors);

    if is_first && !dont_show_ids {
        add_qubit_id_texts(&mut doc, w, n1, n2, xyzs, block_size);
    }

    doc
}

pub struct Output {
    pub l: usize,
    pub w: usize,
    pub h: usize,
    pub n1: usize,
    pub n2: usize,
    pub xyzs: Vec<XYZ>,
    pub targets: Vec<Vec<usize>>,
    pub paths: Vec<Vec<(isize, XYZ, XYZ)>>,
    pub max_turn: usize,
    pub doc_base: svg::Document,
    pub siteconfig: Option<String>,
}

fn validate_siteconfig(siteconfig: Option<&str>, n1: usize) {
    if let Some(config_str) = siteconfig {
        if config_str.len() != n1 {
            eprintln!(
                "Error: siteconfig length ({}) does not match qubit count ({})",
                config_str.len(),
                n1
            );
            std::process::exit(1);
        }
        if !config_str.chars().all(|c| c.is_ascii_digit()) {
            eprintln!("Error: siteconfig must contain only digits");
            std::process::exit(1);
        }
    }
}

fn parse_path_data(iter: &mut std::str::SplitWhitespace) -> Vec<(isize, isize, isize, isize)> {
    let path_len = read_int(iter) as usize;
    let mut path = Vec::with_capacity(path_len);
    for _ in 0..path_len {
        path.push((
            read_int(iter),
            read_int(iter),
            read_int(iter),
            read_int(iter),
        ));
    }
    path
}

fn process_path_segment(
    paths: &mut Vec<Vec<(isize, XYZ, XYZ)>>,
    id: usize,
    current: (isize, isize, isize, isize),
    next: (isize, isize, isize, isize),
) {
    let t_0 = current.0 as usize;
    let t_1 = next.0 as usize;
    let u = XYZ::new(current.1 as usize, current.2 as usize, current.3 as usize);
    let v = XYZ::new(next.1 as usize, next.2 as usize, next.3 as usize);

    if t_0 != t_1 {
        assert!(u.x == v.x && u.y == v.y && u.z == v.z);
        if t_0 > t_1 {
            paths[t_0 + 1].push((id as isize, u, v));
            paths[t_1 + 1].push((!(id as isize), u, v));
        } else {
            paths[t_0 + 1].push((!(id as isize), u, v));
            paths[t_1 + 1].push((id as isize, u, v));
        }
    } else {
        assert!(u.is_adjacent(&v));
        paths[t_0 + 1].push((id as isize, u, v));
    }
}

fn apply_msf_transform(
    w: usize,
    h: usize,
    n1: usize,
    xyzs: &[XYZ],
    paths: &[Vec<(isize, XYZ, XYZ)>],
    max_turn: usize,
) -> (usize, usize, usize, Vec<XYZ>, Vec<Vec<(isize, XYZ, XYZ)>>) {
    let new_w = if w >= 2 { w - 2 } else { w };
    let new_h = if h >= 2 { h - 2 } else { h };
    let new_n2 = 0;

    let mut new_xyzs = Vec::with_capacity(n1);
    for i in 0..n1 {
        let old_xyz = &xyzs[i];
        assert!(old_xyz.x >= 1 && old_xyz.y >= 1);
        new_xyzs.push(XYZ::new(old_xyz.x - 1, old_xyz.y - 1, old_xyz.z));
    }

    let mut new_paths = vec![vec![]; max_turn + 1];
    for turn in 0..=max_turn {
        for (id, u, v) in &paths[turn] {
            assert!(u.x >= 1 && u.y >= 1 && v.x >= 1 && v.y >= 1);
            let new_u = XYZ::new(u.x - 1, u.y - 1, u.z);
            let new_v = XYZ::new(v.x - 1, v.y - 1, v.z);
            new_paths[turn].push((*id, new_u, new_v));
        }
    }

    (new_w, new_h, new_n2, new_xyzs, new_paths)
}

pub fn parse_output(f: &str, siteconfig: Option<&str>, config: &RenderConfig) -> Output {
    let mut iter = f.split_whitespace();

    let w = read_int(&mut iter) as usize;
    let h = read_int(&mut iter) as usize;
    let l = read_int(&mut iter) as usize;
    let n1 = read_int(&mut iter) as usize;
    let n2 = read_int(&mut iter) as usize;
    let total = n1 + n2;

    validate_siteconfig(siteconfig, n1);

    let mut xyzs = Vec::with_capacity(total);
    for _ in 0..total {
        xyzs.push(XYZ::from(&mut iter, w, h, l));
    }

    let m = read_int(&mut iter) as usize;
    let max_turn = read_int(&mut iter) as usize + 1;

    let mut targets = Vec::with_capacity(m);
    let mut paths = vec![vec![]; max_turn + 1];

    for id in 0..m {
        let cnt = read_int(&mut iter) as usize;
        let mut target_inst = Vec::with_capacity(cnt);
        for _ in 0..cnt {
            let t_id = read_int(&mut iter) as usize;
            assert!(t_id < total);
            target_inst.push(t_id);
        }
        targets.push(target_inst);

        let path_data = parse_path_data(&mut iter);
        for window in path_data.windows(2) {
            process_path_segment(&mut paths, id, window[0], window[1]);
        }
    }

    let (final_w, final_h, final_n2, final_xyzs, final_paths) = if config.dont_show_msf {
        apply_msf_transform(w, h, n1, &xyzs, &paths, max_turn)
    } else {
        (w, h, n2, xyzs, paths)
    };

    let block_size = 600 / std::cmp::max(final_w, final_h);
    let doc_base = make_doc_base(
        l,
        final_w,
        final_h,
        n1,
        final_n2,
        &final_xyzs,
        block_size,
        false,
        siteconfig,
        config.dont_show_ids,
    );

    Output {
        l,
        w: final_w,
        h: final_h,
        n1,
        n2: final_n2,
        xyzs: final_xyzs,
        targets,
        paths: final_paths,
        max_turn,
        doc_base,
        siteconfig: siteconfig.map(|s| s.to_string()),
    }
}

enum PathType {
    CrossLayer,
    SameLayer,
    TimeSlice,
}

impl PathType {
    fn from_coordinates(u: &XYZ, v: &XYZ) -> Self {
        if u.z != v.z {
            Self::CrossLayer
        } else if u.x != v.x || u.y != v.y {
            Self::SameLayer
        } else {
            Self::TimeSlice
        }
    }
}

fn add_rounded_rect(
    doc: &mut svg::Document,
    x: usize,
    y: usize,
    width: usize,
    height: usize,
    color: &str,
    block_size: usize,
    title: &str,
) {
    doc.append(
        Rectangle::new()
            .set("x", x)
            .set("y", y)
            .set("width", width)
            .set("height", height)
            .set("fill", color)
            .set("rx", block_size / 6)
            .set("ry", block_size / 6)
            .add(svg::node::element::Title::new(title)),
    );
}

fn add_path_cross_layer(
    doc: &mut svg::Document,
    texts: &mut Vec<Text>,
    u: &XYZ,
    v: &XYZ,
    color: &str,
    block_size: usize,
    output: &Output,
    title: &str,
) {
    let x1 = u.svg_x(output.w, block_size) + block_size / 3;
    let x2 = v.svg_x(output.w, block_size) + block_size / 3;
    let y = u.svg_y(block_size) + block_size / 3;
    let size = block_size / 3;

    add_rounded_rect(doc, x1, y, size, size, color, block_size, title);
    add_rounded_rect(doc, x2, y, size, size, color, block_size, title);

    texts.push(
        Text::new("◉")
            .set("x", u.svg_x(output.w, block_size) + block_size / 2)
            .set("y", u.svg_y(block_size) + block_size / 2)
            .set("font-size", block_size / 3)
            .set("zorder", 100),
    );
    texts.push(
        Text::new("◉")
            .set("x", v.svg_x(output.w, block_size) + block_size / 2)
            .set("y", v.svg_y(block_size) + block_size / 2)
            .set("font-size", block_size / 3),
    );
}

fn add_path_same_layer(
    doc: &mut svg::Document,
    u: &XYZ,
    v: &XYZ,
    color: &str,
    block_size: usize,
    output: &Output,
    title: &str,
) {
    let x = (std::cmp::min(u.x, v.x) + u.z * output.w) * block_size + block_size / 3 + DW * u.z;
    let y = std::cmp::min(u.y, v.y) * block_size + block_size / 3;
    let width = if u.x == v.x {
        block_size / 3
    } else {
        block_size * 4 / 3
    };
    let height = if u.y == v.y {
        block_size / 3
    } else {
        block_size * 4 / 3
    };

    add_rounded_rect(doc, x, y, width, height, color, block_size, title);
}

fn add_path_time_slice(
    doc: &mut svg::Document,
    texts: &mut Vec<Text>,
    u: &XYZ,
    color: &str,
    block_size: usize,
    output: &Output,
    title: &str,
    is_positive_id: bool,
    is_drawn: &mut HashSet<(usize, usize)>,
) {
    let x = u.svg_x(output.w, block_size) + block_size / 3;
    let y = u.svg_y(block_size) + block_size / 3;
    let coord_key = (x, y);

    if is_drawn.contains(&coord_key) {
        return;
    }
    is_drawn.insert(coord_key);

    let size = block_size / 3;
    add_rounded_rect(doc, x, y, size, size, color, block_size, title);

    let text_x = u.svg_x(output.w, block_size) + block_size / 2;
    let mut text_y = u.svg_y(block_size) + block_size / 2;

    let (symbol, font_size) = if is_positive_id {
        text_y += block_size / 30;
        ("⊗", (block_size as f64 / 2.5).round() as usize)
    } else {
        ("⨀", (block_size as f64 / 3.1).round() as usize)
    };

    texts.push(
        Text::new(symbol)
            .set("x", text_x)
            .set("y", text_y)
            .set("font-size", font_size)
            .set("zorder", 100),
    );
}

fn add_path(
    doc: &mut svg::Document,
    texts: &mut Vec<Text>,
    i: usize,
    u: XYZ,
    v: XYZ,
    block_size: usize,
    output: &Output,
    colors: &ColorScheme,
    is_positive_id: bool,
    is_drawn: &mut HashSet<(usize, usize)>,
) {
    let color = colors.path_colors[i % colors.path_colors.len()];
    let title = format!(
        "Inst {} ({} - {})",
        i,
        output.targets[i][0] + 1,
        output.targets[i][1] + 1
    );

    match PathType::from_coordinates(&u, &v) {
        PathType::CrossLayer => {
            add_path_cross_layer(doc, texts, &u, &v, color, block_size, output, &title)
        }
        PathType::SameLayer => add_path_same_layer(doc, &u, &v, color, block_size, output, &title),
        PathType::TimeSlice => add_path_time_slice(
            doc,
            texts,
            &u,
            color,
            block_size,
            output,
            &title,
            is_positive_id,
            is_drawn,
        ),
    }
}

pub fn vis(output: &Output, turn: usize, config: &RenderConfig) -> (i64, String, String, String) {
    let colors = ColorScheme::default();
    let score = output.max_turn as i64;
    let block_size = 600 / std::cmp::max(output.w, output.h);
    let mut doc = output.doc_base.clone();

    if turn == 0 {
        doc = make_doc_base(
            output.l,
            output.w,
            output.h,
            output.n1,
            output.n2,
            &output.xyzs,
            block_size,
            true,
            output.siteconfig.as_deref(),
            config.dont_show_ids,
        );
    } else {
        let mut texts = vec![];
        let mut is_drawn = HashSet::new();

        for (id, u, v) in &output.paths[turn] {
            add_path(
                &mut doc,
                &mut texts,
                if *id >= 0 {
                    *id as usize
                } else {
                    !(*id) as usize
                },
                *u,
                *v,
                block_size,
                output,
                &colors,
                *id >= 0,
                &mut is_drawn,
            );
        }

        for text in texts {
            doc.append(text);
        }

        if !config.dont_show_ids {
            add_qubit_id_texts(
                &mut doc,
                output.w,
                output.n1,
                output.n2,
                &output.xyzs,
                block_size,
            );
        }
    }

    if !config.dont_show_msf && !config.dont_show_turns {
        doc = doc.add(
            Text::new(format!("Turn {}", turn))
                .set("x", 60)
                .set("y", 10)
                .set("fill", "gray")
                .set("font-size", 20)
                .set("text-anchor", "start"),
        );
    }

    (score, String::new(), String::new(), doc.to_string())
}
