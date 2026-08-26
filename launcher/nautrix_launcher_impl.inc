#define WIN32_LEAN_AND_MEAN
#define NOMINMAX

#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <winhttp.h>
#include <iphlpapi.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cctype>
#include <cstdint>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <future>
#include <iomanip>
#include <iostream>
#include <limits>
#include <optional>
#include <random>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "iphlpapi.lib")
#pragma comment(lib, "winhttp.lib")

namespace {

using Clock = std::chrono::steady_clock;
constexpr std::uint16_t kDnsTypeA = 1;
constexpr std::uint16_t kDnsTypeAAAA = 28;

struct Provider {
    std::string id;
    std::vector<std::string> nameservers;
    std::string doh_template;
};

struct DnsSettings {
    std::string mode = "automatic";
    bool prefer_encrypted = true;
    int samples = 6;
    int timeout_ms = 700;
    int retest_minutes = 30;
    double minimum_improvement_percent = 12.0;
    int doh_samples = 2;
    double doh_weight = 0.55;
    int connect_timeout_ms = 800;
    int connect_samples = 1;
    double connect_weight = 0.40;
    std::vector<std::string> probe_domains;
    std::vector<std::string> priority_hosts;
    std::vector<Provider> providers;
    std::vector<std::string> manual_nameservers;
    std::string manual_doh_template;
};

struct LatencySettings {
    bool enable_happy_eyeballs_v3 = true;
    bool enable_priority_preconnect = true;
    bool enable_netlog = false;
    bool enable_startup_trace = false;
    bool enable_quic = true;
    std::string process_priority = "above_normal";
    std::vector<std::string> preconnect_origins;
};

struct DnsQueryResult {
    double elapsed_ms = 0.0;
    std::vector<std::string> addresses;
};

struct ProbeStats {
    std::string provider_id;
    std::string endpoint;
    double dns_median_ms = std::numeric_limits<double>::infinity();
    double dns_p95_ms = std::numeric_limits<double>::infinity();
    double dns_jitter_ms = std::numeric_limits<double>::infinity();
    double dns_failure_rate = 1.0;
    double doh_median_ms = std::numeric_limits<double>::infinity();
    double doh_failure_rate = 1.0;
    double tcp_median_ms = std::numeric_limits<double>::infinity();
    double tcp_v4_median_ms = std::numeric_limits<double>::infinity();
    double tcp_v6_median_ms = std::numeric_limits<double>::infinity();
    double tcp_failure_rate = 1.0;
    double score = std::numeric_limits<double>::infinity();
};

struct SelectionState {
    std::string network_signature;
    std::string provider_id;
    double score = std::numeric_limits<double>::infinity();
    std::int64_t selected_at = 0;
};

struct CliOptions {
    std::filesystem::path browser;
    std::filesystem::path config_dir;
    bool benchmark_only = false;
    bool force_dns_retest = false;
    bool force_netlog = false;
    bool force_trace = false;
    std::vector<std::wstring> browser_args;
};

class InternetHandle {
public:
    InternetHandle() = default;
    explicit InternetHandle(HINTERNET handle) : handle_(handle) {}
    ~InternetHandle() { reset(); }
    InternetHandle(const InternetHandle&) = delete;
    InternetHandle& operator=(const InternetHandle&) = delete;
    InternetHandle(InternetHandle&& other) noexcept : handle_(other.handle_) { other.handle_ = nullptr; }
    InternetHandle& operator=(InternetHandle&& other) noexcept {
        if (this != &other) {
            reset();
            handle_ = other.handle_;
            other.handle_ = nullptr;
        }
        return *this;
    }
    HINTERNET get() const noexcept { return handle_; }
    explicit operator bool() const noexcept { return handle_ != nullptr; }
    void reset(HINTERNET next = nullptr) {
        if (handle_) {
            WinHttpCloseHandle(handle_);
        }
        handle_ = next;
    }
private:
    HINTERNET handle_ = nullptr;
};

std::string Trim(std::string value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

std::vector<std::string> Split(const std::string& value, char delimiter) {
    std::vector<std::string> result;
    std::stringstream stream(value);
    std::string item;
    while (std::getline(stream, item, delimiter)) {
        item = Trim(std::move(item));
        if (!item.empty()) result.push_back(std::move(item));
    }
    return result;
}

std::string Join(const std::vector<std::string>& values, std::string_view separator) {
    std::ostringstream output;
    for (size_t i = 0; i < values.size(); ++i) {
        if (i) output << separator;
        output << values[i];
    }
    return output.str();
}

bool ParseBool(const std::string& value, bool fallback) {
    std::string normalized = value;
    std::transform(normalized.begin(), normalized.end(), normalized.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    if (normalized == "1" || normalized == "true" || normalized == "yes" || normalized == "on") return true;
    if (normalized == "0" || normalized == "false" || normalized == "no" || normalized == "off") return false;
    return fallback;
}

std::wstring Utf8ToWide(const std::string& input) {
    if (input.empty()) return {};
    const int size = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, input.data(),
                                         static_cast<int>(input.size()), nullptr, 0);
    if (size <= 0) return {};
    std::wstring output(static_cast<size_t>(size), L'\0');
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, input.data(),
                            static_cast<int>(input.size()), output.data(), size) <= 0) return {};
    return output;
}

std::filesystem::path ExecutableDirectory() {
    std::wstring buffer(32768, L'\0');
    const DWORD size = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (size == 0 || size >= buffer.size()) return std::filesystem::current_path();
    buffer.resize(size);
    return std::filesystem::path(buffer).parent_path();
}

std::filesystem::path LocalStateDirectory() {
    wchar_t buffer[32768]{};
    const DWORD size = GetEnvironmentVariableW(L"LOCALAPPDATA", buffer, static_cast<DWORD>(std::size(buffer)));
    std::filesystem::path base = (size > 0 && size < std::size(buffer))
        ? std::filesystem::path(buffer) : std::filesystem::temp_directory_path();
    std::filesystem::path result = base / L"Nautrix";
    std::error_code error;
    std::filesystem::create_directories(result, error);
    return result;
}

std::optional<std::string> ReadValueLine(const std::filesystem::path& path, const std::string& wanted_key) {
    std::ifstream input(path);
    if (!input) return std::nullopt;
    std::string line;
    while (std::getline(input, line)) {
        line = Trim(std::move(line));
        if (line.empty() || line[0] == '#' || line[0] == ';') continue;
        const auto separator = line.find('=');
        if (separator == std::string::npos) continue;
        if (Trim(line.substr(0, separator)) == wanted_key) return Trim(line.substr(separator + 1));
    }
    return std::nullopt;
}

DnsSettings LoadDnsSettings(const std::filesystem::path& path) {
    DnsSettings settings;
    std::ifstream input(path);
    if (!input) {
        std::cerr << "[Nautrix] DNS config not found: " << path.string() << "\n";
        return settings;
    }
    std::string line;
    while (std::getline(input, line)) {
        line = Trim(std::move(line));
        if (line.empty() || line[0] == '#' || line[0] == ';') continue;
        const auto separator = line.find('=');
        if (separator == std::string::npos) continue;
        const std::string key = Trim(line.substr(0, separator));
        const std::string value = Trim(line.substr(separator + 1));
        try {
            if (key == "mode") settings.mode = value;
            else if (key == "prefer_encrypted") settings.prefer_encrypted = ParseBool(value, settings.prefer_encrypted);
            else if (key == "samples") settings.samples = std::clamp(std::stoi(value), 2, 40);
            else if (key == "timeout_ms") settings.timeout_ms = std::clamp(std::stoi(value), 100, 5000);
            else if (key == "retest_minutes") settings.retest_minutes = std::clamp(std::stoi(value), 1, 1440);
            else if (key == "minimum_improvement_percent") settings.minimum_improvement_percent = std::clamp(std::stod(value), 0.0, 50.0);
            else if (key == "doh_samples") settings.doh_samples = std::clamp(std::stoi(value), 0, 10);
            else if (key == "doh_weight") settings.doh_weight = std::clamp(std::stod(value), 0.0, 2.0);
            else if (key == "connect_timeout_ms") settings.connect_timeout_ms = std::clamp(std::stoi(value), 100, 5000);
            else if (key == "connect_samples") settings.connect_samples = std::clamp(std::stoi(value), 1, 5);
            else if (key == "connect_weight") settings.connect_weight = std::clamp(std::stod(value), 0.0, 2.0);
            else if (key == "probe_domains") settings.probe_domains = Split(value, ',');
            else if (key == "priority_hosts") settings.priority_hosts = Split(value, ',');
            else if (key == "manual_nameservers") settings.manual_nameservers = Split(value, ',');
            else if (key == "manual_doh_template") settings.manual_doh_template = value;
            else if (key == "provider") {
                const auto parts = Split(value, '|');
                if (parts.size() >= 2) {
                    Provider provider;
                    provider.id = parts[0];
                    provider.nameservers = Split(parts[1], ',');
                    if (parts.size() >= 3) provider.doh_template = parts[2];
                    if (!provider.id.empty() && !provider.nameservers.empty()) settings.providers.push_back(std::move(provider));
                }
            }
        } catch (...) {
            std::cerr << "[Nautrix] Ignoring invalid DNS setting: " << key << "\n";
        }
    }
    if (settings.probe_domains.empty()) {
        settings.probe_domains = {"example.com", "cloudflare.com", "microsoft.com", "google.com"};
    }
    return settings;
}

LatencySettings LoadLatencySettings(const std::filesystem::path& path) {
    LatencySettings settings;
    if (const auto v = ReadValueLine(path, "enable_happy_eyeballs_v3")) settings.enable_happy_eyeballs_v3 = ParseBool(*v, settings.enable_happy_eyeballs_v3);
    if (const auto v = ReadValueLine(path, "enable_priority_preconnect")) settings.enable_priority_preconnect = ParseBool(*v, settings.enable_priority_preconnect);
    if (const auto v = ReadValueLine(path, "enable_netlog")) settings.enable_netlog = ParseBool(*v, settings.enable_netlog);
    if (const auto v = ReadValueLine(path, "enable_startup_trace")) settings.enable_startup_trace = ParseBool(*v, settings.enable_startup_trace);
    if (const auto v = ReadValueLine(path, "enable_quic")) settings.enable_quic = ParseBool(*v, settings.enable_quic);
    if (const auto v = ReadValueLine(path, "process_priority")) settings.process_priority = *v;
    if (const auto v = ReadValueLine(path, "preconnect_origins")) settings.preconnect_origins = Split(*v, ',');
    return settings;
}

std::vector<std::uint8_t> BuildDnsQuery(const std::string& domain, std::uint16_t id, std::uint16_t qtype) {
    std::vector<std::uint8_t> packet(12, 0);
    packet[0] = static_cast<std::uint8_t>(id >> 8);
    packet[1] = static_cast<std::uint8_t>(id & 0xff);
    packet[2] = 0x01;
    packet[5] = 0x01;
    size_t start = 0;
    while (start < domain.size()) {
        const size_t end = domain.find('.', start);
        const size_t length = (end == std::string::npos ? domain.size() : end) - start;
        if (length == 0 || length > 63) return {};
        packet.push_back(static_cast<std::uint8_t>(length));
        packet.insert(packet.end(), domain.begin() + static_cast<std::ptrdiff_t>(start),
                      domain.begin() + static_cast<std::ptrdiff_t>(start + length));
        if (end == std::string::npos) break;
        start = end + 1;
    }
    packet.push_back(0);
    packet.push_back(static_cast<std::uint8_t>(qtype >> 8));
    packet.push_back(static_cast<std::uint8_t>(qtype & 0xff));
    packet.push_back(0);
    packet.push_back(1);
    return packet;
}

std::uint16_t ReadU16(const std::uint8_t* data) {
    return static_cast<std::uint16_t>((static_cast<std::uint16_t>(data[0]) << 8) | data[1]);
}

bool SkipDnsName(const std::uint8_t* response, size_t response_size, size_t* offset) {
    if (!offset || *offset >= response_size) return false;
    while (*offset < response_size) {
        const std::uint8_t length = response[*offset];
        if (length == 0) { ++(*offset); return true; }
        if ((length & 0xC0) == 0xC0) {
            if (*offset + 1 >= response_size) return false;
            *offset += 2;
            return true;
        }
        if ((length & 0xC0) != 0 || length > 63 || *offset + 1 + length > response_size) return false;
        *offset += 1 + length;
    }
    return false;
}

std::vector<std::string> ParseDnsAddresses(const std::uint8_t* response, size_t response_size) {
    std::vector<std::string> addresses;
    if (response_size < 12) return addresses;
    const std::uint16_t questions = ReadU16(response + 4);
    const std::uint32_t records = static_cast<std::uint32_t>(ReadU16(response + 6)) +
                                  ReadU16(response + 8) + ReadU16(response + 10);
    size_t offset = 12;
    for (std::uint16_t i = 0; i < questions; ++i) {
        if (!SkipDnsName(response, response_size, &offset) || offset + 4 > response_size) return {};
        offset += 4;
    }
    for (std::uint32_t i = 0; i < records; ++i) {
        if (!SkipDnsName(response, response_size, &offset) || offset + 10 > response_size) break;
        const std::uint16_t type = ReadU16(response + offset);
        const std::uint16_t klass = ReadU16(response + offset + 2);
        const std::uint16_t rdlength = ReadU16(response + offset + 8);
        offset += 10;
        if (offset + rdlength > response_size) break;
        char literal[INET6_ADDRSTRLEN]{};
        if (klass == 1 && type == kDnsTypeA && rdlength == 4 &&
            InetNtopA(AF_INET, const_cast<std::uint8_t*>(response + offset), literal, sizeof(literal))) {
            addresses.emplace_back(literal);
        } else if (klass == 1 && type == kDnsTypeAAAA && rdlength == 16 &&
                   InetNtopA(AF_INET6, const_cast<std::uint8_t*>(response + offset), literal, sizeof(literal))) {
            addresses.emplace_back(literal);
        }
        offset += rdlength;
    }
    return addresses;
}

std::uint16_t RandomDnsId() {
    static thread_local std::mt19937 engine(std::random_device{}());
    static thread_local std::uniform_int_distribution<std::uint16_t> dist(1, 65535);
    return dist(engine);
}

std::optional<DnsQueryResult> QueryDns(const std::string& server, const std::string& domain,
                                       std::uint16_t qtype, int timeout_ms) {
    sockaddr_storage address{};
    int address_length = 0;
    int family = AF_UNSPEC;
    sockaddr_in a4{};
    if (InetPtonA(AF_INET, server.c_str(), &a4.sin_addr) == 1) {
        a4.sin_family = AF_INET; a4.sin_port = htons(53);
        std::memcpy(&address, &a4, sizeof(a4)); address_length = sizeof(a4); family = AF_INET;
    } else {
        sockaddr_in6 a6{};
        if (InetPtonA(AF_INET6, server.c_str(), &a6.sin6_addr) != 1) return std::nullopt;
        a6.sin6_family = AF_INET6; a6.sin6_port = htons(53);
        std::memcpy(&address, &a6, sizeof(a6)); address_length = sizeof(a6); family = AF_INET6;
    }
    SOCKET s = socket(family, SOCK_DGRAM, IPPROTO_UDP);
    if (s == INVALID_SOCKET) return std::nullopt;
    const DWORD timeout = static_cast<DWORD>(timeout_ms);
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
    setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
    const std::uint16_t id = RandomDnsId();
    const auto request = BuildDnsQuery(domain, id, qtype);
    if (request.empty()) { closesocket(s); return std::nullopt; }
    const auto started = Clock::now();
    const int sent = sendto(s, reinterpret_cast<const char*>(request.data()), static_cast<int>(request.size()), 0,
                            reinterpret_cast<const sockaddr*>(&address), address_length);
    if (sent != static_cast<int>(request.size())) { closesocket(s); return std::nullopt; }
    std::uint8_t response[4096]{};
    sockaddr_storage source{}; int source_length = sizeof(source);
    const int received = recvfrom(s, reinterpret_cast<char*>(response), sizeof(response), 0,
                                  reinterpret_cast<sockaddr*>(&source), &source_length);
    const auto finished = Clock::now();
    closesocket(s);
    if (received < 12) return std::nullopt;
    if (ReadU16(response) != id || (response[2] & 0x80) == 0 || (response[2] & 0x02) != 0 || (response[3] & 0x0f) != 0) return std::nullopt;
    return DnsQueryResult{std::chrono::duration<double, std::milli>(finished - started).count(),
                          ParseDnsAddresses(response, static_cast<size_t>(received))};
}

std::optional<DnsQueryResult> QueryDoh(const std::string& endpoint, const std::string& domain,
                                       std::uint16_t qtype, int timeout_ms) {
    if (endpoint.empty() || endpoint.find('{') != std::string::npos) return std::nullopt;
    std::wstring url = Utf8ToWide(endpoint);
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
    InternetHandle session(WinHttpOpen(L"Nautrix-DNS-Benchmark/1.0", WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY,
                                       WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0));
    if (!session) return std::nullopt;
    WinHttpSetTimeouts(session.get(), timeout_ms, timeout_ms, timeout_ms, timeout_ms);
    InternetHandle connection(WinHttpConnect(session.get(), host.c_str(), parts.nPort, 0));
    if (!connection) return std::nullopt;
    const DWORD flags = parts.nScheme == INTERNET_SCHEME_HTTPS ? WINHTTP_FLAG_SECURE : 0;
    InternetHandle request(WinHttpOpenRequest(connection.get(), L"POST", path.c_str(), nullptr,
                                              WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, flags));
    if (!request) return std::nullopt;
    const wchar_t headers[] = L"Content-Type: application/dns-message\r\nAccept: application/dns-message\r\n";
    WinHttpAddRequestHeaders(request.get(), headers, static_cast<DWORD>(-1), WINHTTP_ADDREQ_FLAG_ADD | WINHTTP_ADDREQ_FLAG_REPLACE);
    const std::uint16_t id = RandomDnsId();
    const auto packet = BuildDnsQuery(domain, id, qtype);
    if (packet.empty()) return std::nullopt;
    const auto started = Clock::now();
    if (!WinHttpSendRequest(request.get(), WINHTTP_NO_ADDITIONAL_HEADERS, 0,
                            const_cast<std::uint8_t*>(packet.data()), static_cast<DWORD>(packet.size()),
                            static_cast<DWORD>(packet.size()), 0) ||
        !WinHttpReceiveResponse(request.get(), nullptr)) return std::nullopt;
    DWORD status = 0; DWORD status_size = sizeof(status);
    if (!WinHttpQueryHeaders(request.get(), WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                             WINHTTP_HEADER_NAME_BY_INDEX, &status, &status_size, WINHTTP_NO_HEADER_INDEX) || status != 200) return std::nullopt;
    std::vector<std::uint8_t> response;
    for (;;) {
        DWORD available = 0;
        if (!WinHttpQueryDataAvailable(request.get(), &available)) return std::nullopt;
        if (available == 0) break;
        if (response.size() + available > 65535) return std::nullopt;
        const size_t old = response.size();
        response.resize(old + available);
        DWORD read = 0;
        if (!WinHttpReadData(request.get(), response.data() + old, available, &read)) return std::nullopt;
        response.resize(old + read);
    }
    const auto finished = Clock::now();
    if (response.size() < 12 || ReadU16(response.data()) != id || (response[3] & 0x0f) != 0) return std::nullopt;
    return DnsQueryResult{std::chrono::duration<double, std::milli>(finished - started).count(),
                          ParseDnsAddresses(response.data(), response.size())};
}

std::optional<double> ConnectTcp443(const std::string& literal, int timeout_ms) {
    sockaddr_storage address{}; int address_length = 0; int family = AF_UNSPEC;
    sockaddr_in a4{};
    if (InetPtonA(AF_INET, literal.c_str(), &a4.sin_addr) == 1) {
        a4.sin_family = AF_INET; a4.sin_port = htons(443);
        std::memcpy(&address, &a4, sizeof(a4)); address_length = sizeof(a4); family = AF_INET;
    } else {
        sockaddr_in6 a6{};
        if (InetPtonA(AF_INET6, literal.c_str(), &a6.sin6_addr) != 1) return std::nullopt;
        a6.sin6_family = AF_INET6; a6.sin6_port = htons(443);
        std::memcpy(&address, &a6, sizeof(a6)); address_length = sizeof(a6); family = AF_INET6;
    }
    SOCKET s = socket(family, SOCK_STREAM, IPPROTO_TCP);
    if (s == INVALID_SOCKET) return std::nullopt;
    u_long nonblocking = 1;
    if (ioctlsocket(s, FIONBIO, &nonblocking) != 0) { closesocket(s); return std::nullopt; }
    const auto started = Clock::now();
    const int result = connect(s, reinterpret_cast<const sockaddr*>(&address), address_length);
    if (result == SOCKET_ERROR) {
        const int error = WSAGetLastError();
        if (error != WSAEWOULDBLOCK && error != WSAEINPROGRESS) { closesocket(s); return std::nullopt; }
    }
    fd_set write_set; FD_ZERO(&write_set); FD_SET(s, &write_set);
    timeval timeout{}; timeout.tv_sec = timeout_ms / 1000; timeout.tv_usec = (timeout_ms % 1000) * 1000;
    const int selected = select(0, nullptr, &write_set, nullptr, &timeout);
    if (selected <= 0 || !FD_ISSET(s, &write_set)) { closesocket(s); return std::nullopt; }
    int socket_error = 0; int error_length = sizeof(socket_error);
    if (getsockopt(s, SOL_SOCKET, SO_ERROR, reinterpret_cast<char*>(&socket_error), &error_length) != 0 || socket_error != 0) {
        closesocket(s); return std::nullopt;
    }
    const auto finished = Clock::now();
    closesocket(s);
    return std::chrono::duration<double, std::milli>(finished - started).count();
}

std::optional<double> Median(std::vector<double> values) {
    if (values.empty()) return std::nullopt;
    std::sort(values.begin(), values.end());
    const size_t middle = values.size() / 2;
    return values.size() % 2 ? values[middle] : (values[middle - 1] + values[middle]) / 2.0;
}

ProbeStats BenchmarkEndpoint(const Provider& provider, const std::string& endpoint, const DnsSettings& settings) {
    ProbeStats stats; stats.provider_id = provider.id; stats.endpoint = endpoint;
    std::vector<double> dns_samples;
    int dns_failures = 0;
    for (int i = 0; i < settings.samples; ++i) {
        const auto& domain = settings.probe_domains[static_cast<size_t>(i) % settings.probe_domains.size()];
        const std::uint16_t qtype = (i % 2 == 0) ? kDnsTypeA : kDnsTypeAAAA;
        const auto result = QueryDns(endpoint, domain, qtype, settings.timeout_ms);
        if (result) dns_samples.push_back(result->elapsed_ms); else ++dns_failures;
    }
    stats.dns_failure_rate = static_cast<double>(dns_failures) / settings.samples;
    if (!dns_samples.empty()) {
        std::sort(dns_samples.begin(), dns_samples.end());
        stats.dns_median_ms = *Median(dns_samples);
        const size_t p95_index = std::min(dns_samples.size() - 1,
            static_cast<size_t>(std::ceil(dns_samples.size() * 0.95) - 1.0));
        stats.dns_p95_ms = dns_samples[p95_index];
        double squares = 0.0;
        for (double value : dns_samples) {
            const double delta = value - stats.dns_median_ms;
            squares += delta * delta;
        }
        stats.dns_jitter_ms = std::sqrt(squares / dns_samples.size());
        const double tail = std::max(0.0, stats.dns_p95_ms - stats.dns_median_ms);
        stats.score = stats.dns_median_ms + 0.35 * tail + 0.20 * stats.dns_jitter_ms +
                      stats.dns_failure_rate * settings.timeout_ms * 2.0;
    } else {
        stats.score = settings.timeout_ms * 10.0;
    }

    if (settings.prefer_encrypted && settings.doh_samples > 0 && !provider.doh_template.empty()) {
        std::vector<double> doh_samples;
        int failures = 0;
        for (int i = 0; i < settings.doh_samples; ++i) {
            const auto& domain = settings.probe_domains[static_cast<size_t>(i) % settings.probe_domains.size()];
            const auto result = QueryDoh(provider.doh_template, domain, i % 2 ? kDnsTypeAAAA : kDnsTypeA, settings.timeout_ms * 2);
            if (result) doh_samples.push_back(result->elapsed_ms); else ++failures;
        }
        stats.doh_failure_rate = static_cast<double>(failures) / settings.doh_samples;
        if (const auto median = Median(doh_samples)) {
            stats.doh_median_ms = *median;
            stats.score += settings.doh_weight * *median;
        }
        stats.score += stats.doh_failure_rate * settings.timeout_ms;
    }

    if (!settings.priority_hosts.empty() && settings.connect_weight > 0.0) {
        std::vector<double> all_connect;
        std::vector<double> v4_connect;
        std::vector<double> v6_connect;
        int attempts = 0;
        int failures = 0;
        for (const std::string& host : settings.priority_hosts) {
            for (int sample = 0; sample < settings.connect_samples; ++sample) {
                for (std::uint16_t qtype : {kDnsTypeA, kDnsTypeAAAA}) {
                    ++attempts;
                    const auto resolved = QueryDns(endpoint, host, qtype, settings.timeout_ms);
                    if (!resolved || resolved->addresses.empty()) { ++failures; continue; }
                    std::optional<double> best;
                    size_t tested = 0;
                    for (const auto& address : resolved->addresses) {
                        if (tested++ >= 4) break;
                        const auto elapsed = ConnectTcp443(address, settings.connect_timeout_ms);
                        if (elapsed && (!best || *elapsed < *best)) best = elapsed;
                    }
                    if (!best) { ++failures; continue; }
                    all_connect.push_back(*best);
                    if (qtype == kDnsTypeA) v4_connect.push_back(*best); else v6_connect.push_back(*best);
                }
            }
        }
        if (attempts > 0) stats.tcp_failure_rate = static_cast<double>(failures) / attempts;
        if (const auto median = Median(all_connect)) { stats.tcp_median_ms = *median; stats.score += settings.connect_weight * *median; }
        if (const auto median = Median(v4_connect)) stats.tcp_v4_median_ms = *median;
        if (const auto median = Median(v6_connect)) stats.tcp_v6_median_ms = *median;
        stats.score += stats.tcp_failure_rate * settings.connect_timeout_ms * settings.connect_weight;
    }
    return stats;
}

ProbeStats BenchmarkProvider(const Provider& provider, const DnsSettings& settings) {
    ProbeStats best; best.provider_id = provider.id;
    for (const auto& endpoint : provider.nameservers) {
        ProbeStats current = BenchmarkEndpoint(provider, endpoint, settings);
        if (current.score < best.score) best = std::move(current);
    }
    return best;
}

std::string NumericAddress(const SOCKET_ADDRESS& socket_address) {
    if (!socket_address.lpSockaddr || socket_address.iSockaddrLength <= 0) return {};
    char host[NI_MAXHOST]{};
    if (getnameinfo(socket_address.lpSockaddr, socket_address.iSockaddrLength, host, sizeof(host), nullptr, 0, NI_NUMERICHOST) != 0) return {};
    return host;
}

std::string NetworkSignature() {
    ULONG buffer_size = 0;
    const ULONG flags = GAA_FLAG_SKIP_ANYCAST | GAA_FLAG_SKIP_MULTICAST | GAA_FLAG_SKIP_FRIENDLY_NAME;
    GetAdaptersAddresses(AF_UNSPEC, flags, nullptr, nullptr, &buffer_size);
    if (!buffer_size) return "unknown";
    std::vector<std::uint8_t> buffer(buffer_size);
    auto* adapters = reinterpret_cast<IP_ADAPTER_ADDRESSES*>(buffer.data());
    if (GetAdaptersAddresses(AF_UNSPEC, flags, nullptr, adapters, &buffer_size) != NO_ERROR) return "unknown";
    std::vector<std::string> tokens;
    for (auto* adapter = adapters; adapter; adapter = adapter->Next) {
        if (adapter->OperStatus != IfOperStatusUp) continue;
        if (adapter->AdapterName) tokens.emplace_back(adapter->AdapterName);
        tokens.push_back(std::to_string(adapter->IfType));
        for (auto* u = adapter->FirstUnicastAddress; u; u = u->Next) {
            const auto value = NumericAddress(u->Address); if (!value.empty()) tokens.push_back("U:" + value);
        }
        for (auto* d = adapter->FirstDnsServerAddress; d; d = d->Next) {
            const auto value = NumericAddress(d->Address); if (!value.empty()) tokens.push_back("D:" + value);
        }
    }
    std::sort(tokens.begin(), tokens.end());
    std::uint64_t hash = 1469598103934665603ULL;
    for (const auto& token : tokens) {
        for (unsigned char ch : token) { hash ^= ch; hash *= 1099511628211ULL; }
        hash ^= 0xff; hash *= 1099511628211ULL;
    }
    std::ostringstream output; output << std::hex << hash; return output.str();
}

std::optional<SelectionState> LoadState(const std::filesystem::path& path) {
    std::ifstream input(path); if (!input) return std::nullopt;
    SelectionState state; std::string line;
    while (std::getline(input, line)) {
        const auto separator = line.find('='); if (separator == std::string::npos) continue;
        const auto key = Trim(line.substr(0, separator)); const auto value = Trim(line.substr(separator + 1));
        try {
            if (key == "network_signature") state.network_signature = value;
            else if (key == "provider_id") state.provider_id = value;
            else if (key == "score") state.score = std::stod(value);
            else if (key == "selected_at") state.selected_at = std::stoll(value);
        } catch (...) { return std::nullopt; }
    }
    if (state.network_signature.empty() || state.provider_id.empty() || !std::isfinite(state.score) || state.selected_at <= 0) return std::nullopt;
    return state;
}

void SaveState(const std::filesystem::path& path, const SelectionState& state) {
    std::ofstream output(path, std::ios::trunc); if (!output) return;
    output << "network_signature=" << state.network_signature << "\nprovider_id=" << state.provider_id << "\n";
    output << std::fixed << std::setprecision(3) << "score=" << state.score << "\nselected_at=" << state.selected_at << "\n";
}

void SaveMetrics(const std::filesystem::path& path, const std::vector<ProbeStats>& metrics, const std::string& selected) {
    std::ofstream output(path, std::ios::trunc); if (!output) return;
    output << "selected=" << selected << "\n";
    output << "provider,endpoint,dns_median_ms,dns_p95_ms,jitter_ms,dns_fail_pct,doh_median_ms,doh_fail_pct,tcp_median_ms,tcp_v4_ms,tcp_v6_ms,tcp_fail_pct,score\n";
    output << std::fixed << std::setprecision(3);
    for (const auto& m : metrics) {
        output << m.provider_id << ',' << m.endpoint << ',' << m.dns_median_ms << ',' << m.dns_p95_ms << ','
               << m.dns_jitter_ms << ',' << m.dns_failure_rate * 100.0 << ',' << m.doh_median_ms << ','
               << m.doh_failure_rate * 100.0 << ',' << m.tcp_median_ms << ',' << m.tcp_v4_median_ms << ','
               << m.tcp_v6_median_ms << ',' << m.tcp_failure_rate * 100.0 << ',' << m.score << "\n";
    }
}

const Provider* FindProvider(const DnsSettings& settings, const std::string& id) {
    for (const auto& provider : settings.providers) if (provider.id == id) return &provider;
    return nullptr;
}

const Provider* SelectAutomaticProvider(const DnsSettings& settings, const std::filesystem::path& state_path,
                                        const std::filesystem::path& metrics_path, bool force_retest) {
    if (settings.providers.empty()) return nullptr;
    const std::string signature = NetworkSignature();
    const std::int64_t now = static_cast<std::int64_t>(std::time(nullptr));
    const auto prior = LoadState(state_path);
    if (!force_retest && prior && prior->network_signature == signature) {
        const auto age = now - prior->selected_at;
        if (age >= 0 && age < static_cast<std::int64_t>(settings.retest_minutes) * 60) {
            if (const Provider* cached = FindProvider(settings, prior->provider_id)) {
                std::cout << "[Nautrix] DNS cached winner: " << cached->id << " score=" << prior->score << "\n";
                return cached;
            }
        }
    }
    std::vector<std::future<ProbeStats>> futures;
    for (const auto& provider : settings.providers) {
        futures.push_back(std::async(std::launch::async, [provider, &settings] { return BenchmarkProvider(provider, settings); }));
    }
    std::vector<ProbeStats> metrics(settings.providers.size());
    size_t best_index = settings.providers.size(); double best_score = std::numeric_limits<double>::infinity();
    for (size_t i = 0; i < futures.size(); ++i) {
        metrics[i] = futures[i].get();
        const auto& m = metrics[i];
        std::cout << "[Nautrix] DNS " << m.provider_id << " dns=" << m.dns_median_ms << "ms p95=" << m.dns_p95_ms
                  << "ms jitter=" << m.dns_jitter_ms << "ms fail=" << m.dns_failure_rate * 100.0
                  << "% doh=" << m.doh_median_ms << "ms tcp=" << m.tcp_median_ms << "ms v4=" << m.tcp_v4_median_ms
                  << "ms v6=" << m.tcp_v6_median_ms << "ms score=" << m.score << "\n";
        if (m.score < best_score) { best_score = m.score; best_index = i; }
    }
    if (best_index == settings.providers.size() || !std::isfinite(best_score)) { SaveMetrics(metrics_path, metrics, "system"); return nullptr; }
    if (prior && prior->network_signature == signature) {
        for (size_t i = 0; i < settings.providers.size(); ++i) {
            if (settings.providers[i].id != prior->provider_id || !std::isfinite(metrics[i].score)) continue;
            const double improvement = (metrics[i].score - best_score) / std::max(metrics[i].score, 0.001) * 100.0;
            if (metrics[i].dns_failure_rate <= 0.25 && improvement < settings.minimum_improvement_percent) {
                best_index = i; best_score = metrics[i].score;
            }
            break;
        }
    }
    SelectionState selected{signature, settings.providers[best_index].id, best_score, now};
    SaveState(state_path, selected); SaveMetrics(metrics_path, metrics, selected.provider_id);
    std::cout << "[Nautrix] DNS selected: " << selected.provider_id << " score=" << selected.score << "\n";
    return &settings.providers[best_index];
}

void ClearNautrixEnvironment() {
    for (const wchar_t* name : {L"NAUTRIX_DNS_MODE", L"NAUTRIX_DNS_NAMESERVERS", L"NAUTRIX_DOH_TEMPLATES", L"NAUTRIX_PRECONNECT_ORIGINS"}) {
        SetEnvironmentVariableW(name, nullptr);
    }
}

void ApplyDnsEnvironment(const std::vector<std::string>& nameservers, const std::string& doh_template, bool prefer_encrypted) {
    SetEnvironmentVariableW(L"NAUTRIX_DNS_NAMESERVERS", Utf8ToWide(Join(nameservers, ",")).c_str());
    if (prefer_encrypted && !doh_template.empty()) {
        SetEnvironmentVariableW(L"NAUTRIX_DNS_MODE", L"automatic");
        SetEnvironmentVariableW(L"NAUTRIX_DOH_TEMPLATES", Utf8ToWide(doh_template).c_str());
    } else if (!nameservers.empty()) {
        SetEnvironmentVariableW(L"NAUTRIX_DNS_MODE", L"plain");
    }
}

std::vector<std::string> BuildPreconnectOrigins(const DnsSettings& dns, const LatencySettings& latency) {
    if (!latency.preconnect_origins.empty()) return latency.preconnect_origins;
    std::vector<std::string> origins;
    for (const auto& host : dns.priority_hosts) origins.push_back("https://" + host);
    return origins;
}

void ApplyPreconnectEnvironment(const DnsSettings& dns, const LatencySettings& latency) {
    if (!latency.enable_priority_preconnect) return;
    const auto origins = BuildPreconnectOrigins(dns, latency);
    if (!origins.empty()) SetEnvironmentVariableW(L"NAUTRIX_PRECONNECT_ORIGINS", Utf8ToWide(Join(origins, ",")).c_str());
}

bool StartsWith(const std::wstring& value, std::wstring_view prefix) {
    return value.size() >= prefix.size() && std::equal(prefix.begin(), prefix.end(), value.begin());
}

void EnableFeature(std::vector<std::wstring>* args, const std::wstring& feature) {
    constexpr std::wstring_view prefix = L"--enable-features=";
    for (auto& arg : *args) {
        if (!StartsWith(arg, prefix)) continue;
        std::wstring features = arg.substr(prefix.size());
        bool exists = false;
        std::wstringstream stream(features); std::wstring token;
        while (std::getline(stream, token, L',')) if (token == feature) exists = true;
        if (!exists) { if (!features.empty()) features += L","; features += feature; arg = std::wstring(prefix) + features; }
        return;
    }
    args->push_back(std::wstring(prefix) + feature);
}

bool HasPrefix(const std::vector<std::wstring>& args, std::wstring_view prefix) {
    return std::any_of(args.begin(), args.end(), [&](const auto& arg) { return StartsWith(arg, prefix); });
}

std::wstring QuoteArgument(const std::wstring& argument) {
    if (argument.find_first_of(L" \t\"") == std::wstring::npos) return argument;
    std::wstring output = L"\""; size_t backslashes = 0;
    for (wchar_t ch : argument) {
        if (ch == L'\\') { ++backslashes; continue; }
        if (ch == L'\"') { output.append(backslashes * 2 + 1, L'\\'); output.push_back(L'\"'); backslashes = 0; continue; }
        output.append(backslashes, L'\\'); backslashes = 0; output.push_back(ch);
    }
    output.append(backslashes * 2, L'\\'); output.push_back(L'\"'); return output;
}

std::wstring TimestampName() {
    SYSTEMTIME st{}; GetLocalTime(&st);
    wchar_t buffer[64]{};
    swprintf_s(buffer, L"%04u%02u%02u-%02u%02u%02u", st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
    return buffer;
}

DWORD PriorityClassFor(const std::string& value) {
    if (value == "high") return HIGH_PRIORITY_CLASS;
    if (value == "normal") return NORMAL_PRIORITY_CLASS;
    if (value == "below_normal") return BELOW_NORMAL_PRIORITY_CLASS;
    return ABOVE_NORMAL_PRIORITY_CLASS;
}

int LaunchBrowser(const std::filesystem::path& browser, std::vector<std::wstring> args,
                  const LatencySettings& latency, bool force_netlog, bool force_trace) {
    if (latency.enable_happy_eyeballs_v3) EnableFeature(&args, L"HappyEyeballsV3");
    if (latency.enable_priority_preconnect) EnableFeature(&args, L"PreconnectFromKeyedService");
    if (!latency.enable_quic && !HasPrefix(args, L"--disable-quic")) args.push_back(L"--disable-quic");
    if (!HasPrefix(args, L"--user-data-dir=")) args.push_back(L"--user-data-dir=" + (LocalStateDirectory() / L"User Data").wstring());

    const auto timestamp = TimestampName();
    if (latency.enable_netlog || force_netlog) {
        const auto dir = LocalStateDirectory() / L"NetLog"; std::error_code error; std::filesystem::create_directories(dir, error);
        args.push_back(L"--log-net-log=" + (dir / (L"netlog-" + timestamp + L".json")).wstring());
        args.push_back(L"--net-log-capture-mode=Default");
    }
    if (latency.enable_startup_trace || force_trace) {
        const auto dir = LocalStateDirectory() / L"Traces"; std::error_code error; std::filesystem::create_directories(dir, error);
        args.push_back(L"--trace-startup=benchmark,net,loading,input,disabled-by-default-latencyInfo");
        args.push_back(L"--trace-startup-duration=15");
        args.push_back(L"--trace-startup-file=" + (dir / (L"startup-" + timestamp + L".json")).wstring());
    }

    std::wstring command = QuoteArgument(browser.wstring());
    for (const auto& arg : args) command += L" " + QuoteArgument(arg);
    std::vector<wchar_t> mutable_command(command.begin(), command.end()); mutable_command.push_back(L'\0');
    STARTUPINFOW startup{}; startup.cb = sizeof(startup); PROCESS_INFORMATION process{};
    const std::wstring cwd = browser.parent_path().wstring();
    const auto started = Clock::now();
    if (!CreateProcessW(browser.c_str(), mutable_command.data(), nullptr, nullptr, FALSE, CREATE_SUSPENDED,
                        nullptr, cwd.empty() ? nullptr : cwd.c_str(), &startup, &process)) {
        std::cerr << "[Nautrix] Failed to launch browser. Win32 error=" << GetLastError() << "\n"; return 1;
    }
    SetPriorityClass(process.hProcess, PriorityClassFor(latency.process_priority));
    ResumeThread(process.hThread);
    const auto finished = Clock::now();
    std::ofstream metrics(LocalStateDirectory() / L"launch-metrics.log", std::ios::app);
    if (metrics) metrics << std::time(nullptr) << ",process_create_ms="
                         << std::chrono::duration<double, std::milli>(finished - started).count()
                         << ",pid=" << process.dwProcessId << "\n";
    CloseHandle(process.hThread); CloseHandle(process.hProcess); return 0;
}

CliOptions ParseCli(int argc, wchar_t** argv) {
    CliOptions options;
    options.browser = ExecutableDirectory() / L"chrome.exe";
    options.config_dir = ExecutableDirectory() / L"config";
    for (int i = 1; i < argc; ++i) {
        std::wstring arg = argv[i];
        if (StartsWith(arg, L"--browser=")) options.browser = arg.substr(10);
        else if (StartsWith(arg, L"--config-dir=")) options.config_dir = arg.substr(13);
        else if (arg == L"--benchmark-only") options.benchmark_only = true;
        else if (arg == L"--force-dns-retest") options.force_dns_retest = true;
        else if (arg == L"--nautrix-netlog") options.force_netlog = true;
        else if (arg == L"--nautrix-trace") options.force_trace = true;
        else options.browser_args.push_back(std::move(arg));
    }
    return options;
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
    WSADATA winsock{};
    if (WSAStartup(MAKEWORD(2, 2), &winsock) != 0) {
        std::cerr << "[Nautrix] Winsock initialization failed.\n"; return 1;
    }
    const CliOptions cli = ParseCli(argc, argv);
    const DnsSettings dns = LoadDnsSettings(cli.config_dir / L"dns.ini");
    const LatencySettings latency = LoadLatencySettings(cli.config_dir / L"latency.ini");
    ClearNautrixEnvironment();

    const Provider* selected = nullptr;
    if (dns.mode == "manual") {
        ApplyDnsEnvironment(dns.manual_nameservers, dns.manual_doh_template, dns.prefer_encrypted);
        std::cout << "[Nautrix] DNS mode: manual\n";
    } else if (dns.mode == "automatic") {
        selected = SelectAutomaticProvider(dns, LocalStateDirectory() / L"dns-selection.state",
                                           LocalStateDirectory() / L"dns-metrics.csv",
                                           cli.force_dns_retest || cli.benchmark_only);
        if (selected) ApplyDnsEnvironment(selected->nameservers, selected->doh_template, dns.prefer_encrypted);
        else std::cout << "[Nautrix] Automatic DNS unavailable; using system DNS.\n";
    } else {
        std::cout << "[Nautrix] DNS mode: system\n";
    }

    ApplyPreconnectEnvironment(dns, latency);
    if (cli.benchmark_only) { WSACleanup(); return selected || dns.mode != "automatic" ? 0 : 2; }
    if (!std::filesystem::exists(cli.browser)) {
        std::wcerr << L"[Nautrix] Browser binary not found: " << cli.browser.wstring() << L"\n";
        WSACleanup(); return 1;
    }
    const int result = LaunchBrowser(cli.browser, cli.browser_args, latency, cli.force_netlog, cli.force_trace);
    WSACleanup(); return result;
}
