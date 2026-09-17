import os
import datetime

from prompt_product.evaluator import evaluate_prompt
from prompt_product.records import append_prompt_record


# 获取当前日期和时间
def get_current_datetime() -> str:
    """
    获取真实的当前日期和时间。
    :return: 当前日期和时间的字符串表示。
    """
    current_datetime = datetime.datetime.now()
    formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
    return formatted_datetime


def get_default_path() -> str:
    """
    获取默认要写入的文件路径。文件名固定为 prompt_result_file.py。
    :return: str
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompt_result_file.py')
    return path


def write_prompt_add_file(prompt: str, file_path: str = "", prompt_type: str = "agent") -> str:
    """
    必须使用此工具保存关键词生成的完整 Prompt。按原样追加写入完整的 Python 变量赋值文本，并同步写入训练记录。
    :param prompt: str
    :param file_path: str
    :param prompt_type: str
    :return: 写入结果和实际文件路径
    """
    if file_path == "":
        file_path = get_default_path()
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(prompt + '\n\n')
    record = append_prompt_record(prompt=prompt, prompt_type=prompt_type)
    score = record["evaluation"]["score"]
    level = record["evaluation"]["level"]
    return f"已写入文件: {file_path}; 训练记录已保存; 质量评分: {score}/100 ({level})"


def evaluate_prompt_text(prompt: str) -> str:
    """
    评估一段 Prompt 是否具备生产级 Agent Prompt 的关键结构，返回评分和改进建议。
    :param prompt: str
    :return: str
    """
    evaluation = evaluate_prompt(prompt)
    suggestions = "\n".join(f"- {item}" for item in evaluation.suggestions)
    missing = "、".join(evaluation.missing_sections) or "无"
    strengths = "、".join(evaluation.strengths) or "无"
    return (
        f"评分: {evaluation.score}/100 ({evaluation.level})\n"
        f"是否通过: {evaluation.passed}\n"
        f"缺失部分: {missing}\n"
        f"增强项: {strengths}\n"
        f"建议:\n{suggestions}"
    )
