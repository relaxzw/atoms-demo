# 国内云服务器部署指南

> 适用于：腾讯云轻量应用服务器 / 阿里云 ECS / 华为云 ECS（Ubuntu 系统）
> 目标：把 Atoms Demo 部署到公网服务器，通过 `http://服务器IP:8000` 访问

---

## 一、领取免费服务器

| 平台 | 入口 | 免费方案 |
|---|---|---|
| 腾讯云 | https://cloud.tencent.com/act/pro/free | 轻量应用服务器 2C2G 试用 3 个月 |
| 阿里云 | https://free.aliyun.com | 新用户 300 元额度（3 个月） |
| 阿里云学生 | https://university.aliyun.com | 飞天加速计划，最多 7 个月 |

**领取建议**：
- 系统镜像选 **Ubuntu 22.04**（或 20.04），不要选 Windows。
- 轻量服务器（腾讯云）会自动开好常用端口；ECS 需要手动在「安全组」放行端口。

---

## 二、登录服务器

领取后拿到**公网 IP** 和 **root 密码**（或密钥）。

```bash
ssh root@你的公网IP
```

> Windows 本地可用：PowerShell 自带 `ssh`，或下载 [Termius](https://termius.com) / Xshell。

---

## 三、部署步骤（复制粘贴即可）

### 1. 安装依赖

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

### 2. 拉取代码

```bash
git clone https://github.com/relaxzw/atoms-demo.git
cd atoms-demo
```

> 若服务器访问 GitHub 慢，可在本地打包 `git archive` 后用 scp 上传，见文末「附：离线部署」。

### 3. 创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> 加 `-i 清华源` 加速国内 pip 安装。

### 4. 配置密钥

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

把 `DEEPSEEK_API_KEY=your_deepseek_api_key_here` 改成你的真实密钥（`sk-` 开头），保存（Ctrl+O 回车，Ctrl+X 退出）。

### 5. 先前台测试

```bash
python backend/main.py
```

看到 `Atoms Demo 已启动` 后，另开终端测试：

```bash
curl http://localhost:8000/api/projects
```

返回 `[]` 说明正常。按 Ctrl+C 停止。

---

## 四、配置 systemd 守护进程（推荐，崩溃自动重启、开机自启）

### 1. 创建服务文件

```bash
sudo nano /etc/systemd/system/atoms-demo.service
```

粘贴以下内容（注意把 `/root/atoms-demo` 换成你的实际路径）：

```ini
[Unit]
Description=Atoms Demo
After=network.target

[Service]
WorkingDirectory=/root/atoms-demo
ExecStart=/root/atoms-demo/.venv/bin/python backend/main.py
Restart=always
RestartSec=3
Environment=PORT=8000

[Install]
WantedBy=multi-user.target
```

保存退出后：

```bash
sudo systemctl daemon-reload
sudo systemctl enable atoms-demo      # 开机自启
sudo systemctl start atoms-demo       # 启动
sudo systemctl status atoms-demo      # 查看状态（应显示 active (running)）
```

常用命令：

```bash
sudo systemctl restart atoms-demo     # 重启
sudo systemctl stop atoms-demo        # 停止
journalctl -u atoms-demo -f           # 实时看日志
```

---

## 五、开放端口（关键！）

### 腾讯云轻量服务器
控制台 → 服务器 → **防火墙** → 添加规则 → 放行 **TCP 8000** 端口。

### 阿里云/华为云 ECS
控制台 → 实例 → **安全组** → 添加入方向规则 → 放行 **TCP 8000**（来源 0.0.0.0/0）。

---

## 六、访问

浏览器打开：

```
http://你的公网IP:8000
```

即可看到 Atoms Demo 界面，输入需求测试生成。

---

## 七、进阶（可选）

### 1. 免端口访问（改用 80 端口）

把 `.env` 里 `PORT=8000` 改成 `PORT=80`，或用 nginx 反代：

```bash
sudo apt install -y nginx
sudo nano /etc/nginx/sites-available/atoms-demo
```

```nginx
server {
    listen 80;
    server_name _;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/atoms-demo /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 2. 绑定域名 + HTTPS

- 购买域名（`.top` 约 10-20 元/年）
- 解析 A 记录到服务器 IP
- **国内服务器绑定域名必须备案**（约 1-2 周）
- 备案后可用 certbot 免费申请 HTTPS 证书：
  ```bash
  sudo apt install -y certbot python3-certbot-nginx
  sudo certbot --nginx -d 你的域名
  ```

---

## 附：离线部署（GitHub 拉不动时）

本地打包后上传：

```bash
# 本地（Windows Git Bash）
cd atoms-demo
git archive --format=zip -o atoms-demo.zip HEAD

# 上传到服务器
scp atoms-demo.zip root@你的IP:/root/

# 服务器解压
ssh root@你的IP "cd /root && unzip atoms-demo.zip && mv atoms-demo atoms-demo-app"
```

> 注意：`.env` 不会打包进 zip（已被 gitignore），需在服务器上手动创建并填入密钥。
