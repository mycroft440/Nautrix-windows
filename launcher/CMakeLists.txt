cmake_minimum_required(VERSION 3.24)

project(NautrixLauncher LANGUAGES CXX)

set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

add_executable(NautrixLauncher WIN32 nautrix_launcher.cpp)
target_compile_features(NautrixLauncher PRIVATE cxx_std_23)
target_compile_definitions(NautrixLauncher PRIVATE UNICODE _UNICODE)
target_link_libraries(NautrixLauncher PRIVATE ws2_32 iphlpapi winhttp shell32)

add_executable(NautrixNetworkSettings WIN32 network_settings.cpp)
target_compile_features(NautrixNetworkSettings PRIVATE cxx_std_23)
target_compile_definitions(NautrixNetworkSettings PRIVATE UNICODE _UNICODE)
target_link_libraries(NautrixNetworkSettings PRIVATE shell32)

if(MSVC)
  foreach(target NautrixLauncher NautrixNetworkSettings)
    # Make the helpers self-contained and remove unreachable duplicate code.
    # /MT deliberately increases the helper EXE sizes versus /MD; see TEST_INSTALL.md.
    target_compile_options(${target} PRIVATE
      /W4
      /WX
      /permissive-
      /EHsc
      "$<$<CONFIG:Release>:/Gy>"
      "$<$<CONFIG:Release>:/Gw>"
    )
    target_link_options(${target} PRIVATE
      "$<$<CONFIG:Release>:/OPT:REF>"
      "$<$<CONFIG:Release>:/OPT:ICF>"
    )
    set_property(TARGET ${target} PROPERTY INTERPROCEDURAL_OPTIMIZATION_RELEASE TRUE)
  endforeach()
endif()
