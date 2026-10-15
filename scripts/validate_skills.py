from pathlib import Path
import sys

from skills_ref import validate


ROOT = Path(__file__).resolve().parents[1]


def validation_errors(root: Path) -> list[str]:
    skills = root / "skills"
    if not skills.is_dir():
        return ["Missing skills/ directory"]

    errors = []
    directories = [root / "templates" / "example-skill"]
    for path in sorted(skills.iterdir()):
        if path.name.startswith("."):
            continue
        if path.is_dir():
            directories.append(path)
        else:
            errors.append(f"skills/{path.name}: Put each skill in its own directory")

    for directory in directories:
        label = directory.relative_to(root).as_posix()
        if not (directory / "SKILL.md").is_file():
            errors.append(f"{label}: Missing required file: SKILL.md")
            continue
        errors.extend(f"{label}: {problem}" for problem in validate(directory))
    return errors


def main() -> int:
    errors = validation_errors(ROOT)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Skill collection and authoring template are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
