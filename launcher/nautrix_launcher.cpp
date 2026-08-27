#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

namespace nautrix_bootstrap {

std::filesystem::path ExecutableDirectory() {
    std::wstring buffer(32768, L'\0');
    const DWORD size = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (!size || size >= buffer.size()) return std::filesystem::current_path();
    buffer.resize(size);
    return std::filesystem::path(buffer).parent_path();
}

std::filesystem::path LocalStateDirectory() {
    wchar_t buffer[32768]{};
    const DWORD size = GetEnvironmentVariableW(L"LOCALAPPDATA", buffer, static_cast<DWORD>(std::size(buffer)));
    std::filesystem::path base = (size > 0 && size < std::size(buffer))
        ? std::filesystem::path(buffer) : std::filesystem::temp_directory_path();
    std::filesystem::path out = base / L"Nautrix";
    std::error_code ec;
    std::filesystem::create_directories(out, ec);
    return out;
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
    if (wide.empty()) SetEnvironmentVariableW(name, nullptr);
    else SetEnvironmentVariableW(name, wide.c_str());
}

std::string MachineSeed() {
    wchar_t computer[256]{};
    DWORD size = static_cast<DWORD>(std::size(computer));
    if (!GetComputerNameW(computer, &size)) return "nautrix";
    std::wstring wide(computer, size);
    const int bytes = WideCharToMultiByte(CP_UTF8, 0, wide.data(), static_cast<int>(wide.size()),
                                          nullptr, 0, nullptr, nullptr);
    if (bytes <= 0) return "nautrix";
    std::string out(static_cast<size_t>(bytes), '\0');
    WideCharToMultiByte(CP_UTF8, 0, wide.data(), static_cast<int>(wide.size()),
                        out.data(), bytes, nullptr, nullptr);
    return out;
}

std::string NetworkSeed() {
    std::ifstream input(LocalStateDirectory() / L"dns-selection.state");
    if (!input) return "unknown-network";
    std::string content((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    return content.empty() ? "unknown-network" : content;
}

bool StableBucket(std::string_view seed, std::string_view feature_name) {
    std::uint64_t hash = 1469598103934665603ULL;
    for (unsigned char ch : seed) {
        hash ^= ch;
        hash *= 1099511628211ULL;
    }
    for (unsigned char ch : feature_name) {
        hash ^= ch;
        hash *= 1099511628211ULL;
    }
    return (hash & 1ULL) != 0;
}

bool FeatureEnabled(const std::string& mode,
                    std::string_view feature_name,
                    std::string_view machine_seed,
                    std::string_view network_seed) {
    if (mode == "on" || mode == "1" || mode == "true") return true;
    if (mode == "ab" || mode == "ab-machine") return StableBucket(machine_seed, feature_name);
    if (mode == "ab-network") {
        std::string scoped(machine_seed);
        scoped.append("|").append(network_seed);
        return StableBucket(scoped, feature_name);
    }
    // Per-origin experiments need the Chromium-side origin gate, so keep the
    // feature available here and let the downstream patch decide per origin.
    if (mode == "ab-origin") return true;
    return false;
}

bool StartDnsRouter(const std::filesystem::path& config_dir) {
    HANDLE ready = OpenEventW(SYNCHRONIZE, FALSE, L"Local\\NautrixDnsRouterReady");
    if (ready) {
        CloseHandle(ready);
        SetEnvironmentVariableW(L"NAUTRIX_DNS_ROUTER_ACTIVE", L"1");
        return true;
    }

    const std::filesystem::path router = ExecutableDirectory() / L"NautrixDnsRouter.exe";
    if (!std::filesystem::exists(router)) return false;
    std::wstring command = L"\"" + router.wstring() + L"\" --config-dir=\"" + config_dir.wstring() + L"\"";
    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(nullptr, command.data(), nullptr, nullptr, FALSE,
                        CREATE_NO_WINDOW | DETACHED_PROCESS, nullptr,
                        ExecutableDirectory().c_str(), &startup, &process)) {
        return false;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);

    for (int i = 0; i < 80; ++i) {
        ready = OpenEventW(SYNCHRONIZE, FALSE, L"Local\\NautrixDnsRouterReady");
        if (ready) {
            CloseHandle(ready);
            SetEnvironmentVariableW(L"NAUTRIX_DNS_ROUTER_ACTIVE", L"1");
            return true;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(25));
    }
    return false;
}

std::vector<std::wstring> BuildInjectedArgs(const std::filesystem::path& latency_path) {
    const std::string machine_seed = MachineSeed();
    const std::string network_seed = NetworkSeed();
    SetEnv(L"NAUTRIX_AB_SEED", machine_seed + "|" + network_seed);
    SetEnv(L"NAUTRIX_TRADING_MODE", ReadKey(latency_path, "trading_mode", "automatic"));
    SetEnv(L"NAUTRIX_TRADING_SITES", ReadKey(latency_path, "trading_sites"));
    SetEnv(L"NAUTRIX_KEEPALIVE_ENABLED", ReadKey(latency_path, "enable_connection_keepalive", "1"));
    SetEnv(L"NAUTRIX_ADAPTIVE_KEEPALIVE", ReadKey(latency_path, "adaptive_keepalive", "1"));
    SetEnv(L"NAUTRIX_KEEPALIVE_IDLE_SECONDS", ReadKey(latency_path, "keepalive_idle_seconds", "120"));
    SetEnv(L"NAUTRIX_KEEPALIVE_PING_SECONDS", ReadKey(latency_path, "keepalive_ping_seconds", "25"));
    SetEnv(L"NAUTRIX_KEEPALIVE_ACTIVE_IDLE_SECONDS", ReadKey(latency_path, "keepalive_active_idle_seconds", "180"));
    SetEnv(L"NAUTRIX_KEEPALIVE_ACTIVE_PING_SECONDS", ReadKey(latency_path, "keepalive_active_ping_seconds", "20"));
    SetEnv(L"NAUTRIX_KEEPALIVE_BACKGROUND_IDLE_SECONDS", ReadKey(latency_path, "keepalive_background_idle_seconds", "45"));
    SetEnv(L"NAUTRIX_KEEPALIVE_BACKGROUND_PING_SECONDS", ReadKey(latency_path, "keepalive_background_ping_seconds", "0"));
    SetEnv(L"NAUTRIX_NETWORK_PRIORITY_BOOST", ReadKey(latency_path, "enable_network_priority_boost", "1"));
    SetEnv(L"NAUTRIX_REQUEST_PRIORITY_POLICY", ReadKey(latency_path, "request_priority_policy", "critical"));
    SetEnv(L"NAUTRIX_SELECTIVE_THROTTLING_BYPASS", ReadKey(latency_path, "enable_selective_throttling_bypass", "1"));
    SetEnv(L"NAUTRIX_INTENT_PRECONNECT", ReadKey(latency_path, "enable_intent_preconnect", "1"));
    SetEnv(L"NAUTRIX_INTENT_HOVER_MS", ReadKey(latency_path, "intent_preconnect_hover_ms", "120"));
    SetEnv(L"NAUTRIX_INTENT_POINTERDOWN", ReadKey(latency_path, "intent_preconnect_pointerdown", "1"));
    SetEnv(L"NAUTRIX_INTENT_TAB_ACTIVATION", ReadKey(latency_path, "intent_preconnect_tab_activation", "1"));
    SetEnv(L"NAUTRIX_HIGH_RES_TIMER", ReadKey(latency_path, "enable_high_resolution_timer", "1"));
    SetEnv(L"NAUTRIX_FREEZING_PROTECTION", ReadKey(latency_path, "enable_freezing_protection", "1"));
    SetEnv(L"NAUTRIX_TRADING_PROCESS_PRIORITY", ReadKey(latency_path, "enable_trading_process_priority", "1"));
    SetEnv(L"NAUTRIX_DISABLE_ECOQOS", ReadKey(latency_path, "disable_ecoqos_for_trading", "1"));
    SetEnv(L"NAUTRIX_SPARE_RENDERER_WARMUP", ReadKey(latency_path, "enable_spare_renderer_warmup", "1"));
    SetEnv(L"NAUTRIX_WEBSOCKET_H3_MODE", ReadKey(latency_path, "websocket_over_http3", "ab-origin"));
    SetEnv(L"NAUTRIX_WEBSOCKET_H3_ORIGINS", ReadKey(latency_path, "websocket_h3_origins"));
    SetEnv(L"NAUTRIX_V8_LATENCY_TELEMETRY", ReadKey(latency_path, "enable_v8_latency_telemetry", "1"));
    SetEnv(L"NAUTRIX_INPUT_FRAME_TELEMETRY", ReadKey(latency_path, "enable_input_to_frame_telemetry", "1"));

    std::vector<std::string> features;
    const std::string optimistic = ReadKey(latency_path, "optimistic_dns_for_tcp", "ab-network");
    if (FeatureEnabled(optimistic, "OptimisticDnsForTcp", machine_seed, network_seed)) {
        features.emplace_back("OptimisticDnsForTcp");
        features.emplace_back("EnableIntermediateDnsResults");
        features.emplace_back("AdjustIPv6FallbackTime");
        features.emplace_back("IPv6FallbackBasedOnRTT");
    }

    const std::string happy = ReadKey(latency_path, "happy_eyeballs_v3", "ab-network");
    if (FeatureEnabled(happy, "HappyEyeballsV3", machine_seed, network_seed)) {
        features.emplace_back("HappyEyeballsV3");
    }

    const std::string https_rr = ReadKey(latency_path, "https_svcb_priority", "ab-network");
    if (FeatureEnabled(https_rr, "PrioritizeHttpsResourceRecord", machine_seed, network_seed)) {
        features.emplace_back("PrioritizeHttpsResourceRecord");
    }

    const std::string tcp_iocp = ReadKey(latency_path, "tcp_iocp_windows", "ab-machine");
    if (FeatureEnabled(tcp_iocp, "TcpSocketIoCompletionPortWin", machine_seed, network_seed)) {
        features.emplace_back("TcpSocketIoCompletionPortWin");
    }

    const std::string websocket_h3 = ReadKey(latency_path, "websocket_over_http3", "ab-origin");
    if (FeatureEnabled(websocket_h3, "EnableWebsocketsOverHttp3", machine_seed, network_seed)) {
        features.emplace_back("EnableWebsocketsOverHttp3");
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

    if (nautrix_bootstrap::ReadKey(config_dir / L"latency.ini", "enable_origin_dns_router", "0") == "1") {
        nautrix_bootstrap::StartDnsRouter(config_dir);
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
