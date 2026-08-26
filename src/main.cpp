#include "BrowserWindow.h"

#include <windows.h>

#include <iterator>

int APIENTRY wWinMain(HINSTANCE instance, HINSTANCE, LPWSTR, int showCommand) {
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);

    const HRESULT comResult = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    if (FAILED(comResult)) {
        MessageBoxW(nullptr, L"Nautrix could not initialize COM.", L"Nautrix", MB_OK | MB_ICONERROR);
        return 1;
    }

    nautrix::BrowserWindow browser;
    if (!browser.Create(instance, showCommand)) {
        CoUninitialize();
        return 1;
    }

    ACCEL accelerators[] = {
        {FVIRTKEY | FCONTROL, 'L', nautrix::BrowserWindow::kCommandFocusAddress},
        {FVIRTKEY | FCONTROL, 'R', nautrix::BrowserWindow::kCommandReload},
        {FVIRTKEY, VK_F5, nautrix::BrowserWindow::kCommandReload},
    };

    HACCEL acceleratorTable =
        CreateAcceleratorTableW(accelerators, static_cast<int>(std::size(accelerators)));

    MSG message{};
    while (GetMessageW(&message, nullptr, 0, 0) > 0) {
        if (!acceleratorTable ||
            !TranslateAcceleratorW(browser.Handle(), acceleratorTable, &message)) {
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
