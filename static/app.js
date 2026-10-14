// GDash Control - 前端逻辑

// 全局状态
let currentTaskToRun = null;

// ============================================================================
// 初始化
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('GDash Control Service - UI Loaded');
    checkServiceStatus();
    loadTasks();
    loadAuditLogs();

    // 自动刷新（每 30 秒）
    setInterval(() => {
        checkServiceStatus();
        loadTasks();
    }, 30000);
});

// ============================================================================
// 服务状态检查
// ============================================================================

async function checkServiceStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        const statusBadge = document.getElementById('serviceStatus');
        const statusText = statusBadge.querySelector('.status-text');

        if (data.status === 'healthy') {
            statusBadge.classList.add('healthy');
            statusBadge.classList.remove('unhealthy');
            statusText.textContent = '服务正常';
        } else {
            statusBadge.classList.add('unhealthy');
            statusBadge.classList.remove('healthy');
            statusText.textContent = '服务异常';
        }
    } catch (error) {
        console.error('Failed to check service status:', error);
        const statusBadge = document.getElementById('serviceStatus');
        statusBadge.classList.add('unhealthy');
        statusBadge.classList.remove('healthy');
        statusBadge.querySelector('.status-text').textContent = '连接失败';
    }
}

// ============================================================================
// 任务管理
// ============================================================================

async function loadTasks() {
    const taskList = document.getElementById('taskList');

    try {
        const response = await fetch('/api/tasks');
        const data = await response.json();

        if (data.tasks.length === 0) {
            taskList.innerHTML = '<div class="loading">暂无任务</div>';
            return;
        }

        taskList.innerHTML = data.tasks.map(task => renderTaskCard(task)).join('');
    } catch (error) {
        console.error('Failed to load tasks:', error);
        taskList.innerHTML = '<div class="loading">加载失败: ' + error.message + '</div>';
    }
}

function renderTaskCard(task) {
    const stateClass = task.state_name.toLowerCase();
    const lastResult = task.last_result === 0 ? 'success' : 'failed';
    const lastResultText = task.last_result_message || 'Unknown';

    return `
        <div class="task-card">
            <div class="task-header">
                <div>
                    <div class="task-name">${escapeHtml(task.name)}</div>
                </div>
                <span class="task-state ${stateClass}">${task.state_name}</span>
            </div>

            <div class="task-info">
                <div class="task-info-row">
                    <span class="task-info-label">状态:</span>
                    <span>${task.enabled ? '已启用' : '已禁用'}</span>
                </div>
                <div class="task-info-row">
                    <span class="task-info-label">上次运行:</span>
                    <span>${formatTime(task.last_run)}</span>
                </div>
                <div class="task-info-row">
                    <span class="task-info-label">下次运行:</span>
                    <span>${formatTime(task.next_run)}</span>
                </div>
            </div>

            ${task.last_result !== undefined ? `
                <div class="task-result ${lastResult}">
                    <strong>最近结果:</strong> ${escapeHtml(lastResultText)}
                </div>
            ` : ''}

            <div class="task-actions">
                <button class="btn btn-secondary" onclick="showTaskDetail('${escapeHtml(task.name)}')">
                    详情
                </button>
                <button class="btn btn-success" onclick="confirmRunTask('${escapeHtml(task.name)}')"
                        ${!task.enabled ? 'disabled' : ''}>
                    立即执行
                </button>
            </div>
        </div>
    `;
}

async function showTaskDetail(taskName) {
    try {
        const response = await fetch(`/api/tasks/${encodeURIComponent(taskName)}`);
        const task = await response.json();

        const detailContent = document.getElementById('detailContent');
        const detailTitle = document.getElementById('detailTitle');

        detailTitle.textContent = `任务详情 - ${task.name}`;

        detailContent.innerHTML = `
            <h4>基础信息</h4>
            <p><strong>任务名称:</strong> ${escapeHtml(task.name)}</p>
            <p><strong>任务路径:</strong> ${escapeHtml(task.path || 'N/A')}</p>
            <p><strong>状态:</strong> ${task.state_name} ${task.enabled ? '(已启用)' : '(已禁用)'}</p>

            <h4>运行信息</h4>
            <p><strong>上次运行时间:</strong> ${formatTime(task.last_run)}</p>
            <p><strong>下次运行时间:</strong> ${formatTime(task.next_run)}</p>
            <p><strong>上次运行结果:</strong> ${escapeHtml(task.last_result_message || 'N/A')}</p>

            <h4>触发器</h4>
            <pre>${JSON.stringify(task.triggers || [], null, 2)}</pre>

            <h4>原始数据</h4>
            <pre>${JSON.stringify(task, null, 2)}</pre>
        `;

        document.getElementById('detailDialog').style.display = 'flex';
    } catch (error) {
        console.error('Failed to load task detail:', error);
        alert('加载任务详情失败: ' + error.message);
    }
}

function closeDetailDialog() {
    document.getElementById('detailDialog').style.display = 'none';
}

function confirmRunTask(taskName) {
    currentTaskToRun = taskName;
    document.getElementById('confirmMessage').textContent =
        `确定要立即执行任务 "${taskName}" 吗？`;
    document.getElementById('confirmDialog').style.display = 'flex';
}

function closeConfirmDialog() {
    currentTaskToRun = null;
    document.getElementById('confirmDialog').style.display = 'none';
}

async function executeConfirmedTask() {
    if (!currentTaskToRun) {
        return;
    }

    const taskName = currentTaskToRun;
    closeConfirmDialog();

    try {
        const response = await fetch(`/api/tasks/${encodeURIComponent(taskName)}/run`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok) {
            alert(`任务 "${taskName}" 已触发执行！\n\n请稍后在任务详情中查看执行结果。`);
            // 延迟 2 秒后刷新任务列表
            setTimeout(() => {
                loadTasks();
                loadAuditLogs();
            }, 2000);
        } else {
            alert(`执行失败: ${data.detail || '未知错误'}`);
        }
    } catch (error) {
        console.error('Failed to run task:', error);
        alert('执行任务失败: ' + error.message);
    }
}

async function refreshTasks() {
    const icon = document.getElementById('refreshIcon');
    icon.style.animation = 'spin 0.5s linear';
    await loadTasks();
    setTimeout(() => {
        icon.style.animation = '';
    }, 500);
}

// ============================================================================
// 日志管理
// ============================================================================

async function loadAuditLogs() {
    const logsContainer = document.getElementById('auditLogs');

    try {
        const response = await fetch('/api/audit?lines=50');
        const data = await response.json();

        if (data.lines.length === 0) {
            logsContainer.innerHTML = '<div class="loading">暂无日志</div>';
            return;
        }

        logsContainer.innerHTML = data.lines
            .reverse()
            .map(line => `<div class="log-line">${escapeHtml(line)}</div>`)
            .join('');

        // 滚动到底部
        logsContainer.scrollTop = logsContainer.scrollHeight;
    } catch (error) {
        console.error('Failed to load audit logs:', error);
        logsContainer.innerHTML = '<div class="loading">加载日志失败: ' + error.message + '</div>';
    }
}

async function refreshLogs() {
    const icon = document.getElementById('logRefreshIcon');
    icon.style.animation = 'spin 0.5s linear';
    await loadAuditLogs();
    setTimeout(() => {
        icon.style.animation = '';
    }, 500);
}

// ============================================================================
// 工具函数
// ============================================================================

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

function formatTime(timeStr) {
    if (!timeStr || timeStr === 'None' || timeStr === 'null') {
        return '未设置';
    }

    try {
        const date = new Date(timeStr);
        if (isNaN(date.getTime())) {
            return timeStr;
        }

        // 格式化为本地时间
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');

        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    } catch (error) {
        return timeStr;
    }
}

// 添加旋转动画
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);
