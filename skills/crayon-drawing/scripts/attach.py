#!/usr/bin/env python3
"""Attach a drawing's PNG to a pull request's description on GitHub or Gitea.

Usage: attach.py PNG [PR]

PR is a pull request number or URL, and defaults to the pull request for the
current branch. The forge is the PR URL's host, or else the host of the current
branch's remote. GitHub goes through gh 2.102 or later, whose `gh pr edit
--attach` uploads the PNG the way dragging it into the description does. Gitea
goes through the API, as the tea login for that server. Attaching a drawing
again, or a revision of it (NAME-v2.png), replaces the earlier one in place.
Prints the pull request's URL, or says there is no pull request and exits 0.
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def run(*args, stdin=None):
    return subprocess.run(args, input=stdin, capture_output=True, text=True)


def with_drawing(body, name, image):
    """Returns BODY with the drawing NAME shown as IMAGE, replacing an earlier version of it."""
    start, end = f"<!-- crayon-drawing:{name} -->", f"<!-- /crayon-drawing:{name} -->"
    block = f"{start}\n{image}\n{end}"
    earlier = re.compile(re.escape(start) + ".*?" + re.escape(end), re.S)
    if earlier.search(body):
        return earlier.sub(lambda _: block, body, count=1)
    return f"{body.rstrip()}\n\n{block}\n" if body.strip() else f"{block}\n"


def no_pull_request(why):
    print(f"No pull request found, so nothing was attached: {why}")
    return 0


def remote_url():
    """The URL of the current branch's remote, or of origin."""
    remote = run("git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}").stdout.split("/")[0]
    url = run("git", "remote", "get-url", remote.strip() or "origin")
    if url.returncode:
        sys.exit(f"Couldn't find this checkout's remote; pass the pull request's URL. ({url.stderr.strip()})")
    return url.stdout.strip()


def split_remote(url):
    """Returns (host, "owner/repo") for an https, ssh:// or scp-style git URL."""
    if "://" in url:
        parsed = urllib.parse.urlsplit(url)
        host, path = parsed.hostname, parsed.path
    else:
        host, path = url.split("@")[-1].split(":", 1)
    return host, "/".join(path.strip("/").removesuffix(".git").split("/")[-2:])


def tea_logins():
    """The logins in tea's config: dicts with url and token."""
    home = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    candidates = [Path(home) / "tea" / "config.yml", Path.home() / "Library" / "Application Support" / "tea" / "config.yml"]
    config = next((path for path in candidates if path.is_file()), None)
    logins, login, in_logins = [], None, False
    for line in config.read_text().splitlines() if config else []:
        if line and not line[0].isspace():
            login = None
            in_logins = line.startswith("logins:")
            continue
        item = re.match(r"\s*(- )?(\w+): ?(.*)", line)
        if not item or not in_logins:
            continue
        if item.group(1):
            login = {}
            logins.append(login)
        if login is not None:
            login[item.group(2)] = item.group(3).strip("\"'")
    return logins


def attach_github(png, name, target):
    found = run("gh", "pr", "view", *target, "--json", "url,body", "--jq", ".url, .body")
    if found.returncode:
        message = (found.stderr or found.stdout).strip()
        if "no pull requests found" in message:
            return no_pull_request(message)
        sys.exit(f"gh pr view failed: {message}")
    url, body = found.stdout.split("\n", 1)
    # gh rewrites this local path to the uploaded image's URL.
    body = with_drawing(body.removesuffix("\n"), name, f"![{name}]({png})")
    edited = run("gh", "pr", "edit", url, "--body-file", "-", "--attach", str(png), stdin=body)
    if edited.returncode:
        message = (edited.stderr or edited.stdout).strip()
        if "unknown flag: --attach" in message:
            sys.exit(f"This gh is too old to attach files; upgrade to 2.102 or later. ({message})")
        sys.exit(f"gh pr edit failed: {message}")
    print(url)
    return 0


class Gitea:
    def __init__(self, login, repo):
        self.base = f"{login['url'].rstrip('/')}/api/v1/repos/{repo}"
        self.token = login["token"]

    def call(self, method, path, payload=None, files=None):
        headers = {"Authorization": f"token {self.token}", "Accept": "application/json"}
        data = None
        if payload is not None:
            data, headers["Content-Type"] = json.dumps(payload).encode(), "application/json"
        if files:
            boundary = uuid.uuid4().hex
            field, (filename, content) = next(iter(files.items()))
            data = (f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                    f"Content-Type: image/png\r\n\r\n").encode() + content + f"\r\n--{boundary}--\r\n".encode()
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                text = response.read()
                return json.loads(text) if text else None
        except urllib.error.HTTPError as error:
            sys.exit(f"Gitea {method} {path} failed: {error.code} {error.read().decode(errors='replace').strip()}")

    def pull_for_branch(self, branch):
        for page in range(1, 100):
            pulls = self.call("GET", f"/pulls?state=open&limit=50&page={page}")
            match = next((pull for pull in pulls if pull["head"]["ref"] == branch), None)
            if match or len(pulls) < 50:
                return match


def attach_gitea(png, name, target, login, repo):
    if not login.get("token"):
        sys.exit(f"tea's login for {login['url']} has no token in its config, so the drawing can't be uploaded.")
    gitea = Gitea(login, repo)
    if target:
        pull = gitea.call("GET", f"/pulls/{target[0].rstrip('/').split('/')[-1]}")
    else:
        branch = run("git", "branch", "--show-current").stdout.strip()
        pull = gitea.pull_for_branch(branch)
        if not pull:
            return no_pull_request(f'no open pull request for branch "{branch}" in {repo}')
    index = pull["number"]
    asset = gitea.call("POST", f"/issues/{index}/assets", files={"attachment": (png.name, png.read_bytes())})
    body = pull.get("body") or ""
    gitea.call("PATCH", f"/pulls/{index}", {"body": with_drawing(body, name, f"![{name}]({asset['browser_download_url']})")})
    # Gitea lists every attachment under the description, so remove the one this drawing replaced.
    earlier = re.search(f"<!-- crayon-drawing:{re.escape(name)} -->\n!\\[[^]]*\\]\\(([^)]+)\\)", body)
    for old in gitea.call("GET", f"/issues/{index}/assets") if earlier else []:
        if old["browser_download_url"] == earlier.group(1):
            gitea.call("DELETE", f"/issues/{index}/assets/{old['id']}")
    print(pull["html_url"])
    return 0


def main(args):
    if len(args) not in (1, 2):
        sys.exit(__doc__)
    png = Path(args[0]).resolve()
    if png.suffix != ".png" or not png.is_file():
        sys.exit(f"{png} isn't a PNG; check.py saves one beside the page.")
    target = args[1:]
    if target and "://" in target[0]:
        parsed = urllib.parse.urlsplit(target[0])
        host, repo = parsed.hostname, "/".join(parsed.path.strip("/").split("/")[:2])
    else:
        host, repo = split_remote(remote_url())
    name = re.sub(r"-v\d+$", "", png.stem)
    if host == "github.com":
        return attach_github(png, name, target)
    login = next((login for login in tea_logins() if urllib.parse.urlsplit(login.get("url", "")).hostname == host), None)
    if login:
        return attach_gitea(png, name, target, login, repo)
    sys.exit(f"{host} is neither GitHub nor a Gitea server tea is logged in to, so the drawing wasn't attached.")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
