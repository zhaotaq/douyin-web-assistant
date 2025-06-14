document.addEventListener('DOMContentLoaded', function() {
    // 获取UI元素
    const saveCookieBtn = document.getElementById('save-cookie-btn');
    const cookieDataInput = document.getElementById('cookie-data-input');
    
    // 新的UI元素
    const poolCountSpan = document.getElementById('account-stats-count');
    const taskCard = document.getElementById('task-card');

    const runBtn = document.getElementById('run-task-btn');
    const stopBtn = document.getElementById('stop-task-btn');
    const urlInput = document.getElementById('url-input');
    const currentTaskStatus = document.getElementById('current-task-status');
    const currentTaskLog = document.getElementById('current-task-log');
    const queueList = document.getElementById('queue-list');
    
    // 教程弹窗元素
    const showTutorialLink = document.getElementById('show-tutorial-link');
    const tutorialModal = document.getElementById('tutorial-modal');
    const modalCloseBtn = document.getElementById('modal-close-btn');

    // Admin Panel Elements
    const adminAccessLink = document.getElementById('admin-access-link');
    const adminPanel = document.getElementById('admin-panel');
    const newCommentsInput = document.getElementById('new-comments-input');
    const saveCommentsBtn = document.getElementById('save-comments-btn');
    const debugModeCheckbox = document.getElementById('debug-mode-checkbox');

    let adminPassword = null;

    // --- State ---
    let userTaskId = localStorage.getItem('userTaskId');

    // --- Task Submission ---
    runBtn.addEventListener('click', () => {
        const urls = urlInput.value.split('\n').filter(url => url.trim() !== '');
        if (urls.length === 0) {
            alert('请输入至少一个主页地址。');
            return;
        }

        runBtn.disabled = true;
        runBtn.textContent = '正在提交...';

        const payload = { urls: urls };

        // Check if admin debug mode is active and enabled
        if (adminPanel.style.display === 'block' && debugModeCheckbox.checked) {
            payload.debug = true;
            payload.password = adminPassword; // Pass password for validation
        }

        fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (!response.ok) return response.json().then(err => { throw new Error(err.error); });
            return response.json();
        })
        .then(data => {
            userTaskId = data.data.task_id;
            localStorage.setItem('userTaskId', userTaskId);
            alert(`您的任务已成功加入队列，编号为 #${userTaskId}`);
            urlInput.value = '';
            pollStatus(); // Immediately poll to update UI
        })
        .catch(error => {
            alert('提交任务失败: ' + error.message);
        })
        .finally(() => {
            runBtn.disabled = false;
            runBtn.textContent = '提交执行';
        });
    });

    // --- Status Polling & UI Rendering ---
    function pollStatus() {
        //CACHE BUSTING: Appending a timestamp to prevent browser caching of the API call
        fetch('/api/status?_t=' + new Date().getTime())
            .then(response => response.json())
            .then(data => {
                if(data.code !== 0) {
                    currentTaskStatus.textContent = '错误';
                    currentTaskStatus.className = 'status-tag failed';
                    currentTaskLog.textContent = `获取状态失败: ${data.error || '未知错误'}`;
                    return;
                };
                
                const { current_task, pending_tasks } = data.data;

                // --- Render Current Task & Manage Button States ---
                if (current_task) {
                    const statusMap = {
                        'running': '运行中', 'pending': '等待中', 'completed': '已完成',
                        'failed': '失败', 'stopped': '已停止'
                    };
                    const statusClassMap = {
                        'running': 'running', 'pending': 'idle', 'completed': 'completed',
                        'failed': 'failed', 'stopped': 'stopped'
                    };
                    currentTaskStatus.textContent = `${statusMap[current_task.status] || '未知'} (任务 #${current_task.id})`;
                    currentTaskStatus.className = `status-tag ${statusClassMap[current_task.status] || 'idle'}`;
                    currentTaskLog.textContent = current_task.log || '正在等待日志...';
                    // A task is active, so disable running a new one and enable stopping the current one.
                    stopBtn.disabled = false;
                    runBtn.disabled = true;
                } else {
                    currentTaskStatus.textContent = '空闲';
                    currentTaskStatus.className = 'status-tag idle';
                    currentTaskLog.textContent = '系统准备就绪，等待新任务...';
                    // No task is active, enable running a new one (if pool is ready) and disable stopping.
                    stopBtn.disabled = true;
                    // We let updateAccountPool decide if the run button should be enabled.
                    updateAccountPool(); 
                }

                // --- Render Queue ---
                queueList.innerHTML = ''; // Clear previous list
                if (pending_tasks && pending_tasks.length > 0) {
                    pending_tasks.forEach(task => {
                        const item = document.createElement('div');
                        item.className = 'queue-item';
                        item.textContent = `任务 #${task.id} (状态: ${task.status})`;
                        if (task.id == userTaskId) {
                            item.classList.add('user-task');
                            item.textContent += ' (这是您的任务)';
                        }
                        queueList.appendChild(item);
                    });
                } else {
                    queueList.innerHTML = '<p>当前没有任务在等待。</p>';
                }

                // --- Clear Finished User Task ---
                const isUserTaskRunning = current_task && current_task.id == userTaskId;
                const isUserTaskInQueue = pending_tasks.some(t => t.id == userTaskId);

                if (userTaskId && !isUserTaskRunning && !isUserTaskInQueue) {
                    console.log(`任务 #${userTaskId} 已结束，正在从本地存储中移除。`);
                    localStorage.removeItem('userTaskId');
                    userTaskId = null;
                }
            })
            .catch(error => {
                console.error("Error polling status:", error);
                currentTaskStatus.textContent = '连接错误';
                currentTaskStatus.className = 'status-tag failed';
                currentTaskLog.textContent = '轮询后端状态失败，请检查网络连接或后台服务是否运行。';
                stopBtn.disabled = true;
            });
    }

    // --- 功能 2: 保存用户提交的Cookie ---
    saveCookieBtn.addEventListener('click', () => {
        const cookieData = cookieDataInput.value.trim();

        if (!cookieData) {
            alert('Cookie内容不能为空！');
            return;
        }

        try {
            JSON.parse(cookieData);
        } catch (e) {
            alert('Cookie数据不是有效的JSON格式，请检查。');
            return;
        }

        saveCookieBtn.textContent = '正在提交...';
        saveCookieBtn.disabled = true;

        fetch('/api/save_cookie', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cookieData: cookieData })
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.error || '未知错误'); });
            }
            return response.json();
        })
        .then(data => {
            alert(data.message || 'Cookie保存成功！感谢您的贡献！');
            cookieDataInput.value = '';
            updateAccountPool();
        })
        .catch(error => {
            console.error('保存Cookie失败:', error);
            alert('保存Cookie失败: ' + error.message);
        })
        .finally(() => {
            saveCookieBtn.textContent = '提交并加入共享池';
            saveCookieBtn.disabled = false;
        });
    });

    // --- 新增: 教程弹窗交互 ---
    showTutorialLink.addEventListener('click', (e) => {
        e.preventDefault();
        tutorialModal.style.display = 'flex';
    });

    modalCloseBtn.addEventListener('click', () => {
        tutorialModal.style.display = 'none';
    });

    tutorialModal.addEventListener('click', (e) => {
        if (e.target === tutorialModal) {
            tutorialModal.style.display = 'none';
        }
    });

    // --- 功能 3: 运行和停止任务 ---
    stopBtn.addEventListener('click', () => {
        if (confirm('您确定要停止当前正在运行的任务吗？')) {
            stopBtn.disabled = true;
            stopBtn.textContent = '正在停止...';
            fetch('/api/stop_task', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    alert(data.message);
                    pollStatus(); // Immediately poll to get the 'stopped' status
                })
                .catch(err => alert('发送停止信号失败: ' + err))
                .finally(() => {
                    stopBtn.textContent = '停止任务';
                });
        }
    });

    // --- 功能 4: 轮询账户池状态 ---
    function updateAccountPool() {
        //CACHE BUSTING: Appending a timestamp to prevent browser caching
        fetch('/api/accounts?_t=' + new Date().getTime())
            .then(response => {
                if (!response.ok) throw new Error('网络响应错误');
                return response.json();
            })
            .then(data => {
                if (data.code !== 0) {
                    throw new Error(data.message || '获取账户信息失败');
                }
                const count = data.data.count || 0;
                poolCountSpan.textContent = count;

                if (count > 0) {
                    taskCard.classList.remove('locked');
                    // Only enable run button if no task is currently active
                    if (stopBtn.disabled) { 
                       runBtn.disabled = false;
                    }
                } else {
                    taskCard.classList.add('locked');
                    runBtn.disabled = true;
                }
            })
            .catch(error => {
                console.error('更新账户池信息失败:', error);
                poolCountSpan.textContent = '✖';
                taskCard.classList.add('locked');
                runBtn.disabled = true;
            });
    }
    
    // --- 初始化 ---
    updateAccountPool(); // Initial load for account pool
    setInterval(pollStatus, 3000); // Poll status every 3 seconds
    pollStatus(); // Initial status poll right away

    // --- 新功能: 管理员入口 ---
    adminAccessLink.addEventListener('click', (e) => {
        e.preventDefault();
        if (adminPanel.style.display !== 'none') {
            adminPanel.style.display = 'none';
            return;
        }

        const password = prompt('请输入管理员密码:');
        if (password) {
            adminPassword = password;
            adminPanel.style.display = 'block';
        }
    });

    // --- 新功能: 保存新评论 ---
    saveCommentsBtn.addEventListener('click', () => {
        if (!adminPassword) {
            alert('请先通过管理员入口输入密码。');
            return;
        }

        const comments = newCommentsInput.value.split('\n').filter(c => c.trim() !== '');
        if (comments.length === 0) {
            alert('请输入至少一条评论。');
            return;
        }

        saveCommentsBtn.textContent = '正在保存...';
        saveCommentsBtn.disabled = true;

        fetch('/api/add_comments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                comments: comments,
                password: adminPassword
            })
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.error || '发生未知错误'); });
            }
            return response.json();
        })
        .then(data => {
            alert(data.message);
            newCommentsInput.value = ''; // Clear input on success
        })
        .catch(error => {
            console.error('保存评论失败:', error);
            alert('保存评论失败: ' + error.message);
        })
        .finally(() => {
            saveCommentsBtn.textContent = '保存到评论库';
            saveCommentsBtn.disabled = false;
        });
    });
});