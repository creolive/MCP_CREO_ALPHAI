"""Emit public SDK enum names and function capability macros from the local SDK."""

import json
import re
from pathlib import Path

HEADERS = [
    "ProElemId.h",
    "ProFeatType.h",
    "ProExtrude.h",
    "ProRevolve.h",
    "ProDtmCrv.h",
    "ProDtmPln.h",
    "ProDtmAxis.h",
    "ProRound.h",
    "ProChamfer.h",
    "ProHole.h",
    "ProShell.h",
    "ProPattern.h",
    "ProSecdimType.h",
    "ProSecconstr.h",
    "ProMirror.h",
    "ProSweep.h",
    "ProBodyOpts.h",
    "ProFeature.h",
    "ProFeatForm.h",
    "ProDirection.h",
    "ProDraft.h",
    "ProSmtFlangeWall.h",
    "ProSmtFlatWall.h",
    "ProRegularUnbend.h",
    "ProSmtBendBack.h",
    "ProAsmcomp.h",
    "ProSmtDrvSurf.h",
    # Q07 G5 probe symbols: boundary blend form, trim sides/types and section
    # selection enums are declared outside the original feature-header list.
    "Probbl.h",
    "ProTrim.h",
    "ProStdSection.h",
    "ProMerge.h",
]

PROBES = ("PRO_E_HLE_ADD_PARAMETERS", "PRO_HOLE_NO_PARAMETERS_FLAG")

# BUG-090: some SDK generations (Creo 10) do not declare every function this
# build calls. A callable declaration (the name followed by "(" once C comments
# are removed) emits a MECHDOG_HAS_<name> capability macro so native code can
# keep missing APIs out of the compile unit; comments and same-name text without
# a call parenthesis do not declare a function.
FUNCTION_PROBES = (
    "ProSmtPartThicknessGet",
    "ProSmtPartThicknessValueGet",
    # FEAT-058: the wall's own body gauge and its part link are the independent
    # read-back path; older SDK generations that lack them must keep compiling.
    "ProSmtBodyThicknessValueGet",
    "ProSmtBodyIsLinkedToPart",
)


def available_headers(inc_dir: Path) -> tuple[list[str], list[str]]:
    """Split ``HEADERS`` into the ones this SDK generation ships and the rest.

    SDK generations differ: Creo 10 has no ``Probbl.h``, so a listed header can
    be absent. Returning both halves keeps the enumeration scan and the emitted
    ``#include`` block sourced from the same set (BUG-107).
    """
    present: list[str] = []
    missing: list[str] = []
    for header in HEADERS:
        (present if (inc_dir / header).is_file() else missing).append(header)
    return present, missing


def generate(root: Path, *, inc_dir: Path | None = None) -> int:
    if inc_dir is None:
        config = json.loads((root / "config.json").read_text(encoding="utf-8-sig"))
        inc_dir = Path(config["creo_root"]) / "Common Files/protoolkit/includes"
    present, missing = available_headers(inc_dir)
    # BUG-107: an absent header contributes neither enums nor an #include, the
    # same "probe what exists" rule the function probes already follow. The line
    # lands in build/generate_constants.log through the build's stdout capture.
    for header in missing:
        print(f"MISSING_SDK_HEADER={header}")
    names = set()
    for header in present:
        source = (inc_dir / header).read_text(encoding="utf-8", errors="replace")
        source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
        names.update(
            re.findall(
                r"^\s*#define\s+(PRO_(?:E|FEAT)_[A-Z0-9_]+)\s+(?:\d+|\([^\n]+\))", source, re.M
            )
        )
        for block in re.findall(r"\benum\s*\w*\s*\{([^}]+)\}", source, re.S):
            names.update(re.findall(r"(?:^|,)\s*(PRO_[A-Z0-9_]+)\s*(?:=|,|$)", block, re.M))
    functions = set()
    for path in sorted(inc_dir.glob("*.h")):
        source = path.read_text(encoding="utf-8", errors="replace")
        source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
        for name in FUNCTION_PROBES:
            if re.search(r"\b" + re.escape(name) + r"\s*\(", source):
                functions.add(name)
    probes = sorted(names.intersection(PROBES) | functions)
    lines = [
        "// Enum names generated from the locally installed Creo Toolkit SDK.",
        *["#include <" + h + ">" for h in present],
        *["#define MECHDOG_HAS_" + n + " 1" for n in probes],
        "static const std::map<std::string,int> tk_constants = {",
    ]
    lines += ['{"' + n + '",static_cast<int>(' + n + ")}," for n in sorted(names)]
    lines += ["};", ""]
    out = root / "native/constants.inc"
    value = "\n".join(lines)
    data = value.encode("utf-8")
    if not out.exists() or out.read_bytes() != data:
        out.write_bytes(data)
    return len(names)


if __name__ == "__main__":
    print("SDK constant names:", generate(Path(__file__).resolve().parents[1]))
