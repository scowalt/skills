# skills

Scott's reusable skills for [Pi](https://pi.dev) and other agents, using the
open [Agent Skills format](https://agentskills.io/specification).

| Skill | What it does |
| --- | --- |
| [crayon-drawing](skills/crayon-drawing/SKILL.md) | Draws how something works as a crayon storyboard, built as one self-contained HTML page. |

The example in `templates/` is an authoring template, not something installed
into your agent.

## Install in Pi

Review the skills and their scripts before installing:

```sh
pi install git:github.com/scowalt/skills
```

This makes the collection available across projects. To install for just the
current project instead:

```sh
pi install --local git:github.com/scowalt/skills
```

After new skills are pushed, update the collection and run `/reload` in an
existing Pi session:

```sh
pi update git:github.com/scowalt/skills
```

Pi loads skill names and descriptions at startup, then reads a skill's full
instructions when relevant. You can also invoke one with `/skill:skill-name`.
To pin an installation, append `@<tag-or-commit>` to the Git source.

## Install in other agents

The [`skills` CLI](https://github.com/vercel-labs/skills) installs skills from
this collection into Claude Code, Codex, Cursor and other agents. For example,
to install crayon-drawing for Claude Code in every project:

```sh
npx skills add scowalt/skills --skill crayon-drawing --agent claude-code --global
```

Run `npx skills update` to get newer versions. Each skill lists what it needs,
such as Python, in its `compatibility` field.

## Add a skill

```sh
cp -R templates/example-skill skills/my-skill
```

Edit `skills/my-skill/SKILL.md`, replacing the name, description, and workflow.
The name must match the directory. See [CONTRIBUTING.md](CONTRIBUTING.md) for
setup, validation, and authoring guidance.

```text
skills/
  my-skill/
    SKILL.md
    scripts/       (optional)
    references/    (optional)
    assets/        (optional)
templates/
  example-skill/
    SKILL.md       (not exported to Pi)
```

The Pi manifest exports only `skills/`; there is no npm publication
requirement, custom installer, or agent extension.

## Why this structure?

The shared convention is `SKILL.md`, not a particular full-repository template.
This collection combines that standard with Pi's official Git-package format.
See the [community conventions and sources](docs/conventions.md).

## License

[MIT](LICENSE).
