// Real SDK declarations, substituted geometry/unit reads. Never connects Creo.
#include "axis_geometry.h"
#include "assembly_units.h"
#include <cassert>
#include <cstdio>
#include <limits>

static ProError data_code = PRO_TK_NO_ERROR, line_code = PRO_TK_NO_ERROR;
static ProError units_code = PRO_TK_NO_ERROR, mm_code = PRO_TK_NO_ERROR;
static ProError conversion_code = PRO_TK_NO_ERROR;
static ProCurvedata curve = {};
static ProGeomitemdata geometry = {PRO_AXIS};
static bool allocate = true;
static double finish[3] = {7, -4, 9}, unit_scale = 1;
static const wchar_t *unit_name = L"mm";
static int frees = 0;

ProError ProGeomitemdataGet(ProGeomitem *, ProGeomitemdata **out) {
    geometry.data.p_curve_data = &curve;
    *out = allocate ? &geometry : nullptr;
    return data_code;
}
ProError ProGeomitemdataFree(ProGeomitemdata **out) {
    ++frees;
    *out = nullptr;
    return PRO_TK_NO_ERROR;
}
ProError ProLinedataGet(ProCurvedata *, Pro3dPnt start, Pro3dPnt end) {
    start[0] = 7;
    start[1] = -4;
    start[2] = 3;
    for (int i = 0; i < 3; ++i)
        end[i] = finish[i];
    return line_code;
}
ProError ProMdlPrincipalunitsystemGet(ProMdl, ProUnitsystem *) {
    return units_code;
}
ProError ProUnitsystemUnitGet(ProUnitsystem *, ProUnitType, ProUnititem *unit) {
    wcscpy_s(unit->name, unit_name);
    return PRO_TK_NO_ERROR;
}
ProError ProUnitInit(ProMdl, wchar_t *, ProUnititem *) {
    return mm_code;
}
ProError ProUnitConversionCalculate(ProUnititem *, ProUnititem *, ProUnitConversion *out) {
    out->scale = unit_scale;
    out->offset = 0;
    return conversion_code;
}
int main() {
    ProGeomitem item = {};
    auto axis = inspect_axis_geometry(&item);
    assert(axis.known && axis.origin[0] == 7 && axis.direction[2] == 1 && frees == 1);
    finish[2] = -3;
    assert(inspect_axis_geometry(&item).direction[2] == -1);
    finish[2] = 3;
    assert(!inspect_axis_geometry(&item).known); // zero length
    finish[2] = std::numeric_limits<double>::infinity();
    assert(!inspect_axis_geometry(&item).known);
    line_code = PRO_TK_BAD_INPUTS;
    assert(!inspect_axis_geometry(&item).known);
    data_code = PRO_TK_E_NOT_FOUND;
    axis = inspect_axis_geometry(&item);
    assert(!axis.known && !axis.line_code && axis.free_code && frees == 6);
    allocate = false;
    axis = inspect_axis_geometry(&item);
    assert(!axis.line_code && !axis.free_code && frees == 6);
    auto units = inspect_length_units(nullptr);
    assert(length_scale_to_mm(nullptr, units).scale == 1);
    unit_name = L"";
    auto unknown = length_scale_to_mm(nullptr, inspect_length_units(nullptr));
    assert(!unknown.known && !unknown.mm_unit_queried && !unknown.conversion_queried);
    unit_name = L"in";
    unit_scale = 25.4;
    units = inspect_length_units(nullptr);
    auto scale = length_scale_to_mm(nullptr, units);
    assert(scale.known && scale.scale == 25.4 && !units.volume_mm3(1));
    units_code = PRO_TK_BAD_INPUTS;
    scale = length_scale_to_mm(nullptr, inspect_length_units(nullptr));
    assert(!scale.known && !scale.mm_unit_queried && !scale.conversion_queried);
    units_code = PRO_TK_NO_ERROR;
    mm_code = PRO_TK_E_NOT_FOUND;
    scale = length_scale_to_mm(nullptr, inspect_length_units(nullptr));
    assert(!scale.known && scale.mm_unit_queried && !scale.conversion_queried);
    mm_code = PRO_TK_NO_ERROR;
    conversion_code = PRO_TK_GENERAL_ERROR;
    scale = length_scale_to_mm(nullptr, inspect_length_units(nullptr));
    assert(!scale.known && scale.conversion_queried);
    std::puts("AXIS_GEOMETRY_OK cases=13; substituted SDK calls; no Toolkit connection");
}
