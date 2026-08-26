#define WIN32_LEAN_AND_MEAN
#define NOMINMAX

#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <iphlpapi.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cctype>
#include <cstring>
#include <ctime>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <future>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <limits>
#include <optional>
#include <random>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "iphlpapi.lib")

namespace {

using Clock = std::chrono::steady_clock;

struct Provider {
    std::string id;
    std::vector<std::string> nameservers;
    std::string doh_template;
};

struct DnsSettings {
    std::string mode = "automatic";
    bool prefer_encrypted = true;
    int samples = 5;
    int timeout_ms = 700;
    int retest_minutes = 30;
    double minimum_improvement_percent = 12.0;
    int connect_timeout_ms = 800;
    int connect_samples = 1;
    double connect_weight = 0.35;
    std::vector<std::string> probe_domains;
    std::vector<std::string> priority_hosts;
    std::vector<Provider> providers;
    std::vector<std::string> manual_nameservers;
    std::string manual_doh_template;
};

struct LatencySettings {
    bool enable_happy_eyeballs_v3 = true;
};

struct ProbeStats {
    double median_ms = std::numeric_limits<double>::infinity();
    double p95_ms = std::numeric_limits<double>::infinity();
    double jitter_ms = std::numeric_limits<double>::infinity();
    double failure_rate = 1.0;
    double connect_median_ms = std::numeric_limits<double>::infinity();
    double connect_failure_rate = 0.0;
    double score = std::numeric_limits<double>::infinity();
    std::string endpoint;
};

struct SelectionState {
    std::string network_signature;
    std::string provider_id;
    double score = std::numeric_limits<double>::infinity();
    std::int64_t selected_at = 0;
};

std::string Trim(std::string value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) {
        return {};
    }
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

std::vector<std::string> Split(const std::string& value, char delimiter) {
    std::vector<std::string> result;
    std::stringstream stream(value);
    std::string item;
    while (std::getline(stream, item, delimiter)) {
        item = Trim(std::move(item));
        if (!item.empty()) {
            result.push_back(std::move(item));
        }
    }
    return result;
}

bool ParseBool(const std::string& value, bool fallback) {
    std::string normalized = value;
    std::transform(normalized.begin(), normalized.end(), normalized.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    if (normalized == "1" || normalized == "true" || normalized == "yes" || normalized == "on") {
        return true;
    }
    if (normalized == "0" || normalized == "false" || normalized == "no" || normalized == "off") {
        return false;
    }
    return fallback;
}

std::wstring Utf8ToWide(const std::string& input) {
    if (input.empty()) {
        return {};
    }
    const int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, input.data(),
                                           static_cast<int>(input.size()), nullptr, 0);
    if (length <= 0) {
        return {};
    }
    std::wstring output(static_cast<size_t>(length), L'\0');
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, input.data(),
                        static_cast<int>(input.size()), output.data(), length);
    return output;
}

std::string WideToUtf8(const std::wstring& input) {
    if (input.empty()) {
        return {};
    }
    const int length = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, input.data(),
                                           static_cast<int>(input.size()), nullptr, 0, nullptr, nullptr);
    if (length <= 0) {
        return {};
    }
    std::string output(static_cast<size_t>(length), '\0');
    WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, input.data(),
                        static_cast<int>(input.size()), output.data(), length, nullptr, nullptr);
    return output;
}

std::filesystem::path ExecutableDirectory() {
    std::wstring buffer(32768, L'\0');
    const DWORD size = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (size == 0 || size >= buffer.size()) {
        return std::filesystem::current_path();
    }
    buffer.resize(size);
    return std::filesystem::path(buffer).parent_path();
}

std::filesystem::path LocalStateDirectory() {
    wchar_t buffer[32768]{};
    const DWORD size = GetEnvironmentVariableW(L"LOCALAPPDATA", buffer, static_cast<DWORD>(std::size(buffer)));
    std::filesystem::path base =
        (size > 0 && size < std::size(buffer)) ? std::filesystem::path(buffer)
                                               : std::filesystem::temp_directory_path();
    std::filesystem::path result = base / L"Nautrix";
    std::error_code error;
    std::filesystem::create_directories(result, error);
    return result;
}

std::optional<std::string> ReadValueLine(const std::filesystem::path& path,
                                         const std::string& wanted_key) {
    std::ifstream input(path);
    if (!input) {
        return std::nullopt;
    }
    std::string line;
    while (std::getline(input, line)) {
        line = Trim(std::move(line));
        if (line.empty() || line[0] == '#' || line[0] == ';') {
            continue;
        }
        const auto separator = line.find('=');
        if (separator == std::string::npos) {
            continue;
        }
        const std::string key = Trim(line.substr(0, separator));
        if (key == wanted_key) {
            return Trim(line.substr(separator + 1));
        }
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
        if (line.empty() || line[0] == '#' || line[0] == ';') {
            continue;
        }
        const auto separator = line.find('=');
        if (separator == std::string::npos) {
            continue;
        }

        const std::string key = Trim(line.substr(0, separator));
        const std::string value = Trim(line.substr(separator + 1));

        try {
            if (key == "mode") {
                settings.mode = value;
            } else if (key == "prefer_encrypted") {
                settings.prefer_encrypted = ParseBool(value, settings.prefer_encrypted);
            } else if (key == "samples") {
                settings.samples = std::clamp(std::stoi(value), 2, 20);
            } else if (key == "timeout_ms") {
                settings.timeout_ms = std::clamp(std::stoi(value), 100, 5000);
            } else if (key == "retest_minutes") {
                settings.retest_minutes = std::clamp(std::stoi(value), 1, 1440);
            } else if (key == "minimum_improvement_percent") {
                settings.minimum_improvement_percent = std::clamp(std::stod(value), 0.0, 50.0);
            } else if (key == "connect_timeout_ms") {
                settings.connect_timeout_ms = std::clamp(std::stoi(value), 100, 5000);
            } else if (key == "connect_samples") {
                settings.connect_samples = std::clamp(std::stoi(value), 1, 5);
            } else if (key == "connect_weight") {
                settings.connect_weight = std::clamp(std::stod(value), 0.0, 2.0);
            } else if (key == "probe_domains") {
                settings.probe_domains = Split(value, ',');
            } else if (key == "priority_hosts") {
                settings.priority_hosts = Split(value, ',');
            } else if (key == "manual_nameservers") {
                settings.manual_nameservers = Split(value, ',');
            } else if (key == "manual_doh_template") {
                settings.manual_doh_template = value;
            } else if (key == "provider") {
                const auto parts = Split(value, '|');
                if (parts.size() >= 2) {
                    Provider provider;
                    provider.id = parts[0];
                    provider.nameservers = Split(parts[1], ',');
                    if (parts.size() >= 3) {
                        provider.doh_template = parts[2];
                    }
                    if (!provider.id.empty() && !provider.nameservers.empty()) {
                        settings.providers.push_back(std::move(provider));
                    }
                }
            }
        } catch (const std::exception&) {
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
    if (const auto value = ReadValueLine(path, "enable_happy_eyeballs_v3")) {
        settings.enable_happy_eyeballs_v3 = ParseBool(*value, settings.enable_happy_eyeballs_v3);
    }
    return settings;
}

std::vector<std::uint8_t> BuildDnsQuery(const std::string& domain, std::uint16_t id) {
    std::vector<std::uint8_t> packet(12, 0);
    packet[0] = static_cast<std::uint8_t>(id >> 8);
    packet[1] = static_cast<std::uint8_t>(id & 0xff);
    packet[2] = 0x01;
    packet[5] = 0x01;

    size_t start = 0;
    while (start < domain.size()) {
        const size_t end = domain.find('.', start);
        const size_t length = (end == std::string::npos ? domain.size() : end) - start;
        if (length == 0 || length > 63) {
            return {};
        }
        packet.push_back(static_cast<std::uint8_t>(length));
        packet.insert(packet.end(), domain.begin() + static_cast<std::ptrdiff_t>(start),
                      domain.begin() + static_cast<std::ptrdiff_t>(start + length));
        if (end == std::string::npos) {
            break;
        }
        start = end + 1;
    }

    packet.push_back(0);
    packet.push_back(0);
    packet.push_back(1);
    packet.push_back(0);
    packet.push_back(1);
    return packet;
}

struct DnsQueryResult {
    double elapsed_ms = 0.0;
    std::vector<std::string> addresses;
};

bool SkipDnsName(const std::uint8_t* response, size_t response_size, size_t* offset) {
    if (!offset || *offset >= response_size) {
        return false;
    }

    while (*offset < response_size) {
        const std::uint8_t length = response[*offset];
        if (length == 0) {
            ++(*offset);
            return true;
        }
        if ((length & 0xC0) == 0xC0) {
            if (*offset + 1 >= response_size) {
                return false;
            }
            *offset += 2;
            return true;
        }
        if ((length & 0xC0) != 0 || length > 63 ||
            *offset + 1 + length > response_size) {
            return false;
        }
        *offset += 1 + length;
    }
    return false;
}

std::uint16_t ReadU16(const std::uint8_t* data) {
    return static_cast<std::uint16_t>(
        (static_cast<std::uint16_t>(data[0]) << 8) |
        static_cast<std::uint16_t>(data[1]));
}

std::vector<std::string> ParseDnsAddresses(const std::uint8_t* response,
                                           size_t response_size) {
    std::vector<std::string> addresses;
    if (response_size < 12) {
        return addresses;
    }

    const std::uint16_t question_count = ReadU16(response + 4);
    const std::uint32_t record_count =
        static_cast<std::uint32_t>(ReadU16(response + 6)) +
        static_cast<std::uint32_t>(ReadU16(response + 8)) +
        static_cast<std::uint32_t>(ReadU16(response + 10));

    size_t offset = 12;
    for (std::uint16_t i = 0; i < question_count; ++i) {
        if (!SkipDnsName(response, response_size, &offset) ||
            offset + 4 > response_size) {
            return {};
        }
        offset += 4;
    }

    for (std::uint32_t i = 0; i < record_count; ++i) {
        if (!SkipDnsName(response, response_size, &offset) ||
            offset + 10 > response_size) {
            break;
        }

        const std::uint16_t type = ReadU16(response + offset);
        const std::uint16_t klass = ReadU16(response + offset + 2);
        const std::uint16_t rdlength = ReadU16(response + offset + 8);
        offset += 10;
        if (offset + rdlength > response_size) {
            break;
        }

        char literal[INET6_ADDRSTRLEN]{};
        if (klass == 1 && type == 1 && rdlength == 4) {
            if (InetNtopA(AF_INET, const_cast<std::uint8_t*>(response + offset),
                          literal, static_cast<DWORD>(sizeof(literal)))) {
                addresses.emplace_back(literal);
            }
        } else if (klass == 1 && type == 28 && rdlength == 16) {
            if (InetNtopA(AF_INET6, const_cast<std::uint8_t*>(response + offset),
                          literal, static_cast<DWORD>(sizeof(literal)))) {
                addresses.emplace_back(literal);
            }
        }
        offset += rdlength;
    }

    return addresses;
}

std::optional<DnsQueryResult> QueryDns(const std::string& server,
                                       const std::string& domain,
                                       int timeout_ms) {
    sockaddr_storage address{};
    int address_length = 0;
    int family = AF_UNSPEC;

    sockaddr_in address4{};
    if (InetPtonA(AF_INET, server.c_str(), &address4.sin_addr) == 1) {
        address4.sin_family = AF_INET;
        address4.sin_port = htons(53);
        std::memcpy(&address, &address4, sizeof(address4));
        address_length = sizeof(address4);
        family = AF_INET;
    } else {
        sockaddr_in6 address6{};
        if (InetPtonA(AF_INET6, server.c_str(), &address6.sin6_addr) != 1) {
            return std::nullopt;
        }
        address6.sin6_family = AF_INET6;
        address6.sin6_port = htons(53);
        std::memcpy(&address, &address6, sizeof(address6));
        address_length = sizeof(address6);
        family = AF_INET6;
    }

    SOCKET socket_handle = socket(family, SOCK_DGRAM, IPPROTO_UDP);
    if (socket_handle == INVALID_SOCKET) {
        return std::nullopt;
    }

    const DWORD timeout = static_cast<DWORD>(timeout_ms);
    setsockopt(socket_handle, SOL_SOCKET, SO_RCVTIMEO,
               reinterpret_cast<const char*>(&timeout), sizeof(timeout));
    setsockopt(socket_handle, SOL_SOCKET, SO_SNDTIMEO,
               reinterpret_cast<const char*>(&timeout), sizeof(timeout));

    static thread_local std::mt19937 random_engine(std::random_device{}());
    std::uniform_int_distribution<std::uint16_t> distribution(1, 65535);
    const std::uint16_t transaction_id = distribution(random_engine);
    const auto request = BuildDnsQuery(domain, transaction_id);
    if (request.empty()) {
        closesocket(socket_handle);
        return std::nullopt;
    }

    const auto started = Clock::now();
    const int sent = sendto(socket_handle,
                            reinterpret_cast<const char*>(request.data()),
                            static_cast<int>(request.size()),
                            0,
                            reinterpret_cast<const sockaddr*>(&address),
                            address_length);
    if (sent != static_cast<int>(request.size())) {
        closesocket(socket_handle);
        return std::nullopt;
    }

    std::uint8_t response[4096]{};
    sockaddr_storage source{};
    int source_length = sizeof(source);
    const int received = recvfrom(socket_handle,
                                  reinterpret_cast<char*>(response),
                                  static_cast<int>(sizeof(response)),
                                  0,
                                  reinterpret_cast<sockaddr*>(&source),
                                  &source_length);
    const auto finished = Clock::now();
    closesocket(socket_handle);

    if (received < 12) {
        return std::nullopt;
    }

    const std::uint16_t response_id = ReadU16(response);
    const bool is_response = (response[2] & 0x80) != 0;
    const bool is_truncated = (response[2] & 0x02) != 0;
    const int response_code = response[3] & 0x0f;
    if (response_id != transaction_id || !is_response || is_truncated ||
        response_code != 0) {
        return std::nullopt;
    }

    DnsQueryResult result;
    result.elapsed_ms =
        std::chrono::duration<double, std::milli>(finished - started).count();
    result.addresses =
        ParseDnsAddresses(response, static_cast<size_t>(received));
    return result;
}

std::optional<double> ConnectTcp443(const std::string& literal, int timeout_ms) {
    sockaddr_storage address{};
    int address_length = 0;
    int family = AF_UNSPEC;

    sockaddr_in address4{};
    if (InetPtonA(AF_INET, literal.c_str(), &address4.sin_addr) == 1) {
        address4.sin_family = AF_INET;
        address4.sin_port = htons(443);
        std::memcpy(&address, &address4, sizeof(address4));
        address_length = sizeof(address4);
        family = AF_INET;
    } else {
        sockaddr_in6 address6{};
        if (InetPtonA(AF_INET6, literal.c_str(), &address6.sin6_addr) != 1) {
            return std::nullopt;
        }
        address6.sin6_family = AF_INET6;
        address6.sin6_port = htons(443);
        std::memcpy(&address, &address6, sizeof(address6));
        address_length = sizeof(address6);
        family = AF_INET6;
    }

    SOCKET socket_handle = socket(family, SOCK_STREAM, IPPROTO_TCP);
    if (socket_handle == INVALID_SOCKET) {
        return std::nullopt;
    }

    u_long nonblocking = 1;
    if (ioctlsocket(socket_handle, FIONBIO, &nonblocking) != 0) {
        closesocket(socket_handle);
        return std::nullopt;
    }

    const auto started = Clock::now();
    const int connect_result =
        connect(socket_handle, reinterpret_cast<const sockaddr*>(&address),
                address_length);
    if (connect_result == SOCKET_ERROR) {
        const int error = WSAGetLastError();
        if (error != WSAEWOULDBLOCK && error != WSAEINPROGRESS) {
            closesocket(socket_handle);
            return std::nullopt;
        }
    }

    fd_set write_set;
    FD_ZERO(&write_set);
    FD_SET(socket_handle, &write_set);
    timeval timeout{};
    timeout.tv_sec = timeout_ms / 1000;
    timeout.tv_usec = (timeout_ms % 1000) * 1000;

    const int selected = select(0, nullptr, &write_set, nullptr, &timeout);
    if (selected <= 0 || !FD_ISSET(socket_handle, &write_set)) {
        closesocket(socket_handle);
        return std::nullopt;
    }

    int socket_error = 0;
    int error_length = sizeof(socket_error);
    if (getsockopt(socket_handle, SOL_SOCKET, SO_ERROR,
                   reinterpret_cast<char*>(&socket_error),
                   &error_length) != 0 ||
        socket_error != 0) {
        closesocket(socket_handle);
        return std::nullopt;
    }

    const auto finished = Clock::now();
    closesocket(socket_handle);
    return std::chrono::duration<double, std::milli>(finished - started).count();
}

std::optional<double> MeasurePriorityHostConnect(const std::string& dns_server,
                                                 const std::string& host,
                                                 const DnsSettings& settings) {
    const auto resolved = QueryDns(dns_server, host, settings.timeout_ms);
    if (!resolved || resolved->addresses.empty()) {
        return std::nullopt;
    }

    std::optional<double> best;
    size_t tested = 0;
    for (const std::string& address : resolved->addresses) {
        if (tested++ >= 4) {
            break;
        }
        const auto elapsed = ConnectTcp443(address, settings.connect_timeout_ms);
        if (elapsed && (!best || *elapsed < *best)) {
            best = elapsed;
        }
    }
    return best;
}

ProbeStats CalculateStats(std::vector<double> samples,
                          int failures,
                          int attempted,
                          int timeout_ms,
                          const std::string& endpoint) {
    ProbeStats stats;
    stats.endpoint = endpoint;
    if (attempted <= 0) {
        return stats;
    }
    stats.failure_rate = static_cast<double>(failures) / static_cast<double>(attempted);
    if (samples.empty()) {
        stats.score = static_cast<double>(timeout_ms) * 10.0;
        return stats;
    }

    std::sort(samples.begin(), samples.end());
    const size_t median_index = samples.size() / 2;
    stats.median_ms = samples.size() % 2 == 0
        ? (samples[median_index - 1] + samples[median_index]) / 2.0
        : samples[median_index];

    const size_t p95_index =
        std::min(samples.size() - 1,
                 static_cast<size_t>(std::ceil(samples.size() * 0.95) - 1.0));
    stats.p95_ms = samples[p95_index];

    double squared_sum = 0.0;
    for (const double value : samples) {
        const double delta = value - stats.median_ms;
        squared_sum += delta * delta;
    }
    stats.jitter_ms = std::sqrt(squared_sum / static_cast<double>(samples.size()));

    const double tail_penalty = std::max(0.0, stats.p95_ms - stats.median_ms);
    stats.score = stats.median_ms +
                  0.35 * tail_penalty +
                  0.20 * stats.jitter_ms +
                  stats.failure_rate * static_cast<double>(timeout_ms) * 2.0;
    return stats;
}

ProbeStats BenchmarkEndpoint(const std::string& endpoint,
                             const DnsSettings& settings) {
    std::vector<double> samples;
    int failures = 0;
    for (int i = 0; i < settings.samples; ++i) {
        const std::string& domain =
            settings.probe_domains[static_cast<size_t>(i) % settings.probe_domains.size()];
        const auto result = QueryDns(endpoint, domain, settings.timeout_ms);
        if (result) {
            samples.push_back(result->elapsed_ms);
        } else {
            ++failures;
        }
    }

    ProbeStats stats = CalculateStats(std::move(samples), failures, settings.samples,
                                     settings.timeout_ms, endpoint);

    if (!settings.priority_hosts.empty() && settings.connect_weight > 0.0) {
        std::vector<double> connect_samples;
        int connect_failures = 0;
        int connect_attempts = 0;

        for (const std::string& host : settings.priority_hosts) {
            for (int sample = 0; sample < settings.connect_samples; ++sample) {
                ++connect_attempts;
                const auto elapsed = MeasurePriorityHostConnect(endpoint, host, settings);
                if (elapsed) {
                    connect_samples.push_back(*elapsed);
                } else {
                    ++connect_failures;
                }
            }
        }

        if (connect_attempts > 0) {
            stats.connect_failure_rate =
                static_cast<double>(connect_failures) /
                static_cast<double>(connect_attempts);
            if (!connect_samples.empty()) {
                std::sort(connect_samples.begin(), connect_samples.end());
                const size_t middle = connect_samples.size() / 2;
                stats.connect_median_ms = connect_samples.size() % 2 == 0
                    ? (connect_samples[middle - 1] + connect_samples[middle]) / 2.0
                    : connect_samples[middle];
                stats.score += settings.connect_weight * stats.connect_median_ms;
            }
            stats.score += stats.connect_failure_rate *
                           static_cast<double>(settings.connect_timeout_ms);
        }
    }

    return stats;
}

ProbeStats BenchmarkProvider(const Provider& provider,
                             const DnsSettings& settings) {
    ProbeStats best;
    for (const std::string& endpoint : provider.nameservers) {
        ProbeStats current = BenchmarkEndpoint(endpoint, settings);
        if (current.score < best.score) {
            best = std::move(current);
        }
    }
    return best;
}

std::string NumericAddress(const SOCKET_ADDRESS& socket_address) {
    if (!socket_address.lpSockaddr || socket_address.iSockaddrLength <= 0) {
        return {};
    }
    char host[NI_MAXHOST]{};
    if (getnameinfo(socket_address.lpSockaddr,
                    socket_address.iSockaddrLength,
                    host,
                    static_cast<DWORD>(sizeof(host)),
                    nullptr,
                    0,
                    NI_NUMERICHOST) != 0) {
        return {};
    }
    return host;
}

std::string NetworkSignature() {
    ULONG buffer_size = 0;
    const ULONG flags = GAA_FLAG_SKIP_ANYCAST |
                        GAA_FLAG_SKIP_MULTICAST |
                        GAA_FLAG_SKIP_FRIENDLY_NAME;
    GetAdaptersAddresses(AF_UNSPEC, flags, nullptr, nullptr, &buffer_size);
    if (buffer_size == 0) {
        return "unknown";
    }

    std::vector<std::uint8_t> buffer(buffer_size);
    auto* adapters = reinterpret_cast<IP_ADAPTER_ADDRESSES*>(buffer.data());
    if (GetAdaptersAddresses(AF_UNSPEC, flags, nullptr, adapters, &buffer_size) != NO_ERROR) {
        return "unknown";
    }

    std::vector<std::string> tokens;
    for (auto* adapter = adapters; adapter; adapter = adapter->Next) {
        if (adapter->OperStatus != IfOperStatusUp) {
            continue;
        }
        if (adapter->AdapterName) {
            tokens.emplace_back(adapter->AdapterName);
        }
        tokens.push_back(std::to_string(adapter->IfType));
        for (auto* unicast = adapter->FirstUnicastAddress; unicast; unicast = unicast->Next) {
            const std::string value = NumericAddress(unicast->Address);
            if (!value.empty()) {
                tokens.push_back("U:" + value);
            }
        }
        for (auto* dns = adapter->FirstDnsServerAddress; dns; dns = dns->Next) {
            const std::string value = NumericAddress(dns->Address);
            if (!value.empty()) {
                tokens.push_back("D:" + value);
            }
        }
    }

    std::sort(tokens.begin(), tokens.end());
    std::uint64_t hash = 1469598103934665603ULL;
    for (const std::string& token : tokens) {
        for (unsigned char ch : token) {
            hash ^= ch;
            hash *= 1099511628211ULL;
        }
        hash ^= 0xff;
        hash *= 1099511628211ULL;
    }

    std::ostringstream output;
    output << std::hex << hash;
    return output.str();
}

std::optional<SelectionState> LoadState(const std::filesystem::path& path) {
    std::ifstream input(path);
    if (!input) {
        return std::nullopt;
    }

    SelectionState state;
    std::string line;
    while (std::getline(input, line)) {
        const auto separator = line.find('=');
        if (separator == std::string::npos) {
            continue;
        }
        const std::string key = Trim(line.substr(0, separator));
        const std::string value = Trim(line.substr(separator + 1));
        try {
            if (key == "network_signature") {
                state.network_signature = value;
            } else if (key == "provider_id") {
                state.provider_id = value;
            } else if (key == "score") {
                state.score = std::stod(value);
            } else if (key == "selected_at") {
                state.selected_at = std::stoll(value);
            }
        } catch (const std::exception&) {
            return std::nullopt;
        }
    }

    if (state.provider_id.empty() || state.network_signature.empty() ||
        !std::isfinite(state.score) || state.selected_at <= 0) {
        return std::nullopt;
    }
    return state;
}

void SaveState(const std::filesystem::path& path, const SelectionState& state) {
    std::ofstream output(path, std::ios::trunc);
    if (!output) {
        return;
    }
    output << "network_signature=" << state.network_signature << "\n";
    output << "provider_id=" << state.provider_id << "\n";
    output << std::fixed << std::setprecision(3);
    output << "score=" << state.score << "\n";
    output << "selected_at=" << state.selected_at << "\n";
}

const Provider* FindProvider(const DnsSettings& settings, const std::string& id) {
    for (const Provider& provider : settings.providers) {
        if (provider.id == id) {
            return &provider;
        }
    }
    return nullptr;
}

void ClearNautrixDnsEnvironment() {
    SetEnvironmentVariableW(L"NAUTRIX_DNS_MODE", nullptr);
    SetEnvironmentVariableW(L"NAUTRIX_DNS_NAMESERVERS", nullptr);
    SetEnvironmentVariableW(L"NAUTRIX_DOH_TEMPLATES", nullptr);
}

std::string Join(const std::vector<std::string>& values, const char* separator) {
    std::ostringstream output;
    for (size_t i = 0; i < values.size(); ++i) {
        if (i) {
            output << separator;
        }
        output << values[i];
    }
    return output.str();
}

void ApplyDnsEnvironment(const std::vector<std::string>& nameservers,
                         const std::string& doh_template,
                         bool prefer_encrypted) {
    ClearNautrixDnsEnvironment();

    const std::string nameserver_list = Join(nameservers, ",");
    if (!nameserver_list.empty()) {
        SetEnvironmentVariableW(L"NAUTRIX_DNS_NAMESERVERS",
                                Utf8ToWide(nameserver_list).c_str());
    }

    if (prefer_encrypted && !doh_template.empty()) {
        SetEnvironmentVariableW(L"NAUTRIX_DNS_MODE", L"automatic");
        SetEnvironmentVariableW(L"NAUTRIX_DOH_TEMPLATES",
                                Utf8ToWide(doh_template).c_str());
    } else if (!nameserver_list.empty()) {
        SetEnvironmentVariableW(L"NAUTRIX_DNS_MODE", L"plain");
    }
}

const Provider* SelectAutomaticProvider(const DnsSettings& settings,
                                        const std::filesystem::path& state_path) {
    if (settings.providers.empty()) {
        std::cerr << "[Nautrix] No automatic DNS providers configured; using system DNS.\n";
        return nullptr;
    }

    const std::string signature = NetworkSignature();
    const std::int64_t now = static_cast<std::int64_t>(std::time(nullptr));
    const auto prior = LoadState(state_path);

    if (prior && prior->network_signature == signature) {
        const std::int64_t age_seconds = now - prior->selected_at;
        if (age_seconds >= 0 &&
            age_seconds < static_cast<std::int64_t>(settings.retest_minutes) * 60) {
            if (const Provider* cached = FindProvider(settings, prior->provider_id)) {
                std::cout << "[Nautrix] DNS cached winner: " << cached->id
                          << " (score " << prior->score << ")\n";
                return cached;
            }
        }
    }

    std::vector<std::future<ProbeStats>> futures;
    futures.reserve(settings.providers.size());
    for (const Provider& provider : settings.providers) {
        futures.push_back(std::async(std::launch::async, [&settings, provider]() {
            return BenchmarkProvider(provider, settings);
        }));
    }

    std::vector<ProbeStats> metrics(settings.providers.size());
    size_t best_index = settings.providers.size();
    double best_score = std::numeric_limits<double>::infinity();

    for (size_t i = 0; i < futures.size(); ++i) {
        metrics[i] = futures[i].get();
        const Provider& provider = settings.providers[i];
        std::cout << "[Nautrix] DNS " << provider.id
                  << " endpoint=" << metrics[i].endpoint
                  << " median=" << metrics[i].median_ms
                  << "ms p95=" << metrics[i].p95_ms
                  << "ms jitter=" << metrics[i].jitter_ms
                  << "ms failures=" << (metrics[i].failure_rate * 100.0);
        if (std::isfinite(metrics[i].connect_median_ms)) {
            std::cout << "% connect=" << metrics[i].connect_median_ms
                      << "ms connect_failures="
                      << (metrics[i].connect_failure_rate * 100.0);
        }
        std::cout << "% score=" << metrics[i].score << "\n";
        if (metrics[i].score < best_score) {
            best_score = metrics[i].score;
            best_index = i;
        }
    }

    if (best_index == settings.providers.size() || !std::isfinite(best_score)) {
        return nullptr;
    }

    if (prior && prior->network_signature == signature) {
        for (size_t i = 0; i < settings.providers.size(); ++i) {
            if (settings.providers[i].id != prior->provider_id ||
                !std::isfinite(metrics[i].score)) {
                continue;
            }
            const double improvement =
                (metrics[i].score - best_score) / std::max(metrics[i].score, 0.001) * 100.0;
            if (metrics[i].failure_rate <= 0.25 &&
                improvement < settings.minimum_improvement_percent) {
                best_index = i;
                best_score = metrics[i].score;
            }
            break;
        }
    }

    SelectionState selected;
    selected.network_signature = signature;
    selected.provider_id = settings.providers[best_index].id;
    selected.score = best_score;
    selected.selected_at = now;
    SaveState(state_path, selected);

    std::cout << "[Nautrix] DNS selected: " << selected.provider_id
              << " (score " << selected.score << ")\n";
    return &settings.providers[best_index];
}

std::wstring QuoteArgument(const std::wstring& argument) {
    if (argument.find_first_of(L" \t\"") == std::wstring::npos) {
        return argument;
    }

    std::wstring output = L"\"";
    size_t backslashes = 0;
    for (wchar_t ch : argument) {
        if (ch == L'\\') {
            ++backslashes;
            continue;
        }
        if (ch == L'\"') {
            output.append(backslashes * 2 + 1, L'\\');
            output.push_back(L'\"');
            backslashes = 0;
            continue;
        }
        output.append(backslashes, L'\\');
        backslashes = 0;
        output.push_back(ch);
    }
    output.append(backslashes * 2, L'\\');
    output.push_back(L'\"');
    return output;
}

bool StartsWith(const std::wstring& value, std::wstring_view prefix) {
    return value.size() >= prefix.size() &&
           std::equal(prefix.begin(), prefix.end(), value.begin());
}

void EnableFeature(std::vector<std::wstring>* args, const std::wstring& feature) {
    constexpr std::wstring_view prefix = L"--enable-features=";
    for (std::wstring& arg : *args) {
        if (!StartsWith(arg, prefix)) {
            continue;
        }
        std::wstring features = arg.substr(prefix.size());
        if (features.find(feature) == std::wstring::npos) {
            if (!features.empty()) {
                features += L",";
            }
            features += feature;
            arg = std::wstring(prefix) + features;
        }
        return;
    }
    args->push_back(std::wstring(prefix) + feature);
}

bool HasUserDataDir(const std::vector<std::wstring>& args) {
    for (const std::wstring& arg : args) {
        if (StartsWith(arg, L"--user-data-dir=")) {
            return true;
        }
    }
    return false;
}

int LaunchBrowser(const std::filesystem::path& browser,
                  std::vector<std::wstring> args,
                  const LatencySettings& latency) {
    if (latency.enable_happy_eyeballs_v3) {
        EnableFeature(&args, L"HappyEyeballsV3");
    }

    if (!HasUserDataDir(args)) {
        const std::filesystem::path user_data = LocalStateDirectory() / L"User Data";
        args.push_back(L"--user-data-dir=" + user_data.wstring());
    }

    std::wstring command_line = QuoteArgument(browser.wstring());
    for (const std::wstring& arg : args) {
        command_line += L" ";
        command_line += QuoteArgument(arg);
    }

    std::vector<wchar_t> mutable_command(command_line.begin(), command_line.end());
    mutable_command.push_back(L'\0');

    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    PROCESS_INFORMATION process{};
    const std::wstring working_directory = browser.parent_path().wstring();

    if (!CreateProcessW(browser.c_str(),
                        mutable_command.data(),
                        nullptr,
                        nullptr,
                        FALSE,
                        0,
                        nullptr,
                        working_directory.empty() ? nullptr : working_directory.c_str(),
                        &startup,
                        &process)) {
        std::cerr << "[Nautrix] Failed to launch browser. Win32 error="
                  << GetLastError() << "\n";
        return 1;
    }

    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
    WSADATA winsock{};
    if (WSAStartup(MAKEWORD(2, 2), &winsock) != 0) {
        std::cerr << "[Nautrix] Winsock initialization failed.\n";
        return 1;
    }

    std::filesystem::path browser = ExecutableDirectory() / L"chrome.exe";
    std::filesystem::path config_dir = ExecutableDirectory() / L"config";
    std::vector<std::wstring> browser_args;

    for (int i = 1; i < argc; ++i) {
        const std::wstring arg = argv[i];
        if (StartsWith(arg, L"--browser=")) {
            browser = arg.substr(std::wstring(L"--browser=").size());
        } else if (StartsWith(arg, L"--config-dir=")) {
            config_dir = arg.substr(std::wstring(L"--config-dir=").size());
        } else {
            browser_args.push_back(arg);
        }
    }

    if (!std::filesystem::exists(browser)) {
        std::wcerr << L"[Nautrix] Browser binary not found: " << browser.wstring() << L"\n";
        WSACleanup();
        return 1;
    }

    const DnsSettings dns = LoadDnsSettings(config_dir / L"dns.ini");
    const LatencySettings latency = LoadLatencySettings(config_dir / L"latency.ini");

    ClearNautrixDnsEnvironment();
    if (dns.mode == "manual") {
        ApplyDnsEnvironment(dns.manual_nameservers,
                            dns.manual_doh_template,
                            dns.prefer_encrypted);
        std::cout << "[Nautrix] DNS mode: manual\n";
    } else if (dns.mode == "automatic") {
        const std::filesystem::path state_path =
            LocalStateDirectory() / L"dns-selection.state";
        if (const Provider* provider = SelectAutomaticProvider(dns, state_path)) {
            ApplyDnsEnvironment(provider->nameservers,
                                provider->doh_template,
                                dns.prefer_encrypted);
        } else {
            std::cout << "[Nautrix] Automatic DNS unavailable; falling back to system DNS.\n";
        }
    } else {
        std::cout << "[Nautrix] DNS mode: system\n";
    }

    const int result = LaunchBrowser(browser, std::move(browser_args), latency);
    WSACleanup();
    return result;
}
