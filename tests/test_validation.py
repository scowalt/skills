import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from scripts.validate_skills import ROOT, validation_errors


class CollectionValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "skills").mkdir()
        shutil.copytree(ROOT / "templates", self.root / "templates")

    def write_skill(self, directory="my-skill", frontmatter=None):
        skill = self.root / "skills" / directory
        skill.mkdir()
        if frontmatter is None:
            frontmatter = f"name: {directory}\ndescription: Test a representative workflow."
        (skill / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n# Test skill\n")

    def test_empty_collection_is_valid(self):
        self.assertEqual([], validation_errors(self.root))

    def test_new_skill_is_validated(self):
        self.write_skill()
        self.assertEqual([], validation_errors(self.root))

    def test_missing_description_fails(self):
        self.write_skill(frontmatter="name: my-skill")
        self.assertTrue(any("description" in error for error in validation_errors(self.root)))

    def test_name_must_match_directory(self):
        self.write_skill(frontmatter="name: other-name\ndescription: Test a workflow.")
        self.assertTrue(any("must match" in error for error in validation_errors(self.root)))

    def test_missing_skill_file_fails(self):
        (self.root / "skills" / "unfinished").mkdir()
        self.assertIn("skills/unfinished: Missing required file: SKILL.md", validation_errors(self.root))

    def test_standalone_skill_file_fails(self):
        (self.root / "skills" / "SKILL.md").write_text("# Misplaced skill\n")
        self.assertIn("skills/SKILL.md: Put each skill in its own directory", validation_errors(self.root))

    def test_nonstandard_frontmatter_fails(self):
        self.write_skill(frontmatter="name: my-skill\ndescription: Test a workflow.\ncustom-field: unsupported")
        self.assertTrue(any("Unexpected fields" in error for error in validation_errors(self.root)))

    def test_malformed_frontmatter_fails(self):
        self.write_skill(frontmatter="name: [broken")
        self.assertTrue(validation_errors(self.root))

    def test_invalid_template_fails(self):
        (self.root / "templates" / "example-skill" / "SKILL.md").write_text("# Missing frontmatter\n")
        self.assertTrue(validation_errors(self.root))

    def test_missing_collection_fails(self):
        (self.root / "skills").rmdir()
        self.assertEqual(["Missing skills/ directory"], validation_errors(self.root))


class RepositoryContractTests(unittest.TestCase):
    def test_real_repository_passes_validation(self):
        self.assertEqual([], validation_errors(ROOT))

    def test_pi_exports_only_the_real_collection(self):
        manifest = json.loads((ROOT / "package.json").read_text())
        self.assertEqual(
            {"skills": ["./skills"], "extensions": [], "prompts": [], "themes": []},
            manifest["pi"],
        )


if __name__ == "__main__":
    unittest.main()
