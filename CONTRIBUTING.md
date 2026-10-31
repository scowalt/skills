# Contributing

## Development setup

Install [mise](https://mise.jdx.dev), then run from this repository:

```sh
mise trust
mise install
mise exec -- uv sync --locked
mise exec -- lefthook install
mise run check
```

Mise pins the development tools. The uv lockfile pins the reference validator
and its dependencies. Installing this collection in Pi does not require these
development tools.

The pre-commit hook scans staged changes for secrets with Gitleaks and runs the
checks. Woodpecker runs the same locked validation and tests on pull requests and
main pushes, not secret scanning. Its pinned container matches the Python and uv
versions in `.mise.toml`; update both together when changing those versions.
Mission Control manages this repository's disabled GitHub Actions permission.

## Author a skill

1. Copy `templates/example-skill/` into `skills/<skill-name>/`.
2. Match the frontmatter `name` to the directory. Use lowercase ASCII letters,
   digits, and single hyphens, up to 64 characters.
3. Write a specific `description` explaining what the skill does and when the
   agent should load it. Use at most 1,024 characters.
4. Replace the template body with an ordered workflow and observable completion
   criteria. Include the important failure cases and when to ask the user.
5. Add `scripts/`, `references/`, or `assets/` only when needed. Resolve bundled
   paths relative to the skill directory, not the agent's working directory.
6. Run `mise run check`, then try the skill against a representative request in
   Pi. Record the expected result and actual evidence in the pull request.

Keep `SKILL.md` focused and under 500 lines. Link to detailed references rather
than loading them for every invocation. Put real environment requirements in
`compatibility`, and keep credentials outside the repository.

Use the standard frontmatter fields for portability. Pi-only fields require
an explicit compatibility decision and an update to validation; the reference
validator currently rejects fields outside the shared specification.

The reference validator checks metadata and naming, not instruction quality,
script safety, file references, or whether the workflow succeeds. Review those
separately. Add tests for executable helpers when a skill introduces them.

## Try local changes

In a separate Pi session, explicitly load one skill for that invocation:

```sh
pi --skill ./skills/my-skill
```

Or register this whole checkout as a local package for live editing:

```sh
pi install /absolute/path/to/skills
```

Run `/reload` after edits. The template stays outside `skills/`, so installing
the collection never advertises a placeholder skill.
