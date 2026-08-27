#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <winhttp.h>

#include <algorithm>
#include <chrono>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <future>
#include <iomanip>
#include <iostream>
#include <map>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "winhttp.lib")

namespace {
using Clock = std::chrono::steady_clock;

struct Provider {
    std::string id;
    std::vector<std::string> nameservers;
    std::string doh;
};

struct Route {
    std::string provider;
    double score_ms = 1e9;
    std::int64_t selected_at = 0;
};

struct Answer {
    std::string provider;
    std::vector<std::uint8_t> packet;
    double elapsed_ms = 1e9;
};

struct InternetHandle {
    HINTERNET value = nullptr;
    InternetHandle() = default;
    explicit InternetHandle(HINTERNET h) : value(h) {}
    ~InternetHandle() { if (value) WinHttpCloseHandle(value); }
    InternetHandle(const InternetHandle&) = delete;
    InternetHandle& operator=(const InternetHandle&) = delete;
};

std::string Trim(std::string value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

std::vector<std::string> Split(const std::string& value, char delimiter) {
    std::vector<std::string> out;
    std::stringstream stream(value);
    std::string part;
    while (std::getline(stream, part, delimiter)) {
        part = Trim(std::move(part));
        if (!part.empty()) out.push_back(std::move(part));
    }
    return out;
}

std::wstring Utf8ToWide(const std::string& input) {
    if (input.empty()) return {};
    const int size = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, input.data(),
                                         static_cast<int>(input.size()), nullptr, 0);
    if (size <= 0) return {};
    std::wstring out(static_cast<std::size_t>(size), L'\0');
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, input.data(),
                            static_cast<int>(input.size()), out.data(), size) <= 0) return {};
    return out;
}

std::filesystem::path LocalStateDirectory() {
    wchar_t buffer[32768]{};
    const DWORD size = GetEnvironmentVariableW(L"LOCALAPPDATA", buffer, 32768);
    std::filesystem::path base = (size > 0 && size < 32768)
        ? std::filesystem::path(buffer) : std::filesystem::temp_directory_path();
    std::filesystem::path out = base / L"Nautrix";
    std::error_code ec;
    std::filesystem::create_directories(out, ec);
    return out;
}

std::string ReadKey(const std::filesystem::path& path, const std::string& wanted,
                    const std::string& fallback = {}) {
    std::ifstream input(path);
    std::string line;
    while (std::getline(input, line)) {
        line = Trim(std::move(line));
        if (line.empty() || line[0] == '#' || line[0] == ';') continue;
        const auto pos = line.find('=');
        if (pos == std::string::npos) continue;
        if (Trim(line.substr(0, pos)) == wanted) return Trim(line.substr(pos + 1));
    }
    return fallback;
}

std::vector<Provider> LoadProviders(const std::filesystem::path& path) {
    std::vector<Provider> providers;
    std::ifstream input(path);
    std::string line;
    while (std::getline(input, line)) {
        line = Trim(std::move(line));
        if (line.rfind("provider=", 0) != 0) continue;
        const auto parts = Split(line.substr(9), '|');
        if (parts.size() < 2) continue;
        Provider p;
        p.id = parts[0];
        p.nameservers = Split(parts[1], ',');
        if (parts.size() > 2) p.doh = parts[2];
        if (!p.id.empty()) providers.push_back(std::move(p));
    }
    return providers;
}

std::string Lower(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return value;
}

bool HostMatches(const std::string& host, const std::vector<std::string>& suffixes) {
    const std::string lower = Lower(host);
    for (std::string suffix : suffixes) {
        suffix = Lower(Trim(std::move(suffix)));
        if (suffix.empty()) continue;
        if (lower == suffix) return true;
        if (lower.size() > suffix.size() &&
            lower.compare(lower.size() - suffix.size(), suffix.size(), suffix) == 0 &&
            lower[lower.size() - suffix.size() - 1] == '.') return true;
    }
    return false;
}

std::optional<std::string> ParseQuestionHost(const std::vector<std::uint8_t>& packet) {
    if (packet.size() < 17) return std::nullopt;
    std::size_t offset = 12;
    std::string host;
    while (offset < packet.size()) {
        const std::uint8_t length = packet[offset++];
        if (length == 0) break;
        if ((length & 0xC0) != 0 || length > 63 || offset + length > packet.size()) return std::nullopt;
        if (!host.empty()) host.push_back('.');
        host.append(reinterpret_cast<const char*>(packet.data() + offset), length);
        offset += length;
    }
    if (host.empty()) return std::nullopt;
    return Lower(host);
}

std::optional<std::vector<std::uint8_t>> DohRequest(const Provider& provider,
                                                     const std::vector<std::uint8_t>& query,
                                                     int timeout_ms,
                                                     double* elapsed_ms) {
    if (provider.doh.empty() || provider.doh.find('{') != std::string::npos) return std::nullopt;
    const std::wstring url = Utf8ToWide(provider.doh);
    if (url.empty()) return std::nullopt;
    URL_COMPONENTSW parts{};
    parts.dwStructSize = sizeof(parts);
    parts.dwSchemeLength = static_cast<DWORD>(-1);
    parts.dwHostNameLength = static_cast<DWORD>(-1);
    parts.dwUrlPathLength = static_cast<DWORD>(-1);
    parts.dwExtraInfoLength = static_cast<DWORD>(-1);
    if (!WinHttpCrackUrl(url.c_str(), 0, 0, &parts)) return std::nullopt;
    std::wstring host(parts.lpszHostName, parts.dwHostNameLength);
    std::wstring path(parts.lpszUrlPath, parts.dwUrlPathLength);
    if (parts.dwExtraInfoLength && parts.lpszExtraInfo) path.append(parts.lpszExtraInfo, parts.dwExtraInfoLength);
    if (path.empty()) path = L"/";

    InternetHandle session(WinHttpOpen(L"Nautrix-Origin-DNS/1.0", WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY,
                                       WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0));
    if (!session.value) return std::nullopt;
    WinHttpSetTimeouts(session.value, timeout_ms, timeout_ms, timeout_ms, timeout_ms);
    InternetHandle connection(WinHttpConnect(session.value, host.c_str(), parts.nPort, 0));
    if (!connection.value) return std::nullopt;
    const DWORD flags = parts.nScheme == INTERNET_SCHEME_HTTPS ? WINHTTP_FLAG_SECURE : 0;
    InternetHandle request(WinHttpOpenRequest(connection.value, L"POST", path.c_str(), nullptr,
                                              WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, flags));
    if (!request.value) return std::nullopt;
    const wchar_t headers[] = L"Content-Type: application/dns-message\r\nAccept: application/dns-message\r\n";
    WinHttpAddRequestHeaders(request.value, headers, static_cast<DWORD>(-1),
                             WINHTTP_ADDREQ_FLAG_ADD | WINHTTP_ADDREQ_FLAG_REPLACE);
    const auto started = Clock::now();
    if (!WinHttpSendRequest(request.value, WINHTTP_NO_ADDITIONAL_HEADERS, 0,
                            const_cast<std::uint8_t*>(query.data()), static_cast<DWORD>(query.size()),
                            static_cast<DWORD>(query.size()), 0) ||
        !WinHttpReceiveResponse(request.value, nullptr)) return std::nullopt;
    DWORD status = 0;
    DWORD status_size = sizeof(status);
    if (!WinHttpQueryHeaders(request.value, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                             WINHTTP_HEADER_NAME_BY_INDEX, &status, &status_size,
                             WINHTTP_NO_HEADER_INDEX) || status != 200) return std::nullopt;
    std::vector<std::uint8_t> response;
    for (;;) {
        DWORD available = 0;
        if (!WinHttpQueryDataAvailable(request.value, &available)) return std::nullopt;
        if (!available) break;
        if (response.size() + available > 65535) return std::nullopt;
        const std::size_t old = response.size();
        response.resize(old + available);
        DWORD read = 0;
        if (!WinHttpReadData(request.value, response.data() + old, available, &read)) return std::nullopt;
        response.resize(old + read);
    }
    if (response.size() < 12) return std::nullopt;
    if (elapsed_ms) {
        *elapsed_ms = std::chrono::duration<double, std::milli>(Clock::now() - started).count();
    }
    return response;
}

std::optional<std::vector<std::uint8_t>> UdpRequest(const Provider& provider,
                                                     const std::vector<std::uint8_t>& query,
                                                     int timeout_ms,
                                                     double* elapsed_ms) {
    for (const std::string& server : provider.nameservers) {
        sockaddr_storage address{};
        int address_length = 0;
        int family = AF_UNSPEC;
        sockaddr_in a4{};
        if (InetPtonA(AF_INET, server.c_str(), &a4.sin_addr) == 1) {
            a4.sin_family = AF_INET; a4.sin_port = htons(53);
            std::memcpy(&address, &a4, sizeof(a4)); address_length = sizeof(a4); family = AF_INET;
        } else {
            sockaddr_in6 a6{};
            if (InetPtonA(AF_INET6, server.c_str(), &a6.sin6_addr) != 1) continue;
            a6.sin6_family = AF_INET6; a6.sin6_port = htons(53);
            std::memcpy(&address, &a6, sizeof(a6)); address_length = sizeof(a6); family = AF_INET6;
        }
        SOCKET socket_handle = socket(family, SOCK_DGRAM, IPPROTO_UDP);
        if (socket_handle == INVALID_SOCKET) continue;
        const DWORD timeout = static_cast<DWORD>(timeout_ms);
        setsockopt(socket_handle, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
        const auto started = Clock::now();
        const int sent = sendto(socket_handle, reinterpret_cast<const char*>(query.data()),
                                static_cast<int>(query.size()), 0,
                                reinterpret_cast<const sockaddr*>(&address), address_length);
        std::uint8_t buffer[65535]{};
        int received = SOCKET_ERROR;
        if (sent == static_cast<int>(query.size())) {
            sockaddr_storage source{}; int source_len = sizeof(source);
            received = recvfrom(socket_handle, reinterpret_cast<char*>(buffer), sizeof(buffer), 0,
                                reinterpret_cast<sockaddr*>(&source), &source_len);
        }
        closesocket(socket_handle);
        if (received >= 12) {
            if (elapsed_ms) *elapsed_ms = std::chrono::duration<double, std::milli>(Clock::now() - started).count();
            return std::vector<std::uint8_t>(buffer, buffer + received);
        }
    }
    return std::nullopt;
}

std::optional<Answer> QueryProvider(const Provider& provider,
                                    const std::vector<std::uint8_t>& query,
                                    int timeout_ms) {
    double elapsed = 1e9;
    auto response = DohRequest(provider, query, timeout_ms, &elapsed);
    if (!response) response = UdpRequest(provider, query, timeout_ms, &elapsed);
    if (!response) return std::nullopt;
    return Answer{provider.id, std::move(*response), elapsed};
}

std::optional<Answer> RaceProviders(const std::vector<Provider>& providers,
                                    const std::vector<std::uint8_t>& query,
                                    int timeout_ms) {
    std::vector<std::future<std::optional<Answer>>> futures;
    futures.reserve(providers.size());
    for (const Provider& provider : providers) {
        futures.emplace_back(std::async(std::launch::async, [provider, query, timeout_ms] {
            return QueryProvider(provider, query, timeout_ms);
        }));
    }
    std::optional<Answer> best;
    for (auto& future : futures) {
        auto result = future.get();
        if (result && (!best || result->elapsed_ms < best->elapsed_ms)) best = std::move(result);
    }
    return best;
}

std::map<std::string, Route> LoadRoutes(const std::filesystem::path& path) {
    std::map<std::string, Route> routes;
    std::ifstream input(path);
    std::string line;
    while (std::getline(input, line)) {
        const auto parts = Split(line, '|');
        if (parts.size() != 4) continue;
        try {
            routes[Lower(parts[0])] = Route{parts[1], std::stod(parts[2]), std::stoll(parts[3])};
        } catch (...) {}
    }
    return routes;
}

void SaveRoutes(const std::filesystem::path& path, const std::map<std::string, Route>& routes) {
    const auto temporary = path.wstring() + L".tmp";
    std::ofstream out(temporary, std::ios::trunc);
    for (const auto& [host, route] : routes) {
        out << host << '|' << route.provider << '|' << std::fixed << std::setprecision(3)
            << route.score_ms << '|' << route.selected_at << '\n';
    }
    out.close();
    std::error_code ec;
    std::filesystem::rename(temporary, path, ec);
    if (ec) {
        std::filesystem::remove(path, ec);
        ec.clear();
        std::filesystem::rename(temporary, path, ec);
    }
}

const Provider* FindProvider(const std::vector<Provider>& providers, const std::string& id) {
    const auto it = std::find_if(providers.begin(), providers.end(), [&](const Provider& p) { return p.id == id; });
    return it == providers.end() ? nullptr : &*it;
}

std::int64_t EpochSeconds() {
    return static_cast<std::int64_t>(std::time(nullptr));
}

std::wstring Quote(const std::wstring& value) {
    return L"\"" + value + L"\"";
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
    WSADATA winsock{};
    if (WSAStartup(MAKEWORD(2, 2), &winsock) != 0) return 1;

    std::filesystem::path config_dir = std::filesystem::current_path() / L"config";
    for (int i = 1; i < argc; ++i) {
        std::wstring arg(argv[i]);
        constexpr std::wstring_view prefix = L"--config-dir=";
        if (arg.rfind(prefix, 0) == 0) config_dir = arg.substr(prefix.size());
    }

    const auto dns_path = config_dir / L"dns.ini";
    const auto latency_path = config_dir / L"latency.ini";
    const auto providers = LoadProviders(dns_path);
    if (providers.empty()) {
        std::cerr << "[NautrixDnsRouter] No DNS providers configured.\n";
        WSACleanup();
        return 2;
    }

    int port = 53;
    int ttl_minutes = 30;
    int timeout_ms = 1400;
    double hysteresis = 8.0;
    try { port = std::clamp(std::stoi(ReadKey(latency_path, "origin_dns_router_port", "53")), 1, 65535); } catch (...) {}
    try { ttl_minutes = std::clamp(std::stoi(ReadKey(latency_path, "origin_route_ttl_minutes", "30")), 1, 1440); } catch (...) {}
    try { hysteresis = std::clamp(std::stod(ReadKey(latency_path, "origin_route_hysteresis_percent", "8")), 0.0, 50.0); } catch (...) {}
    try { timeout_ms = std::clamp(std::stoi(ReadKey(dns_path, "timeout_ms", "700")) * 2, 300, 5000); } catch (...) {}
    const auto routed_sites = Split(ReadKey(latency_path, "origin_route_sites"), ',');

    const auto state_dir = LocalStateDirectory();
    const auto state_path = state_dir / L"origin-routes.state";
    const auto metrics_path = state_dir / L"dns-router-metrics.csv";
    std::map<std::string, Route> routes = LoadRoutes(state_path);
    std::mutex route_mutex;
    std::mutex log_mutex;
    std::string default_provider;

    SOCKET listen_socket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (listen_socket == INVALID_SOCKET) { WSACleanup(); return 3; }
    sockaddr_in local{};
    local.sin_family = AF_INET;
    local.sin_port = htons(static_cast<u_short>(port));
    InetPtonA(AF_INET, "127.0.0.1", &local.sin_addr);
    if (bind(listen_socket, reinterpret_cast<const sockaddr*>(&local), sizeof(local)) != 0) {
        std::cerr << "[NautrixDnsRouter] Cannot bind 127.0.0.1:" << port << ". Another router may already be running.\n";
        closesocket(listen_socket);
        WSACleanup();
        return 4;
    }
    const DWORD recv_timeout = 1000;
    setsockopt(listen_socket, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&recv_timeout), sizeof(recv_timeout));

    HANDLE ready = CreateEventW(nullptr, TRUE, TRUE, L"Local\\NautrixDnsRouterReady");
    if (ready) SetEvent(ready);
    auto last_activity = Clock::now();

    for (;;) {
        std::uint8_t buffer[65535]{};
        sockaddr_storage client{}; int client_len = sizeof(client);
        const int received = recvfrom(listen_socket, reinterpret_cast<char*>(buffer), sizeof(buffer), 0,
                                      reinterpret_cast<sockaddr*>(&client), &client_len);
        if (received == SOCKET_ERROR) {
            if (WSAGetLastError() == WSAETIMEDOUT) {
                if (Clock::now() - last_activity > std::chrono::minutes(30)) break;
                continue;
            }
            break;
        }
        last_activity = Clock::now();
        std::vector<std::uint8_t> query(buffer, buffer + received);
        const auto host_opt = ParseQuestionHost(query);
        if (!host_opt) continue;
        const std::string host = *host_opt;
        const bool per_origin = HostMatches(host, routed_sites);
        const sockaddr_storage client_copy = client;
        const int client_len_copy = client_len;

        std::thread([&, query = std::move(query), host, per_origin, client_copy, client_len_copy] {
            std::optional<Answer> answer;
            std::string preferred;
            double previous_score = 1e9;
            const std::int64_t now = EpochSeconds();
            {
                std::lock_guard lock(route_mutex);
                const auto it = routes.find(host);
                if (per_origin && it != routes.end() &&
                    now - it->second.selected_at < static_cast<std::int64_t>(ttl_minutes) * 60) {
                    preferred = it->second.provider;
                    previous_score = it->second.score_ms;
                } else if (!per_origin) {
                    preferred = default_provider;
                }
            }

            if (!preferred.empty()) {
                if (const Provider* provider = FindProvider(providers, preferred)) {
                    answer = QueryProvider(*provider, query, timeout_ms);
                }
            }
            if (!answer) answer = RaceProviders(providers, query, timeout_ms);
            if (!answer) return;

            if (per_origin) {
                std::lock_guard lock(route_mutex);
                const auto existing = routes.find(host);
                const bool expired = existing == routes.end() ||
                    now - existing->second.selected_at >= static_cast<std::int64_t>(ttl_minutes) * 60;
                const double needed = previous_score * (1.0 - hysteresis / 100.0);
                if (expired || existing == routes.end() || existing->second.provider == answer->provider ||
                    answer->elapsed_ms < needed) {
                    routes[host] = Route{answer->provider, answer->elapsed_ms, now};
                    SaveRoutes(state_path, routes);
                }
            } else {
                std::lock_guard lock(route_mutex);
                if (default_provider.empty()) default_provider = answer->provider;
            }

            sendto(listen_socket, reinterpret_cast<const char*>(answer->packet.data()),
                   static_cast<int>(answer->packet.size()), 0,
                   reinterpret_cast<const sockaddr*>(&client_copy), client_len_copy);
            {
                std::lock_guard lock(log_mutex);
                const bool new_file = !std::filesystem::exists(metrics_path);
                std::ofstream log(metrics_path, std::ios::app);
                if (new_file) log << "epoch,host,provider,elapsed_ms,per_origin\n";
                log << now << ',' << host << ',' << answer->provider << ','
                    << std::fixed << std::setprecision(3) << answer->elapsed_ms << ','
                    << (per_origin ? 1 : 0) << '\n';
            }
        }).detach();
    }

    if (ready) CloseHandle(ready);
    closesocket(listen_socket);
    WSACleanup();
    return 0;
}
