// Controlled inspection sidecars shared by the SDK adapter and the offline
// harness (DEV-048). Only plain file I/O and SHA256 are used here: no Toolkit
// call, no Creo connection, so the behaviour can be compiled and driven with
// substituted inputs.
#pragma once
#include "third_party/json.hpp"
#include "callback_identity.h"
#include <algorithm>
#include <cstddef>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <system_error>

namespace mechdog_sidecar {
using Json = nlohmann::json;

inline constexpr std::size_t max_warnings = 4;
inline constexpr std::size_t max_message_bytes = 256;
inline constexpr const char *write_failed = "native_sidecar_write_failed";
inline constexpr const char *publish_failed = "native_sidecar_publish_failed";

// A sidecar failure carries the fixed reason code of the stage that failed so
// callers never have to guess the stage from the message text.
class Error : public std::runtime_error {
  public:
    Error(const char *code, const std::string &message) : std::runtime_error(message), code_(code) {
    }
    const char *code() const noexcept {
        return code_;
    }

  private:
    const char *code_;
};

// Bound a diagnostic message to 256 UTF-8 bytes without splitting a code point.
inline std::size_t utf8_expected(unsigned char lead) {
    if (lead < 0x80)
        return 1;
    if ((lead & 0xE0) == 0xC0)
        return 2;
    if ((lead & 0xF0) == 0xE0)
        return 3;
    if ((lead & 0xF8) == 0xF0)
        return 4;
    return 1;
}

inline std::string bounded(const std::string &text) {
    if (text.size() <= max_message_bytes)
        return text;
    const std::string suffix = "\xE2\x80\xA6"; // U+2026 HORIZONTAL ELLIPSIS
    std::string prefix = text.substr(0, max_message_bytes - suffix.size());
    std::size_t length = prefix.size();
    while (length > 0) {
        std::size_t start = length - 1;
        while (start > 0 && (static_cast<unsigned char>(prefix[start]) & 0xC0) == 0x80)
            --start;
        const auto lead = static_cast<unsigned char>(prefix[start]);
        if (start + utf8_expected(lead) <= length)
            break;
        length = start;
    }
    return prefix.substr(0, length) + suffix;
}

// One entry per (stage, reason_code); the oldest entry is dropped at the cap.
inline void add_warning(Json &holder, const std::string &stage, const std::string &reason_code,
                        const std::string &fallback_status, const std::string &message) {
    if (!holder.is_object())
        return;
    Json entries = Json::array();
    if (holder.contains("inspection_warnings") && holder["inspection_warnings"].is_array()) {
        for (const auto &entry : holder["inspection_warnings"])
            if (entry.is_object())
                entries.push_back(entry);
    }
    const Json entry = {{"stage", stage},
                        {"reason_code", reason_code},
                        {"fallback_status", fallback_status},
                        {"message", bounded(message)}};
    bool replaced = false;
    for (auto &existing : entries) {
        if (existing.value("stage", "") == stage &&
            existing.value("reason_code", "") == reason_code) {
            existing = entry;
            replaced = true;
            break;
        }
    }
    if (!replaced) {
        entries.push_back(entry);
        while (entries.size() > max_warnings)
            entries.erase(entries.begin());
    }
    holder["inspection_warnings"] = entries;
}

inline std::string utf8(const std::filesystem::path &path) {
    const auto value = path.u8string();
    return std::string(value.begin(), value.end());
}

// This service's own plain file: links and directories are never sidecars.
inline bool regular_file(const std::filesystem::path &path) {
    std::error_code error;
    const auto status = std::filesystem::symlink_status(path, error);
    return !error && std::filesystem::is_regular_file(status);
}

inline bool entry_exists(const std::filesystem::path &path) {
    std::error_code error;
    const auto status = std::filesystem::symlink_status(path, error);
    return !error && status.type() != std::filesystem::file_type::not_found;
}

// A reused sidecar must match the payload in size *and* full SHA256.
inline bool matches(const std::filesystem::path &path, std::size_t size,
                    const std::string &digest) {
    if (!regular_file(path))
        return false;
    std::error_code error;
    const auto actual = std::filesystem::file_size(path, error);
    if (error || actual != size)
        return false;
    try {
        return mechdog_callback::sha256(path) == digest;
    } catch (...) {
        return false;
    }
}

inline void discard(const std::filesystem::path &path) {
    std::error_code ignored;
    std::filesystem::remove(path, ignored);
}

inline Json reference(const std::filesystem::path &file, const std::string &digest,
                      std::size_t size) {
    return {{"file", utf8(file)}, {"sha256", digest}, {"bytes", (long long)size}};
}

// Write the payload to a temporary file, verify it, then publish it under a
// content-addressed name without ever replacing a file another writer owns.
inline Json write_ref(const Json &value, const std::filesystem::path &directory,
                      const std::string &stem) {
    const std::string data = value.dump(2);
    const std::filesystem::path temp =
        directory / ("inspection-" + stem + "-" + std::to_string(GetCurrentProcessId()) + "-" +
                     std::to_string(GetTickCount64()) + ".tmp");
    {
        std::ofstream output(temp, std::ios::binary | std::ios::trunc);
        output.write(data.data(), static_cast<std::streamsize>(data.size()));
        output.flush();
        if (!output.good()) {
            output.close();
            discard(temp);
            throw Error(write_failed, "Cannot write the inspection sidecar file");
        }
    }
    std::string digest;
    try {
        digest = mechdog_callback::sha256(temp);
    } catch (const std::exception &) {
        discard(temp);
        throw Error(write_failed, "Cannot verify the inspection sidecar file after writing");
    }
    if (digest.size() != 64 || !matches(temp, data.size(), digest)) {
        discard(temp);
        throw Error(write_failed, "The inspection sidecar did not verify after writing");
    }
    const std::filesystem::path candidates[] = {
        directory / ("inspection-" + stem + "-" + digest.substr(0, 16) + ".json"),
        directory / ("inspection-" + stem + "-" + digest + ".json")};
    for (const auto &file : candidates) {
        if (entry_exists(file)) {
            if (matches(file, data.size(), digest)) {
                discard(temp);
                return reference(file, digest, data.size());
            }
            continue; // Keep another writer's file and try the next name.
        }
        // MoveFileExW without REPLACE_EXISTING fails when the target appeared
        // first, so publishing never overwrites a concurrent writer.
        if (!MoveFileExW(temp.c_str(), file.c_str(), MOVEFILE_WRITE_THROUGH)) {
            const bool same = matches(file, data.size(), digest);
            discard(temp);
            if (!same)
                throw Error(publish_failed,
                            "Cannot publish the inspection sidecar file; the target was kept");
            return reference(file, digest, data.size());
        }
        if (!matches(file, data.size(), digest)) {
            discard(file);
            throw Error(publish_failed, "The published inspection sidecar did not verify");
        }
        return reference(file, digest, data.size());
    }
    discard(temp);
    throw Error(publish_failed,
                "Inspection sidecar names are occupied by other content; the files were kept");
}

// Close out one inspection stage: publish a reference or keep the inline
// payload and record the fixed stage/reason diagnostic on the report.
inline void split_stage(Json &holder, const char *key, const char *ref_key, const char *stem,
                        const char *stage, const std::filesystem::path &directory, Json &report) {
    if (!holder.is_object() || !holder.contains(key))
        return;
    if (!holder[key].is_object() || holder[key].empty())
        return;
    try {
        holder[ref_key] = write_ref(holder[key], directory, stem);
    } catch (const Error &error) {
        add_warning(report, stage, error.code(), "not_attempted", error.what());
        return;
    }
    holder.erase(key);
}

// Two stages close out independently: a live failure never skips verified.
inline void split_report(const Json &request, Json &report,
                         const std::filesystem::path &directory) {
    if (!request.contains("adoption") && !request.contains("reconciliation"))
        return;
    if (!report.is_object())
        return;
    if (report.contains("live") && report["live"].is_object())
        split_stage(report["live"], "inspection", "inspection_ref", "live", "live", directory,
                    report);
    split_stage(report, "inspection", "inspection_ref", "verified", "verified", directory, report);
}
} // namespace mechdog_sidecar