// FEAT-057: model mass units for real mass properties.
//
// The gram factor is only returned for unit names whose factor is proven here.
// An unknown unit name yields nothing so the caller reports the native mass
// with its unit name instead of converting by guesswork from the unit system.
#pragma once
#include <ProMdlUnits.h>
#include <cwchar>
#include <optional>

struct MassUnitReading {
    ProUnititem unit = {};
    ProError code = PRO_TK_NO_ERROR;
};

inline MassUnitReading inspect_mass_unit(ProMdl model) {
    MassUnitReading result;
    ProUnitsystem system = {};
    result.code = ProMdlPrincipalunitsystemGet(model, &system);
    if (result.code == PRO_TK_NO_ERROR)
        result.code = ProUnitsystemUnitGet(&system, PRO_UNITTYPE_MASS, &result.unit);
    return result;
}

inline std::optional<double> grams_per_mass_unit(const wchar_t *name) {
    if (!name)
        return std::nullopt;
    if (!std::wcscmp(name, L"g"))
        return 1.0;
    if (!std::wcscmp(name, L"kg"))
        return 1000.0;
    if (!std::wcscmp(name, L"tonne") || !std::wcscmp(name, L"t"))
        return 1.0e6;
    return std::nullopt;
}
