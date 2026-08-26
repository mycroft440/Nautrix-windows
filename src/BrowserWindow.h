#pragma once

#include <windows.h>
#include <wrl.h>
#include <WebView2.h>

namespace nautrix {

class BrowserWindow {
public:
    static constexpr int kCommandFocusAddress = 2001;
    static constexpr int kCommandReload = 2002;

    bool Create(HINSTANCE instance, int showCommand);
    HWND Handle() const noexcept;

private:
    static LRESULT CALLBACK WindowProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam);
    static LRESULT CALLBACK AddressBarProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam);

    LRESULT HandleMessage(UINT message, WPARAM wParam, LPARAM lParam);
    int Scale(int value) const;
    void CreateToolbar();
    void Layout();
    void HandleCommand(int command);
    void NavigateFromAddressBar();
    void InitializeWebView();
    void ConfigureWebView();
    void UpdateNavigationButtons();
    void UpdateAddressBar();
    void UpdateWindowTitle();
    void ShowWebViewError(const wchar_t* message) const;

    HWND hwnd_ = nullptr;
    HWND backButton_ = nullptr;
    HWND forwardButton_ = nullptr;
    HWND reloadButton_ = nullptr;
    HWND addressBar_ = nullptr;
    HWND goButton_ = nullptr;
    WNDPROC addressBarOriginalProc_ = nullptr;

    Microsoft::WRL::ComPtr<ICoreWebView2Controller> controller_;
    Microsoft::WRL::ComPtr<ICoreWebView2> webView_;

    EventRegistrationToken sourceChangedToken_{};
    EventRegistrationToken titleChangedToken_{};
    EventRegistrationToken navigationCompletedToken_{};
    EventRegistrationToken newWindowRequestedToken_{};
};

} // namespace nautrix
