// Native drawing database operations. All public positions and sizes use mm.
#include <ProDrawing.h>
#include <ProDrawingView.h>
#include <ProDtlnote.h>
#include <ProDtlattach.h>
#include <ProDwgtable.h>
#include <ProPDF.h>
#include <ProAnnotation.h>
#include <ProLayer.h>

static ProDrawing drawing() {
    return (ProDrawing)board;
}
static void drawing_display() {
    CK(ProMdlDisplay(board));
    CK(ProMdlWindowGet(board, &win));
    CK(ProWindowCurrentSet(win));
}
static void drawing_regenerate() {
    int count, current;
    CK(ProDrawingSheetsCount(drawing(), &count));
    CK(ProDrawingCurrentSheetGet(drawing(), &current));
    for (int sheet = 1; sheet <= count; sheet++) {
        CK(ProDrawingCurrentSheetSet(drawing(), sheet));
        CK(ProDwgSheetRegenerate(drawing(), sheet));
    }
    CK(ProDrawingCurrentSheetSet(drawing(), current));
}
static double drawing_sheet_transform(int sheet, ProMatrix tr) {
    ProName name;
    CK(ProDrawingSheetTrfGet(drawing(), sheet, name, tr));
    ProUnititem unit;
    CK(ProDrawingSheetUnitsGet(drawing(), sheet, &unit));
    if (!wcscmp(unit.name, L"mm"))
        return 1;
    if (!wcscmp(unit.name, L"inch"))
        return 25.4;
    throw std::runtime_error("Unsupported drawing sheet units: " + utf8(unit.name));
}
static void sheet_point(int sheet, const J &xy, ProPoint3d result, bool vector = false) {
    ProMatrix tr;
    double mm = drawing_sheet_transform(sheet, tr);
    // Creo drawing sheets use a uniform axis-aligned scale and translation.
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < 3; j++)
            if (i != j && fabs(tr[i][j]) > 1e-10)
                throw std::runtime_error("Unexpected drawing sheet transform");
    for (int i = 0; i < 3; i++) {
        if (fabs(tr[i][i]) < 1e-12)
            throw std::runtime_error("Singular drawing sheet transform");
        double value = i < 2 ? xy[i].get<double>() / mm : 0;
        result[i] = (value - (vector ? 0 : tr[3][i])) / tr[i][i];
    }
}
static J point_on_sheet(int sheet, const double *p) {
    ProMatrix tr;
    double mm = drawing_sheet_transform(sheet, tr);
    ProPoint3d converted;
    CK(ProPntTrfEval(const_cast<double *>(p), tr, converted));
    return J::array({converted[0] * mm, converted[1] * mm});
}
static int drawing_id(const J &target, const char *type) {
    if (target.is_number_integer())
        return target.get<int>();
    std::string label = target;
    if (!aliases.contains(label) || aliases[label].value("kind", "") != type)
        throw std::runtime_error("Unknown drawing " + std::string(type) + " label: " + label);
    return aliases[label].at("id");
}
static ProView drawing_view(const J &target) {
    ProView v;
    CK(ProDrawingViewInit(drawing(), drawing_id(target, "view"), &v));
    return v;
}
static ProDwgtable drawing_table(const J &target) {
    int id = drawing_id(target, "table");
    ProDwgtable *tables = nullptr;
    CK(ProDrawingTablesCollect(drawing(), &tables));
    int count;
    CK(ProArraySizeGet((ProArray)tables, &count));
    ProDwgtable result = {};
    bool found = false;
    for (int i = 0; i < count; i++)
        if (tables[i].id == id) {
            result = tables[i];
            found = true;
        }
    ProArrayFree((ProArray *)&tables);
    if (!found)
        throw std::runtime_error("Drawing table not found");
    return result;
}
static void remember_drawing(const J &op, const char *type, int id, J more = J::object()) {
    more.update({{"kind", type}, {"id", id}, {"op", op["op"]}});
    aliases[op["label"].get<std::string>()] = more;
}
static J note_lines(ProDtlnotedata data) {
    J result = J::array();
    ProDtlnoteline *lines = nullptr;
    CK(ProDtlnotedataLinesCollect(data, &lines));
    int count;
    CK(ProArraySizeGet((ProArray)lines, &count));
    for (int i = 0; i < count; i++) {
        ProDtlnotetext *texts = nullptr;
        CK(ProDtlnotelineTextsCollect(lines[i], &texts));
        int n;
        CK(ProArraySizeGet((ProArray)texts, &n));
        std::string line;
        for (int j = 0; j < n; j++) {
            ProLine value;
            CK(ProDtlnotetextStringGet(texts[j], value));
            line += utf8(value);
        }
        result.push_back(line);
        ProArrayFree((ProArray *)&texts);
    }
    ProArrayFree((ProArray *)&lines);
    return result;
}
static J drawing_inspection() {
    J state = {{"model_type", "drawing"}, {"units", "mm"},
               {"sheets", J::array()},    {"views", J::array()},
               {"notes", J::array()},     {"tables", J::array()},
               {"models", J::array()},    {"shown_dimensions", J::array()}};
    int count;
    CK(ProDrawingSheetsCount(drawing(), &count));
    for (int sheet = 1; sheet <= count; sheet++) {
        ProPlotPaperSize size;
        double w, h;
        CK(ProDrawingSheetSizeGet(drawing(), sheet, &size, &w, &h));
        ProMatrix tr;
        double mm = drawing_sheet_transform(sheet, tr);
        ProName name;
        CK(ProDrawingSheetNameGet(drawing(), sheet, name));
        state["sheets"].push_back(
            {{"sheet", sheet}, {"name", utf8(name)}, {"width_mm", w * mm}, {"height_mm", h * mm}});
        ProDtlnote *notes = nullptr;
        ProError e = ProDrawingDtlnotesCollect(drawing(), nullptr, sheet, &notes);
        if (e == PRO_TK_E_NOT_FOUND)
            continue;
        check(e, "CollectDrawingNotes");
        int n;
        CK(ProArraySizeGet((ProArray)notes, &n));
        for (int i = 0; i < n; i++) {
            ProDtlnotedata data;
            CK(ProDtlnoteDataGet(&notes[i], nullptr, PRODISPMODE_NUMERIC, &data));
            J note = {{"id", notes[i].id}, {"sheet", sheet}, {"lines", note_lines(data)}};
            ProDtlattach attach;
            CK(ProDtlnotedataAttachmentGet(data, &attach));
            ProDtlattachType type;
            ProView view;
            ProVector p;
            ProSelection ref;
            CK(ProDtlattachGet(attach, &type, &view, p, &ref));
            note["position_mm"] = point_on_sheet(sheet, p);
            ProDtlattachFree(attach);
            ProTextStyle style;
            if (!ProDtlnotedataTextStyleGet(data, &style)) {
                double height;
                if (!ProTextStyleHeightGet(style, &height))
                    note["text_height"] = height;
                ProTextStyleFree(&style);
            }
            ProDtlnotedataFree(data);
            state["notes"].push_back(note);
        }
        ProArrayFree((ProArray *)&notes);
    }
    ProView *views = nullptr;
    ProError e = ProDrawingViewsCollect(drawing(), &views);
    if (e != PRO_TK_E_NOT_FOUND) {
        check(e, "CollectDrawingViews");
        CK(ProArraySizeGet((ProArray)views, &count));
        for (int i = 0; i < count; i++) {
            ProView v = views[i];
            int id, sheet;
            CK(ProDrawingViewIdGet(drawing(), v, &id));
            CK(ProDrawingViewSheetGet(drawing(), v, &sheet));
            ProName name;
            CK(ProDrawingViewNameGet(drawing(), v, name));
            double scale;
            CK(ProDrawingViewScaleGet(drawing(), v, &scale));
            ProPoint3d box[2];
            CK(ProDrawingViewOutlineGet(drawing(), v, box));
            ProDrawingViewDisplay display;
            CK(ProDrawingViewDisplayGet(drawing(), v, &display));
            ProMatrix transform;
            CK(ProDrawingViewTransformGet(drawing(), v, PRO_B_FALSE, transform));
            J rows = J::array();
            for (auto &row : transform)
                rows.push_back(J::array({row[0], row[1], row[2], row[3]}));
            state["views"].push_back({{"id", id},
                                      {"name", utf8(name)},
                                      {"sheet", sheet},
                                      {"scale", scale},
                                      {"display", (int)display.style},
                                      {"transform", rows},
                                      {"outline_mm", J::array({point_on_sheet(sheet, box[0]),
                                                               point_on_sheet(sheet, box[1])})}});
        }
        ProArrayFree((ProArray *)&views);
    }
    ProDwgtable *tables = nullptr;
    e = ProDrawingTablesCollect(drawing(), &tables);
    if (e != PRO_TK_E_NOT_FOUND) {
        check(e, "CollectDrawingTables");
        CK(ProArraySizeGet((ProArray)tables, &count));
        for (int i = 0; i < count; i++) {
            int nr, nc;
            CK(ProDwgtableRowsCount(&tables[i], &nr));
            CK(ProDwgtableColumnsCount(&tables[i], &nc));
            J rows = J::array();
            for (int r = 1; r <= nr; r++) {
                J row = J::array();
                for (int c = 1; c <= nc; c++) {
                    ProWstring *lines = nullptr;
                    ProError code =
                        ProDwgtableCelltextGet(&tables[i], c, r, PRODWGTABLE_NORMAL, &lines);
                    std::string text;
                    if (code != PRO_TK_E_NOT_FOUND && code != PRO_TK_GENERAL_ERROR) {
                        check(code, "GetTableCell");
                        int n;
                        CK(ProArraySizeGet((ProArray)lines, &n));
                        for (int l = 0; l < n; l++) {
                            if (l)
                                text += '\n';
                            text += utf8(lines[l]);
                        }
                        ProWstringproarrayFree(lines);
                    }
                    row.push_back(text);
                }
                rows.push_back(row);
            }
            state["tables"].push_back({{"id", tables[i].id}, {"cells", rows}});
        }
        ProArrayFree((ProArray *)&tables);
    }
    ProSolid *solids = nullptr;
    e = ProDrawingSolidsCollect(drawing(), &solids);
    if (e != PRO_TK_E_NOT_FOUND) {
        check(e, "CollectDrawingModels");
        CK(ProArraySizeGet((ProArray)solids, &count));
        for (int i = 0; i < count; i++) {
            ProName name;
            CK(ProMdlNameGet((ProMdl)solids[i], name));
            ProMdl owner = board;
            board = (ProMdl)solids[i];
            J solid;
            try {
                solid = inspection();
            } catch (...) {
                board = owner;
                throw;
            }
            board = owner;
            state["models"].push_back({{"name", utf8(name)}, {"inspection", solid}});
        }
        ProArrayFree((ProArray *)&solids);
    }
    for (auto alias : aliases)
        if (alias.value("kind", "") == "dimension") {
            ProView view = drawing_view(alias["view_id"]);
            ProSolid solid;
            CK(ProDrawingViewSolidGet(drawing(), view, &solid));
            ProDimension dim;
            CK(ProModelitemInit((ProMdl)solid, alias["id"], PRO_DIMENSION, &dim));
            ProView actual;
            CK(ProDrawingDimensionViewGet(drawing(), &dim, &actual));
            int id;
            CK(ProDrawingViewIdGet(drawing(), actual, &id));
            double value;
            CK(ProDimensionValueGet(&dim, &value));
            state["shown_dimensions"].push_back(
                {{"id", dim.id}, {"view_id", id}, {"value", value}});
        }
    return state;
}
static bool drawing_equal(const J &a, const J &b) {
    if (a.is_number() && b.is_number())
        return fabs(a.get<double>() - b.get<double>()) <=
               1e-6 * std::max(1.0, std::max(fabs(a.get<double>()), fabs(b.get<double>())));
    if (a.type() != b.type() || a.size() != b.size())
        return false;
    if (a.is_object()) {
        for (auto it = a.begin(); it != a.end(); ++it)
            if (!b.contains(it.key()) || !drawing_equal(it.value(), b[it.key()]))
                return false;
        return true;
    }
    if (a.is_array()) {
        for (size_t i = 0; i < a.size(); i++)
            if (!drawing_equal(a[i], b[i]))
                return false;
        return true;
    }
    return a == b;
}
static void verify_drawing(const J &a, const J &b) {
    if (!drawing_equal(a, b))
        throw std::runtime_error(
            "Drawing contents changed after reload, or live drawing differs from saved baseline");
}
static ProError drawing_hide_datum(ProFeature *f, ProError status, ProAppData) {
    if (status)
        return PRO_TK_NO_ERROR;
    ProFeattype type;
    CK(ProFeatureTypeGet(f, &type));
    if (type == PRO_FEAT_CSYS || type == PRO_FEAT_DATUM || type == PRO_FEAT_DATUM_POINT ||
        type == PRO_FEAT_DATUM_AXIS) {
        ProError e = ProModelitemHide(f);
        if (e != PRO_TK_NO_CHANGE)
            check(e, "HideDrawingSnapshotDatum");
    }
    return PRO_TK_NO_ERROR;
}
static void drawing_model_add(const J &op) {
    J source = component_sources.at(op["source_model_id"].get<std::string>());
    ProPath file;
    path(file, wide(source["part_file"]));
    ProMdl original;
    CK(ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &original));
    ProMdl owner = board;
    board = original;
    try {
        verify_saved(source["inspection"], inspection());
    } catch (...) {
        board = owner;
        throw;
    }
    board = owner;
    ProMdlType type;
    CK(ProMdlTypeGet(original, &type));
    if (type != PRO_MDL_PART)
        throw std::runtime_error(
            "Drawing source snapshots currently require part or sheetmetal models");
    ProMdlName name;
    std::wstring token = std::filesystem::path(generic_job).filename().wstring();
    swprintf_s(name, L"d_%s_%u", token.substr(0, 16).c_str(), (unsigned)generated_identity_index());
    ProMdl copy;
    CK(ProMdlnameCopy(original, name, &copy));
    CK(ProSolidFeatVisit((ProSolid)copy, drawing_hide_datum, nullptr, nullptr));
    CK(ProDrawingSolidAdd(drawing(), (ProSolid)copy));
    aliases[op["label"].get<std::string>()] = {{"kind", "model"},
                                               {"name", utf8(name)},
                                               {"source_model_id", source["model_id"]},
                                               {"source_revision", source["revision"]},
                                               {"source_snapshot", true}};
}
static void drawing_style(ProView view, const std::string &style) {
    std::map<std::string, ProDisplayStyle> values = {
        {"wireframe", PRO_DISPSTYLE_WIREFRAME},
        {"hidden", PRO_DISPSTYLE_HIDDEN_LINE},
        {"no_hidden", PRO_DISPSTYLE_NO_HIDDEN},
        {"shaded", PRO_DISPSTYLE_SHADED},
        {"shaded_edges", PRO_DISPSTYLE_SHADED_WITH_EDGES}};
    ProDrawingViewDisplay display;
    CK(ProDrawingViewDisplayGet(drawing(), view, &display));
    display.style = values.at(style);
    display.tangent_edge_display = PRO_TANEDGE_NONE;
    CK(ProDrawingViewDisplaySet(drawing(), view, &display));
}
static ProDtlnotedata drawing_note_data(const J &op, int sheet) {
    ProDtlnotedata data;
    CK(ProDtlnotedataAlloc(board, &data));
    ProTextStyle style;
    CK(ProTextStyleAlloc(&style));
    CK(ProTextStyleHeightSet(style, op.value("text_height", 3.5)));
    CK(ProDtlnotedataTextStyleSet(data, style));
    ProTextStyleFree(&style);
    for (auto text : op["lines"]) {
        ProDtlnoteline line;
        ProDtlnotetext run;
        CK(ProDtlnotelineAlloc(&line));
        CK(ProDtlnotetextAlloc(&run));
        ProLine value;
        wcscpy_s(value, wide(text).c_str());
        CK(ProDtlnotetextStringSet(run, value));
        CK(ProDtlnotelineTextAdd(line, run));
        CK(ProDtlnotedataLineAdd(data, line));
        ProDtlnotetextFree(run);
        ProDtlnotelineFree(line);
    }
    ProPoint3d pos;
    sheet_point(sheet, op["position"], pos);
    ProDtlattach attach;
    CK(ProDtlattachAlloc(PRO_DTLATTACHTYPE_FREE, nullptr, pos, nullptr, &attach));
    CK(ProDtlnotedataAttachmentSet(data, attach));
    ProDtlattachFree(attach);
    CK(ProDtlnotedataDisplayedSet(data, PRO_B_TRUE));
    return data;
}
static void table_cell(ProDwgtable *table, int row, int column, const std::string &value) {
    int nr, nc;
    CK(ProDwgtableRowsCount(table, &nr));
    CK(ProDwgtableColumnsCount(table, &nc));
    if (row > nr || column > nc)
        throw std::runtime_error("Table cell outside table dimensions");
    std::wstring text = wide(value);
    ProWstring *lines = nullptr;
    CK(ProArrayAlloc(1, sizeof(ProWstring), 1, (ProArray *)&lines));
    lines[0] = const_cast<wchar_t *>(text.c_str());
    ProError e = ProDwgtableTextEnter(table, column, row, lines);
    ProArrayFree((ProArray *)&lines);
    check(e, "SetTableCell");
}
static void execute_drawing_operation_body(const J &op) {
    std::string kind = op["op"];
    staged_operation_result = J::object();
    has_staged_operation_result = false;
    log("PHASE=%s\n", kind.c_str());
    if (kind == "drawing_model")
        drawing_model_add(op);
    else if (kind == "drawing_sheet") {
        int sheet = op["sheet"];
        if (op["action"] == "add")
            CK(ProDrawingSheetCreate(drawing(), &sheet));
        CK(ProDrawingCurrentSheetSet(drawing(), sheet));
        CK(ProDrawingFormatSizeSet(drawing(), sheet, VARIABLE_SIZE_IN_MM_PLOT, op["width"],
                                   op["height"]));
        if (op.contains("name")) {
            ProName name;
            wcscpy_s(name, wide(op["name"]).c_str());
            CK(ProDrawingSheetNameSet(drawing(), sheet, name));
        }
        stage_operation_result({{"op", kind}, {"sheet", sheet}});
    } else if (kind == "drawing_view" || kind == "drawing_projection") {
        ProView view;
        int sheet = op.value("sheet", 1);
        ProPoint3d p;
        J extra = J::object();
        if (kind == "drawing_projection") {
            ProView parent = drawing_view(op["parent"]);
            CK(ProDrawingViewSheetGet(drawing(), parent, &sheet));
            sheet_point(sheet, op["position"], p);
            CK(ProDrawingProjectedviewCreate(drawing(), parent, PRO_B_FALSE, p, &view));
            extra["parent_id"] = drawing_id(op["parent"], "view");
        } else {
            std::string label = op["model"];
            if (!aliases.contains(label) || aliases[label].value("kind", "") != "model")
                throw std::runtime_error("Unknown drawing source model label");
            ProName name;
            wcscpy_s(name, wide(aliases[label]["name"]).c_str());
            ProMdl source;
            CK(ProMdlInit(name, PRO_MDL_PART, &source));
            sheet_point(sheet, op["position"], p);
            std::string orient = op["orientation"];
            V right = {1, 0, 0}, up = {0, 0, 1};
            if (orient == "back")
                right = {-1, 0, 0};
            else if (orient == "top")
                up = {0, 1, 0};
            else if (orient == "bottom")
                up = {0, -1, 0};
            else if (orient == "right")
                right = {0, 1, 0};
            else if (orient == "left")
                right = {0, -1, 0};
            else if (orient == "isometric") {
                right = {sqrt(.5), sqrt(.5), 0};
                up = {-sqrt(1.0 / 6), sqrt(1.0 / 6), sqrt(2.0 / 3)};
            }
            V normal = cross(right, up);
            ProMatrix matrix = {};
            for (int i = 0; i < 3; i++) {
                matrix[i][0] = right[i];
                matrix[i][1] = up[i];
                matrix[i][2] = normal[i];
            }
            matrix[3][3] = 1;
            CK(ProDrawingGeneralviewCreate(drawing(), (ProSolid)source, sheet, PRO_B_FALSE, p,
                                           op["scale"], matrix, &view));
            extra["source"] = label;
        }
        int id;
        CK(ProDrawingViewIdGet(drawing(), view, &id));
        ProName name;
        wcscpy_s(name, wide(op["label"]).c_str());
        CK(ProDrawingViewNameSet(drawing(), view, name));
        drawing_style(view, op["display"]);
        extra["sheet"] = sheet;
        remember_drawing(op, "view", id, extra);
    } else if (kind == "drawing_view_update") {
        ProView view = drawing_view(op["view"]);
        int sheet;
        CK(ProDrawingViewSheetGet(drawing(), view, &sheet));
        if (op.contains("scale"))
            CK(ProDrawingViewScaleSet(drawing(), view, op["scale"]));
        if (op.contains("move")) {
            ProVector move;
            sheet_point(sheet, op["move"], move, true);
            CK(ProDrawingViewMove(drawing(), view, move));
        }
        if (op.contains("display"))
            drawing_style(view, op["display"]);
    } else if (kind == "drawing_note") {
        int sheet = op["sheet"];
        CK(ProDrawingCurrentSheetSet(drawing(), sheet));
        ProDtlnotedata data = drawing_note_data(op, sheet);
        ProDtlnote note;
        CK(ProDtlnoteCreate(board, nullptr, data, &note));
        ProDtlnotedataFree(data);
        remember_drawing(op, "note", note.id, {{"sheet", sheet}});
    } else if (kind == "drawing_note_update") {
        int id = drawing_id(op["note"], "note");
        J state = drawing_inspection(), current;
        for (auto note : state["notes"])
            if (note["id"] == id)
                current = note;
        if (current.is_null())
            throw std::runtime_error("Drawing note not found");
        int sheet = current["sheet"];
        CK(ProDrawingCurrentSheetSet(drawing(), sheet));
        J spec = {{"lines", op.value("lines", current["lines"])},
                  {"position", op.value("position", current["position_mm"])},
                  {"text_height", op.value("text_height", current.value("text_height", 3.5))}};
        ProDtlnote note;
        CK(ProModelitemInit(board, id, PRO_NOTE, &note));
        ProDtlnotedata data = drawing_note_data(spec, sheet);
        CK(ProDtlnoteModify(&note, nullptr, data));
        ProDtlnotedataFree(data);
    } else if (kind == "drawing_table") {
        int sheet = op["sheet"];
        CK(ProDrawingCurrentSheetSet(drawing(), sheet));
        ProPoint3d p;
        sheet_point(sheet, op["position"], p);
        ProDwgtabledata data;
        CK(ProDwgtabledataAlloc(&data));
        CK(ProDwgtabledataOriginSet(data, p));
        CK(ProDwgtabledataSizetypeSet(data, PRODWGTABLESIZE_SCREEN));
        ProMatrix tr;
        double mm = drawing_sheet_transform(sheet, tr), scale = mm;
        std::vector<double> widths;
        for (auto w : op["columns"])
            widths.push_back(w.get<double>() / scale);
        std::vector<ProHorzJust> just(widths.size(), PROHORZJUST_LEFT);
        std::vector<double> heights(op["cells"].size(), op["row_height"].get<double>() / scale);
        CK(ProDwgtabledataColumnsSet(data, (int)widths.size(), widths.data(), just.data()));
        CK(ProDwgtabledataRowsSet(data, (int)heights.size(), heights.data()));
        ProDwgtable table;
        CK(ProDrawingTableCreate(drawing(), data, PRO_B_TRUE, &table));
        for (size_t c = 0; c < widths.size(); c++) {
            double actual;
            CK(ProDwgtableColumnSizeGet(&table, -1, (int)c, &actual));
            if (fabs(actual * mm * tr[0][0] - op["columns"][c].get<double>()) > 1e-6)
                throw std::runtime_error("Table column width differs from requested mm");
        }
        for (size_t r = 0; r < heights.size(); r++) {
            double actual;
            CK(ProDwgtableRowSizeGet(&table, -1, (int)r, &actual));
            if (fabs(actual * mm * tr[1][1] - op["row_height"].get<double>()) > 1e-6)
                throw std::runtime_error("Table row height differs from requested mm");
        }
        for (size_t r = 0; r < op["cells"].size(); r++)
            for (size_t c = 0; c < widths.size(); c++)
                table_cell(&table, (int)r + 1, (int)c + 1, op["cells"][r][c]);
        remember_drawing(op, "table", table.id, {{"sheet", sheet}});
    } else if (kind == "drawing_table_cell") {
        ProDwgtable table = drawing_table(op["table"]);
        table_cell(&table, op["row"], op["column"], op["text"]);
    } else if (kind == "drawing_dimension") {
        ProView view = drawing_view(op["view"]);
        int current_sheet;
        CK(ProDrawingViewSheetGet(drawing(), view, &current_sheet));
        CK(ProDrawingCurrentSheetSet(drawing(), current_sheet));
        ProSolid source;
        CK(ProDrawingViewSolidGet(drawing(), view, &source));
        ProDimension dim;
        CK(ProModelitemInit((ProMdl)source, op["dimension_id"], PRO_DIMENSION, &dim));
        {
            ProError shown = ProAnnotationShow(&dim, nullptr, view);
            if (shown != PRO_TK_NO_CHANGE)
                check(shown, "ShowDrawingDimension");
        }
        if (op.contains("position")) {
            int sheet;
            CK(ProDrawingViewSheetGet(drawing(), view, &sheet));
            ProPoint3d p;
            sheet_point(sheet, op["position"], p);
            CK(ProDrawingDimensionMove(drawing(), &dim, p));
        }
        remember_drawing(op, "dimension", dim.id, {{"view_id", drawing_id(op["view"], "view")}});
    } else if (kind == "drawing_delete") {
        std::string type = op["kind"];
        int id = drawing_id(op["target"], type.c_str());
        if (type == "view") {
            for (auto a : aliases)
                if (a.value("parent_id", -1) == id ||
                    (a.value("kind", "") == "dimension" && a.value("view_id", -1) == id))
                    throw std::runtime_error("Remove dependent projected views/dimensions first");
            ProView view = drawing_view(id);
            CK(ProDrawingViewDelete(drawing(), view, PRO_B_FALSE));
        } else if (type == "note") {
            ProDtlnote note;
            CK(ProModelitemInit(board, id, PRO_NOTE, &note));
            CK(ProDtlnoteDelete(&note, nullptr));
        } else if (type == "dimension") {
            ProView view = drawing_view(aliases[op["target"].get<std::string>()]["view_id"]);
            ProSolid solid;
            CK(ProDrawingViewSolidGet(drawing(), view, &solid));
            ProDimension dim;
            CK(ProModelitemInit((ProMdl)solid, id, PRO_DIMENSION, &dim));
            ProError e = ProDrawingAnnotationErase(drawing(), &dim);
            if (e != PRO_TK_NO_CHANGE)
                check(e, "EraseDrawingDimension");
        } else {
            ProDwgtable table = drawing_table(id);
            CK(ProDwgtableDelete(&table, PRO_B_TRUE));
        }
        for (auto it = aliases.begin(); it != aliases.end();)
            if (it.value().value("kind", "") == type &&
                (type == "dimension" ? it.key() == op["target"].get<std::string>()
                                     : it.value().value("id", -1) == id))
                it = aliases.erase(it);
            else
                ++it;
    } else if (kind == "export") {
        ProPath output;
        std::string format = op["format"];
        path(output,
             generic_job + L"\\output\\" + model_name + (format == "pdf" ? L".pdf" : L".jpg"));
        // One staged detail per input (T02); the JPEG capture adds its raw codes
        // to this record instead of appending another one.
        J export_detail = {{"op", kind}, {"file", utf8(output)}};
        if (format == "pdf") {
            ProPDFOptions opts;
            CK(ProPDFoptionsAlloc(&opts));
            ProError e = ProPDFExport(board, output, opts);
            ProPDFoptionsFree(opts);
            check(e, "ExportDrawingPDF");
        } else if (format == "jpeg") {
            // Shared capture (T07). A drawing owns its view, so the fixed model
            // view matrix is not applied; the target window, refit/repaint order
            // and raster call are the same ones the job preview uses.
            PreviewStepOutcome preview =
                capture_preview(board, generic_job + L"\\output\\" + model_name + L".jpg", false,
                                12, 8, PRORASTERTYPE_JPEG);
            J preview_json = preview_outcome_json(preview);
            log("PREVIEW=%s\n", preview_json.dump().c_str());
            export_detail["preview_code"] = preview.raster_code;
            export_detail["preview"] = preview_json;
            if (!preview_written(preview)) {
                stage_operation_result(export_detail);
                throw std::runtime_error("Drawing preview capture failed at " +
                                         preview.failed_step + " (code " +
                                         std::to_string(preview.failed_code) + ", raster code " +
                                         std::to_string(preview.raster_code) + ")");
            }
        } else
            throw std::runtime_error("Drawing export supports PDF/JPEG");
        stage_operation_result(export_detail);
    } else if (kind != "save" && kind != "regenerate")
        throw std::runtime_error("Unsupported drawing operation: " + kind);
    if (kind != "export")
        drawing_regenerate();
    // One terminal record per drawing input (T02); effect_status is finalized
    // by the job once the save or rollback outcome is known.
    J result = has_staged_operation_result ? staged_operation_result : J::object();
    result.update({{"op", kind},
                   {"index", operation_position},
                   {"label", op.value("label", "")},
                   {"succeeded", true},
                   {"execution_status", "succeeded"},
                   {"effect_status", "unknown"}});
    append_operation_result(std::move(result));
}
static void execute_drawing_operation(const J &op) {
    try {
        execute_drawing_operation_body(op);
    } catch (...) {
        std::string kind = op["op"];
        J failure = has_staged_operation_result ? staged_operation_result : J::object();
        failure.update({{"op", kind},
                        {"index", operation_position},
                        {"label", op.value("label", "")},
                        {"succeeded", false},
                        {"execution_status", "failed"},
                        {"effect_status", "unknown"}});
        append_operation_result(std::move(failure));
        throw;
    }
}
static std::wstring latest_drawing_file() {
    std::filesystem::path newest;
    int best = -1;
    std::wstring prefix = model_name + L".drw.";
    for (auto entry : std::filesystem::directory_iterator(folder)) {
        std::wstring name = entry.path().filename().wstring();
        if (name.rfind(prefix, 0))
            continue;
        try {
            int v = std::stoi(name.substr(prefix.size()));
            if (v > best) {
                best = v;
                newest = entry.path();
            }
        } catch (...) {
        }
    }
    if (newest.empty())
        throw std::runtime_error("Saved drawing file not found");
    return newest.wstring();
}
static int run_drawing(const std::wstring &job) {
    generic_job = job;
    J report = {{"success", false},
                {"saved_file_reloaded_and_verified", false},
                {"rollback_succeeded", false}},
      request;
    ProProcessHandle process = {};
    bool connected = false, mutated = false;
    std::wstring checkpoint;
    board_log = _wfsopen((job + L"\\native.log").c_str(), L"w", _SH_DENYNO);
    if (!board_log)
        return 3;
    try {
        std::ifstream input(job + L"\\request.json");
        input >> request;
        J model = request["model"];
        // Split registry records pass controlled references instead of inline
        // payloads; legacy requests keep the inline dicts (BUG-077).
        aliases = model.contains("aliases_ref") ? read_inspection_ref(model.at("aliases_ref"))
                                                : model["aliases"];
        component_sources = request.value("components", J::object());
        for (auto item = component_sources.begin(); item != component_sources.end(); ++item) {
            if (item.value().contains("aliases_ref"))
                item.value()["aliases"] = read_inspection_ref(item.value().at("aliases_ref"));
            if (item.value().contains("inspection_ref"))
                item.value()["inspection"] = read_inspection_ref(item.value().at("inspection_ref"));
        }
        model_name = wide(model["model_name"]);
        folder = wide(model["output_directory"]);
        if (!model["part_file"].is_null())
            checkpoint = wide(model["part_file"]);
        CK(connect_creo(&process));
        connected = true;
        ProName name;
        wcscpy_s(name, model_name.c_str());
        ProError found = ProMdlInit(name, PRO_MDL_DRAWING, &board);
        if (request["new"].get<bool>()) {
            if (found == PRO_TK_NO_ERROR)
                throw std::runtime_error("Drawing name already exists in the session");
            if (found != PRO_TK_E_NOT_FOUND)
                check(found, "FindDrawingName");
            ProPath file;
            path(file, wide(request["template_file"]));
            ProMdl templ;
            CK(ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &templ));
            ProMdlName copy_name;
            wcscpy_s(copy_name, model_name.c_str());
            CK(ProMdlnameCopy(templ, copy_name, &board));
            mutated = true;
            // Template drawings contain graphical view placeholders. Start on a clean
            // sheet so those symbols cannot leak into the user's views or PDF.
            drawing_display();
            int original_count, blank;
            CK(ProDrawingSheetsCount(drawing(), &original_count));
            CK(ProDrawingSheetCreate(drawing(), &blank));
            CK(ProDrawingCurrentSheetSet(drawing(), blank));
            for (int i = 0; i < original_count; i++)
                CK(ProDrawingSheetDelete(drawing(), 1));
            CK(ProDrawingCurrentSheetSet(drawing(), 1));
        } else {
            if (found == PRO_TK_E_NOT_FOUND) {
                ProPath file;
                path(file, checkpoint);
                CK(ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &board));
            } else
                check(found, "FindDrawing");
            ProPath origin;
            CK(ProMdlOriginGet(board, origin));
            std::wstring prefix = folder + L"\\";
            if (_wcsnicmp(origin, prefix.c_str(), prefix.size()))
                throw std::runtime_error("Drawing origin does not match owned model directory");
        }
        drawing_display();
        if (!request["new"].get<bool>() && !request.value("readonly", false))
            verify_drawing(model.contains("inspection_ref")
                               ? read_inspection_ref(model.at("inspection_ref"))
                               : model["inspection"],
                           drawing_inspection());
        int drawing_operation_index = -1;
        for (auto op : request["operations"]) {
            operation_position = ++drawing_operation_index;
            if (!request.value("readonly", false))
                mutated = true;
            execute_drawing_operation(op);
        }
        drawing_regenerate();
        J state = drawing_inspection();
        std::wstring saved = checkpoint;
        if (!request.value("readonly", false)) {
            ProPath destination;
            path(destination, folder);
            CK(ProMdlnameBackup(board, destination));
            saved = latest_drawing_file();
            J before = state;
            CK(ProMdlErase(board));
            board = nullptr;
            ProPath file;
            path(file, saved);
            CK(ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &board));
            drawing_display();
            drawing_regenerate();
            state = drawing_inspection();
            verify_drawing(before, state);
            report["saved_file_reloaded_and_verified"] = true;
        }
        finalize_operation_results(request, true, false, request.value("readonly", false));
        report.update({{"success", true},
                       {"toolkit_code", 0},
                       {"inspection", state},
                       {"aliases", aliases},
                       {"part_file", utf8(saved)},
                       {"operations", operation_results}});
    } catch (ProError error) {
        report["toolkit_code"] = error;
        report["message"] = "Toolkit drawing operation failed; inspect native.log";
    } catch (std::exception &error) {
        report["toolkit_code"] = PRO_TK_GENERAL_ERROR;
        report["message"] = error.what();
    }
    if (!report["success"].get<bool>() && connected && mutated && !checkpoint.empty()) {
        try {
            if (board)
                CK(ProMdlErase(board));
            board = nullptr;
            ProPath file;
            path(file, checkpoint);
            CK(ProMdlFiletypeLoad(file, PRO_MDLFILE_UNUSED, PRO_B_FALSE, &board));
            const J &rollback_model = request["model"];
            aliases = rollback_model.contains("aliases_ref")
                          ? read_inspection_ref(rollback_model.at("aliases_ref"))
                          : rollback_model["aliases"];
            drawing_display();
            drawing_regenerate();
            verify_drawing(rollback_model.contains("inspection_ref")
                               ? read_inspection_ref(rollback_model.at("inspection_ref"))
                               : rollback_model["inspection"],
                           drawing_inspection());
            report["rollback_succeeded"] = true;
        } catch (...) {
            report["rollback_message"] = "Drawing checkpoint could not be restored and verified";
        }
    }
    if (!report["success"].get<bool>()) {
        finalize_operation_results(request, false, report.value("rollback_succeeded", false),
                                   request.is_object() && request.value("readonly", false));
        report["operations"] = operation_results;
    }
    log("PHASE=disconnect\n");
    int delivered = deliver_native_result(job, report, connected, [&]() {
        int code = ProEngineerDisconnect(&process, 15);
        log("DISCONNECT=%d\n", code);
        return code;
    });
    log("PHASE=result_delivery_complete\n");
    fclose(board_log);
    board_log = nullptr;
    return delivered;
}
