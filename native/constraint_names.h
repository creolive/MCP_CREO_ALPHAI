// Shared ProAsmcompConstrType symbol names for assembly constraint snapshots.
//
// One mapping serves both producers so a constraint type always carries the
// same readable symbol: the FEAT-045 resident session-assembly walk
// (generic.cpp constraint_json) and the managed-assembly component list
// (advanced.cpp inspect_constraints, surfaced by creo_list_components).
//
// Callers keep the numeric code from the SDK query; an unrecognized code maps
// to nullptr and callers emit the explicit symbol "unknown" next to it. The
// readable names are the existing FEAT-045 session-assembly vocabulary; the
// numeric codes are the published ProAsmcompConstrType values. When Toolkit
// headers are absent (offline regression harness) the stable published
// integer values are provided; SDK builds pin them with static_assert so a
// future enum drift cannot change production meaning silently.
#pragma once

#if !defined(PROASMCOMP_H)
#define CREO_CONSTRAINT_CODES_FALLBACK 1
enum {
    PRO_ASM_UNDEF = -1,
    PRO_ASM_MATE = 0,
    PRO_ASM_MATE_OFF,
    PRO_ASM_ALIGN,
    PRO_ASM_ALIGN_OFF,
    PRO_ASM_INSERT,
    PRO_ASM_ORIENT,
    PRO_ASM_CSYS,
    PRO_ASM_TANGENT,
    PRO_ASM_PNT_ON_SRF,
    PRO_ASM_EDGE_ON_SRF,
    PRO_ASM_DEF_PLACEMENT,
    PRO_ASM_SUBSTITUTE,
    PRO_ASM_PNT_ON_LINE,
    PRO_ASM_FIX,
    PRO_ASM_AUTO,
    PRO_ASM_ALIGN_ANG_OFF,
    PRO_ASM_MATE_ANG_OFF,
    PRO_ASM_CSYS_PNT,
    PRO_ASM_LINE_NORMAL,
    PRO_ASM_LINE_COPLANAR,
    PRO_ASM_LINE_PARL,
    PRO_ASM_LINE_DIST,
    PRO_ASM_PNT_DIST,
    PRO_ASM_INSERT_NORM,
    PRO_ASM_INSERT_PARL,
    PRO_ASM_PNT_ON_LINE_DIST,
    PRO_ASM_PNT_ON_SRF_DIST,
    PRO_ASM_EDGE_ON_SRF_DIST,
    PRO_ASM_EDGE_ON_SRF_ANG,
    PRO_ASM_EDGE_ON_SRF_NORMAL,
    PRO_ASM_ALIGN_NODEP_ANGLE,
    PRO_ASM_MATE_NODEP_ANGLE,
    PRO_ASM_LINE_ANGLE,
    PRO_ASM_EDGE_ON_SRF_PARL,
    PRO_ASM_SRF_NORMAL,
    PRO_ASM_EXPLICIT,
    PRO_ASM_TANGENT_ALIGN
};
#endif

// Readable symbol for a ProAsmcompConstrType code, or nullptr when unknown.
inline const char *assembly_constraint_type_name(int type) {
    switch (type) {
    case PRO_ASM_MATE:
        return "mate";
    case PRO_ASM_MATE_OFF:
        return "mate_offset";
    case PRO_ASM_ALIGN:
        return "align";
    case PRO_ASM_ALIGN_OFF:
        return "align_offset";
    case PRO_ASM_INSERT:
        return "insert";
    case PRO_ASM_ORIENT:
        return "orient";
    case PRO_ASM_CSYS:
        return "csys";
    case PRO_ASM_TANGENT:
        return "tangent";
    case PRO_ASM_PNT_ON_SRF:
        return "pnt_on_srf";
    case PRO_ASM_EDGE_ON_SRF:
        return "edge_on_srf";
    case PRO_ASM_DEF_PLACEMENT:
        return "default";
    case PRO_ASM_FIX:
        return "fix";
    case PRO_ASM_AUTO:
        return "auto";
    default:
        return nullptr;
    }
}
