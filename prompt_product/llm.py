import os
import json
from types import SimpleNamespace
from openai import OpenAI
from typing import List, Dict, Any
from prompt_product.utils import function_to_json
from prompt_product.prompt import build_system_prompt
from prompt_product.tools import get_current_datetime, write_prompt_add_file, get_default_path
from dotenv import load_dotenv


# 加载项目根目录中的 .env 文件，不依赖启动命令的当前目录
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(env_path)


class Agent:
    def __init__(self, client: OpenAI, model: str = "Qwen/Qwen2.5-32B-Instruct", tools: List = [],
                 verbose: bool = True):
        self.client = client
        self.tools = tools
        self.model = model
        self.messages = [
            {"role": "system", "content": build_system_prompt(self.tools)},
        ]
        self.tool_map = {tool.__name__: tool for tool in self.tools}
        self.verbose = verbose

    def get_tool_schema(self) -> List[Dict[str, Any]]:
        # 获取所有工具的 JSON 模式
        return [function_to_json(tool) for tool in self.tools]

    def handle_tool_call(self, tool_call):
        # 处理工具调用
        function_name = tool_call.function.name
        function_args = tool_call.function.arguments  # 此时这是一个 JSON 字符串
        function_id = tool_call.id

        # 1. 将 JSON 字符串解析为 Python 字典
        try:
            args_dict = json.loads(function_args)
        except json.JSONDecodeError:
            args_dict = {}  # 防止模型胡言乱语返回无效 JSON

        # 2. 动态获取函数并执行（更安全、更优雅的方式）
        func = self.tool_map.get(function_name)

        if func:
            # 现在的 args_dict 是真正的字典了，可以用 ** 解包
            function_call_content = func(**args_dict)
        else:
            function_call_content = f"Error: 找不到名为 {function_name} 的工具"

        # 3. 组装返回给模型的工具结果
        return {
            "role": "tool",
            "content": str(function_call_content),  # 强制转为字符串，确保 API 不报错
            "tool_call_id": function_id,
        }

    def parse_text_tool_call(self, content):
        """兼容模型把工具调用错误输出为 JSON 文本的情况。"""
        if not isinstance(content, str):
            return None
        text = content.strip()
        if text.startswith('```'):
            lines = text.splitlines()
            text = '\n'.join(lines[1:-1]).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        function_name = data.get('name')
        arguments = data.get('arguments', {})
        if function_name not in self.tool_map or not isinstance(arguments, dict):
            return None
        return SimpleNamespace(
            id='text-tool-call',
            function=SimpleNamespace(
                name=function_name,
                arguments=json.dumps(arguments, ensure_ascii=False),
            ),
        )

    def get_completion(self, prompt) -> str:
        self.messages.append({"role": "user", "content": prompt})

        while True:
            # 获取模型的完成响应
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=self.get_tool_schema(),
                tool_choice="auto",
                stream=False,
            )
            message = response.choices[0].message
            # print(message)
            tool_calls = message.tool_calls or []
            if not tool_calls:
                text_tool_call = self.parse_text_tool_call(message.content)
                if text_tool_call:
                    tool_calls = [text_tool_call]

            if not tool_calls:
                break

            # 将包含 tool_calls 的完整 assistant 消息添加到历史中
            assistant_message = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    }
                    for tool_call in tool_calls
                ]
            }
            self.messages.append(assistant_message)

            # 处理工具调用
            tool_list = [
                [tool_call.function.name, tool_call.function.arguments]
                for tool_call in tool_calls
            ]
            if self.verbose:
                print("模型调用工具：", tool_list)

            for tool_call in tool_calls:
                # 处理工具调用并将结果添加到消息列表中
                tool_result = self.handle_tool_call(tool_call)
                self.messages.append(tool_result)
                if self.verbose:
                    print(
                        f"工具执行完成：{tool_call.function.name} -> "
                        f"{tool_result['content']}"
                    )

        # 将模型的完成响应添加到消息列表中
        self.messages.append({"role": "assistant", "content": message.content})
        return message.content


client = OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
    )

agent = Agent(
    client=client,
    model=os.getenv("LLM_MODEL_ID"),
    tools=[get_current_datetime, get_default_path,  write_prompt_add_file],
)


if __name__ == '__main__':
    # 使用彩色输出区分用户输入和AI回答
    prompt = input("\033[94mUser: \033[0m")  # 蓝色显示用户输入提示
    response = agent.get_completion(prompt)
    print("\033[92mAssistant: \033[0m", response)  # 绿色显示AI助手回答