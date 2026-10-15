# Community conventions

Reviewed 2026-10-15. Recommendation: use the Agent Skills format plus a small Pi
package manifest, rather than adopting a framework or copying an entire skills
collection.

## What is broadly shared?

The [Agent Skills specification](https://agentskills.io/specification) defines
a skill as a directory with `SKILL.md`, YAML `name` and `description`
frontmatter, and optional `scripts/`, `references/`, and `assets/` directories.
It recommends progressive disclosure: descriptions at startup, instructions
when invoked, supporting material as needed.

[Pi's official skill documentation](https://pi.dev/docs/latest/skills)
explicitly implements that specification. Its documented examples include
[badlogic/pi-skills](https://github.com/badlogic/pi-skills), a substantial
community collection, and [anthropics/skills](https://github.com/anthropics/skills).
Anthropic also provides a
[minimal skill template](https://github.com/anthropics/skills/blob/main/template/SKILL.md).
These establish a shared file format and examples, not one required
full-repository boilerplate.

## What is Pi-specific?

[Pi packages](https://pi.dev/docs/latest/packages) support Git installation and
an explicit `pi.skills` manifest in `package.json`. This collection exports
only `./skills`, with other resource types disabled. Its authoring template is
outside that directory so it cannot become an advertised placeholder skill.
No npm publication or custom installer is needed.

The older clone-into-a-skills-directory workflow shown by `badlogic/pi-skills`
is also supported, but the official package mechanism provides installation,
updates, project scope, and resource selection without maintaining symlinks.

## Validation and limits

The specification recommends the
[`skills-ref` reference library](https://github.com/agentskills/agentskills/tree/main/skills-ref).
We use it only for development-time metadata validation, pinned to an upstream
commit through uv. Upstream describes it as demonstration code, not a production
library. It is not part of the installed skills' runtime.

Validation is not a security audit or behavioral test. Review instructions and
scripts before installing a skill, and test each actual workflow. Keep skills
portable by using the shared fields; agent-specific features need a deliberate
compatibility decision.

The MIT license, pinned development tools, pre-commit secret scanning, and CI
are this repository's maintenance choices, not requirements of the standard.
No existing personal or third-party skills were copied into this starter.
