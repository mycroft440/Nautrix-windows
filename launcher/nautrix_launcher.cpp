#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iterator>
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
    SetEnv(L"NAUTRIX_KEEPALIVE_ENABLED", ReadKey(latency_path, "enable_connection_keepalive", "1"));
    SetEnv(L"NAUTRIX_KEEPALIVE_IDLE_SECONDS", ReadKey(latency_path, "keepalive_idle_seconds", "120"));
    SetEnv(L"NAUTRIX_KEEPALIVE_PING_SECONDS", ReadKey(latency_path, "keepalive_ping_seconds", "25"));
    SetEnv(L"NAUTRIX_NETWORK_PRIORITY_BOOST", ReadKey(latency_path, "enable_network_priority_boost", "1"));
    SetEnv(L"NAUTRIX_SELECTIVE_THROTTLING_BYPASS", ReadKey(latency_path, "enable_selective_throttling_bypass", "1"));
    SetEnv(L"NAUTRIX_INTENT_PRECONNECT", ReadKey(latency_path, "enable_intent_preconnect", "1"));

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

    if (ReadKey(latency_path, "enable_warm_renderer_pool", "1") != "0") {
        features.emplace_back("PreferWarmRendererProcess");
        features.emplace_back("SpareRendererForSitePerProcess");
    }

    if (features.empty()) return {};
    std::wstring value = L"--enable-features=";
    for (size_t i = 0; i < features.size(); ++i) {
        if (i) value.push_back(L',');
        value += Utf8ToWide(features[i]);
    }
    return {std::move(value)};
}

}  // namespace nautrix_bootstrap

#include <cstring>

#define wmain NautrixOriginalMain
#include "nautrix_launcher_impl.inc"
#undef wmain

int wmain(int argc, wchar_t** argv) {
    std::filesystem::path config_dir = nautrix_bootstrap::ExecutableDirectory() / L"config";
    for (int i = 1; i < argc; ++i) {
        constexpr std::wstring_view prefix = L"--config-dir=";
        std::wstring_view arg(argv[i]);
        if (arg.rfind(prefix, 0) == 0) config_dir = std::wstring(arg.substr(prefix.size()));
    }

    std::vector<std::wstring> owned;
    owned.reserve(static_cast<size_t>(argc) + 4);
    for (int i = 0; i < argc; ++i) owned.emplace_back(argv[i]);
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
