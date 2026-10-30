import importlib.util
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


if __name__ == "__main__":
    unittest.main()
