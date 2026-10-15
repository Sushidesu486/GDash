"""
GDash - ROG G18 远程控制服务主应用

FastAPI 应用，提供定时任务管理和硬件控制接口
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# 导入配置和管理模块
from config import Config, ensure_directories, LOG_DIR
from task_manager import TaskManager

# 初始化日志
def setup_logging(config: Config):
    """配置日志系统"""
    log_file = LOG_DIR / "app.log"
    audit_file = LOG_DIR / "audit.log"

    # 主应用日志
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # 审计日志
    audit_logger = logging.getLogger('audit')
    audit_handler = logging.FileHandler(audit_file, encoding='utf-8')
    audit_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(message)s'
    ))
    audit_logger.addHandler(audit_handler)
    audit_logger.setLevel(logging.INFO)

    return logging.getLogger(__name__)


# 初始化配置
ensure_directories()
config = Config()
logger = setup_logging(config)
audit_logger = logging.getLogger('audit')

# Lifespan 事件管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("=" * 60)
    logger.info("GDash Control Service Starting")
    logger.info(f"Host: {config.host}:{config.port}")
    logger.info(f"Task Prefix: {config.task_prefix}")
    logger.info(f"Log Level: {config.log_level}")
    logger.info("=" * 60)

    yield

    # 关闭
    logger.info("GDash Control Service Shutting Down")


# 创建 FastAPI 应用
app = FastAPI(
    title="GDash Control Service",
    description="ROG G18 远程控制服务",
    version="0.1.0",
    lifespan=lifespan
)

# 任务管理器（延迟初始化）
task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """获取任务管理器实例"""
    global task_manager
    if task_manager is None:
        task_manager = TaskManager(task_prefix=config.task_prefix)
    return task_manager


def audit_log(request: Request, action: str, target: str, result: str, details: str = ""):
    """记录审计日志"""
    if config.audit_log_enabled:
        client_ip = request.client.host if request.client else "unknown"
        audit_logger.info(
            f"action={action} | target={target} | result={result} | "
            f"ip={client_ip} | details={details}"
        )


# ============================================================================
# API 端点
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """返回 Web UI 主页"""
    static_dir = Path(__file__).parent / "static"
    index_file = static_dir / "index.html"

    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding='utf-8'))
    else:
        return HTMLResponse(content="""
        <html>
            <head><title>GDash Control</title></head>
            <body>
                <h1>GDash Control Service</h1>
                <p>Static files not deployed yet.</p>
                <p>API Documentation: <a href="/docs">/docs</a></p>
            </body>
        </html>
        """)


@app.get("/api/status")
async def get_status():
    """服务健康检查"""
    try:
        tm = get_task_manager()
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "GDash Control Service",
            "version": "0.1.0",
            "task_scheduler_connected": tm.scheduler is not None
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.get("/api/tasks")
async def list_tasks(request: Request):
    """列出所有任务"""
    try:
        tm = get_task_manager()
        tasks = tm.list_tasks()

        audit_log(request, "list_tasks", "all", "success", f"count={len(tasks)}")

        return {
            "count": len(tasks),
            "tasks": tasks
        }
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        audit_log(request, "list_tasks", "all", "failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tasks/{task_name}")
async def get_task(task_name: str, request: Request):
    """获取单个任务详情"""
    try:
        tm = get_task_manager()
        task_info = tm.get_task(task_name)

        if task_info is None:
            audit_log(request, "get_task", task_name, "not_found")
            raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

        audit_log(request, "get_task", task_name, "success")
        return task_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task '{task_name}': {e}")
        audit_log(request, "get_task", task_name, "failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks/{task_name}/run")
async def run_task(task_name: str, request: Request):
    """手动触发任务运行"""
    try:
        # 验证任务名称前缀
        if not task_name.startswith(config.task_prefix):
            audit_log(request, "run_task", task_name, "rejected", "invalid_prefix")
            raise HTTPException(
                status_code=403,
                detail=f"Can only run tasks with prefix '{config.task_prefix}'"
            )

        tm = get_task_manager()

        # 检查任务是否存在
        task_info = tm.get_task(task_name)
        if task_info is None:
            audit_log(request, "run_task", task_name, "not_found")
            raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")

        # 触发运行
        success = tm.run_task(task_name)

        if success:
            audit_log(request, "run_task", task_name, "success")
            return {
                "success": True,
                "message": f"Task '{task_name}' triggered successfully",
                "task_name": task_name,
                "triggered_at": datetime.now().isoformat()
            }
        else:
            audit_log(request, "run_task", task_name, "failed", "trigger_failed")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to trigger task '{task_name}'"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run task '{task_name}': {e}")
        audit_log(request, "run_task", task_name, "failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs")
async def get_logs(request: Request, lines: int = 100):
    """获取最近的日志条目"""
    try:
        log_file = LOG_DIR / "app.log"

        if not log_file.exists():
            return {"lines": [], "count": 0}

        # 读取最后 N 行
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        audit_log(request, "get_logs", "app.log", "success", f"lines={len(recent_lines)}")

        return {
            "lines": [line.strip() for line in recent_lines],
            "count": len(recent_lines),
            "total": len(all_lines)
        }

    except Exception as e:
        logger.error(f"Failed to read logs: {e}")
        audit_log(request, "get_logs", "app.log", "failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audit")
async def get_audit_logs(request: Request, lines: int = 100):
    """获取审计日志"""
    try:
        audit_file = LOG_DIR / "audit.log"

        if not audit_file.exists():
            return {"lines": [], "count": 0}

        with open(audit_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        return {
            "lines": [line.strip() for line in recent_lines],
            "count": len(recent_lines),
            "total": len(all_lines)
        }

    except Exception as e:
        logger.error(f"Failed to read audit logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 主程序入口
# ============================================================================

if __name__ == "__main__":
    # 直接运行（开发模式）
    logger.info("Running in development mode")
    uvicorn.run(
        "app:app",
        host=config.host,
        port=config.port,
        reload=False,
        log_level=config.log_level.lower()
    )
