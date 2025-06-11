document.addEventListener('DOMContentLoaded', () => {

    // --- DOM Element References ---
    const statusText = document.getElementById('status-text');
    const logText = document.getElementById('log-text');
    const accountList = document.getElementById('account-list');
    const urlsInput = document.getElementById('urls-input');
    const startTaskBtn = document.getElementById('start-task-btn');
    const stopTaskBtn = document.getElementById('stop-task-btn');

    const API_BASE_URL = 'http://127.0.0.1:5000/api';

    // --- State Management ---
    let statusInterval; // To hold the interval ID for polling status

    // --- API Functions ---

    /**
     * Fetches the current status from the backend and updates the UI.
     */
    const fetchStatus = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/status`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const result = await response.json();
            if (result.code === 0) {
                updateStatusUI(result.data.status, result.data.log);
            } else {
                updateStatusUI('failed', result.error || '获取状态失败');
            }
        } catch (error) {
            console.error("Error fetching status:", error);
            updateStatusUI('failed', '无法连接到后端服务。');
            // Stop polling if we can't connect
            if(statusInterval) clearInterval(statusInterval);
        }
    };

    /**
     * Fetches the list of accounts and populates the account list UI.
     */
    const fetchAccounts = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/accounts`);
            if (!response.ok) throw new Error('Failed to load accounts.');
            const result = await response.json();
            
            accountList.innerHTML = ''; // Clear loading text
            if (result.code === 0 && result.data.accounts.length > 0) {
                result.data.accounts.forEach(account => {
                    const li = document.createElement('li');
                    li.textContent = account;
                    accountList.appendChild(li);
                });
            } else if(result.data.accounts.length === 0) {
                 accountList.innerHTML = '<li>未找到任何账户 Cookie 文件。</li>';
            } else {
                 accountList.innerHTML = `<li>加载失败: ${result.error}</li>`;
            }
        } catch (error) {
            console.error("Error fetching accounts:", error);
            accountList.innerHTML = '<li>无法加载账户列表。</li>';
        }
    };

    // --- UI Update Functions ---

    /**
     * Updates the UI based on the current task status.
     * @param {string} status - The current status ('idle', 'running', etc.)
     * @param {string} log - The log message.
     */
    const updateStatusUI = (status, log) => {
        statusText.textContent = status;
        // Apply class for color coding based on status
        statusText.className = status; 
        logText.textContent = log;

        // Enable/disable buttons based on status
        if (status === 'running') {
            startTaskBtn.disabled = true;
            stopTaskBtn.disabled = false;
        } else { // idle, completed, failed, stopped
            startTaskBtn.disabled = false;
            stopTaskBtn.disabled = true;
        }
    };
    
    // --- Event Listeners ---

    /**
     * Handles the click event for the "Start Task" button.
     */
    startTaskBtn.addEventListener('click', async () => {
        const urls = urlsInput.value.trim().split('\n').filter(url => url.trim() !== '');
        if (urls.length === 0) {
            alert('请输入至少一个URL！');
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/run_task`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ urls }),
            });

            const result = await response.json();

            // On 202 Accepted, we don't need to do much, the status poller will pick it up.
            if (response.status === 202) {
                 console.log('Task started successfully');
                 fetchStatus(); // Immediately fetch status to update UI faster
            } else {
                // Handle errors like 409 Conflict
                alert(`启动任务失败: ${result.error}`);
            }
        } catch (error) {
            console.error("Error starting task:", error);
            alert('启动任务时发生网络错误。');
        }
    });

    /**
     * Handles the click event for the "Stop Task" button.
     */
    stopTaskBtn.addEventListener('click', async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/stop_task`, { method: 'POST' });
            const result = await response.json();

            if(response.ok) {
                console.log('Stop signal sent.');
                fetchStatus(); // Immediately fetch status to update UI faster
            } else {
                 alert(`发送停止信号失败: ${result.error}`);
            }
        } catch (error) {
            console.error("Error stopping task:", error);
            alert('停止任务时发生网络错误。');
        }
    });

    // --- Initial Load ---

    /**
     * Initializes the application.
     */
    const init = () => {
        fetchAccounts();
        fetchStatus(); // Initial fetch
        statusInterval = setInterval(fetchStatus, 3000); // Poll every 3 seconds
    };

    init();
}); 