import os
import tempfile
import unittest
from pathlib import Path
from miniseek.core.security import PathSecurity, SecurityError

class TestPathSecurity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name).resolve()
        
        # Create subdirectories and test files inside root
        self.sub_dir = self.root_dir / "subdir"
        self.sub_dir.mkdir()
        self.inside_file = self.sub_dir / "valid.txt"
        self.inside_file.write_text("Hello inside")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_canonical_path_resolution(self):
        canonical = PathSecurity.get_canonical_path(self.inside_file)
        self.assertEqual(canonical, self.inside_file.resolve())

    def test_valid_path_within_root(self):
        validated = PathSecurity.validate_within_root(self.inside_file, self.root_dir)
        self.assertEqual(validated, self.inside_file.resolve())

    def test_relative_path_within_root(self):
        rel_path = Path("subdir/valid.txt")
        # Testing relative path resolution against root
        target = self.root_dir / rel_path
        validated = PathSecurity.validate_within_root(target, self.root_dir)
        self.assertEqual(validated, self.inside_file.resolve())

    def test_path_traversal_escape_rejected(self):
        # Attempting `../` to escape root directory
        escaping_path = self.root_dir / "../outside.txt"
        with self.assertRaises(SecurityError):
            PathSecurity.validate_within_root(escaping_path, self.root_dir)

    def test_absolute_escape_rejected(self):
        # Target pointing to /etc/hosts or /tmp outside root
        outside_path = Path("/etc/hosts")
        with self.assertRaises(SecurityError):
            PathSecurity.validate_within_root(outside_path, self.root_dir)

    def test_symlink_inside_root(self):
        # Symlink pointing to a file inside root is valid
        symlink_path = self.root_dir / "link_inside.txt"
        os.symlink(self.inside_file, symlink_path)

        validated = PathSecurity.validate_within_root(symlink_path, self.root_dir)
        self.assertEqual(validated, self.inside_file.resolve())
        self.assertFalse(PathSecurity.is_symlink_escaping_root(symlink_path, self.root_dir))

    def test_symlink_escape_rejected(self):
        # Symlink pointing outside root is flagged as escaping
        outside_temp = tempfile.NamedTemporaryFile(delete=False)
        outside_temp.write(b"Secret outside data")
        outside_temp.close()

        try:
            symlink_escape = self.root_dir / "escape_link.txt"
            os.symlink(outside_temp.name, symlink_escape)

            with self.assertRaises(SecurityError):
                PathSecurity.validate_within_root(symlink_escape, self.root_dir)

            self.assertTrue(PathSecurity.is_symlink_escaping_root(symlink_escape, self.root_dir))
        finally:
            os.unlink(outside_temp.name)

if __name__ == "__main__":
    unittest.main()
