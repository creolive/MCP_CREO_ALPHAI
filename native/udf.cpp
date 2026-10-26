// Native UDF library placement; never opens the interactive placement menu.
#include <ProUdf.h>
#include <ProGroup.h>

struct UdfData {
    ProUdfdata value = nullptr;
    explicit UdfData(const J &op) {
        CK(ProUdfdataAlloc(&value));
        try {
            ProPath file;
            path(file, wide(op["file_path"]));
            CK(ProUdfdataPathSet(value, file));
            if (op.contains("instance")) {
                ProName name;
                wcscpy_s(name, wide(op["instance"]).c_str());
                CK(ProUdfdataInstancenameSet(value, name));
            }
        } catch (...) {
            ProUdfdataFree(value);
            throw;
        }
    }
    ~UdfData() {
        if (value)
            ProUdfdataFree(value);
    }
};
static J udf_metadata(ProUdfdata data) {
    J info = {{"references", J::array()}, {"dimensions", J::array()}};
    ProUdfRequiredRef *refs = nullptr;
    ProError e = ProUdfdataRequiredreferencesGet(data, &refs);
    if (e != PRO_TK_E_NOT_FOUND) {
        check(e, "UdfRequiredReferences");
        int n;
        CK(ProArraySizeGet((ProArray)refs, &n));
        try {
            for (int i = 0; i < n; i++) {
                ProLine prompt;
                ProType type;
                CK(ProUdfrequiredrefPromptGet(refs[i], prompt));
                CK(ProUdfrequiredrefTypeGet(refs[i], &type));
                info["references"].push_back({{"prompt", utf8(prompt)}, {"type", (int)type}});
            }
        } catch (...) {
            ProUdfrequiredrefProarrayFree(refs);
            throw;
        }
        ProUdfrequiredrefProarrayFree(refs);
    }
    ProUdfvardim *dims = nullptr;
    e = ProUdfdataVardimsGet(data, &dims);
    if (e != PRO_TK_E_NOT_FOUND) {
        check(e, "UdfVariableDimensions");
        int n;
        CK(ProArraySizeGet((ProArray)dims, &n));
        try {
            for (int i = 0; i < n; i++) {
                ProName name;
                ProLine prompt;
                ProUdfVardimType type;
                double value;
                CK(ProUdfvardimNameGet(dims[i], name));
                CK(ProUdfvardimPromptGet(dims[i], prompt));
                CK(ProUdfvardimDefaultvalueGet(dims[i], &type, &value));
                info["dimensions"].push_back({{"name", utf8(name)},
                                              {"prompt", utf8(prompt)},
                                              {"type", (int)type},
                                              {"default_value", value}});
            }
        } catch (...) {
            ProUdfvardimProarrayFree(dims);
            throw;
        }
        ProUdfvardimProarrayFree(dims);
    }
    return info;
}
static void generic_udf(const J &op) {
    UdfData data(op);
    J metadata = udf_metadata(data.value);
    if (op["op"] == "udf_inspect") {
        stage_operation_result({{"op", "udf_inspect"}, {"metadata", metadata}});
        return;
    }
    const J &supplied = op["references"];
    std::set<std::string> prompts;
    for (auto ref : metadata["references"]) {
        std::string prompt = ref["prompt"];
        if (!prompts.insert(prompt).second)
            throw std::runtime_error("Duplicate UDF reference prompts are not supported");
        if (!supplied.contains(prompt))
            throw std::runtime_error("Missing UDF reference: " + prompt);
    }
    if (prompts.size() != supplied.size())
        throw std::runtime_error("Unexpected UDF reference prompt");
    for (auto r : metadata["references"]) {
        std::string prompt = r["prompt"];
        ProSelection selection = resolve(supplied[prompt]);
        ProModelitem item;
        ProError e = ProSelectionModelitemGet(selection, &item);
        if (e || item.type != r["type"].get<int>()) {
            ProSelectionFree(&selection);
            throw std::runtime_error("UDF reference type mismatch: " + prompt);
        }
        ProLine key;
        wcscpy_s(key, wide(prompt).c_str());
        ProUdfreference ref = nullptr;
        e = ProUdfreferenceAlloc(key, selection, PRO_B_FALSE, &ref);
        ProSelectionFree(&selection);
        check(e, "UdfReferenceAlloc");
        e = ProUdfdataReferenceAdd(data.value, ref);
        ProUdfreferenceFree(ref);
        check(e, "UdfReferenceAdd");
    }
    const J &values = op["dimensions"];
    std::set<std::string> names;
    for (auto d : metadata["dimensions"])
        names.insert(d["name"]);
    for (auto it = values.begin(); it != values.end(); ++it)
        if (!names.count(it.key()))
            throw std::runtime_error("Unknown UDF variable dimension name: " + it.key());
    for (auto d : metadata["dimensions"]) {
        std::string key = d["name"];
        ProName name;
        wcscpy_s(name, wide(key).c_str());
        double value = values.value(key, d["default_value"].get<double>());
        ProUdfvardim dim = nullptr;
        CK(ProUdfvardimAlloc(name, value, (ProUdfVardimType)d["type"].get<int>(), &dim));
        ProError e = ProUdfdataUdfvardimAdd(data.value, dim);
        ProUdfvardimFree(dim);
        check(e, "UdfVariableDimensionAdd");
    }
    CK(ProUdfdataDependencySet(data.value, PROUDFDEPENDENCY_INDEPENDENT));
    CK(ProUdfdataScaleSet(data.value, PROUDFSCALETYPE_SAME_DIMS, 1.0));
    ProUdfCreateOption options[] = {PROUDFOPT_NO_REDEFINE, PROUDFOPT_FIX_MODEL_UI_OFF};
    ProGroup group;
    CK(ProUdfCreate((ProSolid)board, data.value, nullptr, options, 2, &group));
    ProFeature *members = nullptr;
    CK(ProGroupFeaturesCollect(&group, &members));
    int count;
    CK(ProArraySizeGet((ProArray)members, &count));
    J ids = J::array();
    for (int i = 0; i < count; i++)
        ids.push_back(members[i].id);
    ProArrayFree((ProArray *)&members);
    aliases[op["label"].get<std::string>()] = {{"op", "udf_create"},
                                               {"group_id", group.id},
                                               {"member_feature_ids", ids},
                                               {"udf_metadata", metadata},
                                               {"dependency", "independent"}};
}
