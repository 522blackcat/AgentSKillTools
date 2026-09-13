import os
import json
import smtplib
from datetime import datetime

from email.message import EmailMessage

import httpx
from mcp.server.mcpserver import MCPServer

from dotenv import load_dotenv
from openai import OpenAI

# 加载项目根目录中的 .env 文件，不依赖启动命令的当前目录
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(env_path)


mcp = MCPServer("NewServer")


@mcp.tool()
async def search_google_news(keyword: str) -> str:
    """
    使用Serper Api (Google Search 封装)根据关键词搜索新闻内容，返回前5条标题、描述和链接。

    参数:
        keyword（str）: 关键词，如"小米汽车"

    返回:
        str: JSON 字符串，包含新闻标题、描述、链接
    """

    api_key = os.getenv("SERPER_API_KEY")

    if api_key is None:
        return "未配置SERPER_API_KEY,请在.env中配置"
    # 这里返回假数据
    articles = [
        {"title": "test1", "desc": "开心", "url": "url1"},
        {"title": "test2", "desc": "快乐", "url": "url2"},
        {"title": "test3", "desc": "失望", "url": "url3"},
        {"title": "test4", "desc": "难过", "url": "url4"},
        {"title": "test5", "desc": "疯狂", "url": "url5"},
    ]
    output_dir = './google_news'
    os.makedirs(output_dir, exist_ok=True)
    filename = f"google_news_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    file_path = os.path.join(output_dir, filename)

    with open(file_path, "w", encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    return (f"已获取与[{keyword}]相关的前5条google新闻：\n"
            f"{json.dump(articles, ensure_ascii=False, indent=2)}\n"
            f"已保存到：{file_path}")


@mcp.tool()
async def analyze_sentiment(text: str, filename: str) -> str:
    """
    对传入的一段文本内容进行情感分析，并保存为指定的Markdown文件

    参数:
        text（str）: 新闻描述或文本内容
        filename（str）: 保存的Markdown文件名(不含路径)

    返回:
        str: 完整的文件路径（用于邮件发送）
    """

    client = OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL")
    )

    prompt = f"请对以下新闻内容进行情感倾向分析，并说明原因:\n\n{text}"
    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL_ID"),
        messages=[{"role": "user", "content": prompt}]
    )
    result = response.choices[0].message.content.strip()

    markdown = f"""# 舆情分析报告
    
    **分析时间：**{datetime.now().strftime('%Y%m%d_%H%M%S')}
    
    ---
    
    ## 原始文本
    
    {text}
    
    ---
    
    ## 分析结果
    
    {result}

    """

    output_dir = './sentiment_reports'
    os.makedirs(output_dir, exist_ok=True)

    if not filename:
        filename = f"""sentiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"""
    file_path = os.path.join(output_dir, filename)
    with open(file_path, "w", encoding='utf-8') as f:
        f.write(markdown)

    return file_path


if __name__ == '__main__':
    mcp.run(transport='stdio')
