# GDash Control Service - 快速部署脚本（Windows）
# 用于 Phase 1 部署

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "GDash Control Service - Phase 1 部署脚本" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "错误: 需要管理员权限！请以管理员身份运行此脚本。" -ForegroundColor Red
    exit 1
}

# 配置
$DEPLOY_DIR = "C:\Tools\GDashControl"
$DATA_DIR = "C:\ProgramData\GDashControl"
$PYTHON_EXE = "C:\Users\29546\miniconda3\python.exe"
$SOURCE_DIR = $PSScriptRoot  # 脚本所在目录

Write-Host "步骤 1/7: 创建目录结构..." -ForegroundColor Yellow

# 创建目录
$directories = @(
    $DEPLOY_DIR,
    "$DEPLOY_DIR\static",
    $DATA_DIR,
    "$DATA_DIR\logs"
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        Write-Host "  创建: $dir" -ForegroundColor Green
    } else {
        Write-Host "  已存在: $dir" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "步骤 2/7: 复制应用文件..." -ForegroundColor Yellow

# 复制文件
$files = @{
    "app.py" = "$DEPLOY_DIR\app.py"
    "config.py" = "$DEPLOY_DIR\config.py"
    "task_manager.py" = "$DEPLOY_DIR\task_manager.py"
    "requirements.txt" = "$DEPLOY_DIR\requirements.txt"
    "GDashControl.xml" = "$DEPLOY_DIR\GDashControl.xml"
    "static\index.html" = "$DEPLOY_DIR\static\index.html"
    "static\style.css" = "$DEPLOY_DIR\static\style.css"
    "static\app.js" = "$DEPLOY_DIR\static\app.js"
}

foreach ($file in $files.Keys) {
    $source = Join-Path $SOURCE_DIR $file
    $dest = $files[$file]

    if (Test-Path $source) {
        Copy-Item -Path $source -Destination $dest -Force
        Write-Host "  复制: $file" -ForegroundColor Green
    } else {
        Write-Host "  警告: 源文件不存在 - $file" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "步骤 3/7: 安装 Python 依赖..." -ForegroundColor Yellow

if (-not (Test-Path $PYTHON_EXE)) {
    Write-Host "  错误: Python 未找到 - $PYTHON_EXE" -ForegroundColor Red
    exit 1
}

& $PYTHON_EXE -m pip install -r "$DEPLOY_DIR\requirements.txt" --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "  依赖安装成功" -ForegroundColor Green
} else {
    Write-Host "  警告: 依赖安装可能失败" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "步骤 4/7: 创建配置文件..." -ForegroundColor Yellow

$configFile = "$DATA_DIR\config.json"
if (-not (Test-Path $configFile)) {
    $config = @{
        host = "127.0.0.1"
        port = 5000
        log_level = "INFO"
        task_prefix = "G18"
        audit_log_enabled = $true
        max_log_size_mb = 10
        log_retention_days = 30
    } | ConvertTo-Json -Depth 10

    $config | Out-File -FilePath $configFile -Encoding UTF8
    Write-Host "  创建配置文件: $configFile" -ForegroundColor Green
} else {
    Write-Host "  配置文件已存在，跳过" -ForegroundColor Gray
}

Write-Host ""
Write-Host "步骤 5/7: 设置 WinSW..." -ForegroundColor Yellow

# 检查 WinSW
$winswSource = "C:\Tools\G18Monitor\winsw.exe"
$winswDest = "$DEPLOY_DIR\GDashControl.exe"

if (Test-Path $winswSource) {
    Copy-Item -Path $winswSource -Destination $winswDest -Force
    Write-Host "  复制 WinSW: $winswDest" -ForegroundColor Green
} else {
    Write-Host "  警告: WinSW 未找到 - $winswSource" -ForegroundColor Yellow
    Write-Host "  请手动下载 WinSW 并放置到: $winswDest" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "步骤 6/7: 测试应用..." -ForegroundColor Yellow

Push-Location $DEPLOY_DIR
try {
    Write-Host "  启动测试服务（5 秒）..." -ForegroundColor Gray

    $job = Start-Job -ScriptBlock {
        param($pythonExe)
        & $pythonExe app.py
    } -ArgumentList $PYTHON_EXE

    Start-Sleep -Seconds 5

    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/status" -TimeoutSec 3
        if ($response.StatusCode -eq 200) {
            Write-Host "  测试成功: 服务响应正常" -ForegroundColor Green
        }
    } catch {
        Write-Host "  警告: 测试连接失败 - $_" -ForegroundColor Yellow
    }

    Stop-Job $job
    Remove-Job $job
} catch {
    Write-Host "  警告: 测试启动失败 - $_" -ForegroundColor Yellow
}
Pop-Location

Write-Host ""
Write-Host "步骤 7/7: 安装 Windows 服务..." -ForegroundColor Yellow

if (Test-Path $winswDest) {
    Push-Location $DEPLOY_DIR

    # 检查服务是否已存在
    $service = Get-Service -Name "GDashControl" -ErrorAction SilentlyContinue

    if ($service) {
        Write-Host "  服务已存在，先卸载..." -ForegroundColor Gray
        & .\GDashControl.exe stop
        & .\GDashControl.exe uninstall
        Start-Sleep -Seconds 2
    }

    # 安装服务
    & .\GDashControl.exe install
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  服务安装成功" -ForegroundColor Green

        # 启动服务
        & .\GDashControl.exe start
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  服务启动成功" -ForegroundColor Green
        } else {
            Write-Host "  警告: 服务启动失败" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  警告: 服务安装失败" -ForegroundColor Yellow
    }

    Pop-Location
} else {
    Write-Host "  跳过: WinSW 不可用" -ForegroundColor Gray
}

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "部署完成！" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "后续步骤:" -ForegroundColor White
Write-Host "1. 检查服务状态: Get-Service GDashControl" -ForegroundColor Gray
Write-Host "2. 查看日志: Get-Content $DATA_DIR\logs\app.log -Tail 20" -ForegroundColor Gray
Write-Host "3. 测试 API: Invoke-WebRequest http://127.0.0.1:5000/api/status" -ForegroundColor Gray
Write-Host "4. 配置 K1 网关（参考 DEPLOY.md Phase 1b）" -ForegroundColor Gray
Write-Host ""
