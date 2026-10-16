# ═══════════════════════════════════════════════════════════════════════════# NEXUS W3C VALIDATOR — CMakeLists.txt
# Auteur : Aissa Mohammedi (DGK)
# License : NEXUS-OPEN-2.0
# ═══════════════════════════════════════════════════════════════════════════

cmake_minimum_required(VERSION 3.20)

# ─── Project ───
project(nexus_w3c_validator
VERSION 1.0.0
DESCRIPTION "NEXUS W3C Validator — Multi-Standard Code Validator"
HOMEPAGE_URL "https://github.com/Aissamohammedi88/nexus-w3c-validator"
LANGUAGES C CXX
)

# ─── C++ Standard ───
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# ─── Default Build Type ───
if(NOT CMAKE_BUILD_TYPE)
set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

# ─── Export compile commands ───
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# ─── Options ───
option(BUILD_TESTS "Build tests" ON)
option(BUILD_DOCS "Build documentation" OFF)
option(ENABLE_COVERAGE "Enable coverage" OFF)
option(ENABLE_SANITIZERS "Enable sanitizers" OFF)

# ─── Output directories ───
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# ─── Compiler flags ───
if(MSVC)
add_compile_options(/W4 /permissive- /Zc:__cplusplus)
add_compile_definitions(_CRT_SECURE_NO_WARNINGS NOMINMAX)
else()
add_compile_options(-Wall -Wextra -Wpedantic -Wshadow -Wconversion)
endif()

# ─── Sanitizers ───
if(ENABLE_SANITIZERS AND NOT MSVC)
add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
add_link_options(-fsanitize=address,undefined)
endif()

# ─── Coverage ───
if(ENABLE_COVERAGE AND NOT MSVC)
add_compile_options(--coverage -fprofile-arcs -ftest-coverage)
add_link_options(--coverage)
endif()

# ─── Source files ───
set(SOURCES
src/main.cpp
src/validator.cpp
src/html_validator.cpp
src/css_validator.cpp
src/i18n_checker.cpp
src/feed_validator.cpp
src/rdf_validator.cpp
)

set(HEADERS
include/nexus/validator.hpp
include/nexus/html_validator.hpp
include/nexus/css_validator.hpp
include/nexus/i18n_checker.hpp
include/nexus/feed_validator.hpp
include/nexus/rdf_validator.hpp
)

# ─── Main executable ───
add_executable(nexus_w3c_validator ${SOURCES})
target_include_directories(nexus_w3c_validator PRIVATE include)

# ─── Tests ───
if(BUILD_TESTS)
enable_testing()
add_subdirectory(tests)
endif()

# ─── Install ───
include(GNUInstallDirs)
install(TARGETS nexus_w3c_validator
RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

# ─── CPack ───
set(CPACK_PROJECT_NAME "NEXUS W3C Validator")
set(CPACK_PROJECT_VERSION ${PROJECT_VERSION})
include(CPack)
