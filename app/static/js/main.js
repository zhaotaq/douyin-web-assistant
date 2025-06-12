document.addEventListener('DOMContentLoaded', function() {
    // 获取UI元素
    const saveCookieBtn = document.getElementById('save-cookie-btn');
    const cookieDataInput = document.getElementById('cookie-data-input');
    
    // 新的UI元素
    const poolCountSpan = document.getElementById('account-stats-count');
    const taskCard = document.getElementById('task-card');

    const runBtn = document.getElementById('run-btn');
    const stopBtn = document.getElementById('stop-btn');
    const urlInput = document.getElementById('url-input');
    const statusText = document.getElementById('status-text');
    const logText = document.getElementById('log-text');
    const logViewer = document.getElementById('log-viewer');
    
    // 教程弹窗元素
    const showTutorialLink = document.getElementById('show-tutorial-link');
    const tutorialModal = document.getElementById('tutorial-modal');
    const modalCloseBtn = document.getElementById('modal-close-btn');

    // Admin Panel Elements
    const adminAccessLink = document.getElementById('admin-access-link');
    const adminPanel = document.getElementById('admin-panel');
    const newCommentsInput = document.getElementById('new-comments-input');
    const saveCommentsBtn = document.getElementById('save-comments-btn');

    let adminPassword = null;

    // --- 新功能: 更新共享池状态并控制UI锁定 ---
    function updateAccountPool() {
        fetch('/api/accounts')
            .then(response => {
                if (!response.ok) throw new Error('网络响应错误');
                return response.json();
            })
            .then(data => {
                if (data.code !== 0) {
                    throw new Error(data.message || '获取账户信息失败');
                }
                const count = data.data.count || 0;

                // 更新顶部醒目的数字
                poolCountSpan.textContent = count;

                // 根据账户数量锁定或解锁第二步
                if (count > 0) {
                    taskCard.classList.remove('locked');
                    // 如果任务不在运行中，则启用运行按钮
                    if (stopBtn.disabled) {
                       runBtn.disabled = false;
                    }
                } else {
                    taskCard.classList.add('locked');
                    runBtn.disabled = true; // 池为空，必须禁用
                }
            })
            .catch(error => {
                console.error('更新账户池信息失败:', error);
                poolCountSpan.textContent = '✖'; // 使用错误符号
                taskCard.classList.add('locked'); // 获取失败时也锁定
                runBtn.disabled = true;
            });
    }

    // --- 功能 2: 保存用户提交的Cookie ---
    saveCookieBtn.addEventListener('click', () => {
        const cookieData = cookieDataInput.value.trim();

        if (!cookieData) {
            alert('Cookie内容不能为空！');
            return;
        }

        // 尝试前端校验JSON格式
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
            body: JSON.stringify({
                cookieData: cookieData
            })
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.error || '未知错误'); });
            }
            return response.json();
        })
        .then(data => {
            alert(data.message || 'Cookie保存成功！感谢您的贡献！');
            // 清空输入框
            cookieDataInput.value = '';
            // 立即刷新账户池状态，这将自动解锁UI
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
        // 如果点击的是背景遮罩本身，而不是内容区域，则关闭弹窗
        if (e.target === tutorialModal) {
            tutorialModal.style.display = 'none';
        }
    });

    // --- 功能 3: 运行和停止任务 ---
    runBtn.addEventListener('click', () => {
        const urls = urlInput.value.split('\\n').filter(url => url.trim() !== '');

        if (urls.length === 0) {
            alert('请输入至少一个主页地址。');
            return;
        }

        runBtn.disabled = true;
        stopBtn.disabled = false;
        
        // 规约: 不再发送 aacount 参数
        fetch('/api/run_task', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls: urls })
        });
    });

    stopBtn.addEventListener('click', () => {
        stopBtn.disabled = true;
        fetch('/api/stop_task', { method: 'POST' })
            .then(() => {
                // 停止后，状态轮询会自动处理按钮状态，但我们可以立即刷新一次池信息
                updateAccountPool();
            });
    });

    // --- 功能 4: 轮询状态和日志 ---
    function pollStatus() {
        const statusTranslations = {
            'idle': '待命',
            'running': '运行中...',
            'completed': '任务完成',
            'failed': '任务失败',
            'stopped': '已停止',
        };

        fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                if(data.code !== 0) return;
                
                const statusKey = (data.data.status || 'idle').toLowerCase();
                const currentLog = data.data.log || "暂无日志";

                // 翻译状态
                const translatedStatus = statusTranslations[statusKey] || statusKey;
                statusText.textContent = translatedStatus;
                
                // 更新状态的CSS类以应用背景色
                statusText.classList.remove('idle', 'running', 'completed', 'failed', 'stopped');
                statusText.classList.add(statusKey);
                
                // 更新日志并滚动到底部
                if (logText.textContent !== currentLog) {
                    logText.textContent = currentLog;
                    logViewer.scrollTop = logViewer.scrollHeight;
                }
                
                const isRunning = statusKey === 'running';
                
                // 如果任务从运行中变为非运行状态，则刷新一次账户池
                if (!isRunning && !stopBtn.disabled) {
                    updateAccountPool();
                }

                // 只有当池不为空时，运行按钮才可能被启用
                const poolIsReady = !taskCard.classList.contains('locked');
                runBtn.disabled = isRunning || !poolIsReady;
                stopBtn.disabled = !isRunning;
            });
    }
    
    // --- 初始化 ---
    stopBtn.disabled = true;
    runBtn.disabled = true; // 初始时总是禁用，等待updateAccountPool来决定
    updateAccountPool(); // 页面加载后立即获取初始状态
    setInterval(pollStatus, 2000); // 保持状态轮询
    // 可以降低账户池的轮询频率，因为它不那么频繁变化
    setInterval(updateAccountPool, 15000); 

    // --- 新功能: 管理员入口 ---
    adminAccessLink.addEventListener('click', (e) => {
        e.preventDefault();
        if (adminPanel.style.display !== 'none') {
            adminPanel.style.display = 'none';
            return;
        }

        const password = prompt('请输入管理员密码:');
        if (password) {
            adminPassword = password; // Store password for the session
            // A simple check to see if we should show the panel.
            // The real validation is on the backend.
            adminPanel.style.display = 'block';
        }
    });

    // --- 新功能: 保存新评论 ---
    saveCommentsBtn.addEventListener('click', () => {
        if (!adminPassword) {
            alert('请先通过管理员入口输入密码。');
            return;
        }

        const comments = newCommentsInput.value.split('\\n').filter(c => c.trim() !== '');
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