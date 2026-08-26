cmake_minimum_required(VERSION 3.25)

project(NautrixWindows VERSION 0.1.0 LANGUAGES CXX)

if(NOT WIN32)
    message(FATAL_ERROR "Nautrix Windows currently supports Windows only.")
endif()

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(NAUTRIX_WEBVIEW2_VERSION "1.0.4129.50" CACHE STRING "Pinned Microsoft.Web.WebView2 SDK version")
set(NAUTRIX_WEBVIEW2_ROOT
    "${CMAKE_SOURCE_DIR}/packages/Microsoft.Web.WebView2.${NAUTRIX_WEBVIEW2_VERSION}"
    CACHE PATH "Path to the extracted Microsoft.Web.WebView2 NuGet package")

set(WEBVIEW2_INCLUDE_DIR "${NAUTRIX_WEBVIEW2_ROOT}/build/native/include")

if(CMAKE_SIZEOF_VOID_P EQUAL 8)
    set(WEBVIEW2_ARCH "x64")
else()
    message(FATAL_ERROR "Nautrix currently targets Windows x64 only.")
endif()

set(WEBVIEW2_LOADER_STATIC
    "${NAUTRIX_WEBVIEW2_ROOT}/build/native/${WEBVIEW2_ARCH}/WebView2LoaderStatic.lib")

if(NOT EXISTS "${WEBVIEW2_INCLUDE_DIR}/WebView2.h" OR NOT EXISTS "${WEBVIEW2_LOADER_STATIC}")
    message(FATAL_ERROR
        "WebView2 SDK was not found. Run: powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1")
endif()

add_executable(Nautrix WIN32
    src/main.cpp
)

target_include_directories(Nautrix PRIVATE
    "${WEBVIEW2_INCLUDE_DIR}"
)

target_compile_definitions(Nautrix PRIVATE
    UNICODE
    _UNICODE
    WIN32_LEAN_AND_MEAN
    NOMINMAX
    WINVER=0x0A00
    _WIN32_WINNT=0x0A00
)

if(MSVC)
    target_compile_options(Nautrix PRIVATE
        /W4
        /permissive-
        /EHsc
        /utf-8
    )
endif()

target_link_libraries(Nautrix PRIVATE
    "${WEBVIEW2_LOADER_STATIC}"
    advapi32
    gdi32
    ole32
    shell32
    shlwapi
    user32
    version
)

set_target_properties(Nautrix PROPERTIES
    OUTPUT_NAME "Nautrix"
)
