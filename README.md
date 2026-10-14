# GDash - ROG G18 远程控制服务

Web 服务，用于远程管理 Windows ROG G18 笔记本的定时任务和硬件控制。

## 架构

```
外部请求
  ↓
Caddy (443) - TLS 终止
  ↓
S-entri (127.0.0.1:18080) - MFA 认证（密码 + TOTP）
  ↓
Caddy 回环路由 (127.0.0.1:13500) - 路径路由 /control/*
  ↓
SSH 隧道 (k1:13500 → Windows:5000)
  ↓
GDash Service (127.0.0.1:5000) - FastAPI 应用
```

## 功能阶段

### Phase 1: 定时任务管理（当前）
- ✅ 查看所有 G18* 定时任务
- ✅ 查看任务状态（上次运行、结果、下次运行）
- ✅ 手动触发任务
- ✅ 查看操作日志
- **无 Armoury Crate 冲突**

### Phase 2: 只读硬件监控（计划中）
- CPU 温度、风扇转速展示
- 性能模式展示
- 电池状态展示
- 数据导出到 Prometheus
- **与 Armoury Crate 共存**

### Phase 3: 硬件控制（计划中）
- 性能模式切换
- 风扇曲线调整
- 灯效控制
- 电池充电限制
- **需停止 Armoury Crate**

## 目录结构

```
C:\Tools\GDashControl\              # Windows 部署目录
├── app.py                          # FastAPI 主应用
├── task_manager.py                 # Task Scheduler COM API 封装
├── config.py                       # 配置管理
├── requirements.txt
└── static/
    ├── index.html
    ├── style.css
    └── app.js

C:\ProgramData\GDashControl\        # 数据与日志
├── config.json
└── logs/
    ├── app.log
    └── audit.log
```

## 技术栈

- **后端**: Python 3.x + FastAPI + pywin32
- **前端**: 原生 HTML/CSS/JavaScript
- **部署**: WinSW 托管为 Windows 服务

## 部署

### Windows 端

1. 创建目录结构：
```powershell
New-Item -ItemType Directory -Force -Path C:\Tools\GDashControl
New-Item -ItemType Directory -Force -Path C:\Tools\GDashControl\static
New-Item -ItemType Directory -Force -Path C:\ProgramData\GDashControl\logs
```

2. 安装依赖：
```powershell
pip install -r requirements.txt
```

3. 测试运行：
```powershell
python app.py
# 访问 http://127.0.0.1:5000
```

4. 配置 WinSW 服务（待补充）

### K1 网关配置

1. 配置 SSH 隧道（待补充）
2. 修改 Caddy 配置（待补充）

## API 端点

### Phase 1

- `GET /` - Web UI 主页
- `GET /api/status` - 服务健康检查
- `GET /api/tasks` - 列出所有 G18 任务
- `GET /api/tasks/{name}` - 获取单个任务详情
- `POST /api/tasks/{name}/run` - 手动触发任务
- `GET /api/logs` - 查看操作日志

## 安全

- 服务仅绑定 `127.0.0.1:5000`
- 通过 SSH 隧道暴露到 K1
- 复用 S-entri MFA 认证
- 所有操作记录审计日志

## 许可证

待定
