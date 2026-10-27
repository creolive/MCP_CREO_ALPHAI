// DEV-048: offline policy check for the shared inspection sidecar helper.
// Only plain file I/O and SHA256 run here; no Toolkit call, no Creo connection.
#include "inspection_sidecar.h"
#include <cassert>
#include <cstdio>
#include <fstream>
#include <string>

using mechdog_sidecar::Json;

namespace {
int cases = 0;

std::filesystem::path scratch(const char *name, bool reset = true) {
    const std::filesystem::path path = std::filesystem::temp_directory_path() / name;
    if (reset) {
        std::error_code ignored;
        std::filesystem::remove_all(path, ignored);
        std::filesystem::create_directories(path);
    }
    return path;
}

std::string read(const std::filesystem::path &file) {
    std::ifstream input(file, std::ios::binary);
    return std::string((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
}

void write(const std::filesystem::path &file, const std::string &data) {
    std::ofstream output(file, std::ios::binary | std::ios::trunc);
    output << data;
}

std::string digest_of(const std::string &data) {
    const std::filesystem::path probe = scratch("dev048_sidecar_digest") / "probe.bin";
    write(probe, data);
    const std::string digest = mechdog_callback::sha256(probe);
    std::error_code ignored;
    std::filesystem::remove_all(probe.parent_path(), ignored);
    return digest;
}

bool utf8_valid(const std::string &text) {
    for (std::size_t i = 0; i < text.size();) {
        const auto lead = static_cast<unsigned char>(text[i]);
        const std::size_t expected = mechdog_sidecar::utf8_expected(lead);
        if (expected == 1 && lead >= 0x80)
            return false;
        if (i + expected > text.size())
            return false;
        for (std::size_t offset = 1; offset < expected; ++offset)
            if ((static_cast<unsigned char>(text[i + offset]) & 0xC0) != 0x80)
                return false;
        i += expected;
    }
    return true;
}

Json payload(int volume) {
    return {
        {"healthy", true}, {"units", "mm"}, {"volume_mm3", volume}, {"features", Json::array()}};
}
} // namespace

int main() {
    // 1. Repeating the same payload reuses one verified file.
    {
        const auto directory = scratch("dev048_sidecar_reuse");
        const Json value = payload(10);
        const Json first = mechdog_sidecar::write_ref(value, directory, "live");
        const Json second = mechdog_sidecar::write_ref(value, directory, "live");
        assert(first == second);
        assert(first["bytes"].get<long long>() == (long long)value.dump(2).size());
        assert(mechdog_sidecar::matches(directory / first["file"].get<std::string>(),
                                        value.dump(2).size(), first["sha256"].get<std::string>()));
        std::size_t files = 0;
        for (const auto &entry : std::filesystem::directory_iterator(directory))
            if (entry.is_regular_file())
                ++files;
        assert(files == 1 && "a repeated payload must not leave extra files");
        ++cases;
    }
    // 2. A same-size file with other bytes is kept; the payload goes elsewhere.
    {
        const auto directory = scratch("dev048_sidecar_decoy");
        const Json value = payload(20);
        const std::string data = value.dump(2);
        const std::string digest = digest_of(data);
        const auto decoy = directory / ("inspection-live-" + digest.substr(0, 16) + ".json");
        std::string foreign = data;
        foreign.replace(foreign.find("20"), 2, "29");
        assert(foreign.size() == data.size());
        write(decoy, foreign);
        const Json ref = mechdog_sidecar::write_ref(value, directory, "live");
        assert(read(decoy) == foreign && "another writer's file must stay untouched");
        assert(std::filesystem::path(ref["file"].get<std::string>()) != decoy);
        assert(std::filesystem::exists(std::filesystem::path(ref["file"].get<std::string>())));
        assert(mechdog_sidecar::matches(directory / ref["file"].get<std::string>(), data.size(),
                                        ref["sha256"].get<std::string>()));
        ++cases;
    }
    // 3. Both candidate names occupied by directories: publishing fails and
    //    keeps the occupied names instead of replacing them.
    {
        const auto directory = scratch("dev048_sidecar_publish");
        const Json value = payload(30);
        const std::string data = value.dump(2);
        const std::string digest = digest_of(data);
        const auto short_name = directory / ("inspection-live-" + digest.substr(0, 16) + ".json");
        const auto full_name = directory / ("inspection-live-" + digest + ".json");
        std::filesystem::create_directories(short_name);
        std::filesystem::create_directories(full_name);
        bool failed = false;
        try {
            mechdog_sidecar::write_ref(value, directory, "live");
        } catch (const mechdog_sidecar::Error &error) {
            failed = std::string(error.code()) == mechdog_sidecar::publish_failed;
        }
        assert(failed);
        assert(std::filesystem::is_directory(short_name) &&
               std::filesystem::is_directory(full_name));
        std::size_t temporaries = 0;
        for (const auto &entry : std::filesystem::directory_iterator(directory))
            if (entry.path().extension() == ".tmp")
                ++temporaries;
        assert(temporaries == 0 && "a failed publish must clean its own temporary file");
        ++cases;
    }
    // 4. Writing before the directory exists is a write failure, not a publish one.
    {
        std::error_code ignored;
        const auto directory = scratch("dev048_sidecar_missing");
        std::filesystem::remove_all(directory, ignored);
        bool failed = false;
        try {
            mechdog_sidecar::write_ref(payload(40), directory, "live");
        } catch (const mechdog_sidecar::Error &error) {
            failed = std::string(error.code()) == mechdog_sidecar::write_failed;
        }
        assert(failed);
        ++cases;
    }
    // 5. Diagnostics dedupe, cap at four and stay valid UTF-8 within 256 bytes.
    {
        Json report = Json::object();
        mechdog_sidecar::add_warning(report, "live", mechdog_sidecar::write_failed, "not_attempted",
                                     "first");
        mechdog_sidecar::add_warning(report, "live", mechdog_sidecar::write_failed, "verified",
                                     "upgraded");
        assert(report["inspection_warnings"].size() == 1);
        assert(report["inspection_warnings"][0]["fallback_status"].get<std::string>() ==
               "verified");
        std::string long_message;
        for (int index = 0; index < 300; ++index)
            long_message += "ab\xC3\xA9"; // two ASCII bytes plus a two-byte character
        mechdog_sidecar::add_warning(report, "verified", mechdog_sidecar::publish_failed, "failed",
                                     long_message);
        const std::string message =
            report["inspection_warnings"].back()["message"].get<std::string>();
        assert(message.size() <= mechdog_sidecar::max_message_bytes);
        assert(utf8_valid(message));
        // Eight distinct (stage, reason_code) pairs; only the newest four stay.
        Json capped = Json::object();
        const char *stages[] = {"live", "verified"};
        const char *reasons[] = {"native_sidecar_write_failed", "native_sidecar_publish_failed",
                                 "inspection_ref_invalid", "inspection_ref_removed_after_refusal"};
        for (const char *stage : stages)
            for (const char *reason : reasons)
                mechdog_sidecar::add_warning(capped, stage, reason, "failed", "entry");
        assert(capped["inspection_warnings"].size() == mechdog_sidecar::max_warnings);
        // The newest four entries survive: the whole second stage in order.
        const Json &kept = capped["inspection_warnings"];
        for (std::size_t index = 0; index < kept.size(); ++index) {
            assert(kept[index]["stage"].get<std::string>() == "verified");
            assert(kept[index]["reason_code"].get<std::string>() == reasons[index]);
        }
        ++cases;
    }
    // 6. live and verified close out independently: a blocked live publish keeps
    //    its inline payload and records the stage, while verified still splits.
    {
        const auto directory = scratch("dev048_sidecar_stages");
        const Json live_value = payload(50);
        const Json verified_value = payload(51);
        const std::string live_data = live_value.dump(2);
        const std::string live_digest = digest_of(live_data);
        std::filesystem::create_directories(
            directory / ("inspection-live-" + live_digest.substr(0, 16) + ".json"));
        std::filesystem::create_directories(directory /
                                            ("inspection-live-" + live_digest + ".json"));
        Json request = {{"adoption", {{"action", "inspect"}}}};
        Json report = {{"live", {{"inspection", live_value}}}, {"inspection", verified_value}};
        mechdog_sidecar::split_report(request, report, directory);
        assert(report["live"].contains("inspection"));
        assert(!report["live"].contains("inspection_ref"));
        assert(report.contains("inspection_ref") && !report.contains("inspection"));
        assert(report.contains("inspection_warnings"));
        const Json &warning = report["inspection_warnings"][0];
        assert(warning["stage"].get<std::string>() == "live");
        assert(warning["reason_code"].get<std::string>() == mechdog_sidecar::publish_failed);
        assert(warning["fallback_status"].get<std::string>() == "not_attempted");
        ++cases;
    }
    // 7. A healthy closeout records no warning, and ordinary modeling reports
    //    are never split at all.
    {
        const auto directory = scratch("dev048_sidecar_healthy");
        Json request = {{"reconciliation", {{"action", "inspect"}}}};
        Json report = {{"live", {{"inspection", payload(60)}}}, {"inspection", payload(61)}};
        mechdog_sidecar::split_report(request, report, directory);
        assert(!report.contains("inspection_warnings"));
        assert(report["live"].contains("inspection_ref") && report.contains("inspection_ref"));
        Json plan = {{"new", true}};
        Json modeling = {{"inspection", payload(62)}};
        mechdog_sidecar::split_report(plan, modeling, directory);
        assert(modeling.contains("inspection") && !modeling.contains("inspection_ref"));
        ++cases;
    }
    std::printf("INSPECTION_SIDECAR_OK cases=%d; no Toolkit call, plain file I/O and SHA256 only\n",
                cases);
    return 0;
}