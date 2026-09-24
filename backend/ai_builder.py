"""
ai_builder.py —— AI Builder 引擎（DeepSeek）

把用户的一句话需求，交给 DeepSeek 生成一个完整可运行的单文件 HTML 应用，
并从中提取应用名称与描述。

使用 openai SDK 的 OpenAI 兼容接口调用 DeepSeek（base_url=https://api.deepseek.com）。
密钥只在本后端读取环境变量，绝不进入前端或仓库。
"""
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# 在读取任何环境变量之前加载 .env，确保无论本模块何时被 import，密钥与模型名都已就绪
load_dotenv(Path(__file__).resolve().parent / ".env")

# 模型名别名兼容：早期文档曾用 deepseek-v4-* 等占位名，统一映射到 DeepSeek 官方模型
MODEL_ALIASES = {
    "deepseek-v4-pro": "deepseek-chat",
    "deepseek-v4-flash": "deepseek-chat",
    "deepseek-flash": "deepseek-chat",
    "deepseek-v3": "deepseek-chat",
}


def _resolve_model(raw: str) -> str:
    return MODEL_ALIASES.get((raw or "").strip().lower(), raw)


BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
MODEL = _resolve_model(os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"))

# 常见的占位/无效密钥，命中则直接给出清晰提示，避免发出无意义的请求
PLACEHOLDER_KEYS = {
    "", "your_deepseek_api_key_here", "your-api-key", "your_api_key",
    "sk-xxx", "sk-xxxxxxxx", "sk-your-", "changeme", "123456",
}

SYSTEM_PROMPT = """你是一位顶尖的全栈 AI Builder，工作于 Atoms 平台：根据用户的一句话需求，生成一个完整、可独立运行的「单文件 HTML 应用」。

硬性要求：
1. 输出一个完整的 HTML 文档，内含 <style> 与 <script>（全部内联，禁止引用任何外部 CDN / 远程资源，确保离线可用）。
2. 应用必须真实可交互（按钮、输入、表单、计时、列表增删等），而不是静态展示。
3. 界面现代美观：浅色或深色均可，使用系统字体栈，卡片圆角、留白合理，移动端友好（响应式）。
4. 语言：界面文案默认使用中文。
5. 合理使用 localStorage 做数据持久化（如记录、设置等），并对 localStorage 读写做 try/catch 降级，保证在不可用时应用仍能正常运行。
6. 只输出 HTML 代码本体，不要任何解释、不要 markdown 代码围栏（```html 之类）、不要其他文字。
"""

MODIFY_SYSTEM_PROMPT = """你是一位顶尖的全栈 AI Builder。用户已有一个可运行的单文件 HTML 应用（见下方「现有代码」），现在要求对它进行修改。

硬性要求：
1. 在现有代码基础上做修改：保留原有功能与整体风格，只实现用户要求的改动，不要推倒重来。
2. 输出一个完整、可独立运行的「单文件 HTML 文档」，内含内联 <style> 与 <script>，禁止引用任何外部 CDN / 远程资源。
3. 界面现代美观、响应式、移动端友好。
4. 语言：界面文案默认使用中文。
5. 合理使用 localStorage 做数据持久化，并对 localStorage 读写做 try/catch 降级。
6. 只输出完整 HTML 代码本体，不要任何解释、不要 markdown 代码围栏、不要其他文字。
"""

# 从需求文本提取应用名时，去掉这些常见引导词
_LEADING_WORDS = (
    "请帮我", "帮我", "请", "我想要", "我要", "我想", "我需要", "我需要一个",
    "做一个", "一个", "给我", "搞一个", "来个", "来一个", "构建", "创建", "生成", "设计",
)


class AIBuilderError(Exception):
    """AI 构建失败（配置 / 调用 / 解析错误），消息可直接展示给用户"""


def _friendly_error(e: Exception) -> AIBuilderError:
    """把底层异常翻译成用户可读的中文提示"""
    msg = str(e)
    if "401" in msg or "authentication" in msg.lower():
        return AIBuilderError("DEEPSEEK_API_KEY 无效（鉴权失败）：请检查 backend/.env 中的密钥是否正确。")
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return AIBuilderError("DeepSeek 响应超时，请稍后重试。")
    return AIBuilderError(f"调用 DeepSeek 失败：{e}")


def _get_client() -> OpenAI:
    key = (API_KEY or "").strip()
    if key.lower() in PLACEHOLDER_KEYS:
        raise AIBuilderError(
            "尚未配置有效的 DEEPSEEK_API_KEY：请打开 backend/.env，"
            "把 DEEPSEEK_API_KEY 换成你在 https://platform.deepseek.com 申请的真实密钥。"
        )
    return OpenAI(api_key=key, base_url=BASE_URL, timeout=120.0)


def _clean_html(raw: str) -> str:
    """清理模型输出，只保留 HTML 文档本体"""
    text = raw.strip()
    # 去掉 markdown 代码围栏
    fence = re.search(r"```(?:html|HTML)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    # 截取第一个 <!DOCTYPE 或 <html 到文档结束
    start = text.find("<!DOCTYPE")
    if start == -1:
        start = text.find("<html")
    if start != -1:
        text = text[start:]
    # 去掉 </html> 之后的多余文字
    end = text.rfind("</html>")
    if end != -1:
        text = text[: end + len("</html>")]
    if "<html" not in text.lower() and "<!doctype" not in text.lower():
        raise AIBuilderError("模型没有返回有效的 HTML 文档，请重试或改写需求描述。")
    return text


def _extract_meta(prompt: str) -> tuple[str, str]:
    """从需求文本规则提取应用名与简介（零额外 API 调用，省一次请求的延迟与费用）"""
    s = re.sub(r"\s+", " ", prompt or "").strip()
    for w in _LEADING_WORDS:
        if s.startswith(w):
            s = s[len(w):].strip()
            break
    name = s[:12] if s else "未命名应用"
    # 英文按单词边界截断，避免出现 "a simple pom" 这类半个单词
    if len(s) > 12 and " " in name and " " in s:
        name = s[:12].rsplit(" ", 1)[0]
    description = s[:50] if s else "由 AI 生成的应用"
    return name or "未命名应用", description or "由 AI 生成的应用"


def generate_app(prompt: str) -> dict:
    """根据用户需求生成应用，返回 {name, description, html_code}"""
    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"请帮我构建一个应用，需求如下：\n{prompt}"},
            ],
            temperature=0.5,
            max_tokens=8000,
        )
        choice = resp.choices[0]
        raw = choice.message.content or ""
    except AIBuilderError:
        raise
    except Exception as e:  # 网络 / 鉴权 / 限流 / 超时等错误透传给前端
        raise _friendly_error(e) from e

    # 检测输出是否因达到 max_tokens 被截断
    if getattr(choice, "finish_reason", None) == "length":
        raise AIBuilderError("生成内容过长被截断，请把需求描述得更具体、更精简后重试。")

    html_code = _clean_html(raw)
    name, description = _extract_meta(prompt)
    return {"name": name, "description": description, "html_code": html_code}


def modify_app(instruction: str, existing_html: str) -> dict:
    """基于现有 HTML 应用，按用户指令迭代修改，返回 {name, description, html_code}"""
    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": MODIFY_SYSTEM_PROMPT},
                {"role": "user", "content": f"现有代码：\n{existing_html}\n\n修改需求：{instruction}"},
            ],
            temperature=0.4,
            max_tokens=8000,
        )
        choice = resp.choices[0]
        raw = choice.message.content or ""
    except AIBuilderError:
        raise
    except Exception as e:
        raise _friendly_error(e) from e

    if getattr(choice, "finish_reason", None) == "length":
        raise AIBuilderError("生成内容过长被截断，请把修改需求描述得更精简后重试。")

    html_code = _clean_html(raw)
    name, description = _extract_meta(instruction)
    return {"name": name, "description": description, "html_code": html_code}
