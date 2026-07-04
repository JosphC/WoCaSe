"""
Unit tests for td5_builder module.

Tests cover:
  - _local_name: namespace stripping
  - _parse_bool: strict boolean parsing
  - _collect_valid_target_names: multi-target IsInvisible filtering
  - _collect_buildtypenames: BuildProcessDefinition/BuildTypes extraction
  - extract_targets_and_buildtypes_from_file: single-file API
  - find_target_name_recursively: single/multiple candidates, visibility rules
  - find_buildtypes_recursively: build-type discovery
"""

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET

from wcs_modules.td5_builder import (
    _local_name,
    _parse_bool,
    _collect_valid_target_names,
    _collect_buildtypenames,
    _collect_targets_with_buildtypes,
    TargetEntry,
    extract_targets_and_buildtypes_from_file,
    extract_targets_from_file,
    extract_from_dir,
    extract_targets_from_dir,
    find_target_name_recursively,
    find_buildtypes_recursively,
    find_targets_recursively,
)


class TestLocalName(unittest.TestCase):
    """Tests for _local_name()."""

    def test_with_namespace(self):
        self.assertEqual(_local_name("{http://example.com}TargetName"), "TargetName")

    def test_without_namespace(self):
        self.assertEqual(_local_name("TargetName"), "TargetName")

    def test_empty_namespace(self):
        self.assertEqual(_local_name("{}Tag"), "Tag")

    def test_plain_string(self):
        self.assertEqual(_local_name("simple"), "simple")


class TestParseBool(unittest.TestCase):
    """Tests for _parse_bool()."""

    def test_true_lowercase(self):
        self.assertIs(_parse_bool("true"), True)

    def test_false_lowercase(self):
        self.assertIs(_parse_bool("false"), False)

    def test_true_mixed_case(self):
        self.assertIs(_parse_bool("True"), True)

    def test_false_mixed_case(self):
        self.assertIs(_parse_bool("False"), False)

    def test_true_uppercase(self):
        self.assertIs(_parse_bool("TRUE"), True)

    def test_whitespace_around_true(self):
        self.assertIs(_parse_bool("  true  "), True)

    def test_none_returns_none(self):
        self.assertIsNone(_parse_bool(None))

    def test_empty_string(self):
        self.assertIsNone(_parse_bool(""))

    def test_invalid_string(self):
        self.assertIsNone(_parse_bool("yes"))

    def test_number_string(self):
        self.assertIsNone(_parse_bool("1"))


class TestCollectValidTargetNames(unittest.TestCase):
    """Tests for _collect_valid_target_names()."""

    def _root(self, xml_str: str) -> ET.Element:
        return ET.fromstring(xml_str)

    def test_visible_false_accepted(self):
        xml = """<Root>
            <TargetInformation>
                <TargetName>MyTarget</TargetName>
                <IsInvisible>false</IsInvisible>
            </TargetInformation>
        </Root>"""
        self.assertEqual(_collect_valid_target_names(self._root(xml)), ["MyTarget"])

    def test_invisible_true_rejected(self):
        xml = """<Root>
            <TargetInformation>
                <TargetName>HiddenTarget</TargetName>
                <IsInvisible>true</IsInvisible>
            </TargetInformation>
        </Root>"""
        self.assertEqual(_collect_valid_target_names(self._root(xml)), [])

    def test_missing_invisible_accepted(self):
        xml = """<Root>
            <TargetInformation>
                <TargetName>NoFlag</TargetName>
            </TargetInformation>
        </Root>"""
        self.assertEqual(_collect_valid_target_names(self._root(xml)), ["NoFlag"])

    def test_no_target_information(self):
        xml = """<Root><Other>data</Other></Root>"""
        self.assertEqual(_collect_valid_target_names(self._root(xml)), [])

    def test_empty_target_name_skipped(self):
        xml = """<Root>
            <TargetInformation>
                <TargetName>   </TargetName>
            </TargetInformation>
        </Root>"""
        self.assertEqual(_collect_valid_target_names(self._root(xml)), [])

    def test_with_namespace(self):
        xml = """<ns:Root xmlns:ns="http://example.com">
            <ns:TargetInformation>
                <ns:TargetName>NSTarget</ns:TargetName>
                <ns:IsInvisible>false</ns:IsInvisible>
            </ns:TargetInformation>
        </ns:Root>"""
        self.assertEqual(_collect_valid_target_names(self._root(xml)), ["NSTarget"])

    def test_multiple_entries_mixed(self):
        """Two TargetInformation blocks: one visible, one hidden."""
        xml = """<Root>
            <TargetInformation>
                <TargetName>Visible</TargetName>
                <IsInvisible>false</IsInvisible>
            </TargetInformation>
            <TargetInformation>
                <TargetName>Hidden</TargetName>
                <IsInvisible>true</IsInvisible>
            </TargetInformation>
        </Root>"""
        self.assertEqual(_collect_valid_target_names(self._root(xml)), ["Visible"])


class TestCollectBuildTypeNames(unittest.TestCase):
    """Tests for _collect_buildtypenames()."""

    def _root(self, xml_str: str) -> ET.Element:
        return ET.fromstring(xml_str)

    def test_extracts_buildtypenames(self):
        xml = """<Root>
            <BuildProcessDefinition>
                <BuildTypes>
                    <BuildType><BuildTypeName>NORMAL</BuildTypeName></BuildType>
                    <BuildType><BuildTypeName>RELEASE</BuildTypeName></BuildType>
                </BuildTypes>
            </BuildProcessDefinition>
        </Root>"""
        self.assertEqual(_collect_buildtypenames(self._root(xml)), ["NORMAL", "RELEASE"])

    def test_deduplication(self):
        xml = """<Root>
            <BuildProcessDefinition>
                <BuildTypes>
                    <BuildType><BuildTypeName>NORMAL</BuildTypeName></BuildType>
                    <BuildType><BuildTypeName>NORMAL</BuildTypeName></BuildType>
                </BuildTypes>
            </BuildProcessDefinition>
        </Root>"""
        self.assertEqual(_collect_buildtypenames(self._root(xml)), ["NORMAL"])

    def test_no_buildprocessdefinition(self):
        xml = """<Root><Other/></Root>"""
        self.assertEqual(_collect_buildtypenames(self._root(xml)), [])

    def test_empty_buildtypename_skipped(self):
        xml = """<Root>
            <BuildProcessDefinition>
                <BuildTypes>
                    <BuildType><BuildTypeName>  </BuildTypeName></BuildType>
                    <BuildType><BuildTypeName>NORMAL</BuildTypeName></BuildType>
                </BuildTypes>
            </BuildProcessDefinition>
        </Root>"""
        self.assertEqual(_collect_buildtypenames(self._root(xml)), ["NORMAL"])



class TestFindTargetNameRecursively(unittest.TestCase):
    """Tests for find_target_name_recursively()."""

    def _write_tdxml(self, directory: str, filename: str,
                     target_name: str, is_invisible: str = None) -> str:
        """Helper: write a .tdxml file with TargetInformation."""
        invisible_tag = ""
        if is_invisible is not None:
            invisible_tag = f"<isInvisible>{is_invisible}</isInvisible>"
        content = f"""<?xml version="1.0"?>
<Project>
    <TargetInformation>
        <TargetName>{target_name}</TargetName>
        {invisible_tag}
    </TargetInformation>
</Project>"""
        filepath = os.path.join(directory, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def test_single_visible_file(self):
        """Single .tdxml with isInvisible=false -> returns target name."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_tdxml(tmp, "project.tdxml", "MyBuild", "false")
            result = find_target_name_recursively(tmp)
            self.assertEqual(result, "MyBuild")

    def test_single_file_no_flag(self):
        """Single .tdxml without isInvisible -> accepted."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_tdxml(tmp, "project.tdxml", "DefaultBuild")
            result = find_target_name_recursively(tmp)
            self.assertEqual(result, "DefaultBuild")

    def test_single_invisible_file(self):
        """Single .tdxml with isInvisible=true -> rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_tdxml(tmp, "project.tdxml", "Hidden", "true")
            result = find_target_name_recursively(tmp)
            self.assertIsNone(result)

    def test_multiple_files_picks_visible(self):
        """Among multiple files, only isInvisible=false candidates are considered."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_tdxml(tmp, "a.tdxml", "Invisible", "true")
            self._write_tdxml(tmp, "b.tdxml", "Visible", "false")
            result = find_target_name_recursively(tmp)
            self.assertEqual(result, "Visible")

    def test_multiple_files_one_invisible_one_noflag_returns_noflag(self):
        """One invisible + one no-flag: no-flag IS accepted (new behaviour)."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_tdxml(tmp, "a.tdxml", "A", "true")   # invisible -> rejected
            self._write_tdxml(tmp, "b.tdxml", "B")            # no flag   -> accepted
            result = find_target_name_recursively(tmp)
            self.assertEqual(result, "B")

    def test_all_invisible_returns_none(self):
        """All .tdxml files have isInvisible=true -> None."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_tdxml(tmp, "a.tdxml", "A", "true")
            self._write_tdxml(tmp, "b.tdxml", "B", "true")
            result = find_target_name_recursively(tmp)
            self.assertIsNone(result)

    def test_nonexistent_directory(self):
        """Returns None for non-existent directory."""
        result = find_target_name_recursively(r"C:\nonexistent_12345")
        self.assertIsNone(result)

    def test_empty_directory(self):
        """Returns None when no .tdxml files exist."""
        with tempfile.TemporaryDirectory() as tmp:
            result = find_target_name_recursively(tmp)
            self.assertIsNone(result)

    def test_prefers_shallower_file(self):
        """Among multiple visible files, shallower depth wins."""
        with tempfile.TemporaryDirectory() as tmp:
            self._write_tdxml(tmp, "shallow.tdxml", "ShallowTarget", "false")
            sub = os.path.join(tmp, "deep", "nested")
            self._write_tdxml(sub, "deep.tdxml", "DeepTarget", "false")
            result = find_target_name_recursively(tmp)
            self.assertEqual(result, "ShallowTarget")


class TestExtractFromDir(unittest.TestCase):
    """Tests for extract_from_dir()."""

    def _write_tdxml(self, directory: str, filename: str,
                     targets: list, buildtypes: list = None) -> str:
        parts = []
        for t in targets:
            btsection = ""
            if buildtypes:
                btlist = "".join(
                    f"<BuildType><BuildTypeName>{b}</BuildTypeName></BuildType>"
                    for b in buildtypes
                )
                btsection = f"<BuildProcessDefinition><BuildTypes>{btlist}</BuildTypes></BuildProcessDefinition>"
            parts.append(
                f"<TargetInformation><TargetName>{t}</TargetName>{btsection}</TargetInformation>"
            )
        content = f'<?xml version="1.0"?><Project>{"" .join(parts)}</Project>'
        filepath = os.path.join(directory, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def test_single_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_tdxml(tmp, "x.tdxml", ["T1"], ["NORMAL"])
            result = extract_from_dir(tmp)
            self.assertIn(p, result)
            self.assertEqual(result[p]["targets"], ["T1"])
            self.assertEqual(result[p]["buildtypes"], ["NORMAL"])

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(extract_from_dir(tmp), {})

    def test_nonexistent_dir(self):
        self.assertEqual(extract_from_dir(r"C:\nonexistent_99999"), {})

    def test_multiple_files_in_subdirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            sub = os.path.join(tmp, "sub")
            self._write_tdxml(tmp, "a.tdxml", ["A"], [])
            self._write_tdxml(sub, "b.tdxml", ["B"], ["RELEASE"])
            result = extract_from_dir(tmp)
            self.assertEqual(len(result), 2)

    def test_file_with_no_targets_excluded(self):
        """Files yielding no valid targets should not appear in result."""
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write_tdxml(tmp, "empty.tdxml", [], [])
            result = extract_from_dir(tmp)
            self.assertNotIn(p, result)


class TestFindBuildtypesRecursively(unittest.TestCase):
    """Tests for find_buildtypes_recursively()."""

    def _write_tdxml(self, directory: str, filename: str,
                     buildtypes: list) -> str:
        btlist = "".join(
            f"<BuildType><BuildTypeName>{b}</BuildTypeName></BuildType>"
            for b in buildtypes
        )
        btsection = f"<BuildProcessDefinition><BuildTypes>{btlist}</BuildTypes></BuildProcessDefinition>"
        content = (
            f'<?xml version="1.0"?><Project>'
            f'<TargetInformation><TargetName>T</TargetName>{btsection}</TargetInformation>'
            f'</Project>'
        )
        filepath = os.path.join(directory, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def test_finds_buildtypes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_tdxml(tmp, "a.tdxml", ["NORMAL", "RELEASE"])
            result = find_buildtypes_recursively(tmp)
            self.assertIn("NORMAL", result)
            self.assertIn("RELEASE", result)

    def test_fallback_normal_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(find_buildtypes_recursively(tmp), ["NORMAL"])

    def test_fallback_normal_nonexistent_dir(self):
        self.assertEqual(find_buildtypes_recursively(r"C:\nonexistent_77777"), ["NORMAL"])

    def test_deduplicates_across_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_tdxml(tmp, "a.tdxml", ["NORMAL", "RELEASE"])
            self._write_tdxml(tmp, "b.tdxml", ["NORMAL"])
            result = find_buildtypes_recursively(tmp)
            self.assertEqual(result.count("NORMAL"), 1)
            self.assertIn("RELEASE", result)


class TestCollectTargetsWithBuildtypes(unittest.TestCase):
    """Tests for _collect_targets_with_buildtypes()."""

    def _root(self, xml_str: str) -> ET.Element:
        return ET.fromstring(xml_str)

    def test_single_target_with_buildtypes(self):
        xml = """<Root>
            <TargetInformation>
                <TargetName>FSW</TargetName>
                <IsInvisible>false</IsInvisible>
                <BuildProcessDefinition>
                    <BuildTypes>
                        <BuildType><BuildTypeName>delivery</BuildTypeName></BuildType>
                        <BuildType><BuildTypeName>development</BuildTypeName></BuildType>
                    </BuildTypes>
                </BuildProcessDefinition>
            </TargetInformation>
        </Root>"""
        entries = _collect_targets_with_buildtypes(self._root(xml))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].name, "FSW")
        self.assertEqual(entries[0].buildtypes, ["delivery", "development"])

    def test_multiple_targets_different_buildtypes(self):
        """Two targets with different build types — like AUT02_0U0_XXX."""
        xml = """<Root>
            <TargetInformation>
                <TargetName>FSW</TargetName>
                <BuildProcessDefinition>
                    <BuildTypes>
                        <BuildType><BuildTypeName>delivery</BuildTypeName></BuildType>
                        <BuildType><BuildTypeName>development</BuildTypeName></BuildType>
                    </BuildTypes>
                </BuildProcessDefinition>
            </TargetInformation>
            <TargetInformation>
                <TargetName>FSW_ASW_Complete</TargetName>
                <IsInvisible>false</IsInvisible>
                <BuildProcessDefinition>
                    <BuildTypes>
                        <BuildType><BuildTypeName>delivery</BuildTypeName></BuildType>
                    </BuildTypes>
                </BuildProcessDefinition>
            </TargetInformation>
        </Root>"""
        entries = _collect_targets_with_buildtypes(self._root(xml))
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].name, "FSW")
        self.assertEqual(entries[0].buildtypes, ["delivery", "development"])
        self.assertEqual(entries[1].name, "FSW_ASW_Complete")
        self.assertEqual(entries[1].buildtypes, ["delivery"])

    def test_invisible_target_excluded(self):
        xml = """<Root>
            <TargetInformation>
                <TargetName>Hidden</TargetName>
                <IsInvisible>true</IsInvisible>
                <BuildProcessDefinition>
                    <BuildTypes>
                        <BuildType><BuildTypeName>NORMAL</BuildTypeName></BuildType>
                    </BuildTypes>
                </BuildProcessDefinition>
            </TargetInformation>
        </Root>"""
        entries = _collect_targets_with_buildtypes(self._root(xml))
        self.assertEqual(entries, [])

    def test_target_without_buildprocessdefinition(self):
        xml = """<Root>
            <TargetInformation>
                <TargetName>Bare</TargetName>
            </TargetInformation>
        </Root>"""
        entries = _collect_targets_with_buildtypes(self._root(xml))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].name, "Bare")
        self.assertEqual(entries[0].buildtypes, [])

    def test_proj2_style_four_buildtypes(self):
        """Single target with NORMAL, RELEASE, SAMPLE, BAAS."""
        xml = """<Root>
            <TargetInformation>
                <TargetName>FS_PROJ2_0U0</TargetName>
                <BuildProcessDefinition>
                    <BuildTypes>
                        <BuildType><BuildTypeName>NORMAL</BuildTypeName></BuildType>
                        <BuildType><BuildTypeName>RELEASE</BuildTypeName></BuildType>
                        <BuildType><BuildTypeName>SAMPLE</BuildTypeName></BuildType>
                        <BuildType><BuildTypeName>BAAS</BuildTypeName></BuildType>
                    </BuildTypes>
                </BuildProcessDefinition>
            </TargetInformation>
        </Root>"""
        entries = _collect_targets_with_buildtypes(self._root(xml))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].buildtypes,
                         ["NORMAL", "RELEASE", "SAMPLE", "BAAS"])

    def test_mixed_visible_invisible(self):
        xml = """<Root>
            <TargetInformation>
                <TargetName>Visible</TargetName>
                <IsInvisible>false</IsInvisible>
                <BuildProcessDefinition>
                    <BuildTypes>
                        <BuildType><BuildTypeName>A</BuildTypeName></BuildType>
                    </BuildTypes>
                </BuildProcessDefinition>
            </TargetInformation>
            <TargetInformation>
                <TargetName>Invisible</TargetName>
                <IsInvisible>true</IsInvisible>
                <BuildProcessDefinition>
                    <BuildTypes>
                        <BuildType><BuildTypeName>B</BuildTypeName></BuildType>
                    </BuildTypes>
                </BuildProcessDefinition>
            </TargetInformation>
        </Root>"""
        entries = _collect_targets_with_buildtypes(self._root(xml))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].name, "Visible")
        self.assertEqual(entries[0].buildtypes, ["A"])

    def test_sibling_buildprocessdefinition(self):
        """TargetInformation and BuildProcessDefinition as siblings (real TD5 layout)."""
        xml = """<Root>
            <TargetInformation>
                <TargetName>FS_PROJ2_0U0</TargetName>
            </TargetInformation>
            <BuildProcessDefinition>
                <BuildTypes>
                    <BuildType><BuildTypeName>NORMAL</BuildTypeName></BuildType>
                    <BuildType><BuildTypeName>RELEASE</BuildTypeName></BuildType>
                    <BuildType><BuildTypeName>SAMPLE</BuildTypeName></BuildType>
                    <BuildType><BuildTypeName>BAAS</BuildTypeName></BuildType>
                </BuildTypes>
            </BuildProcessDefinition>
        </Root>"""
        entries = _collect_targets_with_buildtypes(self._root(xml))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].name, "FS_PROJ2_0U0")
        self.assertEqual(entries[0].buildtypes, ["NORMAL", "RELEASE", "SAMPLE", "BAAS"])


class TestFindTargetsRecursively(unittest.TestCase):
    """Tests for find_targets_recursively()."""

    def _write_tdxml(self, directory: str, filename: str,
                     targets_and_bts: list) -> str:
        """Write .tdxml with [(target_name, [bt, ...]), ...]."""
        parts = []
        for tname, bts in targets_and_bts:
            bt_xml = ""
            if bts:
                btlist = "".join(
                    f"<BuildType><BuildTypeName>{b}</BuildTypeName></BuildType>"
                    for b in bts
                )
                bt_xml = f"<BuildProcessDefinition><BuildTypes>{btlist}</BuildTypes></BuildProcessDefinition>"
            parts.append(
                f"<TargetInformation><TargetName>{tname}</TargetName>{bt_xml}</TargetInformation>"
            )
        content = f'<?xml version="1.0"?><Project>{"" .join(parts)}</Project>'
        filepath = os.path.join(directory, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def test_single_file_single_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_tdxml(tmp, "a.tdxml", [("V3M", ["NORMAL"])])
            result = find_targets_recursively(tmp)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].name, "V3M")
            self.assertEqual(result[0].buildtypes, ["NORMAL"])

    def test_single_file_multiple_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_tdxml(tmp, "a.tdxml", [
                ("FSW", ["delivery", "development"]),
                ("FSW_ASW_Complete", ["delivery"]),
            ])
            result = find_targets_recursively(tmp)
            self.assertEqual(len(result), 2)
            names = [r.name for r in result]
            self.assertIn("FSW", names)
            self.assertIn("FSW_ASW_Complete", names)

    def test_deduplicates_across_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_tdxml(tmp, "a.tdxml", [("T1", ["NORMAL"])])
            sub = os.path.join(tmp, "sub")
            self._write_tdxml(sub, "b.tdxml", [("T1", ["RELEASE"])])
            result = find_targets_recursively(tmp)
            # T1 from shallowest file wins
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].name, "T1")
            self.assertEqual(result[0].buildtypes, ["NORMAL"])

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(find_targets_recursively(tmp), [])

    def test_nonexistent_dir(self):
        self.assertEqual(find_targets_recursively(r"C:\nonexistent_88888"), [])

    def test_target_without_buildtypes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_tdxml(tmp, "a.tdxml", [("Bare", [])])
            result = find_targets_recursively(tmp)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].name, "Bare")
            self.assertEqual(result[0].buildtypes, [])


if __name__ == "__main__":
    unittest.main()
