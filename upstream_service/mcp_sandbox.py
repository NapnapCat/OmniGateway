import json
from typing import Any


def mock_weather_tool(city: str) -> str:
    weather_map = {
        "北京": "北京今天天气晴，气温 22C，东北风 2 级。",
        "上海": "上海今天天气多云，气温 25C，东南风 3 级。",
        "广州": "广州今天天气小雨，气温 28C，南风 2 级。",
    }
    return weather_map.get(city, f"{city}今天天气未知，当前为沙盒模拟结果。")


def dispatch_jsonrpc(request_packet: dict[str, Any]) -> dict[str, Any]:
    request_id = request_packet.get("id")

    if request_packet.get("jsonrpc") != "2.0":
        return {
            "jsonrpc": "2.0",  # JSON-RPC 协议版本，响应端必须明确回写 2.0
            "error": {
                "code": -32600,
                "message": "Invalid Request: jsonrpc must be 2.0",
            },
            "id": request_id,  # 用于让客户端知道这条响应对应哪一次调用
        }

    if request_packet.get("method") != "tools/call":
        return {
            "jsonrpc": "2.0",  # JSON-RPC 协议版本
            "error": {
                "code": -32601,
                "message": "Method not found",
            },
            "id": request_id,  # 透传请求 id，便于客户端做请求-响应匹配
        }

    params = request_packet.get("params", {})
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    if tool_name != "mock_weather_tool":
        return {
            "jsonrpc": "2.0",  # JSON-RPC 协议版本
            "error": {
                "code": -32602,
                "message": f"Unknown tool: {tool_name}",
            },
            "id": request_id,  # 对应原始请求 id
        }

    city = arguments.get("city", "")
    tool_result = mock_weather_tool(city)

    return {
        "jsonrpc": "2.0",  # JSON-RPC 协议版本，表示这是标准 2.0 响应包
        "result": {  # MCP tools/call 的执行结果载荷，服务端把工具输出放在这里返回
            "content": [
                {
                    "type": "text",  # 结果内容类型，这里用 text 模拟最常见的文本返回
                    "text": tool_result,  # 工具真正执行后的结果文本
                }
            ]
        },
        "id": request_id,  # 必须与请求包 id 一致，客户端据此关联响应
    }


def main() -> None:
    request_packet = {
        "jsonrpc": "2.0",  # JSON-RPC 协议版本，MCP 底层消息遵循该格式
        "method": "tools/call",  # MCP 方法名，表示客户端请求调用某个工具
        "params": {  # 方法参数区，描述要调用哪个工具以及传什么参数
            "name": "mock_weather_tool",  # 工具名，服务端用它做路由分发
            "arguments": {  # 工具入参，等价于一次函数调用的参数对象
                "city": "上海"
            },
        },
        "id": 1,  # 请求唯一标识，客户端用它匹配异步或同步响应
    }

    print("➡️ 发送的 JSON 请求包")
    print(json.dumps(request_packet, indent=2, ensure_ascii=False))

    response_packet = dispatch_jsonrpc(request_packet)

    print("\n⬅️ 收到的 JSON 响应包")
    print(json.dumps(response_packet, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
