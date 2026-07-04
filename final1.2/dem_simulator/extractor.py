"""Automatic DEM configuration extractor from generated C sources.

It parses ``icsp_dem_cnf.c`` and the ``icsp_dem_cnf_ptu*.h`` files to build
``ProjectConfig`` and PTU variants without hardcoded values.

Parsed C structures
-------------------
- ``Icsp_Dem_Cnf_Fmy_ConstStruct``       → NrFifoBas, NrFifoIntm, NrFifoRsv,
                                           NrFmy, NrFmyBufNvmWr
- ``Icsp_Dem_Cnf_Frf_ConstStruct``       → NrByteFrfFmy, NrFrfDataTot,
                                           NrFrfPreData, NrBlockFrf
- ``Icsp_Dem_Cnf_Frf_Block_ConstStruct`` → FrfBlocks[N] (NrByteFrame,
                                           NrFrfIdxCalMax, LfOptions,
                                           NrFrfHold, NrFrfTot, NrIdxPerClass)
- ``Icsp_Dem_Cnf_FrfPre_ConstStruct``    → NrFrfPre
- ``Icsp_Dem_Cnf_Lamp_ConstStruct``      → NrMaxLampDeb (stored as NrLamp)
- Array ``Icsp_Dem_Smad_SmadNum[N]``     → NrEve (array size)
- PTU files ``icsp_dem_cnf_ptu*.h``      → NrClcFmyEveAsyn, NrClcFmyPost,
                                           NrEve per variant

Usage
-----
    from dem_simulator.extractor import load_project_from_c

    project = load_project_from_c(
        cnf_c_path   = r"PROJ3/.../icsp_dem_cnf.c",
        ptu_dir      = r"PROJ3/work/bsw/icsp/dem/dem/pi/main/t",
        project_name = "PROJ3",
    )
"""

from __future__ import annotations

import glob
import logging
import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from dem_simulator.config import (
    FrfBlockConfig,
    ProjectConfig,
    ProjectDefinition,
)
from dem_simulator.exceptions import SimulatorError


def _make_variant(base: ProjectConfig, **overrides: Any) -> ProjectConfig:
    """Create a config variant by overriding the specified fields.

    All ``ProjectConfig`` fields except ``FrfBlocks`` are copied shallowly;
    ``FrfBlocks`` receives a list copy to avoid aliasing.
    """
    _FIELDS = [
        'name', 'NrFmy', 'NrFifoBas', 'NrFifoIntm', 'NrFifoRsv',
        'NrClcFmyEveAsyn', 'NrClcFmyPost', 'NrEve', 'NrFrfDataTot',
        'NrFrfPreData', 'NrBlockFrf', 'NrFrfPre', 'NrByteFrfFmy',
        'nr_inject_first', 'nr_inject_next', 'has_prio_obd_uds_swap', 'gpt_api',
        'NrCallbackTypes', 'NrFctDtcStatusChangedTot',
        'NrFctEventStatusChanged', 'NrFctFrfDataChanged',
        'NrLamp', 'NrFmyBufNvmWr', 'NrClient', 'NrCore', 'NrPtuProfiles',
        'IsSharedCore', 'cpu_clock_mhz',
    ]
    d: Dict[str, Any] = {f: getattr(base, f) for f in _FIELDS}
    d['FrfBlocks'] = list(base.FrfBlocks)
    d.update(overrides)
    return ProjectConfig(**d)

logger = logging.getLogger("dem_simulator")


# ==============================================================================
# Helpers
# ==============================================================================

def _normalize_existing_search_root(hint_path: Optional[str]) -> Optional[str]:
    """Return an existing directory usable as a search root.

    ``hint_path`` may point to a missing file in the expected project layout.
    In that case we walk up until we find an existing parent directory.
    """
    if not hint_path:
        return None

    current = os.path.abspath(hint_path)
    while not os.path.exists(current):
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent

    if os.path.isfile(current):
        current = os.path.dirname(current)
    return current

def _read(path: str) -> str:
    """Read a file and return its contents as a string."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as exc:
        raise SimulatorError(f"Cannot read file {path!r}: {exc}") from exc


def _extract_braced_block(text: str, open_brace_index: int) -> str:
    """Extract a balanced ``{...}`` block starting at *open_brace_index*."""
    if open_brace_index < 0 or open_brace_index >= len(text) or text[open_brace_index] != "{":
        return ""
    depth = 1
    i = open_brace_index + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[open_brace_index + 1: i - 1]


def _find_if_body(main_fn_body: str, cond_name: str) -> str:
    """Return the body of ``if (<cond_name>) { ... }`` from main function body."""
    m = re.search(rf"if\s*\(\s*{re.escape(cond_name)}\s*\)", main_fn_body)
    if not m:
        return ""
    brace_idx = main_fn_body.find("{", m.end())
    if brace_idx < 0:
        return ""
    return _extract_braced_block(main_fn_body, brace_idx)


def extract_wcs_injection_counts(main_c_path: str) -> Tuple[int, int]:
    """Parse ``Icsp_Dem_MainFunction`` and count WCS diagnostic injections.

    Returns ``(nr_inject_first, nr_inject_next)`` where each value is the
    number of ``ACTION_ERRM_ResultDiag(...)`` calls in the corresponding
    calibration branch.
    """
    text = _read(main_c_path)
    fn_m = re.search(r"void\s+Icsp_Dem_MainFunction\s*\(\s*void\s*\)", text)
    if not fn_m:
        return 20, 20
    fn_brace = text.find("{", fn_m.end())
    if fn_brace < 0:
        return 20, 20
    fn_body = _extract_braced_block(text, fn_brace)
    first_body = _find_if_body(fn_body, "lc_enable_first_nr_fmy_events")
    next_body = _find_if_body(fn_body, "lc_enable_next_nr_fmy_events")
    nr_first = len(re.findall(r"\bACTION_ERRM_ResultDiag\s*\(", first_body))
    nr_next = len(re.findall(r"\bACTION_ERRM_ResultDiag\s*\(", next_body))
    if nr_first <= 0:
        nr_first = 20
    if nr_next <= 0:
        nr_next = 20
    return nr_first, nr_next


def _detect_gpt_api(main_c_path: Optional[str]) -> str:
    """Detect runtime timer API style used in ``Icsp_Dem_MainFunction``."""
    if not main_c_path or not os.path.isfile(main_c_path):
        return "iopt_gpt"
    text = _read(main_c_path)
    if "Iopt_Gpt_GetSystemTime" in text or "Iopt_Gpt_ConvertTicksToMicrosec" in text:
        return "iopt_gpt"
    if "Gpt_GetSystemTime" in text or "Gpt_ConvertTicksToMicrosec" in text:
        return "gpt"
    return "iopt_gpt"


def _detect_prio_obd_uds_swap(cnf_text: str) -> bool:
    """Best-effort detection of OBD-on-UDS priority-switch support."""
    return (
        "Icsp_Dem_Cnf_Prio_ConstStruct_OBD" in cnf_text
        and "Icsp_Dem_Cnf_Prio_ConstStruct_OBDonUDS" in cnf_text
    )


def _discover_main_c_from_hint(hint_path: Optional[str]) -> Optional[str]:
    """Discover the most relevant ``icsp_dem_main.c`` near *hint_path*."""
    start = _normalize_existing_search_root(hint_path)
    if not start:
        return None

    current = start
    anchor = os.path.basename(start).lower()
    candidates: List[str] = []
    for _ in range(3):
        base_depth = current.count(os.sep)
        for dirpath, dirnames, filenames in os.walk(current):
            if dirpath.count(os.sep) - base_depth >= 10:
                dirnames.clear()
                continue
            if "icsp_dem_main.c" in filenames:
                candidates.append(os.path.join(dirpath, "icsp_dem_main.c"))
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    if not candidates:
        return None

    def _score(path: str) -> Tuple[int, int]:
        p = path.replace("/", "\\").lower()
        s = 0
        if anchor and anchor in p:
            s += 40
        else:
            s -= 80
        if "\\work\\" in p:
            s += 20
        if "\\proc\\" in p:
            s -= 8
        if "\\bld\\" in p:
            s -= 5
        if "\\pi\\main\\i\\icsp_dem_main.c" in p:
            s += 10
        return s, -len(path)

    return sorted(candidates, key=_score, reverse=True)[0]


def _discover_cnf_c_from_hint(hint_path: Optional[str]) -> Optional[str]:
    """Discover ``icsp_dem_cnf.c`` near the provided project hint path."""
    start = _normalize_existing_search_root(hint_path)
    if not start:
        return None
    current = start
    anchor = os.path.basename(start).lower()
    candidates: List[str] = []
    for _ in range(3):
        base_depth = current.count(os.sep)
        for dirpath, dirnames, filenames in os.walk(current):
            if dirpath.count(os.sep) - base_depth >= 10:
                dirnames.clear()
                continue
            if "icsp_dem_cnf.c" in filenames:
                candidates.append(os.path.join(dirpath, "icsp_dem_cnf.c"))
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    if not candidates:
        return None

    def _score(path: str) -> Tuple[int, int]:
        p = path.replace("/", "\\").lower()
        s = 0
        if anchor and anchor in p:
            s += 50
        else:
            s -= 100
        if "\\proc\\arproc\\out\\icsp_dem_cnf.c" in p:
            s += 25
        if "generated\\icsp_dem\\compilables" in p:
            s += 20
        if "\\out\\icsp_dem_cnf.c" in p:
            s += 12
        if "\\_v" in p and "\\normal\\" in p:
            s += 8
        if "\\bld\\_" in p:
            s -= 30
        if "\\bld\\work\\" in p:
            s -= 15
        if "\\release\\" in p:
            s += 2
        if "\\normal\\" in p:
            s += 1
        return s, -len(path)

    return sorted(candidates, key=_score, reverse=True)[0]


def _strip_comments(text: str) -> str:
    """Remove C comments (// and /* */) from text."""
    # Remove /* ... */
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    # Remove // ...
    text = re.sub(r"//[^\n]*", " ", text)
    return text


def _extract_struct_body(text: str, struct_name: str) -> Optional[str]:
    """Extract the body of an initializer like ``struct_name = { ... };``.

    Returns the contents between the outer braces (without the outer braces),
    or None if the structure was not found.

    Also supports arrays: ``struct_name[N] = { ... }``
    """
    # Search for "struct_name" optionally followed by "[N]" and "= {"
    pattern = re.compile(
        r"\b" + re.escape(struct_name) + r"(?:\s*\[\s*\d+\s*\])?\s*=\s*\{",
        re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return None

    start = m.end()  # after the first opening brace
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[start : i - 1]  # without the closing brace


def _parse_scalar_values(body: str) -> List[str]:
    """Extract scalar values from a struct initializer.

    Returns a list of tokens: pointers (``&...``), numeric literals
    (``40U``, ``20U``), and keywords (``NULL_PTR``).
    Ignores nested sub-struct initializers ``{ ... }``.
    """
    tokens: List[str] = []
    i = 0
    text = body.strip()
    while i < len(text):
        c = text[i]
        if c in (" ", "\t", "\n", "\r", ","):
            i += 1
        elif c == "{":
            # sub-struct — skip the whole block
            depth = 1
            i += 1
            while i < len(text) and depth > 0:
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                i += 1
        elif c == "&":
            # pointer — ia până la virgulă/newline/spațiu
            j = i + 1
            while j < len(text) and text[j] not in (",", "\n", " ", "\t"):
                j += 1
            tokens.append(text[i:j])
            i = j
        elif c == "(":
            # cast expression: (uint32)sizeof(...)  → ia tot
            depth = 1
            j = i + 1
            while j < len(text) and depth > 0:
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                j += 1
            tokens.append(text[i:j])
            i = j
        elif c.isalnum() or c == "_":
            j = i
            while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                j += 1
            tokens.append(text[i:j])
            i = j
        else:
            i += 1
    return tokens


def _to_int(token: str) -> Optional[int]:
    """Convert a numeric C token (``40U``, ``0x1AU``) to a Python int."""
    t = token.rstrip("UuLl").strip()
    try:
        return int(t, 0)
    except (ValueError, TypeError):
        return None


# ==============================================================================
# Parsare Fmy
# ==============================================================================

def _parse_fmy(text: str) -> Dict[str, int]:
        """Extract numeric fields from ``Icsp_Dem_Cnf_Fmy_ConstStruct``.

        The structure has 26 fields according to the header from the user request;
        the last 7 are numeric scalars (after the pointers):
            NrByteFmyNvmBlock (uint32, cast), LfVarAgingWhileHealing,
            LfVarReconfirmImmediately, NrFifoBas, NrFifoIntm, NrFifoRsv,
            NrFmy, NrFmyBufNvmWr
        """
    body = _extract_struct_body(text, "Icsp_Dem_Cnf_Fmy_ConstStruct")
    if body is None:
        raise SimulatorError("Could not find Icsp_Dem_Cnf_Fmy_ConstStruct in the C file")

    tokens = _parse_scalar_values(_strip_comments(body))
    # The last 8 tokens are the numeric fields (the rest are pointers)
    # Order in the struct:
    #   [0..18] pointeri  →  19 pointeri + (uint32)sizeof(...) = ~20 tokens non-scalar
    #   [-8]  NrByteFmyNvmBlock  (poate fi cast)
    #   [-7]  LfVarAgingWhileHealing
    #   [-6]  LfVarReconfirmImmediately
    #   [-5]  NrFifoBas
    #   [-4]  NrFifoIntm
    #   [-3]  NrFifoRsv
    #   [-2]  NrFmy
    #   [-1]  NrFmyBufNvmWr

    # Keep only tokens that are numeric values or casts
    scalar_tokens = []
    for t in tokens:
        if t.startswith("&") or t == "NULL_PTR":
            continue
        scalar_tokens.append(t)

    if len(scalar_tokens) < 8:
        raise SimulatorError(
            f"Fmy struct: found {len(scalar_tokens)} scalars, expected >= 8"
        )

    result: Dict[str, int] = {}
    tail = scalar_tokens[-8:]

    # NrByteFmyNvmBlock — may be (uint32)sizeof(...), ignore it
    result["NrFifoBas"]      = _to_int(tail[-5]) or 0
    result["NrFifoIntm"]     = _to_int(tail[-4]) or 0
    result["NrFifoRsv"]      = _to_int(tail[-3]) or 0
    result["NrFmy"]          = _to_int(tail[-2]) or 0
    result["NrFmyBufNvmWr"]  = _to_int(tail[-1]) or 0

    logger.debug("Fmy: %s", result)
    return result


# ==============================================================================
# Parsare Frf
# ==============================================================================

def _parse_frf(text: str) -> Dict[str, int]:
    """Extract numeric fields from ``Icsp_Dem_Cnf_Frf_ConstStruct``.

    There are two structure variants in different projects:

    **Variant A** (with ``NrFrfDataTot``) — 4 scalars at the end:
        ``NrByteFrfFmy``, ``NrFrfDataTot``, ``NrFrfPreData``, ``NrBlockFrf``

    **Variant B** (without ``NrFrfDataTot``) — 3 scalars at the end:
        ``NrByteFrfFmy``, ``NrFrfPreData``, ``NrBlockFrf``

    Detection checks whether ``NrFrfDataTot`` appears as a member in the
    definition ``struct Icsp_Dem_Cnf_Frf_Struct_tag``.
    """
    body = _extract_struct_body(text, "Icsp_Dem_Cnf_Frf_ConstStruct")
    if body is None:
        raise SimulatorError("Could not find Icsp_Dem_Cnf_Frf_ConstStruct in the C file")

    tokens = _parse_scalar_values(_strip_comments(body))
    # Filter out pointers -> keep only scalar values
    scalar_tokens = [t for t in tokens if not t.startswith("&") and t != "NULL_PTR"]
    # From the scalars, keep only those convertible to int
    numeric_tokens = [t for t in scalar_tokens if _to_int(t) is not None]

    # Detect the structure variant by checking the type definition
    has_nr_frf_data_tot = bool(
        re.search(
            r"struct\s+Icsp_Dem_Cnf_Frf_Struct_tag\b.*?"
            r"\bNrFrfDataTot\b",
            _strip_comments(text),
            re.DOTALL,
        )
    )

    if has_nr_frf_data_tot:
        # Variant A: 4 scalars — NrByteFrfFmy, NrFrfDataTot, NrFrfPreData, NrBlockFrf
        if len(numeric_tokens) < 4:
            raise SimulatorError(
                f"Frf struct (variant A): found {len(numeric_tokens)} numeric scalars, "
                f"expected >= 4. Raw tokens: {tokens!r}"
            )
        tail = numeric_tokens[-4:]
        result = {
            "NrByteFrfFmy":  _to_int(tail[0]) or 0,
            "NrFrfDataTot":  _to_int(tail[1]) or 0,
            "NrFrfPreData":  _to_int(tail[2]) or 0,
            "NrBlockFrf":    _to_int(tail[3]) or 0,
        }
        logger.debug("Frf (variant A, with NrFrfDataTot): %s", result)
    else:
        # Variant B: 3 scalars — NrByteFrfFmy, NrFrfPreData, NrBlockFrf
        if len(numeric_tokens) < 3:
            raise SimulatorError(
                f"Frf struct (variant B): found {len(numeric_tokens)} numeric scalars, "
                f"expected >= 3. Raw tokens: {tokens!r}"
            )
        tail = numeric_tokens[-3:]
        result = {
            "NrByteFrfFmy":  _to_int(tail[0]) or 0,
            "NrFrfDataTot":  0,  # missing in this variant
            "NrFrfPreData":  _to_int(tail[1]) or 0,
            "NrBlockFrf":    _to_int(tail[2]) or 0,
        }
        logger.debug("Frf (variant B, without NrFrfDataTot): %s", result)

    return result


# ==============================================================================
# Parsare FrfBlocks
# ==============================================================================

def _parse_frf_blocks(text: str) -> List[FrfBlockConfig]:
        """Extract the array ``Icsp_Dem_Cnf_Frf_Block_ConstStruct[N]``.

        Each element has 13 fields:
            5 pointers + NrByteFrame, NrFrfIdxCalMax, offsetStoragePlace,
            offsetStoragePlacePrev, LfOptions, NrFrfHold, NrFrfTot, NrIdxPerClass
        """
    body = _extract_struct_body(text, "Icsp_Dem_Cnf_Frf_Block_ConstStruct")
    if body is None:
        raise SimulatorError(
            "Could not find Icsp_Dem_Cnf_Frf_Block_ConstStruct in the C file"
        )

    clean = _strip_comments(body)

    # Fiecare bloc este un { ... } la nivel de top
    blocks: List[FrfBlockConfig] = []
    i = 0
    while i < len(clean):
        if clean[i] == "{":
            # găsit un bloc
            depth = 1
            j = i + 1
            while j < len(clean) and depth > 0:
                if clean[j] == "{":
                    depth += 1
                elif clean[j] == "}":
                    depth -= 1
                j += 1
            bloc_body = clean[i + 1 : j - 1]
            tokens = _parse_scalar_values(bloc_body)
            scalars = [t for t in tokens if not t.startswith("&") and t != "NULL_PTR"]

            # Trebuie să avem cel puțin 8 scalari numerici
            # (NrByteFrame, NrFrfIdxCalMax, offset1, offset2,
            #  LfOptions, NrFrfHold, NrFrfTot, NrIdxPerClass)
            num_scalars = []
            for t in scalars:
                v = _to_int(t)
                if v is not None:
                    num_scalars.append(v)

            if len(num_scalars) >= 8:
                # ultimii 8 câmpuri numerice
                tail = num_scalars[-8:]
                # NrByteFrame, NrFrfIdxCalMax, offset1, offset2,
                # LfOptions, NrFrfHold, NrFrfTot, NrIdxPerClass
                blk = FrfBlockConfig(
                    NrByteFrame     = tail[0],
                    NrFrfIdxCalMax  = tail[1],
                    NrIdxPerClass   = tail[7],
                    NrFrfHold       = tail[5],
                    NrFrfTot        = tail[6],
                    LfOptions       = tail[4],
                )
                blocks.append(blk)
                logger.debug("FrfBlock %d: %s", len(blocks) - 1, blk)
            i = j
        else:
            i += 1

    if not blocks:
        raise SimulatorError("Nu am găsit niciun bloc în Icsp_Dem_Cnf_Frf_Block_ConstStruct")

    return blocks


# ==============================================================================
# Parsare FrfPre
# ==============================================================================

def _parse_frfpre(text: str) -> int:
    """Extrage NrFrfPre din ``Icsp_Dem_Cnf_FrfPre_ConstStruct``.

    Structura are 8 câmpuri, ultimul este NrFrfPre (uint8).
    """
    body = _extract_struct_body(text, "Icsp_Dem_Cnf_FrfPre_ConstStruct")
    if body is None:
        raise SimulatorError(
            "Nu am găsit Icsp_Dem_Cnf_FrfPre_ConstStruct în fișierul C"
        )

    tokens = _parse_scalar_values(_strip_comments(body))
    scalar_tokens = [t for t in tokens if not t.startswith("&") and t != "NULL_PTR"]

    if not scalar_tokens:
        raise SimulatorError("FrfPre struct: nu am găsit scalari")

    val = _to_int(scalar_tokens[-1])
    if val is None:
        raise SimulatorError(
            f"FrfPre struct: ultimul scalar nu e numeric: {scalar_tokens[-1]!r}"
        )
    logger.debug("NrFrfPre: %d", val)
    return val


# ==============================================================================
# Parsare Lamp (NrMaxLampDeb)
# ==============================================================================

def _parse_lamp(text: str) -> int:
    """Extrage NrMaxLampDeb din ``Icsp_Dem_Cnf_Lamp_ConstStruct``.

    Structura Lamp are pointeri urmate de scalari numerici.
    NrMaxLampDeb este al treilea scalar de la sfârșit (înainte de NrLamp=2).
    Ordinea ultimelor câmpuri: ..., NrMaxLampDeb, (rezervat=0), NrLamp
    """
    body = _extract_struct_body(text, "Icsp_Dem_Cnf_Lamp_ConstStruct")
    if body is None:
        raise SimulatorError(
            "Nu am găsit Icsp_Dem_Cnf_Lamp_ConstStruct în fișierul C"
        )

    tokens = _parse_scalar_values(_strip_comments(body))
    scalar_tokens = [t for t in tokens if not t.startswith("&") and t != "NULL_PTR"]
    num_scalars = [_to_int(t) for t in scalar_tokens if _to_int(t) is not None]

    if len(num_scalars) < 3:
        raise SimulatorError(
            f"Lamp struct: am găsit {len(num_scalars)} scalari, așteptam >= 3"
        )

    # ultimii 3: NrMaxLampDeb, 0, NrLamp(=2)
    nr_max_lamp_deb = num_scalars[-3]
    logger.debug("NrMaxLampDeb: %d", nr_max_lamp_deb)
    return nr_max_lamp_deb


# ==============================================================================
# Parsare NrEve din array-ul Smad
# ==============================================================================

def _find_genr_xml(cnf_c_path: str) -> Optional[str]:
    """Localizează ``icsp_dem_genr.xml`` relativ la ``icsp_dem_cnf.c``.

    ``icsp_dem_cnf.c`` se află tipic în::

        …/<PROJECT>/_FS_<PROJECT>_NORMAL/proc/ARPROC/out/icsp_dem_cnf.c

    iar ``icsp_dem_genr.xml`` poate fi adânc sub un director frate, de ex.::

        …/<PROJECT>/_FS_<PROJECT>_NORMAL/proc/ARPROC/tmp/…/icsp_dem_genr.xml

    Strategia:
      1. Urcă de la directorul ``cnf_c_path`` până la 6 nivele părinți.
      2. La fiecare nivel, face un ``os.walk`` recursiv *limitat la 8 nivele
         de adâncime* pentru a căuta ``icsp_dem_genr.xml``.
      3. Oprirea la primul rezultat găsit.

    Limitele de adâncime previn scanarea întregului disc.
    """
    _TARGET = "icsp_dem_genr.xml"
    _MAX_PARENT_LEVELS = 6   # cât urcăm din directorul cnf.c
    _MAX_WALK_DEPTH = 8      # cât coborâm recursiv la fiecare nivel

    current = os.path.dirname(os.path.abspath(cnf_c_path))

    for _ in range(_MAX_PARENT_LEVELS):
        # os.walk coboară recursiv; limităm adâncimea
        base_depth = current.count(os.sep)
        for dirpath, dirnames, filenames in os.walk(current):
            # Limităm adâncimea de parcurgere
            if dirpath.count(os.sep) - base_depth >= _MAX_WALK_DEPTH:
                dirnames.clear()  # oprește coborârea mai adânc
                continue
            if _TARGET in filenames:
                found = os.path.join(dirpath, _TARGET)
                logger.debug("icsp_dem_genr.xml găsit: %s", found)
                return found

        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    return None


def _parse_nr_eve_from_xml(xml_path: str) -> Optional[int]:
    """Extrage NrEve din ``icsp_dem_genr.xml``.

    Caută elementul cu ``<swSymbolName>NrEve</swSymbolName>`` și citește
    ``<initialValue><integer><value>N</value></integer></initialValue>``.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        # Eliminăm namespace-ul dacă există
        ns = ""
        m = re.match(r"\{(.+?)\}", root.tag)
        if m:
            ns = m.group(1)

        def _find(tag: str) -> str:
            return f"{{{ns}}}{tag}" if ns else tag

        # Căutăm recursiv toate elementele cu swSymbolName
        for sym_el in root.iter(_find("swSymbolName")):
            if sym_el.text and sym_el.text.strip() == "NrEve":
                # Navigăm la părintele care conține initialValue
                # ET nu are parent map direct, deci căutăm cu XPath
                break
        else:
            logger.debug("[XML] Nu am găsit <swSymbolName>NrEve</swSymbolName> în %s", xml_path)
            return None

        # Strategia: căutăm în tot XML-ul secvența NrEve → initialValue → integer → value
        # deoarece ET standard nu expune parent. Folosim regex pe textul brut.
        raw = _read(xml_path)
        pattern = re.compile(
            r"<swSymbolName>\s*NrEve\s*</swSymbolName>"
            r".*?<initialValue>\s*<integer>\s*<value>\s*(\d+)\s*</value>",
            re.DOTALL,
        )
        m_val = pattern.search(raw)
        if m_val:
            val = int(m_val.group(1))
            logger.debug("NrEve (din XML %s): %d", xml_path, val)
            return val

        logger.debug("[XML] Am găsit NrEve dar nu initialValue în %s", xml_path)
        return None

    except ET.ParseError as exc:
        logger.warning("[XML] Eroare la parsarea %s: %s", xml_path, exc)
        return None


def _parse_nr_eve(text: str, cnf_c_path: Optional[str] = None) -> int:
    """Extrage NrEve cu strategie în cascadă:

    1. **XML primar** — caută ``icsp_dem_genr.xml`` relativ la ``cnf_c_path``
       și extrage ``<swSymbolName>NrEve</swSymbolName>`` →
       ``<initialValue><integer><value>``.
    2. **C array fallback** — caută dimensiunea ``Icsp_Dem_Smad_SmadNum[N]``
       din fișierul C.
    """
    # 1. Încercare XML
    if cnf_c_path:
        xml_path = _find_genr_xml(cnf_c_path)
        if xml_path:
            val = _parse_nr_eve_from_xml(xml_path)
            if val is not None:
                return val
            logger.debug("NrEve: XML găsit (%s) dar fără valoare, fallback la C.", xml_path)
        else:
            logger.debug("NrEve: icsp_dem_genr.xml negăsit, fallback la C.")

    # 2. Fallback: C array
    m = re.search(r"Icsp_Dem_Smad_SmadNum\s*\[\s*(\d+)\s*\]", text)
    if m:
        val = int(m.group(1))
        logger.debug("NrEve (din Smad C array): %d", val)
        return val

    raise SimulatorError(
        "Nu am putut determina NrEve: nici XML (icsp_dem_genr.xml) "
        "nici C array (Icsp_Dem_Smad_SmadNum[N]) nu au fost găsite."
    )


def _parse_nr_client(text: str) -> Optional[int]:
    """Extract NrClient from generated client arrays in ``icsp_dem_cnf.c``."""
    patterns = (
        r"Icsp_Dem_Client_RamStruct\s+\w+\s*\[\s*(\d+)\s*\]",
        r"Icsp_Dem_Client_Struct\s*\[\s*(\d+)\s*\]",
    )
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                val = int(m.group(1))
                if val > 0:
                    return val
            except ValueError:
                continue
    return None


def _parse_transition_topology_from_text(text: str) -> Dict[str, int]:
    """Parse transition topology from generated transition config arrays.

    Returns
    -------
    dict
        ``{"NrCore": int, "NrPtuProfiles": int}``
    """
    pattern = re.compile(
        r"Icsp_Dem_Cnf_TranStruct\s+const\s+Icsp_Dem_Cnf_ConstTranStruct\w*\s*"
        r"(?:\[\s*\d+\s*\])?\s*=\s*\{",
        re.DOTALL,
    )
    max_nr_core = 1
    nr_profiles = 0

    for m in pattern.finditer(text):
        open_brace = text.find("{", m.end() - 1)
        if open_brace < 0:
            continue
        body = _extract_braced_block(text, open_brace)
        if not body:
            continue
        nr_profiles += 1

        clean = _strip_comments(body)
        i = 0
        while i < len(clean):
            if clean[i] != "{":
                i += 1
                continue
            depth = 1
            j = i + 1
            while j < len(clean) and depth > 0:
                if clean[j] == "{":
                    depth += 1
                elif clean[j] == "}":
                    depth -= 1
                j += 1
            entry = clean[i + 1 : j - 1]
            tokens = _parse_scalar_values(entry)
            numeric = [_to_int(t) for t in tokens if (not t.startswith("&")) and t != "NULL_PTR"]
            numeric = [n for n in numeric if n is not None]
            if numeric:
                candidate = numeric[-1]
                if candidate is not None and 1 <= candidate <= 64:
                    max_nr_core = max(max_nr_core, candidate)
            i = j

    return {
        "NrCore": max_nr_core,
        "NrPtuProfiles": max(1, nr_profiles),
    }


# ==============================================================================
# Parsare PTU headers
# ==============================================================================

def _parse_ptu_file(ptu_path: str) -> Dict[str, int]:
    """Extrage NrClcFmyEveAsyn și NrClcFmyPost dintr-un fișier PTU.

    Caută pattern-uri de forma:
      ``uint8 const Icsp_Dem_Fmy_NrClcFmyEveAsyn_PTUx = 20U;``
      ``uint8 const Icsp_Dem_Fmy_NrClcFmyPost_PTUx = 40U;``
    """
    text = _read(ptu_path)
    result: Dict[str, int] = {}

    m_asyn = re.search(
        r"Icsp_Dem_Fmy_NrClcFmyEveAsyn_PTU\w+\s*=\s*(\d+)\s*U\s*;",
        text,
    )
    m_post = re.search(
        r"Icsp_Dem_Fmy_NrClcFmyPost_PTU\w+\s*=\s*(\d+)\s*U\s*;",
        text,
    )

    if m_asyn:
        result["NrClcFmyEveAsyn"] = int(m_asyn.group(1))
    if m_post:
        result["NrClcFmyPost"] = int(m_post.group(1))

    topo = _parse_transition_topology_from_text(text)
    if topo.get("NrCore", 0) > 0:
        result["NrCore"] = topo["NrCore"]

    return result


def _discover_ptu_files(ptu_dir: str) -> Dict[str, str]:
    """Returnează ``{ "PTU0": path, "PTU1": path, ... }`` din directorul PTU."""
    pattern = os.path.join(ptu_dir, "icsp_dem_cnf_ptu*.h")
    files = glob.glob(pattern)
    result: Dict[str, str] = {}
    for f in sorted(files):
        m = re.search(r"icsp_dem_cnf_ptu(\w+)\.h$", f, re.IGNORECASE)
        if m:
            key = f"PTU{m.group(1).upper()}"
            result[key] = f
    logger.debug("Fișiere PTU găsite: %s", list(result.keys()))
    return result


# ==============================================================================
# Funcție principală de extracție
# ==============================================================================

def extract_project_config(
    cnf_c_path: str,
    project_name: str,
    *,
    nr_clc_fmy_eve_asyn: int = 20,
    nr_clc_fmy_post: int = 10,
    nr_client: Optional[int] = None,
    cpu_clock_mhz: float = 300.0,
) -> ProjectConfig:
    """Parsează ``icsp_dem_cnf.c`` și construiește un ``ProjectConfig``.

    Parameters
    ----------
    cnf_c_path : str
        Calea completă către ``icsp_dem_cnf.c`` generat.
    project_name : str
        Numele proiectului (ex: ``"PROJ3"``).
    nr_clc_fmy_eve_asyn : int
        Valoarea de calibrare EveAsyn (default 20 — poate fi suprascrisă din PTU).
    nr_clc_fmy_post : int
        Valoarea de calibrare Post (default 10 — poate fi suprascrisă din PTU).
    nr_client : int
        Numărul de clienți DEM.
    cpu_clock_mhz : float
        Frecvența CPU în MHz.

    Returns
    -------
    ProjectConfig
        Configurația extrasă automat.
    """
    logger.info("Extrag configurație din: %s", cnf_c_path)
    raw = _read(cnf_c_path)
    main_c_path = _discover_main_c_from_hint(cnf_c_path)
    nr_inject_first, nr_inject_next = (20, 20)
    if main_c_path and os.path.isfile(main_c_path):
        nr_inject_first, nr_inject_next = extract_wcs_injection_counts(main_c_path)

    fmy    = _parse_fmy(raw)
    frf    = _parse_frf(raw)
    blocks = _parse_frf_blocks(raw)
    nr_frfpre = _parse_frfpre(raw)
    nr_lamp   = _parse_lamp(raw)
    nr_eve    = _parse_nr_eve(raw, cnf_c_path)
    prio_flag = _detect_prio_obd_uds_swap(raw)
    detected_nr_client = _parse_nr_client(raw)
    topo = _parse_transition_topology_from_text(raw)
    if nr_client is None:
        nr_client = detected_nr_client or 6
    gpt_api = _detect_gpt_api(main_c_path)

    cfg = ProjectConfig(
        name             = project_name,
        NrFmy            = fmy["NrFmy"],
        NrFifoBas        = fmy["NrFifoBas"],
        NrFifoIntm       = fmy["NrFifoIntm"],
        NrFifoRsv        = fmy["NrFifoRsv"],
        NrFmyBufNvmWr    = fmy["NrFmyBufNvmWr"],
        NrClcFmyEveAsyn  = nr_clc_fmy_eve_asyn,
        NrClcFmyPost     = nr_clc_fmy_post,
        NrEve            = nr_eve,
        nr_inject_first  = nr_inject_first,
        nr_inject_next   = nr_inject_next,
        NrFrfDataTot     = frf["NrFrfDataTot"],
        NrFrfPreData     = frf["NrFrfPreData"],
        NrBlockFrf       = frf["NrBlockFrf"],
        NrByteFrfFmy     = frf["NrByteFrfFmy"],
        NrFrfPre         = nr_frfpre,
        NrLamp           = nr_lamp,
        FrfBlocks        = blocks,
        NrClient         = nr_client,
        NrCore           = topo.get("NrCore", 1),
        NrPtuProfiles    = topo.get("NrPtuProfiles", 1),
        IsSharedCore     = False,
        cpu_clock_mhz    = cpu_clock_mhz,
        has_prio_obd_uds_swap = prio_flag,
        gpt_api          = gpt_api,
    )

    logger.info(
        "[%s] Extras: NrFmy=%d NrEve=%d NrFrfDataTot=%d NrBlockFrf=%d "
        "NrFrfPre=%d NrLamp=%d",
        project_name, cfg.NrFmy, cfg.NrEve, cfg.NrFrfDataTot,
        cfg.NrBlockFrf, cfg.NrFrfPre, cfg.NrLamp,
    )
    return cfg


def extract_ptu_variants(
    base_cfg: ProjectConfig,
    ptu_dir: str,
) -> Dict[str, ProjectConfig]:
    """Construiește variantele PTU citind fișierele ``icsp_dem_cnf_ptu*.h``.

    Suprascrie ``NrClcFmyEveAsyn`` și ``NrClcFmyPost`` din fiecare fișier PTU.
    NrEve per variantă rămâne cel din configurația de bază (același pentru
    toate variantele dintr-un proiect la nivel de struct Smad).

    Parameters
    ----------
    base_cfg : ProjectConfig
        Configurația de bază extrasă din ``icsp_dem_cnf.c``.
    ptu_dir : str
        Directorul care conține fișierele ``icsp_dem_cnf_ptu*.h``.

    Returns
    -------
    dict
        ``{ "PTU0": ProjectConfig, "PTU1": ProjectConfig, ... }``
    """
    ptu_files = _discover_ptu_files(ptu_dir)
    variants: Dict[str, ProjectConfig] = {}

    for ptu_key, ptu_path in sorted(ptu_files.items()):
        params = _parse_ptu_file(ptu_path)
        overrides = {}
        if "NrClcFmyEveAsyn" in params:
            overrides["NrClcFmyEveAsyn"] = params["NrClcFmyEveAsyn"]
        if "NrClcFmyPost" in params:
            overrides["NrClcFmyPost"] = params["NrClcFmyPost"]
        if "NrCore" in params:
            overrides["NrCore"] = params["NrCore"]
        overrides["NrPtuProfiles"] = max(base_cfg.NrPtuProfiles, len(ptu_files))
        if overrides:
            overrides["name"] = f"{base_cfg.name}_{ptu_key}"
            variants[ptu_key] = _make_variant(base_cfg, **overrides)
            logger.debug(
                "  %s: EveAsyn=%s Post=%s",
                ptu_key,
                overrides.get("NrClcFmyEveAsyn", "—"),
                overrides.get("NrClcFmyPost", "—"),
            )
        else:
            # Fișier PTU fără parametri de calibrare relevanți — folosim baza
            variants[ptu_key] = _make_variant(base_cfg, name=f"{base_cfg.name}_{ptu_key}")

    logger.info("[%s] %d variante PTU extrase.", base_cfg.name, len(variants))
    return variants


# Bench reference data — stocate exclusiv în bench_store.db (populate din seeds.py).
# Nu mai există valori hardcodate aici; get_project_reference() citește direct din DB.

# Descrieri — nu sunt în fișierele C
_DESCRIPTIONS: Dict[str, str] = {
    "PROJ3": "PROJ3_0U0_P16_624  (Aurix TC3xx, STM@50MHz, CPU@300MHz)",
    "PROJ2": "PROJ2_0U0_OB6_024  (Aurix TC3xx, STM@50MHz, CPU@300MHz)",
    "PROJ1": "PROJ1  (Aurix TC3xx, STM@50MHz, CPU@300MHz)",
}


def get_project_reference(project_name: str) -> Optional[Dict[str, List[int]]]:
    """Returnează datele de referință bench pentru un proiect, sau None.

    Singura sursă de date este ``bench_store.db``, populat automat la prima
    pornire din ``seeds.py`` cu toate proiectele de referință validate.
    Dacă proiectul nu are date de bench înregistrate, returnează ``None``
    și RMSE nu va fi calculat.

    Parameters
    ----------
    project_name : str
        Numele proiectului (ex: ``"PROJ5_000U0"`` sau ``"PROJ3"``).

    Returns
    -------
    dict or None
        ``{ "scenario_1": [...], "scenario_2": [...], "scenario_3": [...] }``
        sau ``None`` dacă proiectul nu are date de bench.
    """
    try:
        from dem_simulator.bench_store import get_bench_data
        db_data = get_bench_data(project_name)
        if db_data:
            logger.debug(
                "[%s] Date de referință încărcate din bench_store.db.",
                project_name,
            )
            return db_data
    except Exception as exc:
        logger.debug("[%s] bench_store lookup eșuat: %s", project_name, exc)

    logger.debug(
        "[%s] Nu există date de referință bench → RMSE nu va fi calculat.",
        project_name,
    )
    return None

# Structura standard a directorului de proiect (relativ la root)
_CNF_C_REL  = os.path.join("_FS_{name}_0U0_NORMAL", "proc", "ARPROC", "out", "icsp_dem_cnf.c")
_PTU_DIR_REL = os.path.join("work", "bsw", "icsp", "dem", "dem", "pi", "main", "t")


def _discover_ptu_dir_from_project_root(project_root: str) -> Optional[str]:
    """Discover a PTU directory containing ``icsp_dem_cnf_ptu*.h`` files."""
    base_depth = project_root.count(os.sep)
    candidates: List[str] = []
    for dirpath, dirnames, filenames in os.walk(project_root):
        if dirpath.count(os.sep) - base_depth >= 10:
            dirnames.clear()
            continue
        if any(re.match(r"icsp_dem_cnf_ptu\w+\.h$", fn, re.IGNORECASE) for fn in filenames):
            candidates.append(dirpath)
    if not candidates:
        return None

    def _score(path: str) -> Tuple[int, int]:
        p = path.replace("/", "\\").lower()
        s = 0
        if "\\pi\\main\\t" in p:
            s += 10
        if "\\static\\" in p:
            s += 3
        if "\\work\\" in p:
            s += 5
        return s, -len(path)

    return sorted(candidates, key=_score, reverse=True)[0]


def discover_projects(
    base_dir: str,
    project_names: Optional[List[str]] = None,
) -> Dict[str, "ProjectDefinition"]:
    """Descoperă și încarcă automat proiectele din structura standard de directoare.

    Caută ``{base_dir}/{name}/_FS_{name}_0U0_NORMAL/proc/ARPROC/out/icsp_dem_cnf.c``
    și PTU headers în ``{base_dir}/{name}/work/bsw/icsp/dem/dem/pi/main/t``.

    Parameters
    ----------
    base_dir : str
        Directorul rădăcină care conține subdirectoarele proiectelor
        (ex. ``d:/casdev/td5/PR/OJ3/Projects``).
    project_names : list of str, optional
        Proiectele de căutat (implicit: toate subdirectoarele cu structura corectă).

    Returns
    -------
    dict
        ``{ "PROJ3": ProjectDefinition, "PROJ2": ProjectDefinition, ... }``
        Dict gol dacă nu se găsesc fișiere.
    """
    projects: Dict[str, "ProjectDefinition"] = {}

    # Dacă nu s-au specificat nume, scanează toate subdirectoarele
    if project_names is None:
        try:
            candidates = [
                d for d in os.listdir(base_dir)
                if os.path.isdir(os.path.join(base_dir, d))
                and not d.startswith(".")
                and not d.startswith("_")
                and d not in ("dem_simulator",)
            ]
        except OSError:
            return {}
    else:
        candidates = list(project_names)

    for name in sorted(candidates):
        project_root = os.path.join(base_dir, name)
        cnf_path = os.path.join(project_root, _CNF_C_REL.format(name=name))
        ptu_dir = os.path.join(project_root, _PTU_DIR_REL)
        if not os.path.isdir(ptu_dir):
            ptu_dir = _discover_ptu_dir_from_project_root(project_root)

        if (not os.path.isfile(cnf_path)) and (not ptu_dir):
            logger.debug("[%s] fișier C/ptu negăsite în %s", name, project_root)
            continue
        try:
            proj = load_project_from_c(
                cnf_c_path   = cnf_path,
                project_name = name.upper(),
                ptu_dir      = ptu_dir,
                description  = _DESCRIPTIONS.get(name.upper(), name),
                reference_wcs= get_project_reference(name.upper()),
            )
            projects[name.upper()] = proj
            logger.info("[%s] încărcat din %s", name.upper(), cnf_path)
        except SimulatorError as exc:
            logger.warning("[%s] Eroare la încărcare: %s", name, exc)

    return projects


def load_project_from_c(
    cnf_c_path: str,
    project_name: str,
    ptu_dir: Optional[str] = None,
    description: str = "",
    reference_wcs: Optional[Dict[str, List[int]]] = None,
    *,
    nr_client: Optional[int] = None,
    cpu_clock_mhz: float = 300.0,
) -> ProjectDefinition:
    """Funcție principală: parsează sursele C și returnează ``ProjectDefinition``.

    Parameters
    ----------
    cnf_c_path : str
        Calea către ``icsp_dem_cnf.c`` generat (NORMAL sau RELEASE build).
    project_name : str
        Numele scurt al proiectului (ex: ``"PROJ3"``).
    ptu_dir : str, optional
        Directorul cu fișierele ``icsp_dem_cnf_ptu*.h``.
        Dacă None, variantele PTU nu sunt extrase.
    description : str
        Descriere afișată în rapoarte.
    reference_wcs : dict, optional
        Date de referință bench pentru validare RMSE.
    nr_client : int
        Numărul de clienți DEM.
    cpu_clock_mhz : float
        Frecvența CPU în MHz.

    Returns
    -------
    ProjectDefinition
        Proiect complet cu configurație implicită și variante PTU.
    """
    resolved_cnf = cnf_c_path if os.path.isfile(cnf_c_path) else None
    if not resolved_cnf:
        resolved_cnf = _discover_cnf_c_from_hint(cnf_c_path)
    if not resolved_cnf and ptu_dir:
        resolved_cnf = _discover_cnf_c_from_hint(ptu_dir)

    if resolved_cnf and os.path.isfile(resolved_cnf):
        default_cfg = extract_project_config(
            resolved_cnf,
            project_name,
            nr_client=nr_client,
            cpu_clock_mhz=cpu_clock_mhz,
        )

        # Align default calibration with PTU0 when available (project baseline).
        if ptu_dir and os.path.isdir(ptu_dir):
            ptu_files = _discover_ptu_files(ptu_dir)
            ptu0 = ptu_files.get("PTU0")
            if ptu0:
                ptu0_vals = _parse_ptu_file(ptu0)
                default_cfg.NrClcFmyEveAsyn = ptu0_vals.get(
                    "NrClcFmyEveAsyn", default_cfg.NrClcFmyEveAsyn
                )
                default_cfg.NrClcFmyPost = ptu0_vals.get(
                    "NrClcFmyPost", default_cfg.NrClcFmyPost
                )
    else:
        logger.warning(
            "[%s] icsp_dem_cnf.c missing; building fallback config from PTU/main instrumentation.",
            project_name,
        )
        main_c_path = _discover_main_c_from_hint(ptu_dir or cnf_c_path)
        nr_first, nr_next = (20, 20)
        if main_c_path and os.path.isfile(main_c_path):
            nr_first, nr_next = extract_wcs_injection_counts(main_c_path)

        ptu0_asyn = 20
        ptu0_post = 10
        fallback_nr_core = 1
        fallback_ptu_profiles = 1
        if ptu_dir and os.path.isdir(ptu_dir):
            ptu_files = _discover_ptu_files(ptu_dir)
            fallback_ptu_profiles = max(1, len(ptu_files))
            ptu0 = ptu_files.get("PTU0")
            if ptu0:
                ptu0_vals = _parse_ptu_file(ptu0)
                ptu0_asyn = ptu0_vals.get("NrClcFmyEveAsyn", ptu0_asyn)
                ptu0_post = ptu0_vals.get("NrClcFmyPost", ptu0_post)
                fallback_nr_core = ptu0_vals.get("NrCore", fallback_nr_core)

        nr_fmy_fallback = max(20, nr_first, nr_next)
        default_cfg = ProjectConfig(
            name=project_name,
            NrFmy=nr_fmy_fallback,
            NrFifoBas=max(2 * nr_fmy_fallback, ptu0_asyn),
            NrFifoIntm=nr_fmy_fallback,
            NrFifoRsv=3,
            NrClcFmyEveAsyn=ptu0_asyn,
            NrClcFmyPost=ptu0_post,
            NrEve=max(nr_first + nr_next, nr_fmy_fallback),
            nr_inject_first=nr_first,
            nr_inject_next=nr_next,
            NrFrfDataTot=0,
            NrFrfPreData=0,
            NrBlockFrf=0,
            NrFrfPre=0,
            NrByteFrfFmy=0,
            NrLamp=0,
            NrFmyBufNvmWr=1,
            NrClient=nr_client,
            NrCore=fallback_nr_core,
            NrPtuProfiles=fallback_ptu_profiles,
            IsSharedCore=False,
            cpu_clock_mhz=cpu_clock_mhz,
            has_prio_obd_uds_swap=False,
            gpt_api=_detect_gpt_api(main_c_path),
            FrfBlocks=[],
        )

    variant_configs: Dict[str, ProjectConfig] = {}
    if ptu_dir and os.path.isdir(ptu_dir):
        variant_configs = extract_ptu_variants(default_cfg, ptu_dir)
        default_cfg.NrPtuProfiles = max(default_cfg.NrPtuProfiles, len(variant_configs))
    else:
        if ptu_dir:
            logger.warning(
                "Directorul PTU nu există: %s — variante PTU omise.", ptu_dir
            )

    return ProjectDefinition(
        name           = project_name,
        description    = description or f"{project_name} (extras automat)",
        default_config = default_cfg,
        variant_configs= variant_configs,
        reference_wcs  = reference_wcs or {},
    )