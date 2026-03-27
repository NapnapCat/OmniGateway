cmake_minimum_required(VERSION 3.15)
project(local_embedding_service LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Set a default build type.
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE "Release" CACHE STRING "Build type" FORCE)
endif()

# Using vcpkg toolchain is recommended:
#   cmake -B build -S . -DCMAKE_TOOLCHAIN_FILE=/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake

# Prefer system-installed protobuf (avoid conda/anaconda mixing)
list(APPEND CMAKE_IGNORE_PATH "/home/liyufeng/anaconda3" "/opt/conda")
set(Protobuf_PROTOC_EXECUTABLE "/usr/bin/protoc" CACHE FILEPATH "System protoc executable" FORCE)
set(Protobuf_INCLUDE_DIR "/usr/include" CACHE PATH "System protobuf include directory" FORCE)
set(Protobuf_LIBRARY "/usr/lib/x86_64-linux-gnu/libprotobuf.so" CACHE FILEPATH "System protobuf library" FORCE)
set(Protobuf_LIBRARIES "/usr/lib/x86_64-linux-gnu/libprotobuf.so" CACHE FILEPATH "System protobuf libraries" FORCE)
set(Protobuf_PROTOC_LIBRARY "/usr/lib/x86_64-linux-gnu/libprotoc.so" CACHE FILEPATH "System libprotoc library" FORCE)

find_program(GRPC_CPP_PLUGIN_EXECUTABLE grpc_cpp_plugin HINTS /usr/bin /usr/local/bin)
if(NOT GRPC_CPP_PLUGIN_EXECUTABLE)
  find_program(GRPC_CPP_PLUGIN_EXECUTABLE protoc-gen-grpc HINTS /usr/bin /usr/local/bin)
endif()
if(NOT GRPC_CPP_PLUGIN_EXECUTABLE)
  message(FATAL_ERROR "grpc_cpp_plugin not found. Install protobuf-compiler-grpc or use an environment with grpc_cpp_plugin available.")
endif()
message(STATUS "Using grpc_cpp_plugin: ${GRPC_CPP_PLUGIN_EXECUTABLE}")

find_package(Protobuf REQUIRED)

find_path(GRPC_INCLUDE_DIR
  NAMES grpcpp/grpcpp.h
  HINTS /usr/include /usr/local/include
)
find_library(GRPCPP_LIBRARY
  NAMES grpc++
  HINTS /usr/lib /usr/lib/x86_64-linux-gnu /usr/local/lib
)
find_library(GRPC_LIBRARY
  NAMES grpc
  HINTS /usr/lib /usr/lib/x86_64-linux-gnu /usr/local/lib
)

if(NOT GRPCPP_LIBRARY OR NOT GRPC_LIBRARY)
  message(FATAL_ERROR "gRPC libraries not found. Install libgrpc++-dev and libgrpc-dev")
endif()

if(NOT GRPC_INCLUDE_DIR)
  message(FATAL_ERROR "gRPC headers not found. Install gRPC development headers")
endif()

set(PROTO_SRC_DIR "${CMAKE_CURRENT_SOURCE_DIR}/proto")
set(PROTO_FILE "${PROTO_SRC_DIR}/embedding.proto")
set(GENERATED_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
file(MAKE_DIRECTORY ${GENERATED_DIR})

option(USE_PREGENERATED_PROTO "Use pre-generated protobuf/gRPC code" ON)

if(USE_PREGENERATED_PROTO)
  message(STATUS "Using pre-generated protobuf/gRPC files from ${CMAKE_CURRENT_SOURCE_DIR}/generated")
  set(EMBEDDING_PB_CPP "${CMAKE_CURRENT_SOURCE_DIR}/generated/embedding.pb.cc")
  set(EMBEDDING_PB_H "${CMAKE_CURRENT_SOURCE_DIR}/generated/embedding.pb.h")
  set(EMBEDDING_GRPC_PB_CPP "${CMAKE_CURRENT_SOURCE_DIR}/generated/embedding.grpc.pb.cc")
  set(EMBEDDING_GRPC_PB_H "${CMAKE_CURRENT_SOURCE_DIR}/generated/embedding.grpc.pb.h")
else()
  find_program(GRPC_CPP_PLUGIN_EXECUTABLE grpc_cpp_plugin)
  if(NOT GRPC_CPP_PLUGIN_EXECUTABLE)
    find_program(GRPC_CPP_PLUGIN_EXECUTABLE protoc-gen-grpc)
  endif()
  if(NOT GRPC_CPP_PLUGIN_EXECUTABLE)
    message(FATAL_ERROR "grpc_cpp_plugin/protoc-gen-grpc not found. Install gRPC to generate code or enable USE_PREGENERATED_PROTO.")
  endif()

  set(EMBEDDING_PB_CPP "${GENERATED_DIR}/embedding.pb.cc")
  set(EMBEDDING_PB_H "${GENERATED_DIR}/embedding.pb.h")
  set(EMBEDDING_GRPC_PB_CPP "${GENERATED_DIR}/embedding.grpc.pb.cc")
  set(EMBEDDING_GRPC_PB_H "${GENERATED_DIR}/embedding.grpc.pb.h")

  add_custom_command(
    OUTPUT ${EMBEDDING_PB_CPP} ${EMBEDDING_PB_H} ${EMBEDDING_GRPC_PB_CPP} ${EMBEDDING_GRPC_PB_H}
    COMMAND ${Protobuf_PROTOC_EXECUTABLE}
            --proto_path=${PROTO_SRC_DIR}
            --cpp_out=${GENERATED_DIR}
            --grpc_out=${GENERATED_DIR}
            --plugin=protoc-gen-grpc=${GRPC_CPP_PLUGIN_EXECUTABLE}
            ${PROTO_FILE}
    DEPENDS ${PROTO_FILE}
    COMMENT "Generating C++ protobuf and gRPC code from ${PROTO_FILE}"
  )
endif()

add_library(embedding_proto
  ${EMBEDDING_PB_CPP}
  ${EMBEDDING_GRPC_PB_CPP}
)
target_include_directories(embedding_proto
  PUBLIC
    /usr/include
    ${GENERATED_DIR}
)

target_link_libraries(embedding_proto
  PUBLIC
    ${Protobuf_LIBRARIES}
    ${GRPCPP_LIBRARY}
    ${GRPC_LIBRARY}
)

add_library(embedding_service_impl
  src/embedding_service_impl.cpp
)

target_include_directories(embedding_service_impl
  PUBLIC
    include
    ${GENERATED_DIR}
    /usr/include
)

target_link_libraries(embedding_service_impl
  PUBLIC
    embedding_proto
    ${GRPCPP_LIBRARY}
    ${GRPC_LIBRARY}
)

add_executable(embedding_server
  src/main.cpp
)

target_include_directories(embedding_server
  PRIVATE
    include
)

target_link_libraries(embedding_server
  PRIVATE
    embedding_service_impl
    embedding_proto
    ${GRPCPP_LIBRARY}
    ${GRPC_LIBRARY}
)

install(TARGETS embedding_server
  RUNTIME DESTINATION bin
)
