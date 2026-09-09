import os
import datetime


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


def write_prompt_add_file(prompt: str, file_path: str = "") -> str:
    """
    必须使用此工具保存关键词生成的完整 Prompt。按原样追加写入完整的 Python 变量赋值文本，保留换行、缩进和标点；不提供路径时写入默认文件。
    :param prompt: str
    :param file_path: str
    :return: 写入结果和实际文件路径
    """
    if file_path == "":
        file_path = get_default_path()
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(prompt + '\n\n')
    return f"已写入文件: {file_path}"
