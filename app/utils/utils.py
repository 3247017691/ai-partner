# -----------工具函数------------
from datetime import datetime


def generate_session_name():
    """生成会话名称, 格式是: 年-月-日_时-分-秒"""
    return datetime.now().strftime('%Y-%m-%d_%H-%M-%S')