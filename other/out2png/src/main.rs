mod util;

use std::env;
use std::fs;
use std::path::Path;

fn main() {
    // Get command line arguments
    let args: Vec<String> = env::args().collect();

    if args.len() < 2 {
        println!("Usage: out2png <input_file> [--siteconfig <config_string>] [--dont_show_msf] [--dont_show_ids]");
        println!("No input file provided. Exiting.");
        return;
    }

    let input_path_str = &args[1];
    let input_path = Path::new(input_path_str);

    if !input_path.is_file() {
        eprintln!("Error: File not found or not accessible: {:?}", input_path);
        std::process::exit(1);
    }

    // Parse optional arguments
    let mut siteconfig = None;
    let mut dont_show_msf = false;
    let mut dont_show_turns = false;
    let mut dont_show_ids = false;

    let mut i = 2;
    while i < args.len() {
        match args[i].as_str() {
            "--siteconfig" => {
                if i + 1 >= args.len() {
                    eprintln!("Error: --siteconfig requires a config string argument.");
                    std::process::exit(1);
                }
                siteconfig = Some(args[i + 1].clone());
                i += 2;
            }
            "--dont_show_msf" => {
                dont_show_msf = true;
                i += 1;
            }
            "--dont_show_turns" => {
                dont_show_turns = true;
                i += 1;
            }
            "--dont_show_ids" => {
                dont_show_ids = true;
                i += 1;
            }
            _ => {
                eprintln!("Error: Unknown argument: {}", args[i]);
                eprintln!(
                    "Usage: out2png <input_file> [--siteconfig <config_string>] [--dont_show_msf] [--dont_show_ids]"
                );
                std::process::exit(1);
            }
        }
    }

    let content = match fs::read_to_string(&input_path) {
        Ok(content) => content,
        Err(e) => {
            eprintln!("Error: Unable to read file {:?}: {}", input_path, e);
            std::process::exit(1);
        }
    };

    let config = util::RenderConfig {
        dont_show_msf,
        dont_show_turns,
        dont_show_ids,
    };

    let output = util::parse_output(&content, siteconfig.as_deref(), &config);

    let step = 1;

    // Create JSON structure with all SVG data
    let mut svg_data = serde_json::Map::new();

    let max_turn = std::cmp::min(output.max_turn, 100usize);
    for turn in (0..max_turn + 1).step_by(step) {
        let (_, _, _, svg_string) = util::vis(&output, turn, &config);
        svg_data.insert(
            format!("{:03}", turn),
            serde_json::Value::String(svg_string),
        );
    }

    // Output JSON to stdout
    let json_output = serde_json::Value::Object(svg_data);
    println!("{}", serde_json::to_string(&json_output).unwrap());
}
