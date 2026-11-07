#!/usr/bin/env python3
"""Attach a drawing's PNG to a GitHub pull request's description.

Usage: attach.py PNG [PR]

PR is a number, URL or branch, as `gh pr view` takes it, and defaults to the pull
request for the current branch. `gh pr edit --attach` uploads the PNG the way
dragging it into the description does. Attaching a drawing again, or a revision
of it (NAME-v2.png), replaces the earlier one in place. Prints the pull request's
URL, or says there is no pull request and exits 0.
"""

import re
import subprocess
import sys
from pathlib import Path


def gh(*args, body=None):
    return subprocess.run(["gh", *args], input=body, capture_output=True, text=True)


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
    png = Path(args[0]).resolve()
    if png.suffix != ".png" or not png.is_file():
        sys.exit(f"{png} isn't a PNG; check.py saves one beside the page.")
    found = gh("pr", "view", *args[1:], "--json", "url,body", "--jq", ".url, .body")
    if found.returncode:
        message = (found.stderr or found.stdout).strip()
        if "no pull requests found" in message:
            print(f"No pull request found, so nothing was attached: {message}")
            return 0
        sys.exit(f"gh pr view failed: {message}")
    url, body = found.stdout.split("\n", 1)
    name = re.sub(r"-v\d+$", "", png.stem)
    # gh rewrites this local path to the uploaded image's URL.
    body = with_drawing(body.removesuffix("\n"), name, f"![{name}]({png})")
    edited = gh("pr", "edit", url, "--body-file", "-", "--attach", str(png), body=body)
    if edited.returncode:
        message = (edited.stderr or edited.stdout).strip()
        if "unknown flag: --attach" in message:
            sys.exit(f"This gh is too old to attach files; upgrade to 2.102 or later. ({message})")
        sys.exit(f"gh pr edit failed: {message}")
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
