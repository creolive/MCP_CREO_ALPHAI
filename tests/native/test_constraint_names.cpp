// Offline regression for the shared assembly-constraint symbol mapping
// (native/constraint_names.h). Compiles without Toolkit headers: the header
// provides the stable published ProAsmcompConstrType integer values; SDK
// builds additionally pin them via static_assert in generic.cpp.
#include "constraint_names.h"

#include <cassert>
#include <cstdio>
#include <cstring>

int main() {
    // Published enum sequence used by the production static_assert pins.
    static_assert(PRO_ASM_UNDEF == -1, "enum drift");
    static_assert(PRO_ASM_MATE == 0, "enum drift");
    static_assert(PRO_ASM_MATE_OFF == 1, "enum drift");
    static_assert(PRO_ASM_ALIGN == 2, "enum drift");
    static_assert(PRO_ASM_ALIGN_OFF == 3, "enum drift");
    static_assert(PRO_ASM_INSERT == 4, "enum drift");
    static_assert(PRO_ASM_ORIENT == 5, "enum drift");
    static_assert(PRO_ASM_CSYS == 6, "enum drift");
    static_assert(PRO_ASM_DEF_PLACEMENT == 10, "enum drift");
    static_assert(PRO_ASM_FIX == 13, "enum drift");
    static_assert(PRO_ASM_AUTO == 14, "enum drift");

    struct {
        int code;
        const char *symbol;
    } known[] = {
        {PRO_ASM_MATE, "mate"},
        {PRO_ASM_MATE_OFF, "mate_offset"},
        {PRO_ASM_ALIGN, "align"},
        {PRO_ASM_ALIGN_OFF, "align_offset"},
        {PRO_ASM_INSERT, "insert"},
        {PRO_ASM_ORIENT, "orient"},
        {PRO_ASM_CSYS, "csys"},
        {PRO_ASM_TANGENT, "tangent"},
        {PRO_ASM_PNT_ON_SRF, "pnt_on_srf"},
        {PRO_ASM_EDGE_ON_SRF, "edge_on_srf"},
        {PRO_ASM_DEF_PLACEMENT, "default"},
        {PRO_ASM_FIX, "fix"},
        {PRO_ASM_AUTO, "auto"},
    };
    for (auto &entry : known) {
        const char *name = assembly_constraint_type_name(entry.code);
        assert(name != nullptr);
        assert(std::strcmp(name, entry.symbol) == 0);
    }
    // Unknown codes stay numeric for the caller and map to nullptr here so the
    // caller emits the explicit "unknown" symbol instead of guessing.
    assert(assembly_constraint_type_name(999) == nullptr);
    assert(assembly_constraint_type_name(-1) == nullptr);
    std::puts("constraint_names: all checks passed");
    return 0;
}
