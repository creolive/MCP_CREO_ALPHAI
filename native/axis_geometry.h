// BUG-065: read actual datum-axis geometry; never infer it from constraints.
#pragma once
#include <ProGeomitemdata.h>
#include <ProCurvedata.h>
#include <array>
#include <cmath>
#include <optional>

struct AxisGeometry {
    std::array<double, 3> origin = {}, direction = {};
    bool known = false;
    ProError data_code = PRO_TK_NO_ERROR;
    std::optional<ProError> line_code, free_code;
};

inline AxisGeometry inspect_axis_geometry(ProGeomitem *item) {
    AxisGeometry result;
    ProGeomitemdata *data = nullptr;
    result.data_code = ProGeomitemdataGet(item, &data);
    if (!result.data_code && data && data->obj_type == PRO_AXIS && data->data.p_curve_data) {
        Pro3dPnt start = {}, end = {};
        result.line_code = ProLinedataGet(data->data.p_curve_data, start, end);
        if (!*result.line_code) {
            double length = 0.0;
            bool finite = true;
            for (int i = 0; i < 3; ++i) {
                result.origin[i] = start[i];
                result.direction[i] = end[i] - start[i];
                finite = finite && std::isfinite(start[i]) && std::isfinite(end[i]);
                length = std::hypot(length, result.direction[i]);
            }
            result.known = finite && std::isfinite(length) && length > 1e-12;
            if (result.known)
                for (double &value : result.direction)
                    value /= length;
        }
    }
    // Some failing SDK queries may still allocate. Always release that allocation.
    if (data)
        result.free_code = ProGeomitemdataFree(&data);
    return result;
}
