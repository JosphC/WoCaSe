"""
Unit tests for path_utils module.

Tests cover:
  - create_case_path: 2-part, 3-part, 4-part names, and invalid formats
  - find_first_work_subdir: found, not found, permission error
  - find_folder: nested folder search
  - find_project_file: file search via work directory
"""

import os
import tempfile
import unittest

from wcs_modules.path_utils import (
    create_case_path,
    find_first_work_subdir,
    find_folder,
    find_project_file,
)


class TestCreateCasePath(unittest.TestCase):
    """Tests for create_case_path()."""

    def test_three_parts(self):
        """3-part name: PROJ6_0U0_000 -> PR/OJ6/000/PROJ6_0U0_000"""
        result = create_case_path("PROJ6_0U0_000", base_dir=r"D:\casdev\td5")
        expected = os.path.join(r"D:\casdev\td5", "PR", "OJ6", "000", "PROJ6_0U0_000")
        self.assertEqual(result, expected)

    def test_four_parts(self):
        """4-part name: PROJ2_0U0_OB6_024 -> PR/OJ2/OB6/PROJ2_0U0_OB6_024"""
        result = create_case_path("PROJ2_0U0_OB6_024", base_dir=r"D:\casdev\td5")
        expected = os.path.join(r"D:\casdev\td5", "PR", "OJ2", "OB6", "PROJ2_0U0_OB6_024")
        self.assertEqual(result, expected)

    def test_two_parts(self):
        """2-part name: FOH12_0U0 -> FO/H12/0U0/FOH12_0U0"""
        result = create_case_path("FOH12_0U0", base_dir=r"D:\casdev\td5")
        expected = os.path.join(r"D:\casdev\td5", "FO", "H12", "0U0", "FOH12_0U0")
        self.assertEqual(result, expected)

    def test_invalid_short_first_part(self):
        """First part too short -> None."""
        self.assertIsNone(create_case_path("AB_0U0_000"))

    def test_invalid_long_first_part(self):
        """First part too long -> None."""
        self.assertIsNone(create_case_path("ABCDEF_0U0_000"))

    def test_invalid_single_part(self):
        """Single part (no underscores) -> None."""
        self.assertIsNone(create_case_path("PROJ6"))

    def test_invalid_five_parts(self):
        """Five parts -> None."""
        self.assertIsNone(create_case_path("PROJ6_0U0_OB6_024_extra"))

    def test_empty_string(self):
        """Empty string -> None."""
        self.assertIsNone(create_case_path(""))

    def test_custom_base_dir(self):
        """Custom base directory is used."""
        result = create_case_path("PROJ6_0U0_000", base_dir=r"C:\projects")
        expected = os.path.join(r"C:\projects", "PR", "OJ6", "000", "PROJ6_0U0_000")
        self.assertEqual(result, expected)

    def test_brand_extraction(self):
        """Brand is first 2 chars of 5-char first part."""
        result = create_case_path("XYZ99_0U0_001", base_dir="/tmp")
        self.assertIn("XY", result)

    def test_platform_extraction(self):
        """Platform is last 3 chars of 5-char first part."""
        result = create_case_path("XYZ99_0U0_001", base_dir="/tmp")
        self.assertIn("Z99", result)


class TestFindFirstWorkSubdir(unittest.TestCase):
    """Tests for find_first_work_subdir()."""

    def test_work_dir_exists(self):
        """Returns path when 'work' directory exists."""
        with tempfile.TemporaryDirectory() as tmp:
            work_path = os.path.join(tmp, "work")
            os.makedirs(work_path)
            result = find_first_work_subdir(tmp)
            self.assertEqual(os.path.normpath(result), os.path.normpath(work_path))

    def test_work_dir_case_insensitive(self):
        """Matches 'Work', 'WORK', etc."""
        with tempfile.TemporaryDirectory() as tmp:
            work_path = os.path.join(tmp, "Work")
            os.makedirs(work_path)
            result = find_first_work_subdir(tmp)
            self.assertIsNotNone(result)

    def test_no_work_dir(self):
        """Returns None when no 'work' directory exists."""
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "src"))
            result = find_first_work_subdir(tmp)
            self.assertIsNone(result)

    def test_nonexistent_path(self):
        """Returns None for a path that does not exist."""
        result = find_first_work_subdir(r"C:\nonexistent_path_12345")
        self.assertIsNone(result)

    def test_only_searches_direct_children(self):
        """Does NOT find 'work' nested two levels deep."""
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "sub", "work"))
            result = find_first_work_subdir(tmp)
            self.assertIsNone(result)


class TestFindFolder(unittest.TestCase):
    """Tests for find_folder()."""

    def test_finds_nested_folder(self):
        """Finds a folder matching a relative path pattern."""
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "a", "errm_fctdg_test", "i")
            os.makedirs(target)
            result = find_folder(tmp, r"errm_fctdg_test\i")
            self.assertEqual(os.path.normpath(result), os.path.normpath(target))

    def test_finds_folder_forward_slash(self):
        """Accepts forward-slash separators."""
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "Dem", "cnf")
            os.makedirs(target)
            result = find_folder(tmp, "Dem/cnf")
            self.assertEqual(os.path.normpath(result), os.path.normpath(target))

    def test_returns_none_when_not_found(self):
        """Returns None when folder pattern is absent."""
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "other"))
            result = find_folder(tmp, r"errm_fctdg_test\i")
            self.assertIsNone(result)

    def test_single_component_folder(self):
        """Finds a single-component folder."""
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "sub", "target_folder")
            os.makedirs(target)
            result = find_folder(tmp, "target_folder")
            self.assertEqual(os.path.normpath(result), os.path.normpath(target))


class TestFindProjectFile(unittest.TestCase):
    """Tests for find_project_file()."""

    def test_finds_file_in_work(self):
        """Finds a file inside the 'work' subdirectory."""
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = os.path.join(tmp, "work", "sub")
            os.makedirs(work_dir)
            target_file = os.path.join(work_dir, "test_file.arxml")
            with open(target_file, "w") as f:
                f.write("content")
            result = find_project_file("test_file.arxml", tmp)
            self.assertEqual(os.path.normpath(result), os.path.normpath(target_file))

    def test_case_insensitive_search(self):
        """File search is case-insensitive."""
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = os.path.join(tmp, "work")
            os.makedirs(work_dir)
            target_file = os.path.join(work_dir, "MyFile.TXT")
            with open(target_file, "w") as f:
                f.write("data")
            result = find_project_file("myfile.txt", tmp)
            self.assertIsNotNone(result)

    def test_returns_none_without_work_dir(self):
        """Returns None when no 'work' directory exists."""
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "src"))
            result = find_project_file("file.c", tmp)
            self.assertIsNone(result)

    def test_returns_none_when_file_missing(self):
        """Returns None when file does not exist in 'work'."""
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "work"))
            result = find_project_file("nonexistent.c", tmp)
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
