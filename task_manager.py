"""
Windows Task Scheduler 管理模块

使用 COM API 管理 Windows 计划任务
"""
import win32com.client
from datetime import datetime
from typing import List, Dict, Optional
import pythoncom
import logging

logger = logging.getLogger(__name__)


class TaskState:
    """任务状态常量"""
    UNKNOWN = 0
    DISABLED = 1
    QUEUED = 2
    READY = 3
    RUNNING = 4


class TaskResult:
    """任务结果代码"""
    SUCCESS = 0
    # 其他常见错误码
    ERROR_CODES = {
        0x0: "Success",
        0x1: "Incorrect function called or unknown function called",
        0x2: "File not found",
        0x10: "The environment is incorrect",
        0x41300: "Task is ready to run at its next scheduled time",
        0x41301: "Task is currently running",
        0x41302: "Task is disabled",
        0x41303: "Task has not yet run",
        0x41304: "There are no more runs scheduled for this task",
        0x41306: "Task was terminated by the user",
        0x800704DD: "The service is not available (run 'sc start Schedule')",
        0xC000013A: "The application terminated as a result of CTRL+C"
    }

    @classmethod
    def get_message(cls, code: int) -> str:
        """获取结果代码的描述"""
        return cls.ERROR_CODES.get(code, f"Unknown error code: {hex(code)}")


class TaskManager:
    """Windows Task Scheduler 管理类"""

    def __init__(self, task_prefix: str = "G18"):
        """
        初始化 Task Scheduler 连接

        Args:
            task_prefix: 只管理以此前缀开头的任务
        """
        self.task_prefix = task_prefix
        self.scheduler = None
        self.root_folder = None
        self._connect()

    def _connect(self):
        """连接到 Task Scheduler"""
        try:
            # 初始化 COM
            pythoncom.CoInitialize()

            # 创建 Task Scheduler 对象
            self.scheduler = win32com.client.Dispatch('Schedule.Service')
            self.scheduler.Connect()

            # 获取根文件夹
            self.root_folder = self.scheduler.GetFolder('\\')

            logger.info("Connected to Task Scheduler")
        except Exception as e:
            logger.error(f"Failed to connect to Task Scheduler: {e}")
            raise

    def list_tasks(self) -> List[Dict]:
        """
        列出所有符合前缀的任务

        Returns:
            任务信息列表
        """
        tasks = []
        try:
            for task in self.root_folder.GetTasks(0):
                if task.Name.startswith(self.task_prefix):
                    task_info = self._get_task_info(task)
                    tasks.append(task_info)

            logger.info(f"Listed {len(tasks)} tasks with prefix '{self.task_prefix}'")
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            raise

        return tasks

    def get_task(self, name: str) -> Optional[Dict]:
        """
        获取单个任务的详细信息

        Args:
            name: 任务名称

        Returns:
            任务信息字典，如果不存在则返回 None
        """
        try:
            task = self.root_folder.GetTask(name)
            return self._get_task_info(task)
        except Exception as e:
            logger.warning(f"Task '{name}' not found: {e}")
            return None

    def run_task(self, name: str) -> bool:
        """
        手动运行任务

        Args:
            name: 任务名称

        Returns:
            是否成功触发运行
        """
        try:
            task = self.root_folder.GetTask(name)
            task.Run(None)  # None 表示不传递参数
            logger.info(f"Task '{name}' triggered successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to run task '{name}': {e}")
            return False

    def _get_task_info(self, task) -> Dict:
        """
        提取任务信息

        Args:
            task: COM 任务对象

        Returns:
            任务信息字典
        """
        try:
            # 基础信息
            info = {
                'name': task.Name,
                'path': task.Path,
                'enabled': task.Enabled,
                'state': task.State,
                'state_name': self._get_state_name(task.State),
            }

            # 运行信息
            last_run = task.LastRunTime
            next_run = task.NextRunTime
            last_result = task.LastTaskResult

            info['last_run'] = self._format_time(last_run) if last_run else None
            info['next_run'] = self._format_time(next_run) if next_run else None
            info['last_result'] = last_result
            info['last_result_message'] = TaskResult.get_message(last_result)

            # 定义信息
            definition = task.Definition

            # 触发器信息
            triggers = []
            for trigger in definition.Triggers:
                triggers.append(self._get_trigger_info(trigger))
            info['triggers'] = triggers

            # 动作信息（简化版）
            info['action_count'] = definition.Actions.Count

            return info

        except Exception as e:
            logger.error(f"Failed to get task info for '{task.Name}': {e}")
            return {
                'name': task.Name,
                'error': str(e)
            }

    def _get_state_name(self, state: int) -> str:
        """获取状态名称"""
        state_names = {
            TaskState.UNKNOWN: "Unknown",
            TaskState.DISABLED: "Disabled",
            TaskState.QUEUED: "Queued",
            TaskState.READY: "Ready",
            TaskState.RUNNING: "Running"
        }
        return state_names.get(state, f"Unknown({state})")

    def _get_trigger_info(self, trigger) -> Dict:
        """提取触发器信息"""
        try:
            info = {
                'type': trigger.Type,
                'enabled': trigger.Enabled,
            }

            # 根据类型提取具体信息
            # Type 1 = Time trigger, 2 = Daily, 3 = Weekly, etc.
            if hasattr(trigger, 'StartBoundary'):
                info['start_boundary'] = str(trigger.StartBoundary)

            if hasattr(trigger, 'Repetition') and trigger.Repetition.Interval:
                info['repetition_interval'] = str(trigger.Repetition.Interval)

            return info
        except Exception as e:
            logger.warning(f"Failed to get trigger info: {e}")
            return {'error': str(e)}

    def _format_time(self, dt) -> str:
        """格式化 COM 日期时间为 ISO 字符串"""
        try:
            if isinstance(dt, datetime):
                return dt.isoformat()
            # COM 日期可能是字符串
            return str(dt) if dt else None
        except Exception as e:
            logger.warning(f"Failed to format time: {e}")
            return str(dt) if dt else None

    def __del__(self):
        """清理 COM 资源"""
        try:
            pythoncom.CoUninitialize()
        except:
            pass
