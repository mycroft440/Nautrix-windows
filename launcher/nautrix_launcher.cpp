#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <shellapi.h>

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace nautrix_bootstrap {

std::filesystem::path ExecutableDirectory() {
    std::wstring buffer(32768, L'\0');
    const DWORD size = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (!size || size >= buffer.size()) return std::filesystem::current_path();
    buffer.resize(size);
    return std::filesystem::path(buffer).parent_path();
}

std::string Trim(std::string value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

std::string ReadKey(const std::filesystem::path& path,
                    const std::string& wanted,
                    const std::string& fallback = {}) {
    std::ifstream input(path);
    std::string line;
    while (std::getline(input, line)) {
        line = Trim(std::move(line));
        if (line.empty() || line[0] == '#' || line[0] == ';') continue;
        const auto separator = line.find('=');
        if (separator == std::string::npos) continue;
        if (Trim(line.substr(0, separator)) == wanted) {
            return Trim(line.substr(separator + 1));
        }
    }
    return fallback;
}

std::wstring Utf8ToWide(const std::string& input) {
    if (input.empty()) return {};
    const int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
                                            input.data(), static_cast<int>(input.size()),
                                            nullptr, 0);
    if (length <= 0) return {};
    std::wstring output(static_cast<size_t>(length), L'\0');
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
                            input.data(), static_cast<int>(input.size()),
                            output.data(), length) <= 0) {
        return {};
    }
    return output;
}

void SetEnv(const wchar_t* name, const std::string& value) {
    const std::wstring wide = Utf8ToWide(value);
    if (!wide.empty()) SetEnvironmentVariableW(name, wide.c_str());
}

bool StableAbBucket(std::string_view feature_name) {
    wchar_t computer[256]{};
    DWORD size = static_cast<DWORD>(std::size(computer));
    std::wstring seed_wide;
    if (GetComputerNameW(computer, &size)) seed_wide.assign(computer, size);
    std::uint64_t hash = 1469598103934665603ULL;
    for (wchar_t ch : seed_wide) {
        hash ^= static_cast<std::uint64_t>(ch);
        hash *= 1099511628211ULL;
    }
    for (unsigned char ch : feature_name) {
        hash ^= ch;
        hash *= 1099511628211ULL;
    }
    return (hash & 1ULL) != 0;
}

bool FeatureEnabled(const std::string& mode, std::string_view feature_name) {
    if (mode == "on" || mode == "1" || mode == "true") return true;
    if (mode == "ab") return StableAbBucket(feature_name);
    return false;
}

std::vector<std::wstring> BuildInjectedArgs(const std::filesystem::path& latency_path) {
    SetEnv(L"NAUTRIX_TRADING_MODE", ReadKey(latency_path, "trading_mode", "automatic"));
    SetEnv(L"NAUTRIX_TRADING_SITES", ReadKey(latency_path, "trading_sites"));
    SetEnv(L"NAUTRIX_CRITICAL_TRADING_SITES", ReadKey(latency_path, "critical_trading_sites"));
    SetEnv(L"NAUTRIX_MEMORY_SAVER_ENABLED", ReadKey(latency_path, "enable_memory_saver", "1"));
    SetEnv(L"NAUTRIX_MEMORY_SAVER_AGGRESSIVENESS", ReadKey(latency_path, "memory_saver_aggressiveness", "medium"));
    SetEnv(L"NAUTRIX_MEMORY_SAVER_DISCARD_MINUTES", ReadKey(latency_path, "memory_saver_discard_minutes", "120"));
    SetEnv(L"NAUTRIX_PRECONNECT_MAX_ORIGINS", ReadKey(latency_path, "preconnect_max_origins", "4"));
    SetEnv(L"NAUTRIX_KEEPALIVE_MAX_ORIGINS", ReadKey(latency_path, "keepalive_max_origins", "2"));
    SetEnv(L"NAUTRIX_KEEPALIVE_ENABLED", ReadKey(latency_path, "enable_connection_keepalive", "1"));
    SetEnv(L"NAUTRIX_KEEPALIVE_IDLE_SECONDS", ReadKey(latency_path, "keepalive_idle_seconds", "120"));
    SetEnv(L"NAUTRIX_KEEPALIVE_PING_SECONDS", ReadKey(latency_path, "keepalive_ping_seconds", "25"));
    SetEnv(L"NAUTRIX_NETWORK_PRIORITY_BOOST", ReadKey(latency_path, "enable_network_priority_boost", "1"));
    SetEnv(L"NAUTRIX_SELECTIVE_THROTTLING_BYPASS", ReadKey(latency_path, "enable_selective_throttling_bypass", "1"));
    SetEnv(L"NAUTRIX_BACKGROUND_CONNECTION_BYPASS", ReadKey(latency_path, "enable_background_connection_bypass", "1"));
    SetEnv(L"NAUTRIX_INTENT_PRECONNECT", ReadKey(latency_path, "enable_intent_preconnect", "1"));
    SetEnv(L"NAUTRIX_HIGH_RES_TIMER", ReadKey(latency_path, "enable_high_resolution_timer", "1"));
    SetEnv(L"NAUTRIX_FREEZING_PROTECTION", ReadKey(latency_path, "enable_freezing_protection", "1"));
    SetEnv(L"NAUTRIX_TRADING_PROCESS_PRIORITY", ReadKey(latency_path, "enable_trading_process_priority", "1"));
    SetEnv(L"NAUTRIX_DISABLE_ECOQOS", ReadKey(latency_path, "disable_ecoqos_for_trading", "1"));
    SetEnv(L"NAUTRIX_SPARE_RENDERER_WARMUP", ReadKey(latency_path, "enable_spare_renderer_warmup", "1"));

    std::vector<std::wstring> injected_args;
    const std::string blocker_mode = ReadKey(latency_path, "lightweight_blocker", "off");
    if (FeatureEnabled(blocker_mode, "NautrixLightweightBlocker")) {
        const auto blocker_dir = latency_path.parent_path().parent_path() /
                                 L"extensions" / L"nautrix-blocker";
        if (std::filesystem::is_regular_file(blocker_dir / L"manifest.json")) {
            injected_args.emplace_back(L"--load-extension=" + blocker_dir.wstring());
        }
    }

    std::vector<std::string> features;
    const std::string optimistic = ReadKey(latency_path, "optimistic_dns_for_tcp", "ab");
    if (FeatureEnabled(optimistic, "OptimisticDnsForTcp")) {
        features.emplace_back("OptimisticDnsForTcp");
        features.emplace_back("EnableIntermediateDnsResults");
        features.emplace_back("AdjustIPv6FallbackTime");
        features.emplace_back("IPv6FallbackBasedOnRTT");
    }

    const std::string websocket_h3 = ReadKey(latency_path, "websocket_over_http3", "ab");
    if (FeatureEnabled(websocket_h3, "EnableWebsocketsOverHttp3")) {
        features.emplace_back("EnableWebsocketsOverHttp3");
    }

    if (!features.empty()) {
        std::wstring value = L"--enable-features=";
        for (size_t i = 0; i < features.size(); ++i) {
            if (i) value.push_back(L',');
            value += Utf8ToWide(features[i]);
        }
        injected_args.push_back(std::move(value));
    }
    return injected_args;
}

std::optional<std::wstring> ExtractShellSingleArgument() {
    const wchar_t* raw = GetCommandLineW();
    if (!raw) return std::nullopt;
    constexpr std::wstring_view marker = L" --single-argument ";
    const std::wstring_view command(raw);
    const size_t position = command.find(marker);
    if (position == std::wstring_view::npos) return std::nullopt;
    return std::wstring(command.substr(position + marker.size()));
}

std::optional<std::wstring> g_shell_single_argument;

BOOL WINAPI NautrixCreateProcessW(LPCWSTR application_name,
                                  LPWSTR command_line,
                                  LPSECURITY_ATTRIBUTES process_attributes,
                                  LPSECURITY_ATTRIBUTES thread_attributes,
                                  BOOL inherit_handles,
                                  DWORD creation_flags,
                                  LPVOID environment,
                                  LPCWSTR current_directory,
                                  LPSTARTUPINFOW startup_info,
                                  LPPROCESS_INFORMATION process_information) {
    if (!g_shell_single_argument.has_value()) {
        return ::CreateProcessW(application_name, command_line, process_attributes,
                                thread_attributes, inherit_handles, creation_flags,
                                environment, current_directory, startup_info,
                                process_information);
    }

    std::wstring rebuilt = command_line ? command_line : L"";
    rebuilt += L" --single-argument";
    if (!g_shell_single_argument->empty()) {
        rebuilt.push_back(L' ');
        rebuilt += *g_shell_single_argument;
    }
    std::vector<wchar_t> mutable_command(rebuilt.begin(), rebuilt.end());
    mutable_command.push_back(L'\0');
    return ::CreateProcessW(application_name, mutable_command.data(), process_attributes,
                            thread_attributes, inherit_handles, creation_flags,
                            environment, current_directory, startup_info,
                            process_information);
}

}  // namespace nautrix_bootstrap

#include <cstring>

#define CreateProcessW nautrix_bootstrap::NautrixCreateProcessW
#define wmain NautrixOriginalMain
#include "nautrix_launcher_impl.inc"
#undef wmain
#undef CreateProcessW

int NautrixLauncherMain(int argc, wchar_t** argv) {
    std::filesystem::path config_dir = nautrix_bootstrap::ExecutableDirectory() / L"config";
    size_t single_argument_index = static_cast<size_t>(argc);
    for (int i = 1; i < argc; ++i) {
        constexpr std::wstring_view prefix = L"--config-dir=";
        std::wstring_view arg(argv[i]);
        if (arg == L"--single-argument") {
            single_argument_index = static_cast<size_t>(i);
            break;
        }
        if (arg.rfind(prefix, 0) == 0) config_dir = std::wstring(arg.substr(prefix.size()));
    }

    nautrix_bootstrap::g_shell_single_argument = nautrix_bootstrap::ExtractShellSingleArgument();
    if (single_argument_index < static_cast<size_t>(argc) &&
        !nautrix_bootstrap::g_shell_single_argument.has_value()) {
        // Never forward a shell marker whose raw argument could not be recovered;
        // doing so would allow later injected switches to become part of the URL.
        return 2;
    }

    std::vector<std::wstring> owned;
    owned.reserve(static_cast<size_t>(argc) + 6);
    const size_t copy_count = std::min(single_argument_index, static_cast<size_t>(argc));
    for (size_t i = 0; i < copy_count; ++i) owned.emplace_back(argv[i]);

    for (auto& injected : nautrix_bootstrap::BuildInjectedArgs(config_dir / L"latency.ini")) {
        bool merged_feature_switch = false;
        if (injected.rfind(L"--enable-features=", 0) == 0) {
            for (size_t i = 1; i < owned.size(); ++i) {
                if (owned[i].rfind(L"--enable-features=", 0) == 0) {
                    owned[i] += L"," + injected.substr(std::wstring_view(L"--enable-features=").size());
                    merged_feature_switch = true;
                    break;
                }
            }
        }
        if (!merged_feature_switch) owned.push_back(std::move(injected));
    }

    std::vector<wchar_t*> forwarded;
    forwarded.reserve(owned.size());
    for (auto& item : owned) forwarded.push_back(item.data());
    return NautrixOriginalMain(static_cast<int>(forwarded.size()), forwarded.data());
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    int argc = 0;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (!argv || argc <= 0) {
        if (argv) LocalFree(argv);
        return 1;
    }

    const int result = NautrixLauncherMain(argc, argv);
    LocalFree(argv);
    return result;
}
