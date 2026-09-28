"""
auth.py —— 注册登录认证模块

安全设计：
1. 密码强度校验（明文阶段，前端实时校验，后端提供校验函数）
2. 传输：前端 SHA-256 散列后传输（HTTP 下密码不以明文出现在网络中）
3. 存储：后端 PBKDF2 加盐二次散列（即使数据库泄露也无法还原密码）
4. 登录：图形验证码（SVG 渲染，零额外依赖），防暴力破解

说明：生产环境应使用 HTTPS（TLS）作为真正的加密传输通道。
"""
import hashlib
import random
import secrets

# ---------- 密码强度校验 ----------


def validate_password_strength(password: str) -> list[str]:
    """返回密码强度错误列表，空列表表示通过"""
    errors = []
    if len(password) < 8:
        errors.append("密码长度至少 8 位")
    if not any(c.isupper() for c in password):
        errors.append("至少包含一个大写字母")
    if not any(c.islower() for c in password):
        errors.append("至少包含一个小写字母")
    if not any(c.isdigit() for c in password):
        errors.append("至少包含一个数字")
    if _has_consecutive_digits(password):
        errors.append("数字不能连续（如 123、456、789）")
    return errors


def _has_consecutive_digits(password: str, length: int = 3) -> bool:
    """检测是否存在 length 个及以上连续递增/递减的数字序列"""
    for i in range(len(password) - length + 1):
        seq = password[i:i + length]
        if seq.isdigit():
            nums = [int(c) for c in seq]
            if all(nums[j + 1] == nums[j] + 1 for j in range(length - 1)):
                return True  # 递增：123
            if all(nums[j + 1] == nums[j] - 1 for j in range(length - 1)):
                return True  # 递减：987
    return False


# ---------- 密码散列（前端 SHA-256 → 后端 PBKDF2 加盐） ----------


def hash_password(sha256_hex: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", sha256_hex.encode(), salt.encode(), 100_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(sha256_hex: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac("sha256", sha256_hex.encode(), salt.encode(), 100_000)
    return secrets.compare_digest(calc.hex(), digest)


# ---------- 图形验证码（SVG，无需额外依赖） ----------

_CAPTCHA_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去掉易混淆的 I/O/0/1


def generate_captcha() -> tuple[str, str]:
    """返回 (svg 字符串, 验证码明文)"""
    code = "".join(secrets.choice(_CAPTCHA_CHARS) for _ in range(4))
    return _render_svg(code), code


def _render_svg(code: str) -> str:
    rnd = random.Random(secrets.randbits(32))
    width, height = 120, 44
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
    parts.append(f'<rect width="100%" height="100%" fill="#f2f4f8"/>')
    # 干扰线
    for _ in range(6):
        x1, y1 = rnd.randint(0, width), rnd.randint(0, height)
        x2, y2 = rnd.randint(0, width), rnd.randint(0, height)
        color = rnd.choice(["#c8ccd4", "#d5d9e0", "#b8bcc6"])
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1"/>')
    # 字符
    for idx, ch in enumerate(code):
        x = 14 + idx * 26
        y = rnd.randint(27, 35)
        color = rnd.choice(["#3b6fe0", "#2f56b8", "#1a1b1c", "#5a6b8c"])
        rotate = rnd.randint(-18, 18)
        parts.append(
            f'<text x="{x}" y="{y}" font-size="24" font-family="Arial, sans-serif" font-weight="bold" '
            f'fill="{color}" transform="rotate({rotate} {x} {y})">{ch}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)
