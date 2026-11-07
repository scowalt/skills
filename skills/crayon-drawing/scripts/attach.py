#!/usr/bin/env python3
"""Attach a drawing's PNG to a GitHub pull request's description.

Usage: attach.py PNG [PR]

PR is a number, URL or branch, as `gh pr view` takes it, and defaults to the pull
request for the current branch. GitHub has no API for PR attachments, so the PNG
is committed to the repository's `crayon-drawings` branch, which shares no history
with the code, and the description links to that commit. Attaching a drawing
again, or a revision of it (NAME-v2.png), replaces the earlier one in place.
Prints the pull request's URL, or says there is no pull request and exits 0.
"""

import base64
import json
import re
import subprocess
import sys
from pathlib import Path

BRANCH = "crayon-drawings"


def gh(*args, payload=None, check=True):
    result = subprocess.run(
        ["gh", *args, *(["--input", "-"] if payload is not None else [])],
        input=json.dumps(payload) if payload is not None else None,
        capture_output=True,
        text=True,
    )
    if check and result.returncode:
        sys.exit(f"gh {' '.join(args[:2])} failed: {(result.stderr or result.stdout).strip()}")
    return result


def api(method, path, payload=None):
    return json.loads(gh("api", "-X", method, path, payload=payload).stdout)


def upload(repo, path, png):
    """Commits PNG at PATH on BRANCH and returns the commit's SHA."""
    tip = gh("api", f"repos/{repo}/git/ref/heads/{BRANCH}", check=False)
    parent = json.loads(tip.stdout)["object"]["sha"] if tip.returncode == 0 else None
    blob = api("POST", f"repos/{repo}/git/blobs", {"content": base64.b64encode(png).decode(), "encoding": "base64"})
    tree = {"tree": [{"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]}]}
    if parent:
        tree["base_tree"] = api("GET", f"repos/{repo}/git/commits/{parent}")["tree"]["sha"]
    tree = api("POST", f"repos/{repo}/git/trees", tree)
    commit = api("POST", f"repos/{repo}/git/commits", {
        "message": f"Add {path}",
        "tree": tree["sha"],
        "parents": [parent] if parent else [],
    })
    if parent:
        api("PATCH", f"repos/{repo}/git/refs/heads/{BRANCH}", {"sha": commit["sha"]})
    else:
        api("POST", f"repos/{repo}/git/refs", {"ref": f"refs/heads/{BRANCH}", "sha": commit["sha"]})
    return commit["sha"]


def with_drawing(body, name, image):
    """Returns BODY with the drawing NAME shown as IMAGE, replacing an earlier version of it."""
    start, end = f"<!-- crayon-drawing:{name} -->", f"<!-- /crayon-drawing:{name} -->"
    block = f"{start}\n{image}\n{end}"
    earlier = re.compile(re.escape(start) + ".*?" + re.escape(end), re.S)
    if earlier.search(body):
        return earlier.sub(lambda _: block, body, count=1)
    return f"{body.rstrip()}\n\n{block}\n" if body.strip() else f"{block}\n"


def main(args):
    if len(args) not in (1, 2):
        sys.exit(__doc__)
    png = Path(args[0])
    if png.suffix != ".png" or not png.is_file():
        sys.exit(f"{png} isn't a PNG; check.py saves one beside the page.")
    found = gh("pr", "view", *args[1:], "--json", "number,url,body", check=False)
    if found.returncode:
        message = (found.stderr or found.stdout).strip()
        if "no pull requests found" in message:
            print(f"No pull request found, so nothing was attached: {message}")
            return 0
        sys.exit(f"gh pr view failed: {message}")
    pr = json.loads(found.stdout)
    repo = re.match(r"https://github\.com/([^/]+/[^/]+)/pull/", pr["url"]).group(1)
    name = re.sub(r"-v\d+$", "", png.stem)
    path = f"pr-{pr['number']}/{png.name}"
    sha = upload(repo, path, png.read_bytes())
    image = f"![{name}](https://github.com/{repo}/blob/{sha}/{path}?raw=true)"
    api("PATCH", f"repos/{repo}/pulls/{pr['number']}", {"body": with_drawing(pr["body"] or "", name, image)})
    print(pr["url"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
