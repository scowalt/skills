#!/usr/bin/env python3
"""Check a built crayon page in a headless browser.

Usage: check.py PAGE.html

Lists drawings that failed, text that runs outside its picture or overlaps other
text, and a page wider than its column. Then saves screenshots at desktop (710px,
bb's chat column) and phone (360px) widths and prints their paths.
Exits 1 when it lists problems. In a bb thread it uses bb's headless browser;
anywhere else it uses Playwright for Python.
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
  if (document.documentElement.scrollWidth > innerWidth + 1) problems.push(`the page is wider than its ${innerWidth}px column`);
  const notes = [];
  if (document.fonts && !document.fonts.check('16px "Patrick Hand"'))
    notes.push("the handwriting fonts didn't load, so the page used fallback fonts");
  return { height: Math.ceil(document.body.getBoundingClientRect().height), problems, notes };
}"""

PAGE_WIDTH = "() => document.documentElement.scrollWidth"
UV = "uv run --no-project --with playwright"
NO_PLAYWRIGHT = f"""Outside a bb thread, this check runs in Playwright for Python, which isn't installed here. Run it through uv:
  {UV} python {Path(__file__).resolve()} PAGE.html
or, without uv, install it with: python3 -m pip install playwright"""
NO_BROWSER = f"""Playwright couldn't start Chromium, Chrome or Edge. Install Playwright's Chromium:
  {UV} playwright install chromium"""


def bb(*args, timeout=120):
    result = subprocess.run([BB, *args, "--json"], capture_output=True, text=True, timeout=timeout)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.exit(f"bb {' '.join(args[:2])} failed: {(result.stderr or result.stdout).strip()}")
    if isinstance(data, dict) and data.get("ok") is False:
        sys.exit(f"bb {' '.join(args[:2])} failed: {data['error'].get('message')}")
    return data


class BbBrowser:
    """bb's headless browser, on the thread's machine."""

    def __init__(self, thread):
        opened = bb("browser-automation", "open", "--backend", "local", "--headless",
                    "--machine", thread["environment"]["hostId"], timeout=240)
        self.session = opened["id"]
        print(f"previewDirective: {opened.get('previewDirective')}")

    def run(self, script):
        data = bb("browser-automation", "run", self.session, "--timeout", "90s", "--script", script, timeout=150)
        if data.get("exitCode"):
            sys.exit(f"The browser script failed:\n{data.get('text', '')}")
        return data

    def check(self, uri):
        text = self.run(f"""const p = await browser.getPage("crayon-check");
await p.setViewport({{ width: {DESKTOP}, height: {SHOT_HEIGHT} }});
await p.goto({json.dumps(uri)});
console.log("CRAYON " + JSON.stringify(await p.evaluate({CHECK})));
undefined""").get("text", "")
        line = next((l for l in text.splitlines() if l.startswith("CRAYON ")), None)
        if not line:
            sys.exit(f"The page check printed nothing:\n{text}")
        return json.loads(line.removeprefix("CRAYON "))

    def shoot(self, path, top, height):
        clip = {"x": 0, "y": top, "width": DESKTOP, "height": height}
        data = self.run(f"""const p = await browser.getPage("crayon-check");
await p.shot({{ clip: {json.dumps(clip)}, maxEdge: 960, quality: 70 }});
undefined""")
        shutil.copy(data["images"][0]["path"], path)

    def phone(self, path):
        """Screenshots the page at phone width and returns how wide the page is there."""
        data = self.run(f"""const p = await browser.getPage("crayon-check");
await p.setViewport({{ width: {PHONE}, height: 800 }});
await new Promise((done) => setTimeout(done, 300));
console.log("CRAYON " + JSON.stringify(await p.evaluate({PAGE_WIDTH})));
await p.shot({{ maxEdge: 960, quality: 70 }});
undefined""")
        shutil.copy(data["images"][0]["path"], path)
        return next((int(l.split()[1]) for l in data.get("text", "").splitlines() if l.startswith("CRAYON ")), PHONE)

    def close(self):
        subprocess.run([BB, "browser-automation", "close", self.session, "--json"], capture_output=True, timeout=60)


class PlaywrightBrowser:
    """Playwright's own Chromium, or else an installed Chrome or Edge."""

    def __init__(self):
        try:
            from playwright.sync_api import Error, sync_playwright
        except ImportError:
            sys.exit(NO_PLAYWRIGHT)
        self.playwright = sync_playwright().start()
        for channel in (None, "chrome", "msedge"):
            try:
                self.browser = self.playwright.chromium.launch(channel=channel)
                break
            except Error:
                pass
        else:
            self.playwright.stop()
            sys.exit(NO_BROWSER)
        self.page = self.browser.new_page(viewport={"width": DESKTOP, "height": SHOT_HEIGHT})

    def check(self, uri):
        self.page.goto(uri)
        return self.page.evaluate(CHECK)

    def shoot(self, path, top, height):
        clip = {"x": 0, "y": top, "width": DESKTOP, "height": height}
        self.page.screenshot(path=path, clip=clip, full_page=True, type="jpeg", quality=70)

    def phone(self, path):
        """Screenshots the page at phone width and returns how wide the page is there."""
        self.page.set_viewport_size({"width": PHONE, "height": 800})
        self.page.wait_for_timeout(300)
        width = self.page.evaluate(PAGE_WIDTH)
        self.page.screenshot(path=path, type="jpeg", quality=70)
        return width

    def close(self):
        self.browser.close()
        self.playwright.stop()


def main(args):
    if len(args) != 1:
        sys.exit(__doc__)
    page = Path(args[0]).resolve()
    if not page.is_file():
        sys.exit(f"{page} doesn't exist; build the scene first.")
    thread = bb("status").get("thread") if os.environ.get("BB_THREAD_ID") else None
    out = Path(os.environ.get("BB_THREAD_STORAGE") or tempfile.gettempdir()) / "crayon-check" / page.stem
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)

    browser = BbBrowser(thread) if thread else PlaywrightBrowser()
    try:
        report = browser.check(page.as_uri())
        shots = []
        for i, top in enumerate(range(0, report["height"], SHOT_HEIGHT)[:MAX_SHOTS], 1):
            shots.append(out / f"desktop-{i}.jpg")
            browser.shoot(shots[-1], top, min(SHOT_HEIGHT, report["height"] - top))
        shots.append(out / "phone-1.jpg")
        if browser.phone(shots[-1]) > PHONE + 1:
            report["problems"].append(f"the page is wider than a {PHONE}px phone")
    finally:
        browser.close()

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
