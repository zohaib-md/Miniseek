import os
import tempfile
import unittest
from pathlib import Path

from miniseek.core.config import Config
from miniseek.applications.janitor.scanner import FileScanner

class TestFileScanner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name).resolve()

        self.config = Config(max_preview_chars=50)
        self.scanner = FileScanner(config=self.config)

        # Create test directory hierarchy and files
        self.doc1 = self.root_dir / "invoice_march.txt"
        self.doc1.write_text("Invoice for Acme Corp: $450.00 on March 15 2024")

        self.sub_folder = self.root_dir / "downloads"
        self.sub_folder.mkdir()

        # Create exact duplicate files
        self.dup1 = self.sub_folder / "file_original.txt"
        self.dup1.write_text("Exact duplicate content for hashing test")

        self.dup2 = self.sub_folder / "file_copy.txt"
        self.dup2.write_text("Exact duplicate content for hashing test")

        # Create file with same size but different content (to test hash collision handling)
        self.diff_content = self.root_dir / "diff.txt"
        self.diff_content.write_text("Different content with length 40 chars!")  # Ensure distinct hash

        # Create a symlink file
        self.symlink_file = self.root_dir / "symlink_doc.txt"
        os.symlink(self.doc1, self.symlink_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_scan_basic_metadata(self):
        result = self.scanner.scan(self.root_dir)

        self.assertEqual(result.root_path, str(self.root_dir))
        # Total regular files: doc1, dup1, dup2, diff.txt (4 regular files)
        self.assertEqual(result.total_files, 4)
        self.assertGreater(result.total_bytes, 0)
        self.assertEqual(len(result.skipped_symlinks), 1)
        self.assertEqual(result.skipped_symlinks[0].name, "symlink_doc.txt")

    def test_bounded_preview_extraction(self):
        result = self.scanner.scan(self.root_dir)
        doc_info = next(f for f in result.files if f.name == "invoice_march.txt")
        self.assertTrue("Invoice for Acme Corp" in doc_info.preview)
        self.assertLessEqual(len(doc_info.preview), self.config.max_preview_chars)

    def test_deterministic_duplicate_detection(self):
        result = self.scanner.scan(self.root_dir)

        self.assertEqual(len(result.duplicate_groups), 1)
        group = result.duplicate_groups[0]
        self.assertEqual(len(group.files), 2)
        filenames = {f.name for f in group.files}
        self.assertEqual(filenames, {"file_original.txt", "file_copy.txt"})

        # Verify wasted bytes calculation: size * (count - 1)
        expected_wasted = group.size_bytes * (2 - 1)
        self.assertEqual(group.wasted_bytes, expected_wasted)
        self.assertEqual(result.total_wasted_bytes, expected_wasted)

    def test_symlinked_directory_not_traversed(self):
        # Create an external directory outside root with a file
        external_temp = tempfile.TemporaryDirectory()
        external_path = Path(external_temp.name).resolve()
        secret_file = external_path / "secret.txt"
        secret_file.write_text("Secret outside data")

        try:
            # Create a symlinked directory pointing to external directory
            symlink_dir = self.root_dir / "external_link"
            os.symlink(external_path, symlink_dir, target_is_directory=True)

            result = self.scanner.scan(self.root_dir)
            
            # File inside external directory must NOT be scanned
            scanned_names = {f.name for f in result.files}
            self.assertNotIn("secret.txt", scanned_names)
        finally:
            external_temp.cleanup()

    def test_nonexistent_directory_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.scanner.scan(self.root_dir / "nonexistent_dir")

if __name__ == "__main__":
    unittest.main()
