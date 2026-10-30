#!/usr/bin/env python3
"""Check a built crayon page in bb's headless browser.

Usage: check.py PAGE.html

Lists drawings that failed, text that runs outside its picture or overlaps other
text, and a page wider than the chat column. Then saves screenshots at the chat's
desktop (710px) and phone (360px) widths and prints their paths.
Exits 1 when it lists problems. Run it inside a bb thread.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BB = os.environ.get("BB_CLI") or "bb"
DESKTOP, PHONE, SHOT_HEIGHT, MAX_SHOTS = 710, 360, 900, 6

# Runs in the page, laid out like bb's chat frame (no body margin or scrollbar). Text boxes are compared by
# their middle half, so stacked lines don't count as overlapping.
CHECK = """async () => {
  document.body.style.margin = "0";
  document.documentElement.style.scrollbarWidth = "none";
  const late = new Promise((done) => setTimeout(() => done({ errors: ["the drawings never finished; does the scene call crayon.draw?"] }), 10000));
  const missing = Promise.resolve({ errors: ["crayon.js isn't on the page; build it with scripts/build.py"] });
  const ready = await Promise.race([window.crayonReady || missing, late]);
  const problems = [...ready.errors];
  const middle = (r) => ({ left: r.left, right: r.right, top: r.top + r.height / 4, bottom: r.bottom - r.height / 4 });
  for (const svg of document.querySelectorAll("svg[data-draw]")) {
    const name = svg.dataset.draw, pic = svg.getBoundingClientRect();
    const texts = [...svg.querySelectorAll("text:not([data-crayon-error])")].filter((t) => t.textContent.trim());
    const boxes = texts.map((t) => t.getBoundingClientRect());
    texts.forEach((t, i) => {
      const r = boxes[i];
      if (r.left < pic.left - 1 || r.right > pic.right + 1 || r.top < pic.top - 1 || r.bottom > pic.bottom + 1)
        problems.push(`${name}: "${t.textContent}" runs outside the picture`);
    });
    for (let i = 0; i < texts.length; i++)
      for (let j = i + 1; j < texts.length; j++) {
        const a = middle(boxes[i]), b = middle(boxes[j]);
        if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1)
          problems.push(`${name}: "${texts[i].textContent}" overlaps "${texts[j].textContent}"`);
      }
  }
  if (document.documentElement.scrollWidth > innerWidth + 1) problems.push(`the page is wider than the ${innerWidth}px chat column`);
  const notes = [];
  if (document.fonts && !document.fonts.check('16px "Patrick Hand"'))
    notes.push("the handwriting fonts didn't load, so the page used fallback fonts");
  return { height: Math.ceil(document.body.getBoundingClientRect().height), problems, notes };
}"""


def bb(*args, timeout=120):
    result = subprocess.run([BB, *args, "--json"], capture_output=True, text=True, timeout=timeout)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.exit(f"bb {' '.join(args[:2])} failed: {(result.stderr or result.stdout).strip()}")
    if isinstance(data, dict) and data.get("ok") is False:
        sys.exit(f"bb {' '.join(args[:2])} failed: {data['error'].get('message')}")
    return data


def run(session, script):
    data = bb("browser-automation", "run", session, "--timeout", "90s", "--script", script, timeout=150)
    if data.get("exitCode"):
        sys.exit(f"The browser script failed:\n{data.get('text', '')}")
    return data


def shoot(session, width, top, height):
    clip = {"x": 0, "y": top, "width": width, "height": height}
    script = f"""const p = await browser.getPage("crayon-check");
await p.shot({{ clip: {json.dumps(clip)}, maxEdge: 960, quality: 70 }});
undefined"""
    return run(session, script)["images"][0]["path"]


def main(args):
    if len(args) != 1:
        sys.exit(__doc__)
    page = Path(args[0]).resolve()
    if not page.is_file():
        sys.exit(f"{page} doesn't exist; build the scene first.")
    thread = bb("status").get("thread")
    if not thread:
        sys.exit("Run this inside a bb thread: it uses the thread's headless browser.")
    out = Path(os.environ.get("BB_THREAD_STORAGE") or tempfile.gettempdir()) / "crayon-check" / page.stem
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)

    opened = bb("browser-automation", "open", "--backend", "local", "--headless",
                "--machine", thread["environment"]["hostId"], timeout=240)
    session = opened["id"]
    print(f"previewDirective: {opened.get('previewDirective')}")
    try:
        script = f"""const p = await browser.getPage("crayon-check");
await p.setViewport({{ width: {DESKTOP}, height: {SHOT_HEIGHT} }});
await p.goto({json.dumps(page.as_uri())});
console.log("CRAYON " + JSON.stringify(await p.evaluate({CHECK})));
undefined"""
        text = run(session, script).get("text", "")
        line = next((l for l in text.splitlines() if l.startswith("CRAYON ")), None)
        if not line:
            sys.exit(f"The page check printed nothing:\n{text}")
        report = json.loads(line.removeprefix("CRAYON "))

        shots = []
        for i, top in enumerate(range(0, report["height"], SHOT_HEIGHT)[:MAX_SHOTS], 1):
            path = out / f"desktop-{i}.jpg"
            shutil.copy(shoot(session, DESKTOP, top, min(SHOT_HEIGHT, report["height"] - top)), path)
            shots.append(path)

        script = f"""const p = await browser.getPage("crayon-check");
await p.setViewport({{ width: {PHONE}, height: 800 }});
await new Promise((done) => setTimeout(done, 300));
console.log("CRAYON " + JSON.stringify(await p.evaluate(() => document.documentElement.scrollWidth)));
await p.shot({{ maxEdge: 960, quality: 70 }});
undefined"""
        phone = run(session, script)
        width = next((int(l.split()[1]) for l in phone.get("text", "").splitlines() if l.startswith("CRAYON ")), PHONE)
        if width > PHONE + 1:
            report["problems"].append(f"the page is wider than the {PHONE}px phone column")
        path = out / "phone-1.jpg"
        shutil.copy(phone["images"][0]["path"], path)
        shots.append(path)
    finally:
        subprocess.run([BB, "browser-automation", "close", session, "--json"], capture_output=True, timeout=60)

    for note in report["notes"]:
        print(f"Note: {note}")
    if report["problems"]:
        print("Problems to fix:")
        for problem in report["problems"]:
            print(f"  - {problem}")
    else:
        print("No problems found by the automatic checks.")
    if report["height"] > SHOT_HEIGHT * MAX_SHOTS:
        print(f"Only the first {SHOT_HEIGHT * MAX_SHOTS}px of the page is in the screenshots.")
    print("Look at every screenshot:")
    for path in shots:
        print(f"  {path}")
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
