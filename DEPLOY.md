# Phase 1 部署指南

本指南用于在 Windows G18 和 K1 网关上部署 GDash Control Service Phase 1。

## 部署前检查

### Windows 端
- [ ] Python 3.x 已安装（建议使用现有 miniconda3）
- [ ] 当前用户有管理员权限（用于访问 Task Scheduler）
- [ ] 端口 5000 未被占用

### K1 端
- [ ] 能通过 SSH 访问 Windows (g18-win)
- [ ] g18-tunnel 用户存在且配置正确
- [ ] Caddy 和 S-entri 服务正常运行

---

## Phase 1a: Windows 端部署

### 1. 创建目录结构

在 Windows 上以管理员身份运行 PowerShell：

```powershell
# 创建部署目录
New-Item -ItemType Directory -Force -Path C:\Tools\GDashControl
New-Item -ItemType Directory -Force -Path C:\Tools\GDashControl\static

# 创建数据目录
New-Item -ItemType Directory -Force -Path C:\ProgramData\GDashControl
New-Item -ItemType Directory -Force -Path C:\ProgramData\GDashControl\logs

# 验证目录
Get-ChildItem C:\Tools\GDashControl
Get-ChildItem C:\ProgramData\GDashControl
```

### 2. 上传文件

将以下文件从本地仓库复制到 Windows：

```
GDash/
├── app.py              → C:\Tools\GDashControl\app.py
├── config.py           → C:\Tools\GDashControl\config.py
├── task_manager.py     → C:\Tools\GDashControl\task_manager.py
├── requirements.txt    → C:\Tools\GDashControl\requirements.txt
└── static/
    ├── index.html      → C:\Tools\GDashControl\static\index.html
    ├── style.css       → C:\Tools\GDashControl\static\style.css
    └── app.js          → C:\Tools\GDashControl\static\app.js
```

**使用 SSH 上传（推荐）**：

在 Mac 上执行：
```bash
# 先打包
cd /Users/shouss/Project/GDash/GDash
tar czf gdash-phase1.tar.gz app.py config.py task_manager.py requirements.txt static/

# 上传
scp gdash-phase1.tar.gz g18-win:C:/Temp/

# 在 Windows 上解压
ssh g18-win "cd C:\Temp && tar xzf gdash-phase1.tar.gz -C C:\Tools\GDashControl\"
```

### 3. 安装 Python 依赖

```powershell
cd C:\Tools\GDashControl

# 使用现有 Python 环境（miniconda3）
C:\Users\29546\miniconda3\python.exe -m pip install -r requirements.txt
```

### 4. 创建配置文件

```powershell
# 创建默认配置
@"
{
  "host": "127.0.0.1",
  "port": 5000,
  "log_level": "INFO",
  "task_prefix": "G18",
  "audit_log_enabled": true,
  "max_log_size_mb": 10,
  "log_retention_days": 30
}
"@ | Out-File -FilePath C:\ProgramData\GDashControl\config.json -Encoding UTF8
```

### 5. 测试运行

```powershell
cd C:\Tools\GDashControl

# 直接运行测试
C:\Users\29546\miniconda3\python.exe app.py
```

在另一个 PowerShell 窗口中测试：
```powershell
# 健康检查
Invoke-WebRequest -Uri http://127.0.0.1:5000/api/status | Select-Object -ExpandProperty Content

# 列出任务
Invoke-WebRequest -Uri http://127.0.0.1:5000/api/tasks | Select-Object -ExpandProperty Content
```

如果能正常返回 JSON，说明服务运行正常。按 Ctrl+C 停止测试。

### 6. 配置 WinSW 服务

参考现有监控服务的配置，创建 WinSW 配置文件：

```powershell
# 下载 WinSW（如果还没有）
# 已有 WinSW 可复用：C:\Tools\G18Monitor\winsw.exe

# 创建服务配置
@"
<service>
  <id>GDashControl</id>
  <name>GDash Control Service</name>
  <description>ROG G18 远程控制服务 - Phase 1: 任务管理</description>
  
  <executable>C:\Users\29546\miniconda3\python.exe</executable>
  <arguments>app.py</arguments>
  <workingdirectory>C:\Tools\GDashControl</workingdirectory>
  
  <logpath>C:\ProgramData\GDashControl\logs</logpath>
  <logmode>rotate</logmode>
  
  <onfailure action="restart" delay="10 sec"/>
  <onfailure action="restart" delay="20 sec"/>
  <onfailure action="restart" delay="30 sec"/>
  
  <resetfailure>1 hour</resetfailure>
</service>
"@ | Out-File -FilePath C:\Tools\GDashControl\GDashControl.xml -Encoding UTF8
```

安装并启动服务：
```powershell
# 复制 WinSW
Copy-Item C:\Tools\G18Monitor\winsw.exe C:\Tools\GDashControl\GDashControl.exe

# 安装服务（需要管理员权限）
cd C:\Tools\GDashControl
.\GDashControl.exe install

# 启动服务
.\GDashControl.exe start

# 检查状态
.\GDashControl.exe status
```

### 7. 验证服务

```powershell
# 检查服务状态
Get-Service GDashControl

# 测试 API
Invoke-WebRequest -Uri http://127.0.0.1:5000/api/status

# 查看日志
Get-Content C:\ProgramData\GDashControl\logs\app.log -Tail 20
```

---

## Phase 1b: K1 网关配置

### 1. 配置 Windows authorized_keys

在 Windows 上编辑 `C:\Users\g18-tunnel\.ssh\authorized_keys`，添加 13500 端口转发权限：

```
command="echo 'This key is only for port forwarding'",no-pty,no-X11-forwarding,permitopen="127.0.0.1:3000",permitopen="127.0.0.1:5000" ssh-ed25519 AAAA... g18-tunnel@k1
```

注意：在现有 `permitopen="127.0.0.1:3000"` 后添加 `,permitopen="127.0.0.1:5000"`

### 2. 创建 SSH 隧道服务

在 K1 上创建新的隧道服务文件：

```bash
sudo nano /etc/systemd/system/g18-gdash-tunnel.service
```

内容：
```ini
[Unit]
Description=SSH tunnel for GDash Control
After=network.target

[Service]
Type=simple
User=g18-tunnel
ExecStart=/usr/bin/ssh -N -T \
  -o ServerAliveInterval=30 \
  -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:13500:127.0.0.1:5000 \
  g18-win
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

启用并启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable g18-gdash-tunnel.service
sudo systemctl start g18-gdash-tunnel.service
sudo systemctl status g18-gdash-tunnel.service
```

验证隧道：
```bash
curl http://127.0.0.1:13500/api/status
```

### 3. 修改 Caddy 配置

备份现有配置：
```bash
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.backup-before-gdash
```

编辑 Caddyfile：
```bash
sudo nano /etc/caddy/Caddyfile
```

在 `:13400` 回环段中添加 GDash 路由（在现有 Grafana 路由之后）：

```caddyfile
:13400 {
    bind 127.0.0.1
    
    # 现有 Grafana 路由
    handle /* {
        reverse_proxy 127.0.0.1:13300
    }
    
    # 新增 GDash 路由
    handle_path /control/* {
        reverse_proxy 127.0.0.1:13500
    }
}
```

验证并重载配置：
```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

### 4. 验证完整链路

在 K1 上测试：
```bash
# 通过 Caddy 回环访问
curl http://127.0.0.1:13400/control/api/status
```

在 Mac 上通过 WireGuard 测试：
```bash
# 需要先连接 WireGuard
curl https://grafana-g18.shouss.top/control/api/status
```

**注意**：首次访问会被 S-entri 重定向到登录页面（303），这是正常的。

### 5. 浏览器访问测试

1. 连接 WireGuard
2. 在浏览器访问：`https://grafana-g18.shouss.top/control/`
3. 输入 S-entri MFA 凭据（密码 + TOTP）
4. 应该能看到 GDash Control 界面
5. 验证能看到所有 G18* 任务列表

---

## 验收清单

### Windows 端
- [ ] GDashControl 服务已安装并运行
- [ ] 本地能访问 http://127.0.0.1:5000/api/status
- [ ] 日志文件正常写入
- [ ] 能列出所有 G18 任务

### K1 端
- [ ] SSH 隧道服务运行正常
- [ ] K1 上能访问 http://127.0.0.1:13500/api/status
- [ ] Caddy 配置已更新并 reload 成功
- [ ] 通过回环能访问 /control/* 路径

### 端到端
- [ ] Mac 通过 WireGuard 能访问 https://grafana-g18.shouss.top/control/
- [ ] S-entri MFA 认证工作正常
- [ ] Web UI 正常显示
- [ ] 能看到任务列表
- [ ] 能查看任务详情
- [ ] 能手动触发 G18PCDaily 任务
- [ ] 操作日志正常记录

---

## 故障排查

### Windows 服务无法启动

检查日志：
```powershell
Get-Content C:\ProgramData\GDashControl\logs\app.log
Get-Content C:\Tools\GDashControl\GDashControl.wrapper.log
```

常见问题：
- Python 路径错误：检查 GDashControl.xml 中的 executable 路径
- 依赖未安装：重新运行 pip install
- 端口被占用：检查 5000 端口

### SSH 隧道连接失败

```bash
# 查看隧道日志
sudo journalctl -u g18-gdash-tunnel.service -n 50

# 手动测试 SSH 连接
sudo -u g18-tunnel ssh -v g18-win
```

### Caddy 路由不工作

```bash
# 检查 Caddy 日志
sudo journalctl -u caddy -n 50

# 验证配置
sudo caddy validate --config /etc/caddy/Caddyfile

# 测试回环访问
curl -v http://127.0.0.1:13400/control/api/status
```

### 403 Forbidden

检查 S-entri 配置中的 IP 白名单是否包含你的来源 IP。

---

## 回滚步骤

如果需要回滚：

### Windows
```powershell
# 停止并卸载服务
cd C:\Tools\GDashControl
.\GDashControl.exe stop
.\GDashControl.exe uninstall

# 可选：删除文件
Remove-Item C:\Tools\GDashControl -Recurse -Force
Remove-Item C:\ProgramData\GDashControl -Recurse -Force
```

### K1
```bash
# 停止并禁用隧道
sudo systemctl stop g18-gdash-tunnel.service
sudo systemctl disable g18-gdash-tunnel.service

# 恢复 Caddy 配置
sudo cp /etc/caddy/Caddyfile.backup-before-gdash /etc/caddy/Caddyfile
sudo systemctl reload caddy

# 恢复 Windows authorized_keys（移除 permitopen 5000）
```

---

## 后续工作

Phase 1 部署完成后，进入 Phase 2：

- [ ] 添加 asus_acpi.py 模块
- [ ] 实现只读硬件监控
- [ ] 集成 Prometheus textfile
- [ ] 在 Grafana 添加硬件监控面板
