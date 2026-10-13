"""Capture the four official TQEC HTML views for the manuscript.

Run on Windows after the WSL comparison: python scripts/render_html_figures.py.
Uses an existing Chrome/Edge installation, no additional Python dependencies.
Only controls are hidden. The embedded model, camera, colors and geometry stay
unchanged. TQEC's HTML imports three.js from unpkg.com, so network is required.
"""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = (
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
)
BROWSER = next((path for path in CANDIDATES if path.is_file()), None)
if BROWSER is None:
    raise FileNotFoundError("Install location of Chrome/Edge was not found.")

work = ROOT / "work/html-figures"
work.mkdir(parents=True, exist_ok=True)
# Presentation-only CSS, applied to a work copy of TQEC's original HTML.
css = """body { margin: 0; font-size: 0; }
body > a, body > br { display: none; }
body > div { width: 100vw !important; height: 100vh !important; font-size: 16px; }
</style>"""
for name in ("mqt_max_parallel", "mqt_min_parallel"):
    for tool in ("ours", "topols"):
        stem = f"{tool}-{name}"
        html = (ROOT / "figures" / f"{stem}.html").read_text()
        prepared = work / f"{stem}.html"
        prepared.write_text(html.replace("</style>", css), encoding="utf-8")
        captured = work / f"{stem}.png"
        completed = subprocess.run([
            str(BROWSER), "--headless=new", "--disable-background-networking",
            "--enable-unsafe-swiftshader", "--use-angle=swiftshader",
            "--hide-scrollbars", "--window-size=1800,1600",
            "--virtual-time-budget=10000", "--dump-dom",
            f"--user-data-dir={work / 'browser-profile'}",
            f"--screenshot={captured}", prepared.as_uri(),
        ], capture_output=True, text=True, timeout=60)
        if completed.returncode or "<canvas" not in completed.stdout or not captured.is_file():
            raise RuntimeError(completed.stderr or f"No screenshot produced for {stem}.")
        shutil.copy2(captured, ROOT / "figures" / f"{stem}.png")
        print(f"Captured {stem}", flush=True)
