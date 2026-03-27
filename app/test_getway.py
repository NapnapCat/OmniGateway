# test_gateway.py
import asyncio
from openai import AsyncOpenAI

async def mock_go_gateway():
    print("🟢 [Go网关模拟器] 启动，准备向 Python 核心大脑发请求...")

    # 【核心奥秘】这里不填智谱/DeepSeek的地址，而是填你自己的本地 8000 端口！
    client = AsyncOpenAI(
        api_key="sk-local-test-key",
        base_url="http://localhost:8000/v1"
    )

    try:
        # 发起流式请求
        response = await client.chat.completions.create(
            model="agent-core-v1", # 用你们协商好的默认名称
            messages=[{"role": "user", "content": "你好，测试一下网关连通性。"}],
            stream=True
        )

        print("🟢 [Go网关模拟器] 成功建立连接，开始接收数据流：")
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
        print("\n🟢 [Go网关模拟器] 接收完毕！")
        
    except Exception as e:
        print(f"\n🔴 [Go网关模拟器] 收到 HTTP 级报错: {e}")

if __name__ == "__main__":
    asyncio.run(mock_go_gateway())
