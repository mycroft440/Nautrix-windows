cmake_minimum_required(VERSION 3.24)

project(NautrixLauncher LANGUAGES CXX)

add_executable(NautrixLauncher main.cpp)
target_compile_features(NautrixLauncher PRIVATE cxx_std_23)
target_compile_definitions(NautrixLauncher PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX UNICODE _UNICODE)
target_link_libraries(NautrixLauncher PRIVATE ws2_32 iphlpapi)

if(MSVC)
  target_compile_options(NautrixLauncher PRIVATE /W4 /permissive- /EHsc)
endif()
