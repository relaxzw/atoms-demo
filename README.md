# Atoms Demo —— AI 智能体驱动的应用构建平台

一个可运行的 **Atoms 风格 Demo**：用户用一句话描述想要的应用，AI 智能体（DeepSeek）自动生成完整可运行的单文件 HTML 应用，并在沙箱中实时预览；所有项目持久化保存，随时回访。

> 笔试作品 · AI Native 研发岗位

---

## ✨ 功能特性

| 能力 | 说明 |
|---|---|
| AI 智能体生成应用 | 输入自然语言需求，DeepSeek 生成完整应用（含样式与交互） |
| 可视化实时预览 | 生成的应用在 iframe 沙箱中直接运行，可交互体验 |
| 数据持久化 | 项目自动保存到 SQLite，刷新不丢失，支持历史回访 |
| 应用管理 | 查看代码、复制代码、下载 HTML、删除项目 |
| 一键打开 | 将生成的应用在新标签页独立运行 |
| 迭代再生 | 「重新生成」基于原需求继续优化 |
| 对话式迭代 | 「修改应用」在现有应用基础上按指令继续修改（如“改成深色主题”） |

## 🧱 技术栈

- **后端**：Python + FastAPI + DeepSeek API（OpenAI 兼容接口）+ SQLite
- **前端**：原生 HTML / CSS / JS（零构建、零外部 CDN，离线可用）
- **架构**：单进程服务，FastAPI 同时伺服 API 与静态前端

## 📁 目录结构

```
atoms-demo/
├── backend/
│   ├── main.py          # FastAPI 入口（API + 静态伺服）
│   ├── ai_builder.py    # DeepSeek 调用与代码清洗
│   ├── database.py      # SQLite 持久化
│   ├── requirements.txt # Python 依赖
│   └── .env.example     # 环境变量模板（复制为 .env 使用）
├── frontend/
│   ├── index.html       # 页面结构
│   ├── style.css        # 样式（Atoms 风格）
│   └── app.js           # 前端交互逻辑
├── README.md
└── .gitignore
```

## 🚀 本地运行（Windows）

**前置要求**：Python 3.10+（在 [python.org](https://www.python.org) 下载安装时勾选 *Add Python to PATH*）

```bash
# 1. 进入项目目录
cd atoms-demo

# 2. 创建虚拟环境（推荐）并激活
python -m venv .venv
.venv\Scripts\activate

# 3. 安装依赖
pip install -r backend/requirements.txt

# 4. 配置密钥：复制模板并填写你的 DeepSeek API Key
copy backend\.env.example backend\.env
# 用记事本打开 backend\.env，把 DEEPSEEK_API_KEY 换成你的真实 Key

# 5. 启动
python backend/main.py
```

浏览器打开 **http://localhost:8000** 即可使用。

> 💡 也可以直接双击 `start.bat`（macOS/Linux 用 `./start.sh`）：脚本会自动创建虚拟环境、安装依赖并启动，零手工步骤。

> API Key 申请：https://platform.deepseek.com → API Keys → 创建。模型默认 `deepseek-chat`（DeepSeek 官方通用模型），可在 `.env` 中通过 `DEEPSEEK_MODEL` 切换为 `deepseek-reasoner`（深度推理）。
> ⚠️ 必须填写**真实密钥**：`.env` 里默认是占位符 `your_deepseek_api_key_here`，不替换的话会一直报 `401 鉴权失败`。

## 🔑 密钥安全说明

- 真实密钥只写在 `backend/.env`（已被 `.gitignore` 排除，**不会**提交到 Git）
- 仓库只包含 `.env.example` 占位模板，提交到 GitHub 安全
- AI 调用全部发生在后端，前端只拿到生成结果，密钥不经过浏览器

## ❓ 常见问题（FAQ）

**Q1：点「开始构建」报「尚未配置有效的 DEEPSEEK_API_KEY」？**
`.env` 里还是占位符 `your_deepseek_api_key_here`，请填入 https://platform.deepseek.com 申请的真实密钥，然后重启后端。

**Q2：报「鉴权失败 / 401」？**
密钥填错或未生效：检查 `.env` 是否有多余空格、是否保存为 UTF-8 编码。

**Q3：报「Model Not Exist / 模型不存在」？**
模型名请用 `deepseek-chat`（通用）或 `deepseek-reasoner`（深度推理）。旧文档里的 `deepseek-v4-*` 已被自动映射兼容。

**Q4：生成速度慢？**
单文件应用生成通常需要 10~30 秒，属正常；界面有循环进度动画提示。

**Q5：改了 `.env` 不生效？**
后端只在启动时读取一次 `.env`，改完请重启 `python backend/main.py`。

## ☁️ 部署到公网（推荐：Railway，免费额度）

1. 把本项目推到 GitHub 仓库
2. [Railway.app](https://railway.app) → New Project → **Deploy from GitHub repo**
3. 设置：
   - **Root Directory**：留空（项目根）
   - **Start Command**：`pip install -r backend/requirements.txt && python backend/main.py`
   - **Environment Variables**：
     - `DEEPSEEK_API_KEY` = 你的真实 Key
     - `DEEPSEEK_MODEL` = `deepseek-chat`
     - `PORT` = `8000`
4. Railway 自动生成公网 HTTPS 域名（`*.up.railway.app`），即得可测试的在线链接

> 其他可选部署：Render / Zeabur / 国内云服务器 + frp 内网穿透，原理相同：Python 应用 + 环境变量注入密钥。

### 🔒 关于 HTTP / HTTPS 与安全

- **本地运行用 HTTP 完全没问题**：`localhost` 被浏览器视为安全上下文，流量不出本机。
- **密钥不会因 HTTP 泄露**：DeepSeek API Key 只存在后端 `backend/.env`，浏览器与后端之间传输的只有需求文本与生成的 HTML，**密钥从不经过前端链路**；后端到 DeepSeek 的调用走的是 `https://api.deepseek.com`。
- **公网部署应使用 HTTPS**：Railway / Render / Zeabur 等平台会**自动颁发 HTTPS 证书**（如 `*.up.railway.app`），无需自己配置。
- **自建服务器**：推荐用 [Caddy](https://caddyserver.com) 或 Nginx 做反向代理；Caddy 可零配置自动申请 Let's Encrypt 证书实现 HTTPS。

## 📡 API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/generate` | 生成应用，body: `{"prompt": "需求描述", "project_id": 可选}` |
| GET | `/api/projects` | 历史项目列表 |
| GET | `/api/projects/{id}` | 项目详情（含完整代码） |
| PATCH | `/api/projects/{id}` | 重命名项目，body: `{"name": "新名字"}` |
| DELETE | `/api/projects/{id}` | 删除项目 |

## 🎯 笔试要求对照

- ✅ 可运行的网页应用（前后端一体，单命令启动）
- ✅ 真实交互（AI 生成、沙箱预览、历史管理）
- ✅ 数据持久化（SQLite）
- ✅ 基本使用流程（描述需求 → 生成 → 预览 → 保存）
- ✅ 延展能力（查看/复制/下载代码、新标签页打开、重新生成）
- ✅ 可测试在线链接（Railway 部署）
- ✅ 源码 GitHub 仓库（不含密钥，配置说明见上）

## 📝 说明文档（实现思路与取舍）

- **单进程架构**：FastAPI 伺服静态前端，Windows 下只需 Python 环境即可运行，避免 Node 工具链，降低"跑不起来"风险
- **原生前端**：零构建、零 CDN，评审环境离线/国内访问均稳定；代价是代码组织不如框架工程化
- **沙箱预览**：iframe `sandbox="allow-scripts allow-modals allow-forms allow-popups"`，隔离 AI 生成代码，避免影响宿主页面
- **生成策略**：一次调用产出完整 HTML（内联样式与脚本），再做元信息提取（名称/描述），速度与质量的平衡
- **未做/后续可扩展**：多轮对话式迭代（当前为单轮再生）、用户登录与私有项目、更多模板/示例、流式输出（SSE 打字机效果）、生成应用的单元测试
