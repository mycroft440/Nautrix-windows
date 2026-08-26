#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <shellapi.h>

#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#pragma comment(lib, "shell32.lib")

namespace {

constexpr int kMode = 1001;
constexpr int kNameservers = 1002;
constexpr int kDoh = 1003;
constexpr int kEncrypted = 1004;
constexpr int kSave = 1005;
constexpr int kBenchmark = 1006;
constexpr int kMetrics = 1007;

std::filesystem::path g_config_dir;
HWND g_mode = nullptr;
HWND g_nameservers = nullptr;
HWND g_doh = nullptr;
HWND g_encrypted = nullptr;
HWND g_metrics = nullptr;

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
    std::filesystem::path base = (size > 0 && size < std::size(buffer)) ? std::filesystem::path(buffer)
                                                                       : std::filesystem::temp_directory_path();
    return base / L"Nautrix";
}

std::string Trim(std::string value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

std::string ReadKey(const std::filesystem::path& path, const std::string& wanted, const std::string& fallback = {}) {
    std::ifstream input(path);
    std::string line;
    while (std::getline(input, line)) {
        const auto separator = line.find('=');
        if (separator == std::string::npos) continue;
        if (Trim(line.substr(0, separator)) == wanted) return Trim(line.substr(separator + 1));
    }
    return fallback;
}

bool WriteKey(const std::filesystem::path& path, const std::string& key, const std::string& value) {
    std::ifstream input(path);
    std::vector<std::string> lines;
    std::string line;
    bool replaced = false;
    while (std::getline(input, line)) {
        const auto separator = line.find('=');
        if (separator != std::string::npos && Trim(line.substr(0, separator)) == key) {
            lines.push_back(key + "=" + value);
            replaced = true;
        } else {
            lines.push_back(line);
        }
    }
    if (!replaced) lines.push_back(key + "=" + value);
    std::ofstream output(path, std::ios::trunc);
    if (!output) return false;
    for (const auto& item : lines) output << item << "\n";
    return true;
}

std::wstring Utf8ToWide(const std::string& input) {
    if (input.empty()) return {};
    const int length = MultiByteToWideChar(CP_UTF8, 0, input.data(), static_cast<int>(input.size()), nullptr, 0);
    if (length <= 0) return {};
    std::wstring output(static_cast<size_t>(length), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, input.data(), static_cast<int>(input.size()), output.data(), length);
    return output;
}

std::string WideToUtf8(const std::wstring& input) {
    if (input.empty()) return {};
    const int length = WideCharToMultiByte(CP_UTF8, 0, input.data(), static_cast<int>(input.size()), nullptr, 0, nullptr, nullptr);
    if (length <= 0) return {};
    std::string output(static_cast<size_t>(length), '\0');
    WideCharToMultiByte(CP_UTF8, 0, input.data(), static_cast<int>(input.size()), output.data(), length, nullptr, nullptr);
    return output;
}

std::wstring ControlText(HWND control) {
    const int length = GetWindowTextLengthW(control);
    std::wstring value(static_cast<size_t>(length) + 1, L'\0');
    const int copied = GetWindowTextW(control, value.data(), length + 1);
    value.resize(copied > 0 ? static_cast<size_t>(copied) : 0);
    return value;
}

void SetFont(HWND control) {
    SendMessageW(control, WM_SETFONT, reinterpret_cast<WPARAM>(GetStockObject(DEFAULT_GUI_FONT)), TRUE);
}

void RefreshMetrics() {
    const auto path = LocalStateDirectory() / L"dns-metrics.csv";
    std::ifstream input(path);
    if (!input) {
        SetWindowTextW(g_metrics, L"No DNS benchmark has been run yet.");
        return;
    }
    std::ostringstream content;
    content << input.rdbuf();
    SetWindowTextW(g_metrics, Utf8ToWide(content.str()).c_str());
}

void LoadSettings() {
    const auto dns = g_config_dir / L"dns.ini";
    const std::string mode = ReadKey(dns, "mode", "automatic");
    int selection = 0;
    if (mode == "manual") selection = 1;
    else if (mode == "system") selection = 2;
    SendMessageW(g_mode, CB_SETCURSEL, selection, 0);
    SetWindowTextW(g_nameservers, Utf8ToWide(ReadKey(dns, "manual_nameservers", "1.1.1.1,1.0.0.1")).c_str());
    SetWindowTextW(g_doh, Utf8ToWide(ReadKey(dns, "manual_doh_template", "https://cloudflare-dns.com/dns-query")).c_str());
    const std::string encrypted = ReadKey(dns, "prefer_encrypted", "1");
    SendMessageW(g_encrypted, BM_SETCHECK, (encrypted == "0" || encrypted == "false") ? BST_UNCHECKED : BST_CHECKED, 0);
    RefreshMetrics();
}

void SaveSettings(HWND owner) {
    const auto dns = g_config_dir / L"dns.ini";
    const LRESULT selection = SendMessageW(g_mode, CB_GETCURSEL, 0, 0);
    const std::string mode = selection == 1 ? "manual" : selection == 2 ? "system" : "automatic";
    const bool encrypted = SendMessageW(g_encrypted, BM_GETCHECK, 0, 0) == BST_CHECKED;
    std::error_code error;
    std::filesystem::create_directories(g_config_dir, error);
    if (!WriteKey(dns, "mode", mode) ||
        !WriteKey(dns, "prefer_encrypted", encrypted ? "1" : "0") ||
        !WriteKey(dns, "manual_nameservers", WideToUtf8(ControlText(g_nameservers))) ||
        !WriteKey(dns, "manual_doh_template", WideToUtf8(ControlText(g_doh)))) {
        MessageBoxW(owner, L"Could not save DNS settings.", L"Nautrix Network Settings", MB_ICONERROR);
        return;
    }
    MessageBoxW(owner, L"DNS settings saved. They will apply to the next Nautrix launch.", L"Nautrix Network Settings", MB_OK);
}

std::wstring Quote(const std::wstring& text) {
    return L"\"" + text + L"\"";
}

void RunBenchmark(HWND owner) {
    const auto launcher = ExecutableDirectory() / L"NautrixLauncher.exe";
    if (!std::filesystem::exists(launcher)) {
        MessageBoxW(owner, L"NautrixLauncher.exe was not found next to the settings application.", L"Nautrix", MB_ICONERROR);
        return;
    }
    std::wstring command = Quote(launcher.wstring()) + L" --benchmark-only --force-dns-retest --config-dir=" + Quote(g_config_dir.wstring());
    std::vector<wchar_t> mutable_command(command.begin(), command.end());
    mutable_command.push_back(L'\0');
    STARTUPINFOW startup{}; startup.cb = sizeof(startup);
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(launcher.c_str(), mutable_command.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW,
                        nullptr, launcher.parent_path().c_str(), &startup, &process)) {
        MessageBoxW(owner, L"Could not start the DNS benchmark.", L"Nautrix", MB_ICONERROR);
        return;
    }
    EnableWindow(owner, FALSE);
    WaitForSingleObject(process.hProcess, 30000);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    EnableWindow(owner, TRUE);
    SetForegroundWindow(owner);
    RefreshMetrics();
}

LRESULT CALLBACK WindowProc(HWND hwnd, UINT message, WPARAM wparam, LPARAM lparam) {
    switch (message) {
    case WM_CREATE: {
        CreateWindowW(L"STATIC", L"DNS mode", WS_CHILD | WS_VISIBLE, 20, 20, 120, 22, hwnd, nullptr, nullptr, nullptr);
        g_mode = CreateWindowW(L"COMBOBOX", L"", WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST | WS_VSCROLL,
                               160, 16, 260, 120, hwnd, reinterpret_cast<HMENU>(kMode), nullptr, nullptr);
        SendMessageW(g_mode, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(L"Automatic (lowest stable score)"));
        SendMessageW(g_mode, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(L"Manual/custom"));
        SendMessageW(g_mode, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(L"Windows system DNS"));
        CreateWindowW(L"STATIC", L"Manual nameservers", WS_CHILD | WS_VISIBLE, 20, 62, 130, 22, hwnd, nullptr, nullptr, nullptr);
        g_nameservers = CreateWindowW(L"EDIT", L"", WS_CHILD | WS_VISIBLE | WS_BORDER | ES_AUTOHSCROLL,
                                      160, 58, 560, 26, hwnd, reinterpret_cast<HMENU>(kNameservers), nullptr, nullptr);
        CreateWindowW(L"STATIC", L"Manual DoH", WS_CHILD | WS_VISIBLE, 20, 102, 130, 22, hwnd, nullptr, nullptr, nullptr);
        g_doh = CreateWindowW(L"EDIT", L"", WS_CHILD | WS_VISIBLE | WS_BORDER | ES_AUTOHSCROLL,
                              160, 98, 560, 26, hwnd, reinterpret_cast<HMENU>(kDoh), nullptr, nullptr);
        g_encrypted = CreateWindowW(L"BUTTON", L"Prefer encrypted DNS (DoH)", WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX,
                                    160, 136, 260, 24, hwnd, reinterpret_cast<HMENU>(kEncrypted), nullptr, nullptr);
        HWND save = CreateWindowW(L"BUTTON", L"Save", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                                  160, 172, 120, 32, hwnd, reinterpret_cast<HMENU>(kSave), nullptr, nullptr);
        HWND benchmark = CreateWindowW(L"BUTTON", L"Benchmark now", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                                       292, 172, 150, 32, hwnd, reinterpret_cast<HMENU>(kBenchmark), nullptr, nullptr);
        CreateWindowW(L"STATIC", L"Latest automatic DNS metrics", WS_CHILD | WS_VISIBLE,
                      20, 226, 250, 22, hwnd, nullptr, nullptr, nullptr);
        g_metrics = CreateWindowW(L"EDIT", L"", WS_CHILD | WS_VISIBLE | WS_BORDER | ES_MULTILINE | ES_AUTOVSCROLL |
                                  ES_AUTOHSCROLL | WS_VSCROLL | WS_HSCROLL | ES_READONLY,
                                  20, 252, 700, 230, hwnd, reinterpret_cast<HMENU>(kMetrics), nullptr, nullptr);
        for (HWND control : {g_mode, g_nameservers, g_doh, g_encrypted, save, benchmark, g_metrics}) SetFont(control);
        LoadSettings();
        return 0;
    }
    case WM_COMMAND:
        if (LOWORD(wparam) == kSave) SaveSettings(hwnd);
        else if (LOWORD(wparam) == kBenchmark) RunBenchmark(hwnd);
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0); return 0;
    default:
        return DefWindowProcW(hwnd, message, wparam, lparam);
    }
}

std::filesystem::path ParseConfigDirectory() {
    int argc = 0;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    std::filesystem::path result = ExecutableDirectory() / L"config";
    if (argv) {
        for (int i = 1; i < argc; ++i) {
            std::wstring arg = argv[i];
            constexpr std::wstring_view prefix = L"--config-dir=";
            if (arg.rfind(prefix, 0) == 0) result = arg.substr(prefix.size());
        }
        LocalFree(argv);
    }
    return result;
}

}  // namespace

int APIENTRY wWinMain(HINSTANCE instance, HINSTANCE, LPWSTR, int show_command) {
    g_config_dir = ParseConfigDirectory();
    WNDCLASSEXW wc{};
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = WindowProc;
    wc.hInstance = instance;
    wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    wc.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1);
    wc.lpszClassName = L"NautrixNetworkSettingsWindow";
    if (!RegisterClassExW(&wc) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS) return 1;
    HWND hwnd = CreateWindowExW(0, wc.lpszClassName, L"Nautrix - Network Settings", WS_OVERLAPPED | WS_CAPTION |
                                WS_SYSMENU | WS_MINIMIZEBOX, CW_USEDEFAULT, CW_USEDEFAULT, 760, 540,
                                nullptr, nullptr, instance, nullptr);
    if (!hwnd) return 1;
    ShowWindow(hwnd, show_command);
    UpdateWindow(hwnd);
    MSG msg{};
    while (GetMessageW(&msg, nullptr, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    return static_cast<int>(msg.wParam);
}
