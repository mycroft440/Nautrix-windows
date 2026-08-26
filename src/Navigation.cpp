#include "Navigation.h"

#include <windows.h>

#include <iomanip>
#include <sstream>
#include <string>
#include <utility>

namespace nautrix {
namespace {

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

    const int size = WideCharToMultiByte(
        CP_UTF8,
        0,
        input.c_str(),
        static_cast<int>(input.size()),
        nullptr,
        0,
        nullptr,
        nullptr);
    if (size <= 0) {
        return {};
    }

    std::string utf8(static_cast<size_t>(size), '\0');
    if (WideCharToMultiByte(
            CP_UTF8,
            0,
            input.c_str(),
            static_cast<int>(input.size()),
            utf8.data(),
            size,
            nullptr,
            nullptr) <= 0) {
        return {};
    }

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

} // namespace

std::wstring NormalizeNavigationInput(std::wstring input) {
    input = Trim(std::move(input));
    if (input.empty()) {
        return {};
    }

    if (input.find(L"://") != std::wstring::npos || input.rfind(L"about:", 0) == 0) {
        return input;
    }

    const bool looksLikeHost =
        input.find(L' ') == std::wstring::npos &&
        (input.find(L'.') != std::wstring::npos || input.rfind(L"localhost", 0) == 0);

    if (looksLikeHost) {
        return L"https://" + input;
    }

    const std::string encoded = UrlEncodeUtf8(input);
    return L"https://www.google.com/search?q=" + std::wstring(encoded.begin(), encoded.end());
}

} // namespace nautrix
