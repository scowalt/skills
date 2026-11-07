import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest

from scripts.validate_skills import ROOT


SKILL = ROOT / "skills" / "crayon-drawing"
EXAMPLE = (SKILL / "assets" / "example.scene.html").read_text()
HAS_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None
# Git hooks set GIT_DIR and friends, which would point git in the tests at this repository.
GIT_FREE_ENV = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}

# Stands in for gh: answers `pr view` from the canned PR in $FAKE_GH_PR and logs each
# call, with what it read on stdin, to $FAKE_GH_LOG.
FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
stdin = sys.stdin.read() if "-" in args else None
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps({"args": args, "stdin": stdin}) + "\\n")
if args[:2] == ["pr", "view"]:
    if "FAKE_GH_PR" not in os.environ:
        sys.exit("no pull requests found for branch \\"main\\"")
    print("https://github.com/owner/repo/pull/7")
    print(os.environ["FAKE_GH_PR"])
"""


def run(script, *args, env=None, cwd=None):
    command = [sys.executable, SKILL / "scripts" / script, *args]
    return subprocess.run(command, capture_output=True, text=True, env=env, cwd=cwd, timeout=180)


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


class AttachTestCase(CrayonTestCase):
    def setUp(self):
        super().setUp()
        self.repo = self.root / "repo"
        self.git("init", "-q", "-b", "feature", self.repo)
        self.png = self.root / "flow.png"
        self.png.write_bytes(b"\x89PNG")
        self.env = dict(GIT_FREE_ENV, XDG_CONFIG_HOME=str(self.root / "config"))

    def git(self, *args):
        subprocess.run(["git", *args], check=True, env=GIT_FREE_ENV)

    def set_remote(self, url):
        self.git("-C", self.repo, "remote", "add", "origin", url)

    def attach(self, png=None, *args):
        return run("attach.py", png or self.png, *args, env=self.env, cwd=self.repo)


class GitHubAttachTests(AttachTestCase):
    URL = "https://github.com/owner/repo/pull/7"

    def setUp(self):
        super().setUp()
        self.set_remote("git@github.com:owner/repo.git")
        bin = self.root / "bin"
        bin.mkdir()
        (bin / "gh").write_text(FAKE_GH)
        (bin / "gh").chmod(0o755)
        self.log = self.root / "gh.jsonl"
        self.env |= {"PATH": f"{bin}{os.pathsep}{os.environ['PATH']}", "FAKE_GH_LOG": str(self.log)}

    def attach_to(self, body=None, png=None, *args):
        if body is not None:
            self.env["FAKE_GH_PR"] = body
        return self.attach(png, *args)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_without_a_pull_request_nothing_is_attached(self):
        result = self.attach_to()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("No pull request found", result.stdout)
        self.assertEqual(1, len(self.calls()))

    def test_drawing_is_uploaded_at_the_end_of_the_description(self):
        result = self.attach_to("What changed.")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.URL, result.stdout.strip())
        edit = self.calls()[-1]
        self.assertEqual(["pr", "edit", self.URL, "--body-file", "-", "--attach", str(self.png)], edit["args"])
        self.assertEqual(
            f"What changed.\n\n<!-- crayon-drawing:flow -->\n![flow]({self.png})\n<!-- /crayon-drawing:flow -->\n",
            edit["stdin"],
        )

    def test_revision_replaces_the_earlier_drawing(self):
        earlier = "Intro.\n\n<!-- crayon-drawing:flow -->\n![flow](https://github.com/user-attachments/assets/1)\n<!-- /crayon-drawing:flow -->\nMore words."
        revision = self.root / "flow-v2.png"
        revision.write_bytes(b"\x89PNG2")
        self.assertEqual(0, self.attach_to(earlier, revision).returncode)
        edit = self.calls()[-1]
        self.assertEqual(str(revision), edit["args"][-1])
        self.assertEqual(earlier.replace("https://github.com/user-attachments/assets/1", str(revision)), edit["stdin"])

    def test_explicit_pull_request_is_passed_to_gh(self):
        self.attach_to("", None, self.URL)
        self.assertEqual(["pr", "view", self.URL], self.calls()[0]["args"][:3])
        self.assertTrue(self.calls()[-1]["stdin"].startswith("<!-- crayon-drawing:flow -->"))

    def test_only_pngs_are_attached(self):
        page = self.root / "flow.html"
        page.write_text("")
        self.assertIn("isn't a PNG", self.attach_to("", page).stderr)


class FakeGitea(BaseHTTPRequestHandler):
    """Gitea's pull request and attachment API for one repository, owner/repo."""

    def log_message(self, *args):
        pass

    def reply(self, status, data=None):
        body = json.dumps(data).encode() if data is not None else b""
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def route(self, method):
        state = self.server.state
        if self.headers["Authorization"] != "token secret":
            return self.reply(401, {"message": "unauthorized"})
        path = self.path.removeprefix("/api/v1/repos/owner/repo")
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        pull = state["pull"]
        if method == "GET" and path.startswith("/pulls?"):
            return self.reply(200, [pull] if pull else [])
        if method == "GET" and path == "/pulls/3":
            return self.reply(200, pull)
        if method == "PATCH" and path == "/pulls/3":
            pull["body"] = json.loads(body)["body"]
            return self.reply(201, pull)
        if method == "POST" and path == "/issues/3/assets":
            state["next"] += 1
            asset = {"id": state["next"], "browser_download_url": f"{state['url']}/attachments/{state['next']}", "upload": body}
            state["assets"].append(asset)
            return self.reply(201, {key: value for key, value in asset.items() if key != "upload"})
        if method == "GET" and path == "/issues/3/assets":
            return self.reply(200, [{k: v for k, v in a.items() if k != "upload"} for a in state["assets"]])
        if method == "DELETE" and path.startswith("/issues/3/assets/"):
            state["assets"] = [a for a in state["assets"] if a["id"] != int(path.split("/")[-1])]
            return self.reply(204)
        self.reply(404, {"message": f"no route for {method} {path}"})

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PATCH(self):
        self.route("PATCH")

    def do_DELETE(self):
        self.route("DELETE")


class GiteaAttachTests(AttachTestCase):
    def setUp(self):
        super().setUp()
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGitea)
        url = f"http://127.0.0.1:{server.server_port}"
        self.pull = {"number": 3, "html_url": f"{url}/owner/repo/pulls/3", "head": {"ref": "feature"}, "body": "What changed."}
        server.state = {"url": url, "pull": self.pull, "assets": [], "next": 0}
        self.state = server.state
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.set_remote(f"{url}/owner/repo.git")
        config = self.root / "config" / "tea"
        config.mkdir(parents=True)
        (config / "config.yml").write_text(
            f"logins:\n    - name: other\n      url: https://gitea.example\n      token: wrong\n"
            f"    - name: local\n      url: {url}\n      token: secret\n      default: false\n"
            f"preferences:\n    editor: false\n"
        )

    def test_drawing_is_uploaded_at_the_end_of_the_description(self):
        result = self.attach()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.pull["html_url"], result.stdout.strip())
        [asset] = self.state["assets"]
        self.assertIn(b'name="attachment"; filename="flow.png"', asset["upload"])
        self.assertIn(b"\x89PNG", asset["upload"])
        self.assertEqual(
            f"What changed.\n\n<!-- crayon-drawing:flow -->\n![flow]({asset['browser_download_url']})\n<!-- /crayon-drawing:flow -->\n",
            self.pull["body"],
        )

    def test_revision_replaces_the_earlier_drawing_and_its_attachment(self):
        self.attach()
        revision = self.root / "flow-v2.png"
        revision.write_bytes(b"\x89PNG2")
        self.assertEqual(0, self.attach(revision).returncode)
        [asset] = self.state["assets"]
        self.assertIn(b'filename="flow-v2.png"', asset["upload"])
        self.assertEqual(1, self.pull["body"].count("<!-- crayon-drawing:flow -->"))
        self.assertIn(asset["browser_download_url"], self.pull["body"])

    def test_pull_request_can_be_given_by_url(self):
        self.git("-C", self.repo, "checkout", "-q", "-b", "other")
        result = self.attach(None, self.pull["html_url"])
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, len(self.state["assets"]))

    def test_without_a_pull_request_nothing_is_attached(self):
        self.state["pull"] = None
        result = self.attach()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("No pull request found", result.stdout)

    def test_unknown_forge_is_refused(self):
        self.git("-C", self.repo, "remote", "set-url", "origin", "git@example.org:x/y.git")
        result = self.attach()
        self.assertEqual(1, result.returncode)
        self.assertIn("example.org is neither GitHub nor a Gitea server", result.stderr)


if __name__ == "__main__":
    unittest.main()
