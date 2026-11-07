import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from scripts.validate_skills import ROOT


SKILL = ROOT / "skills" / "crayon-drawing"
EXAMPLE = (SKILL / "assets" / "example.scene.html").read_text()
HAS_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None

# Stands in for gh: answers from the canned PR in $FAKE_GH_PR and logs each call, with its
# --input payload, to $FAKE_GH_LOG.
FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
payload = json.load(sys.stdin) if "--input" in args else None
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps({"args": args, "payload": payload}) + "\\n")
pr = os.environ.get("FAKE_GH_PR")
if args[:2] == ["pr", "view"]:
    if not pr:
        sys.exit("no pull requests found for branch \\"main\\"")
    print(pr)
elif args[-1].endswith("/git/ref/heads/crayon-drawings"):
    if not os.environ.get("FAKE_GH_BRANCH"):
        sys.exit("gh: Not Found (HTTP 404)")
    print(json.dumps({"object": {"sha": "tip"}}))
else:
    print(json.dumps({"sha": "new", "tree": {"sha": "tiptree"}}))
"""


def run(script, *args, env=None):
    command = [sys.executable, SKILL / "scripts" / script, *args]
    return subprocess.run(command, capture_output=True, text=True, env=env, timeout=180)


class CrayonTestCase(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write_scene(self, body, name="drawing.scene.html"):
        scene = self.root / name
        scene.write_text(body)
        return scene


class BuildTests(CrayonTestCase):
    def test_example_builds_into_one_page(self):
        result = run("build.py", self.write_scene(EXAMPLE))
        page = self.root / "drawing.html"
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(page), result.stdout.strip())
        html = page.read_text()
        self.assertTrue(html.startswith("<!doctype html>"))
        for asset in ("crayon.css", "crayon.js"):
            self.assertIn((SKILL / "assets" / asset).read_text(), html)
        self.assertIn('data-draw="snap"', html)

    def test_output_path_can_be_given(self):
        scene = self.write_scene("<script>crayon.draw({});</script>", name="drawing.html")
        page = self.root / "page.html"
        self.assertEqual(0, run("build.py", scene, page).returncode)
        self.assertTrue(page.is_file())

    def test_scene_name_or_output_path_is_required(self):
        result = run("build.py", self.write_scene("<script>crayon.draw({});</script>", name="drawing.html"))
        self.assertIn("Name the scene", result.stderr)

    def test_full_document_is_refused(self):
        result = run("build.py", self.write_scene("<html><body><script>crayon.draw({});</script></body></html>"))
        self.assertIn("must be a fragment", result.stderr)

    def test_scene_that_never_draws_is_refused(self):
        result = run("build.py", self.write_scene('<div class="board"></div>'))
        self.assertIn("never calls crayon.draw", result.stderr)


class CheckTests(CrayonTestCase):
    def setUp(self):
        super().setUp()
        run("build.py", self.write_scene(EXAMPLE))
        self.page = self.root / "drawing.html"

    def check_outside_bb(self):
        env = {key: value for key, value in os.environ.items() if not key.startswith("BB_")}
        return run("check.py", self.page, env=env | {"TMPDIR": str(self.root)})

    def test_missing_page_is_reported(self):
        result = run("check.py", self.root / "missing.html")
        self.assertIn("build the scene first", result.stderr)

    @unittest.skipIf(HAS_PLAYWRIGHT, "Playwright is installed")
    def test_outside_bb_without_playwright_says_how_to_run(self):
        result = self.check_outside_bb()
        self.assertEqual(1, result.returncode)
        self.assertIn("uv run --no-project --with playwright", result.stderr)

    @unittest.skipUnless(HAS_PLAYWRIGHT, "needs Playwright: uv run --locked --with playwright python -m unittest")
    def test_example_passes_in_playwright(self):
        result = self.check_outside_bb()
        if "couldn't start" in result.stderr:
            self.skipTest(result.stderr)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("No problems found", result.stdout)
        shots = [Path(line.strip()) for line in result.stdout.splitlines() if line.endswith(".jpg")]
        self.assertEqual(["desktop-1.jpg", "phone-1.jpg"], [shot.name for shot in shots])
        self.assertTrue(all(shot.is_file() for shot in shots))
        self.assertTrue((self.root / "drawing.png").read_bytes().startswith(b"\x89PNG"))


class AttachTests(CrayonTestCase):
    URL = "https://github.com/owner/repo/pull/7"

    def setUp(self):
        super().setUp()
        bin = self.root / "bin"
        bin.mkdir()
        (bin / "gh").write_text(FAKE_GH)
        (bin / "gh").chmod(0o755)
        self.log = self.root / "gh.jsonl"
        self.env = os.environ | {"PATH": f"{bin}{os.pathsep}{os.environ['PATH']}", "FAKE_GH_LOG": str(self.log)}
        self.png = self.root / "flow.png"
        self.png.write_bytes(b"\x89PNG")

    def attach(self, body=None, branch=False, png=None, *args):
        env = self.env | ({"FAKE_GH_BRANCH": "1"} if branch else {})
        if body is not None:
            env["FAKE_GH_PR"] = json.dumps({"number": 7, "url": self.URL, "body": body})
        return run("attach.py", png or self.png, *args, env=env)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def payloads(self, path):
        return [c["payload"] for c in self.calls() if c["args"][0] == "api" and any(a.endswith(path) for a in c["args"])]

    def new_body(self):
        return self.calls()[-1]["payload"]["body"]

    def test_without_a_pull_request_nothing_is_attached(self):
        result = self.attach()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("No pull request found", result.stdout)
        self.assertEqual(1, len(self.calls()))

    def test_first_drawing_starts_the_branch_and_ends_the_description(self):
        result = self.attach("What changed.")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.URL, result.stdout.strip())
        [blob] = self.payloads("/git/blobs")
        self.assertEqual(base64.b64encode(b"\x89PNG").decode(), blob["content"])
        [commit] = self.payloads("/git/commits")
        self.assertEqual([], commit["parents"])
        self.assertEqual([{"ref": "refs/heads/crayon-drawings", "sha": "new"}], self.payloads("/git/refs"))
        self.assertEqual(["api", "-X", "PATCH", "repos/owner/repo/pulls/7", "--input", "-"], self.calls()[-1]["args"])
        self.assertEqual(
            "What changed.\n\n<!-- crayon-drawing:flow -->\n"
            "![flow](https://github.com/owner/repo/blob/new/pr-7/flow.png?raw=true)\n"
            "<!-- /crayon-drawing:flow -->\n",
            self.new_body(),
        )

    def test_revision_replaces_the_earlier_drawing(self):
        self.attach("Intro.")
        first = self.new_body()
        revision = self.root / "flow-v2.png"
        revision.write_bytes(b"\x89PNG2")
        self.assertEqual(0, self.attach(first + "\nMore words.", True, revision).returncode)
        self.assertEqual(["tip"], self.payloads("/git/commits")[-1]["parents"])
        self.assertEqual([{"sha": "new"}], self.payloads("/git/refs/heads/crayon-drawings")[-1:])
        body = self.new_body()
        self.assertEqual(1, body.count("<!-- crayon-drawing:flow -->"))
        self.assertIn("pr-7/flow-v2.png", body)
        self.assertNotIn("pr-7/flow.png", body)
        self.assertTrue(body.startswith("Intro.") and body.endswith("More words."))

    def test_explicit_pull_request_is_passed_to_gh(self):
        self.attach("", False, None, self.URL)
        self.assertEqual(["pr", "view", self.URL, "--json", "number,url,body"], self.calls()[0]["args"])
        self.assertTrue(self.new_body().startswith("<!-- crayon-drawing:flow -->"))

    def test_only_pngs_are_attached(self):
        page = self.root / "flow.html"
        page.write_text("")
        self.assertIn("isn't a PNG", self.attach("", png=page).stderr)


if __name__ == "__main__":
    unittest.main()
