#ifndef NAUTRIX_LAUNCHER_USER_CONFIG_H_
#define NAUTRIX_LAUNCHER_USER_CONFIG_H_

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <array>
#include <filesystem>
#include <iterator>
#include <system_error>

namespace nautrix_config {

inline std::filesystem::path LocalStateDirectory() {
    wchar_t buffer[32768]{};
    const DWORD size = GetEnvironmentVariableW(
        L"LOCALAPPDATA", buffer, static_cast<DWORD>(std::size(buffer)));
    const std::filesystem::path base =
        (size > 0 && size < std::size(buffer))
            ? std::filesystem::path(buffer)
            : std::filesystem::temp_directory_path();
    const std::filesystem::path result = base / L"Nautrix";
    std::error_code error;
    std::filesystem::create_directories(result, error);
    return result;
}

inline void SeedFileIfMissing(const std::filesystem::path& defaults,
                              const std::filesystem::path& user_config,
                              const std::filesystem::path& filename) {
    const std::filesystem::path destination = user_config / filename;
    std::error_code error;
    if (std::filesystem::is_regular_file(destination, error)) {
        return;
    }

    const std::filesystem::path source = defaults / filename;
    error.clear();
    if (!std::filesystem::is_regular_file(source, error)) {
        return;
    }

    error.clear();
    std::filesystem::copy_file(
        source, destination, std::filesystem::copy_options::skip_existing, error);
}

inline std::filesystem::path PrepareUserConfigDirectory(
    const std::filesystem::path& packaged_defaults) {
    const std::filesystem::path user_config = LocalStateDirectory() / L"Config";
    std::error_code error;
    std::filesystem::create_directories(user_config, error);
    if (error) {
        return packaged_defaults;
    }
    error.clear();
    if (!std::filesystem::is_directory(user_config, error) || error) {
        return packaged_defaults;
    }
    for (const auto* filename : {L"dns.ini", L"latency.ini"}) {
        SeedFileIfMissing(packaged_defaults, user_config, filename);
    }
    return user_config;
}

}  // namespace nautrix_config

#endif  // NAUTRIX_LAUNCHER_USER_CONFIG_H_
