#include <iostream>
#include <memory>
#include <string>

#include <grpcpp/grpcpp.h>

#include "embedding_service_impl.h"

int main() {
  const std::string port = std::getenv("SERVE_PORT") ? std::getenv("SERVE_PORT") : "50051";
  const std::string address = "0.0.0.0:" + port;

  embedding_service::EmbeddingServiceImpl service;
  grpc::ServerBuilder builder;
  builder.AddListeningPort(address, grpc::InsecureServerCredentials());
  builder.RegisterService(&service);

  std::unique_ptr<grpc::Server> server(builder.BuildAndStart());
  if (!server) {
    std::cerr << "[Error] Failed to start local embedding mock on port " << port
              << std::endl;
    return 1;
  }

  std::cout << "[Info] Local embedding mock listening on port " << port
            << std::endl;
  server->Wait();
  return 0;
}