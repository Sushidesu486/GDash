"""
GDash 配置管理模块
"""
import json
import os
from pathlib import Path
from typing import Optional

# Windows 部署路径
DEPLOY_DIR = Path(r"C:\Tools\GDashControl")
DATA_DIR = Path(r"C:\ProgramData\GDashControl")
LOG_DIR = DATA_DIR / "logs"
CONFIG_FILE = DATA_DIR / "config.json"

# 默认配置
DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 5000,
    "log_level": "INFO",
    "task_prefix": "G18",  # 只管理以此前缀开头的任务
    "audit_log_enabled": True,
    "max_log_size_mb": 10,
    "log_retention_days": 30
}


class Config:
    """配置管理类"""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_FILE
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """加载配置文件"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # 合并默认配置和加载的配置
                    return {**DEFAULT_CONFIG, **loaded}
            except Exception as e:
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
                return DEFAULT_CONFIG.copy()
        return DEFAULT_CONFIG.copy()

    def save(self):
        """保存配置到文件"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # 原子写入：先写临时文件，再重命名
        temp_file = self.config_path.with_suffix('.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)

            # Windows 需要先删除目标文件
            if self.config_path.exists():
                self.config_path.unlink()
            temp_file.rename(self.config_path)
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            raise RuntimeError(f"Failed to save config: {e}")

    def get(self, key: str, default=None):
        """获取配置项"""
        return self.config.get(key, default)

    def set(self, key: str, value):
        """设置配置项"""
        self.config[key] = value

    @property
    def host(self) -> str:
        return self.config["host"]

    @property
    def port(self) -> int:
        return self.config["port"]

    @property
    def log_level(self) -> str:
        return self.config["log_level"]

    @property
    def task_prefix(self) -> str:
        return self.config["task_prefix"]

    @property
    def audit_log_enabled(self) -> bool:
        return self.config["audit_log_enabled"]


def ensure_directories():
    """确保所有必需目录存在"""
    directories = [DEPLOY_DIR, DATA_DIR, LOG_DIR]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
