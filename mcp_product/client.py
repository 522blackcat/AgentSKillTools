import datetime
import os
import re
import json
import asyncio
from email import message
from idlelib import query
from typing import Optional, List
from contextlib import AsyncExitStack

from openai import OpenAI
from dotenv import load_dotenv

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# 加载项目根目录中的 .env 文件，不依赖启动命令的当前目录
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(env_path)


class MCPClient:

    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.openai_api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL")
        self.model = os.getenv("LLM_MODEL_ID")

        if not self.openai_api_key:
            raise EnvironmentError("Please set environment variable LLM_API_KEY.")
        self.session: Optional[ClientSession] = None
        self.client = OpenAI(api_key=self.openai_api_key, base_url=self.base_url)


    async def connect_to_server(self, server_script_path: str):
        """
        对服务器脚本进行判断，只允许是.py,.js
        :param server_script_path:
        :return:
        """
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("Path endswith is not .py or .js.")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(command=command, args=[server_script_path], env=None)
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.writer = stdio_transport

        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.writer))

        await self.session.initialize()

        response = await self.session.list_tools()
        tools = response.tools
        print('已连接到服务器，支持以下工具：', [tool.name for tool in tools])


    async def process_query(self, query: str) -> str:
        """
        准备初始消息和获取工具列表
        :param query:
        :return: str
        """

        response = await self.session.list_tools()

        available_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,

                }
            } for tool in response.tools
        ]

        # 提取问题的关键词，对文件名进行生成
        # 在接收到用户提问后就应该生成出最后输出的md文档的文件名
        # 因为导出时再生成文件名会导致部分组件无法识别该名词
        keyword_match = re.search(r'(关于|分析|查询|搜索|查看)([^的\s，。、？\n]+)', query)
        keyword = keyword_match.group(2) if keyword_match else "分析对象"
        safe_keyword= re.sub(r'[\\/:*?"<>|]', '', keyword)[:20]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        md_filename = f"sentiment_{safe_keyword}_{timestamp}.md"
        md_path = os.path.join("./sentiment_reports", md_filename)

        # 更新查询，将文件名添加到原始查询中，使大模型在调用工具链时可以识别到该信息
        # 然后调用plan_tool_usage获取工具计划
        query = query.strip() + f" [md_filename={md_filename}] [md_path={md_path}]"

        tool_plan = await self.plan_tool_usage(query, available_tools)

        print(tool_plan)

        tool_outputs = {}
        messages = [{"role": "user", "content": query}]
        for step in tool_plan:
            tool_name = step["name"]
            tool_args = json.loads(step["arguments"])

            for key, val in tool_args.items():
                if isinstance(val, str) and val.startswith("{{") and val.endswith("}}"):
                    ref_key = val.strip("{} ")
                    resolve_val = tool_outputs.get(ref_key, val)
                    tool_args[key] = resolve_val

            # 注入统一的文件名或路径
            if tool_name == "analyze_sentiment" and "filename" not in tool_args:
                tool_args["filename"] = md_filename
            if tool_name == "send_email_with_attachment" and "attachment_path" not in tool_args:
                tool_args["attachment_path"] = md_path

            result = await self.session.call_tool(tool_name, tool_args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_name,
                "content": result.content[0].text
            })

        # 调用大模型生成回复信息，并输出保存结果
        final_response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )

        final_output = final_response.choices[0].message.content

        # 对辅助函数进行定义
        def clean_filename(text: str) -> str:
            text = text.strip()
            text = re.sub(r'[\\/:*?"<>|]', '', text)
            return text[:50]


        safe_filename = clean_filename(query)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_filename}_{timestamp}.txt"
        output_dir = './llm_output'
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, filename)

        with open(file_path, "w") as f:
            f.write(f"👨用户提问：{query}\n\n")
            f.write(f"🤖模型回复：{safe_filename}\n\n")

        print(f"对话已保存为“ {file_path}")

        return final_output

    async def chat_loop(self):

        while True:
            try:
                query = input("\n你：").strip()
                if query.lower() == "exit":
                    break

                response = await self.process_query(query)
                print(response)
            except Exception as e:
                print("error: {}".format(e))


    async def plan_tool_usage(self, query: str, tools: List[dict]) -> List[dict]:
        tool_list_text = "\n".join([
            f"- {tool['function']['name']}: {tool["function"]["description"]}"
            for tool in tools
        ])

        system_prompt = {
            "role": "system",
            "content": (
                "你是一个智能任务规划助手,用户会给出一句自然语言请求。\n"
                "你只能从以下工具中选择（严格使用工具名词）：\n"
                f"{tool_list_text}\n"
                "如果多个工具需要串联，后续步骤中可以使用{{上一步工具名}}占位。\n"
                "返回格式： JSON 数组，每个对象包含name 和 arguments字段。\n"
                "不要返回自然语言处理，不要使用未列出的工具名。"
            )
        }

        planning_messages = [
            system_prompt,
            {"role": "user", "content": query}
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=planning_messages,
            tools=tools,
            tool_choice="none"
        )

        tool_calls = response.choices[0].message.tool_calls
        try:
            return [{
                "name": tool_call.function.name,
                "arguments": tool_call.function.arguments
            } for tool_call in tool_calls]
        except Exception as e:
            print(f"工具调用链失败：: {e}\n\n原始返回{tool_calls}")

    async def clean_up(self):
        await self.exit_stack.aclose()


async def main():
    server_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
    client = MCPClient()

    try:
        await client.connect_to_server(server_script_path)
        await client.chat_loop()
    finally:
        await client.clean_up()


if __name__ == '__main__':
    asyncio.run(main())






