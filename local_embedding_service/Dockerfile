# 使用预编译二进制文件
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# 更换镜像源（可选，加快下载）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list

# 只安装运行时依赖（Debian包名）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgrpc++-1 \
    libprotobuf32 \
    ca-certificates \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 直接复制本地编译好的二进制文件
COPY build/embedding_server /app/embedding_server

# 复制其他需要的文件
COPY generated/ /app/generated/ 2>/dev/null || true
COPY include/ /app/include/ 2>/dev/null || true

RUN chmod +x /app/embedding_server && \
    ldd /app/embedding_server  # 检查依赖是否满足

EXPOSE 50051

CMD ["/app/embedding_server"]