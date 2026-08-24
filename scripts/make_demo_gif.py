"""Regenerate docs/demo.gif.

Drives the real widget in headless Chrome — one screenshot per storyboard beat —
and assembles the frames into a GIF. Rerun it whenever the widget's look changes
so the README stays honest.

    uv run --group dev python scripts/make_demo_gif.py

Needs a Chrome or Chromium binary on PATH (or pass --chrome). The demo data is
read from examples/marimo_demo.py via marimo's app.run(), so there is only ever
one copy of it.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import pathlib
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATIC = ROOT / "src" / "anyupset" / "static"
CHROME_CANDIDATES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")

# One entry per frame: how long it stays on screen, and the JS that puts the
# widget into that state. Each step starts from a fresh render, so they are
# independent — no state leaks from one frame to the next.
#
# Interactions get a short "cursor has arrived" beat before the longer frame
# that shows the result, otherwise they read as instantaneous.
STORYBOARD: list[tuple[int, str]] = [
    (800, "point(150, 250);"),
    (650, "hover(6);"),
    (1000, "hover(3);"),
    (1000, "hover(0);"),
    (1350, "pin(); hover(0);"),
    (700, 'pin(); leave(); await frame(); atCentre(".upset-search");'),
    (1400, 'pin(); leave(); await frame();'
           ' const s = atCentre(".upset-search"); s.value = "ter";'
           ' s.dispatchEvent(new Event("input", { bubbles: true }));'),
    (700, 'pin(); leave(); await frame(); atCentre(".upset-copy");'),
    # The button restores its label after 1.4s. Chrome's virtual clock races
    # through that long before the screenshot, so freeze timers to hold the
    # "copied" state. The clipboard stub still resolves, so the copy succeeds.
    (1400, 'pin(); leave(); await frame(); atCentre(".upset-copy");'
           ' window.setTimeout = () => 0;'
           ' host.querySelector(".upset-copy").click(); await frame();'),
    (700, 'pin(); leave(); await frame(); atCentre(".upset-num");'),
    (1800, 'pin(); leave(); await frame();'
           ' const n = atCentre(".upset-num"); n.value = "6";'
           ' n.dispatchEvent(new Event("change", { bubbles: true }));'),
]

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
%(css)s
html,body{margin:0;background:#fff;color:#1b1b1d;
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;}
#wrap{padding:14px 16px;}
#cursor{position:fixed;width:22px;height:22px;pointer-events:none;z-index:99;
  transform:translate(-3px,-2px);filter:drop-shadow(0 1px 2px rgba(0,0,0,.35));display:none;}
</style></head><body>
<div id="wrap"><div id="host"></div></div>
<svg id="cursor" viewBox="0 0 22 22"><path d="M3 2 L3 17 L7.2 13.2 L9.8 19 L12.6 17.7 L10 12 L15.5 12 Z"
  fill="#111" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>
<script type="module">
%(js)s

const payload = %(payload)s;
const fullList = %(full)s;
const step = Number(new URLSearchParams(location.search).get("step") || 0);

// headless Chrome has no user activation, so the real clipboard call would
// fail and the button would read "copy failed" in the recording
Object.defineProperty(navigator, "clipboard", {
  value: { writeText: async () => {} }, configurable: true,
});

const st = { _data: payload, sort_by: "size", min_size: 1, max_degree: 0,
             max_intersections: %(columns)d, selected_mask: -1, selected_values: [] };
const model = { get: k => st[k], set: (k, v) => { st[k] = v; }, save_changes(){}, on(){} };
const host = document.getElementById("host");
render({ model, el: host });

const cursor = document.getElementById("cursor");
function point(x, y) {
  cursor.style.display = "block";
  cursor.style.left = x + "px";
  cursor.style.top = y + "px";
}
const frame = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
const col = j => host.querySelectorAll(".upset-col")[j];

function hover(j, dy = 55) {
  const hit = col(j).querySelector(".upset-hit");
  const r = hit.getBoundingClientRect();
  const x = r.left + r.width / 2, y = r.top + dy;
  hit.dispatchEvent(new MouseEvent("mousemove", { bubbles: true, clientX: x, clientY: y }));
  point(x, y);
}
function leave() {
  host.querySelector(".upset-svg").dispatchEvent(new MouseEvent("mouseleave", { bubbles: true }));
}
function pin() {
  st.selected_values = fullList;   // what Python syncs when a bar is pinned
  col(0).querySelector(".upset-hit").dispatchEvent(new MouseEvent("click", { bubbles: true }));
}
function atCentre(sel) {
  const el = host.querySelector(sel);
  const r = el.getBoundingClientRect();
  point(r.left + r.width / 2, r.top + r.height / 2);
  return el;
}

const script = [
%(steps)s
];
await script[step]();
await frame();
await frame();
</script></body></html>"""


def find_chrome(explicit: str | None) -> str:
    if explicit:
        return explicit
    for name in CHROME_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    sys.exit(f"no Chrome found; tried {', '.join(CHROME_CANDIDATES)} — pass --chrome")


def load_movies() -> list:
    """Read the demo dataset out of the marimo notebook, its only home."""
    sys.path.insert(0, str(ROOT / "examples"))
    from marimo_demo import app  # noqa: PLC0415

    _, defs = app.run()
    return defs["MOVIES"]


def build_page(columns: int) -> str:
    from anyupset import UpSet  # noqa: PLC0415

    widget = UpSet.from_memberships(load_movies())
    widget.selected_mask = widget._data["intersections"][0]["mask"]  # the tallest bar

    steps = "\n".join(f"  async () => {{ {js} }}," for _, js in STORYBOARD)
    return PAGE % {
        "css": (STATIC / "upset.css").read_text(),
        "js": (STATIC / "upset.js").read_text().replace("export default { render };", ""),
        "payload": json.dumps(widget._data),
        "full": json.dumps(widget.selected_values),
        "columns": columns,
        "steps": steps,
    }


def serve(directory: pathlib.Path) -> int:
    """A local server: ES module imports do not work over file://."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "docs" / "demo.gif")
    ap.add_argument("--width", type=int, default=880)
    ap.add_argument("--height", type=int, default=520, help="must clear the whole widget, or it is cropped")
    ap.add_argument("--columns", type=int, default=14, help="max_intersections, i.e. how wide the plot is")
    ap.add_argument("--colors", type=int, default=128)
    ap.add_argument("--chrome", default=None)
    args = ap.parse_args()

    from PIL import Image, ImageChops  # noqa: PLC0415

    chrome = find_chrome(args.chrome)
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        (work / "frame.html").write_text(build_page(args.columns))
        port = serve(work)

        shots = []
        for i in range(len(STORYBOARD)):
            shot = work / f"f_{i:02d}.png"
            subprocess.run(
                [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                 "--force-device-scale-factor=1", f"--window-size={args.width},{args.height}",
                 "--virtual-time-budget=6000", f"--screenshot={shot}",
                 f"http://127.0.0.1:{port}/frame.html?step={i}"],
                check=True, capture_output=True,
            )
            if not shot.exists():
                sys.exit(f"chrome produced no screenshot for step {i}")
            shots.append(Image.open(shot).convert("RGB"))
            print(f"  frame {i + 1}/{len(STORYBOARD)}")

        # crop away the dead space, using the union so every frame stays aligned
        white = Image.new("RGB", shots[0].size, (255, 255, 255))
        box = None
        for f in shots:
            b = ImageChops.difference(f, white).getbbox()
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]),
                                         max(box[2], b[2]), max(box[3], b[3]))
        pad = 8
        box = (max(box[0] - pad, 0), max(box[1] - pad, 0),
               min(box[2] + pad, shots[0].width), min(box[3] + pad, shots[0].height))
        if box[3] >= args.height - pad:
            print("  warning: content reaches the bottom edge; raise --height", file=sys.stderr)
        shots = [f.crop(box) for f in shots]

        for a, b in zip(range(len(shots) - 1), range(1, len(shots))):
            if ImageChops.difference(shots[a], shots[b]).getbbox() is None:
                sys.exit(
                    f"frames {a} and {b} are identical, so step {b} changed nothing "
                    "on screen — fix the storyboard rather than shipping a dead beat"
                )

        quant = [f.quantize(colors=args.colors, method=Image.MEDIANCUT) for f in shots]
        args.out.parent.mkdir(parents=True, exist_ok=True)
        quant[0].save(args.out, save_all=True, append_images=quant[1:],
                      duration=[d for d, _ in STORYBOARD], loop=0, optimize=True, disposal=2)

    total = sum(d for d, _ in STORYBOARD) / 1000
    print(f"wrote {args.out} — {shots[0].size[0]}x{shots[0].size[1]}, "
          f"{len(shots)} frames, {args.out.stat().st_size / 1e6:.2f} MB, {total:.1f}s loop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
