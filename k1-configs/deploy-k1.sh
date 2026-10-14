#!/bin/bash
# GDash Control - K1 网关部署脚本
# Phase 1: 配置 SSH 隧道和 Caddy 路由

set -e

echo "=============================================="
echo "GDash Control - K1 网关配置脚本"
echo "=============================================="
echo ""

# 检查是否有 root 权限
if [[ $EUID -ne 0 ]]; then
   echo "错误: 需要 root 权限！请使用 sudo 运行此脚本。"
   exit 1
fi

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TUNNEL_SERVICE="/etc/systemd/system/g18-gdash-tunnel.service"
CADDY_CONFIG="/etc/caddy/Caddyfile"

echo "步骤 1/4: 安装 SSH 隧道服务..."

# 复制隧道服务文件
if [[ -f "$SCRIPT_DIR/g18-gdash-tunnel.service" ]]; then
    cp "$SCRIPT_DIR/g18-gdash-tunnel.service" "$TUNNEL_SERVICE"
    echo "  已安装: $TUNNEL_SERVICE"
else
    echo "  错误: 找不到源文件 g18-gdash-tunnel.service"
    exit 1
fi

# 重新加载 systemd
systemctl daemon-reload
echo "  systemd 已重新加载"

echo ""
echo "步骤 2/4: 启动 SSH 隧道服务..."

# 启用并启动服务
systemctl enable g18-gdash-tunnel.service
systemctl start g18-gdash-tunnel.service

# 等待服务启动
sleep 3

# 检查服务状态
if systemctl is-active --quiet g18-gdash-tunnel.service; then
    echo "  隧道服务启动成功"
else
    echo "  警告: 隧道服务启动失败，查看状态:"
    systemctl status g18-gdash-tunnel.service --no-pager
fi

echo ""
echo "步骤 3/4: 备份并修改 Caddy 配置..."

# 备份 Caddy 配置
BACKUP_FILE="${CADDY_CONFIG}.backup-before-gdash-$(date +%Y%m%d-%H%M%S)"
cp "$CADDY_CONFIG" "$BACKUP_FILE"
echo "  配置已备份: $BACKUP_FILE"

echo ""
echo "  请手动编辑 Caddy 配置文件:"
echo "  sudo nano $CADDY_CONFIG"
echo ""
echo "  在 :13400 回环段中添加以下内容:"
echo ""
cat "$SCRIPT_DIR/caddy-snippet.txt"
echo ""
read -p "  完成后按 Enter 继续..."

echo ""
echo "步骤 4/4: 验证并重载 Caddy..."

# 验证配置
if caddy validate --config "$CADDY_CONFIG"; then
    echo "  Caddy 配置验证成功"

    # 重载配置
    systemctl reload caddy
    echo "  Caddy 已重载"
else
    echo "  错误: Caddy 配置验证失败"
    echo "  请检查配置文件，可以从备份恢复:"
    echo "  sudo cp $BACKUP_FILE $CADDY_CONFIG"
    exit 1
fi

echo ""
echo "=============================================="
echo "K1 网关配置完成！"
echo "=============================================="
echo ""
echo "验证步骤:"
echo "1. 检查隧道状态: sudo systemctl status g18-gdash-tunnel.service"
echo "2. 测试隧道连接: curl http://127.0.0.1:13500/api/status"
echo "3. 测试 Caddy 路由: curl http://127.0.0.1:13400/control/api/status"
echo "4. 查看隧道日志: sudo journalctl -u g18-gdash-tunnel.service -n 50"
echo ""
echo "如需回滚:"
echo "  sudo systemctl stop g18-gdash-tunnel.service"
echo "  sudo systemctl disable g18-gdash-tunnel.service"
echo "  sudo cp $BACKUP_FILE $CADDY_CONFIG"
echo "  sudo systemctl reload caddy"
echo ""
