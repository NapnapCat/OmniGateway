FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cmake \
    libgrpc++-dev \
    libprotobuf-dev \
    pkg-config \
    protobuf-compiler-grpc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY local_embedding_service /app/local_embedding_service

RUN cmake -S /app/local_embedding_service -B /app/local_embedding_service/build \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_EXE_LINKER_FLAGS="-lgpr" \
        -DUSE_PREGENERATED_PROTO=OFF \
    && cmake --build /app/local_embedding_service/build --config Release -j"$(nproc)" \
    && cp /app/local_embedding_service/build/embedding_server /usr/local/bin/embedding_server

EXPOSE 50051

CMD ["/usr/local/bin/embedding_server"]