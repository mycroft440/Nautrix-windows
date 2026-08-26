#include <windows.h>
#include <shlobj.h>
#include <wrl.h>
#include <WebView2.h>

#include <algorithm>
#include <filesystem>
#include <iomanip>
#include <sstream>
#include <string>
#include <string_view>

using Microsoft::WRL::Callback;
using Microsoft::WRL::ComPtr;

namespace {
constexpr wchar_t kWindowClassName[] = L"NautrixMainWindow";
constexpr wchar_t kHomeUrl[] = L"https://www.google.com/";
constexpr int kButtonBack = 1001;
constexpr int kButtonForward = 1002;
constexpr int kButtonReload = 1003;
constexpr int kAddressBar = 1004;
constexpr int kButtonGo = 1005;
constexpr int kCommandFocusAddress = 2001;
constexpr int kCommandReload = 2002;

std::wstring Trim(std::wstring value) {
    const auto first = value.find_first_not_of(L" \t\r\n");
    if (first == std::wstring::npos) {
        return {};
    }
    const auto last = value.find_last_not_of(L" \t\r\n");
    return value.substr(first, last - first + 1);
}

std::string UrlEncodeUtf8(const std::wstring& input) {
    if (input.empty()) {
        return {};
    }

    const int size = WideCharToMultiByte(CP_UTF8, 0, input.c_str(), static_cast<int>(input.size()), nullptr, 0, nullptr, nullptr);
    if (size <= 0) {
        return {};
    }

    std::string utf8(static_cast<size_t>(size), '\0');
    WideCharToMultiByte(CP_UTF8, 0, input.c_str(), static_cast<int>(input.size()), utf8.data(), size, nullptr, nullptr);

    std::ostringstream encoded;
    encoded << std::uppercase << std::hex;
    for (const unsigned char ch : utf8) {
        const bool unreserved =
            (ch >= 'A' && ch <= 'Z') ||
            (ch >= 'a' && ch <= 'z') ||
            (ch >= '0' && ch <= '9') ||
            ch == '-' || ch == '_' || ch == '.' || ch == '~';

        if (unreserved) {
            encoded << static_cast<char>(ch);
        } else if (ch == ' ') {
            encoded << '+';
        } else {
            encoded << '%' << std::setw(2) << std::setfill('0') << static_cast<int>(ch);
        }
    }
    return encoded.str();
}

std::wstring NormalizeNavigationInput(std::wstring input) {
    input = Trim(std::move(input));
    if (input.empty()) {
        return {};
    }

    if (input.find(L"://") != std::wstring::npos || input.rfind(L"about:", 0) == 0) {
        return input;
    }

    const bool looksLikeHost = input.find(L' ') == std::wstring::npos && input.find(L'.') != std::wstring::npos;
    if (looksLikeHost) {
        return L"https://" + input;
    }

    const std::string encoded = UrlEncodeUtf8(input);
    return L"https://www.google.com/search?q=" + std::wstring(encoded.begin(), encoded.end());
}

std::wstring GetWebViewUserDataFolder() {
    PWSTR localAppData = nullptr;
    std::wstring result;

    if (SUCCEEDED(SHGetKnownFolderPath(FOLDERID_LocalAppData, KF_FLAG_CREATE, nullptr, &localAppData)) && localAppData) {
        result = localAppData;
        CoTaskMemFree(localAppData);
        result += L"\\Nautrix\\WebView2";
        std::error_code error;
        std::filesystem::create_directories(result, error);
    }

    return result;
}
} // namespace

class BrowserWindow {
public:
    bool Create(HINSTANCE instance, int showCommand) {
        WNDCLASSEXW windowClass{};
        windowClass.cbSize = sizeof(windowClass);
        windowClass.style = CS_HREDRAW | CS_VREDRAW;
        windowClass.lpfnWndProc = &BrowserWindow::WindowProc;
        windowClass.hInstance = instance;
        windowClass.hCursor = LoadCursorW(nullptr, IDC_ARROW);
        windowClass.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1);
        windowClass.lpszClassName = kWindowClassName;

        if (!RegisterClassExW(&windowClass) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS) {
            return false;
        }

        hwnd_ = CreateWindowExW(
            0,
            kWindowClassName,
            L"Nautrix",
            WS_OVERLAPPEDWINDOW,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            1280,
            800,
            nullptr,
            nullptr,
            instance,
            this);

        if (!hwnd_) {
            return false;
        }

        ShowWindow(hwnd_, showCommand);
        UpdateWindow(hwnd_);
        return true;
    }

    HWND Handle() const noexcept {
        return hwnd_;
    }

private:
    static LRESULT CALLBACK WindowProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam) {
        BrowserWindow* self = nullptr;

        if (message == WM_NCCREATE) {
            const auto* create = reinterpret_cast<CREATESTRUCTW*>(lParam);
            self = static_cast<BrowserWindow*>(create->lpCreateParams);
            self->hwnd_ = hwnd;
            SetWindowLongPtrW(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(self));
        } else {
            self = reinterpret_cast<BrowserWindow*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
        }

        return self ? self->HandleMessage(message, wParam, lParam) : DefWindowProcW(hwnd, message, wParam, lParam);
    }

    static LRESULT CALLBACK AddressBarProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam) {
        auto* self = reinterpret_cast<BrowserWindow*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
        if (self && message == WM_KEYDOWN && wParam == VK_RETURN) {
            self->NavigateFromAddressBar();
            return 0;
        }

        if (self && self->addressBarOriginalProc_) {
            return CallWindowProcW(self->addressBarOriginalProc_, hwnd, message, wParam, lParam);
        }
        return DefWindowProcW(hwnd, message, wParam, lParam);
    }

    LRESULT HandleMessage(UINT message, WPARAM wParam, LPARAM lParam) {
        switch (message) {
        case WM_CREATE:
            CreateToolbar();
            InitializeWebView();
            return 0;

        case WM_SIZE:
            Layout();
            return 0;

        case WM_DPICHANGED: {
            const auto* rect = reinterpret_cast<RECT*>(lParam);
            SetWindowPos(hwnd_, nullptr, rect->left, rect->top, rect->right - rect->left, rect->bottom - rect->top,
                         SWP_NOZORDER | SWP_NOACTIVATE);
            Layout();
            return 0;
        }

        case WM_COMMAND:
            HandleCommand(LOWORD(wParam));
            return 0;

        case WM_DESTROY:
            if (addressBar_ && addressBarOriginalProc_) {
                SetWindowLongPtrW(addressBar_, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(addressBarOriginalProc_));
            }
            webView_.Reset();
            if (controller_) {
                controller_->Close();
                controller_.Reset();
            }
            PostQuitMessage(0);
            return 0;

        default:
            return DefWindowProcW(hwnd_, message, wParam, lParam);
        }
    }

    int Scale(int value) const {
        const UINT dpi = GetDpiForWindow(hwnd_);
        return MulDiv(value, static_cast<int>(dpi), 96);
    }

    void CreateToolbar() {
        const HINSTANCE instance = reinterpret_cast<HINSTANCE>(GetWindowLongPtrW(hwnd_, GWLP_HINSTANCE));
        backButton_ = CreateWindowExW(0, L"BUTTON", L"<-", WS_CHILD | WS_VISIBLE | WS_TABSTOP,
                                      0, 0, 0, 0, hwnd_, reinterpret_cast<HMENU>(kButtonBack), instance, nullptr);
        forwardButton_ = CreateWindowExW(0, L"BUTTON", L"->", WS_CHILD | WS_VISIBLE | WS_TABSTOP,
                                         0, 0, 0, 0, hwnd_, reinterpret_cast<HMENU>(kButtonForward), instance, nullptr);
        reloadButton_ = CreateWindowExW(0, L"BUTTON", L"Reload", WS_CHILD | WS_VISIBLE | WS_TABSTOP,
                                        0, 0, 0, 0, hwnd_, reinterpret_cast<HMENU>(kButtonReload), instance, nullptr);
        addressBar_ = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", kHomeUrl,
                                      WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_AUTOHSCROLL,
                                      0, 0, 0, 0, hwnd_, reinterpret_cast<HMENU>(kAddressBar), instance, nullptr);
        goButton_ = CreateWindowExW(0, L"BUTTON", L"Go", WS_CHILD | WS_VISIBLE | WS_TABSTOP,
                                    0, 0, 0, 0, hwnd_, reinterpret_cast<HMENU>(kButtonGo), instance, nullptr);

        const HFONT font = static_cast<HFONT>(GetStockObject(DEFAULT_GUI_FONT));
        for (HWND control : {backButton_, forwardButton_, reloadButton_, addressBar_, goButton_}) {
            SendMessageW(control, WM_SETFONT, reinterpret_cast<WPARAM>(font), TRUE);
        }

        SetWindowLongPtrW(addressBar_, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(this));
        addressBarOriginalProc_ = reinterpret_cast<WNDPROC>(
            SetWindowLongPtrW(addressBar_, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(&BrowserWindow::AddressBarProc)));

        EnableWindow(backButton_, FALSE);
        EnableWindow(forwardButton_, FALSE);
        Layout();
    }

    void Layout() {
        if (!hwnd_) {
            return;
        }

        RECT client{};
        GetClientRect(hwnd_, &client);

        const int margin = Scale(8);
        const int gap = Scale(6);
        const int toolbarHeight = Scale(44);
        const int smallButtonWidth = Scale(44);
        const int reloadWidth = Scale(68);
        const int goWidth = Scale(48);
        const int controlHeight = Scale(30);
        const int y = (toolbarHeight - controlHeight) / 2;

        int x = margin;
        MoveWindow(backButton_, x, y, smallButtonWidth, controlHeight, TRUE);
        x += smallButtonWidth + gap;
        MoveWindow(forwardButton_, x, y, smallButtonWidth, controlHeight, TRUE);
        x += smallButtonWidth + gap;
        MoveWindow(reloadButton_, x, y, reloadWidth, controlHeight, TRUE);
        x += reloadWidth + gap;

        const int available = std::max(Scale(120), client.right - x - goWidth - gap - margin);
        MoveWindow(addressBar_, x, y, available, controlHeight, TRUE);
        x += available + gap;
        MoveWindow(goButton_, x, y, goWidth, controlHeight, TRUE);

        if (controller_) {
            RECT webBounds{0, toolbarHeight, client.right, client.bottom};
            controller_->put_Bounds(webBounds);
        }
    }

    void HandleCommand(int command) {
        switch (command) {
        case kButtonBack:
            if (webView_) {
                webView_->GoBack();
            }
            break;
        case kButtonForward:
            if (webView_) {
                webView_->GoForward();
            }
            break;
        case kButtonReload:
        case kCommandReload:
            if (webView_) {
                webView_->Reload();
            }
            break;
        case kButtonGo:
            NavigateFromAddressBar();
            break;
        case kCommandFocusAddress:
            SetFocus(addressBar_);
            SendMessageW(addressBar_, EM_SETSEL, 0, -1);
            break;
        default:
            break;
        }
    }

    void NavigateFromAddressBar() {
        if (!webView_ || !addressBar_) {
            return;
        }

        const int length = GetWindowTextLengthW(addressBar_);
        std::wstring text(static_cast<size_t>(length), L'\0');
        if (length > 0) {
            GetWindowTextW(addressBar_, text.data(), length + 1);
        }

        const std::wstring target = NormalizeNavigationInput(std::move(text));
        if (!target.empty()) {
            webView_->Navigate(target.c_str());
        }
    }

    void InitializeWebView() {
        const std::wstring userDataFolder = GetWebViewUserDataFolder();
        const wchar_t* userData = userDataFolder.empty() ? nullptr : userDataFolder.c_str();

        const HRESULT startResult = CreateCoreWebView2EnvironmentWithOptions(
            nullptr,
            userData,
            nullptr,
            Callback<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler>(
                [this](HRESULT result, ICoreWebView2Environment* environment) -> HRESULT {
                    if (FAILED(result) || !environment || !IsWindow(hwnd_)) {
                        ShowWebViewError(L"Nautrix could not initialize the WebView2 environment. Install or repair the Microsoft Edge WebView2 Runtime.");
                        return FAILED(result) ? result : E_FAIL;
                    }

                    return environment->CreateCoreWebView2Controller(
                        hwnd_,
                        Callback<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler>(
                            [this](HRESULT controllerResult, ICoreWebView2Controller* controller) -> HRESULT {
                                if (FAILED(controllerResult) || !controller || !IsWindow(hwnd_)) {
                                    ShowWebViewError(L"Nautrix could not create the WebView2 browser controller.");
                                    return FAILED(controllerResult) ? controllerResult : E_FAIL;
                                }

                                controller_ = controller;
                                webView_.Reset();
                                const HRESULT webViewResult = controller_->get_CoreWebView2(webView_.GetAddressOf());
                                if (FAILED(webViewResult) || !webView_) {
                                    ShowWebViewError(L"Nautrix could not access the WebView2 browser instance.");
                                    return FAILED(webViewResult) ? webViewResult : E_FAIL;
                                }

                                ConfigureWebView();
                                Layout();
                                webView_->Navigate(kHomeUrl);
                                return S_OK;
                            })
                            .Get());
                })
                .Get());

        if (FAILED(startResult)) {
            ShowWebViewError(L"Nautrix could not start WebView2. Install or repair the Microsoft Edge WebView2 Runtime.");
        }
    }

    void ConfigureWebView() {
        ComPtr<ICoreWebView2Settings> settings;
        if (SUCCEEDED(webView_->get_Settings(settings.GetAddressOf())) && settings) {
            settings->put_IsStatusBarEnabled(FALSE);
            settings->put_AreDefaultContextMenusEnabled(TRUE);
            settings->put_AreDevToolsEnabled(TRUE);
        }

        webView_->add_SourceChanged(
            Callback<ICoreWebView2SourceChangedEventHandler>(
                [this](ICoreWebView2*, ICoreWebView2SourceChangedEventArgs*) -> HRESULT {
                    UpdateAddressBar();
                    return S_OK;
                })
                .Get(),
            &sourceChangedToken_);

        webView_->add_DocumentTitleChanged(
            Callback<ICoreWebView2DocumentTitleChangedEventHandler>(
                [this](ICoreWebView2*, IUnknown*) -> HRESULT {
                    UpdateWindowTitle();
                    return S_OK;
                })
                .Get(),
            &titleChangedToken_);

        webView_->add_NavigationCompleted(
            Callback<ICoreWebView2NavigationCompletedEventHandler>(
                [this](ICoreWebView2*, ICoreWebView2NavigationCompletedEventArgs*) -> HRESULT {
                    UpdateNavigationButtons();
                    UpdateAddressBar();
                    return S_OK;
                })
                .Get(),
            &navigationCompletedToken_);

        webView_->add_NewWindowRequested(
            Callback<ICoreWebView2NewWindowRequestedEventHandler>(
                [this](ICoreWebView2*, ICoreWebView2NewWindowRequestedEventArgs* args) -> HRESULT {
                    LPWSTR uri = nullptr;
                    if (SUCCEEDED(args->get_Uri(&uri)) && uri) {
                        webView_->Navigate(uri);
                        CoTaskMemFree(uri);
                        args->put_Handled(TRUE);
                    }
                    return S_OK;
                })
                .Get(),
            &newWindowRequestedToken_);
    }

    void UpdateNavigationButtons() {
        if (!webView_) {
            return;
        }

        BOOL canGoBack = FALSE;
        BOOL canGoForward = FALSE;
        webView_->get_CanGoBack(&canGoBack);
        webView_->get_CanGoForward(&canGoForward);
        EnableWindow(backButton_, canGoBack);
        EnableWindow(forwardButton_, canGoForward);
    }

    void UpdateAddressBar() {
        if (!webView_ || !addressBar_) {
            return;
        }

        LPWSTR source = nullptr;
        if (SUCCEEDED(webView_->get_Source(&source)) && source) {
            if (GetFocus() != addressBar_) {
                SetWindowTextW(addressBar_, source);
            }
            CoTaskMemFree(source);
        }
    }

    void UpdateWindowTitle() {
        if (!webView_) {
            return;
        }

        LPWSTR title = nullptr;
        if (SUCCEEDED(webView_->get_DocumentTitle(&title)) && title) {
            std::wstring windowTitle = *title ? std::wstring(title) + L" - Nautrix" : L"Nautrix";
            SetWindowTextW(hwnd_, windowTitle.c_str());
            CoTaskMemFree(title);
        }
    }

    void ShowWebViewError(const wchar_t* message) const {
        if (IsWindow(hwnd_)) {
            MessageBoxW(hwnd_, message, L"Nautrix - WebView2 error", MB_OK | MB_ICONERROR);
        }
    }

    HWND hwnd_ = nullptr;
    HWND backButton_ = nullptr;
    HWND forwardButton_ = nullptr;
    HWND reloadButton_ = nullptr;
    HWND addressBar_ = nullptr;
    HWND goButton_ = nullptr;
    WNDPROC addressBarOriginalProc_ = nullptr;

    ComPtr<ICoreWebView2Controller> controller_;
    ComPtr<ICoreWebView2> webView_;

    EventRegistrationToken sourceChangedToken_{};
    EventRegistrationToken titleChangedToken_{};
    EventRegistrationToken navigationCompletedToken_{};
    EventRegistrationToken newWindowRequestedToken_{};
};

int APIENTRY wWinMain(HINSTANCE instance, HINSTANCE, LPWSTR, int showCommand) {
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);

    const HRESULT comResult = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    if (FAILED(comResult)) {
        MessageBoxW(nullptr, L"Nautrix could not initialize COM.", L"Nautrix", MB_OK | MB_ICONERROR);
        return 1;
    }

    BrowserWindow browser;
    if (!browser.Create(instance, showCommand)) {
        CoUninitialize();
        return 1;
    }

    ACCEL accelerators[] = {
        {FVIRTKEY | FCONTROL, 'L', kCommandFocusAddress},
        {FVIRTKEY | FCONTROL, 'R', kCommandReload},
        {FVIRTKEY, VK_F5, kCommandReload},
    };
    HACCEL acceleratorTable = CreateAcceleratorTableW(accelerators, static_cast<int>(std::size(accelerators)));

    MSG message{};
    while (GetMessageW(&message, nullptr, 0, 0) > 0) {
        if (!acceleratorTable || !TranslateAcceleratorW(browser.Handle(), acceleratorTable, &message)) {
            TranslateMessage(&message);
            DispatchMessageW(&message);
        }
    }

    if (acceleratorTable) {
        DestroyAcceleratorTable(acceleratorTable);
    }
    CoUninitialize();
    return static_cast<int>(message.wParam);
}
