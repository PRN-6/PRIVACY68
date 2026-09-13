/**
 * PRIVACY68 Mobile Web Remote Client Controller
 */
document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const commandForm = document.getElementById('command-form');
    const commandInput = document.getElementById('command-input');
    const btnSend = document.getElementById('btn-send');
    const btnMic = document.getElementById('btn-mic');
    const voiceStatus = document.getElementById('voice-status');
    const voiceStatusText = document.getElementById('voice-status-text');
    const actionsGrid = document.getElementById('actions-grid');
    const historyList = document.getElementById('history-list');
    const btnClearHistory = document.getElementById('btn-clear-history');
    const pcTarget = document.getElementById('pc-target');
    const connectionStatus = document.getElementById('connection-status');
    const btnQr = document.getElementById('btn-qr');
    const qrModal = document.getElementById('qr-modal');
    const btnCloseModal = document.getElementById('btn-close-modal');
    const modalBackdrop = document.getElementById('modal-backdrop');
    const modalUrl = document.getElementById('modal-url');
    const tabBtns = document.querySelectorAll('.tab-btn');

    let allActions = [];
    let activeCategory = 'all';
    let isListening = false;
    let recognition = null;

    // 1. Initialize Quick Actions
    async function loadQuickActions() {
        try {
            const res = await fetch('/api/quick-actions');
            if (res.ok) {
                const data = await res.json();
                allActions = data.actions || [];
                renderActions();
            }
        } catch (e) {
            console.error('Failed to load quick actions', e);
        }
    }

    function renderActions() {
        actionsGrid.innerHTML = '';
        const filtered = activeCategory === 'all' 
            ? allActions 
            : allActions.filter(a => a.category.toLowerCase() === activeCategory.toLowerCase());

        filtered.forEach(action => {
            const card = document.createElement('div');
            card.className = 'action-card';
            card.innerHTML = `
                <div class="action-icon">${action.icon}</div>
                <div class="action-info">
                    <span class="action-label">${action.label}</span>
                    <span class="action-cmd">${action.command}</span>
                </div>
            `;
            card.addEventListener('click', () => {
                triggerVibrate(30);
                dispatchCommand(action.command);
            });
            actionsGrid.appendChild(card);
        });
    }

    // Category Tabs Filtering
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeCategory = btn.dataset.cat;
            renderActions();
        });
    });

    // 2. Fetch PC & Server Status
    async function checkStatus() {
        try {
            const res = await fetch('/api/status');
            if (res.ok) {
                const data = await res.json();
                pcTarget.textContent = `Connected to ${data.pc_name || 'PC'} (${data.local_ip})`;
                connectionStatus.className = 'status-chip';
                connectionStatus.querySelector('.status-text').textContent = 'Online';
                if (modalUrl) {
                    modalUrl.textContent = data.remote_url || window.location.origin;
                }
            } else {
                markOffline();
            }
        } catch (e) {
            markOffline();
        }
    }

    function markOffline() {
        pcTarget.textContent = 'Disconnected';
        connectionStatus.className = 'status-chip offline';
        connectionStatus.querySelector('.status-text').textContent = 'Offline';
    }

    // 3. Dispatch Command to Privacy68 PC Core
    async function dispatchCommand(commandText) {
        const text = commandText.trim();
        if (!text) return;

        showToast(`⚡ Dispatching: "${text}"...`, 'info');
        btnSend.disabled = true;

        try {
            const res = await fetch('/api/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: text })
            });

            const result = await res.json();
            
            if (result.success) {
                triggerVibrate([40, 60, 40]);
                showToast(`✅ Executed: ${result.tool || text}`, 'success');
                addHistoryItem({
                    command: text,
                    tool: result.tool,
                    method: result.method,
                    success: true,
                    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                });
            } else {
                triggerVibrate(150);
                showToast(`❌ ${result.message || 'Command unhandled'}`, 'error');
                addHistoryItem({
                    command: text,
                    tool: result.tool || 'Failed',
                    method: result.method || 'none',
                    success: false,
                    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                });
            }
        } catch (err) {
            showToast(`⚠️ Error: ${err.message}`, 'error');
        } finally {
            btnSend.disabled = false;
        }
    }

    // Command Form Submit
    commandForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const cmd = commandInput.value.trim();
        if (cmd) {
            dispatchCommand(cmd);
            commandInput.value = '';
            commandInput.blur();
        }
    });

    // 4. Voice Input via Web Speech API (Phone Mic)
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
            isListening = true;
            btnMic.classList.add('listening');
            voiceStatus.style.display = 'flex';
            voiceStatusText.textContent = 'Listening... Speak command now';
            triggerVibrate(50);
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            voiceStatusText.textContent = `Heard: "${transcript}"`;
            commandInput.value = transcript;
            setTimeout(() => {
                dispatchCommand(transcript);
            }, 300);
        };

        recognition.onerror = (event) => {
            console.warn('Speech recognition error', event.error);
            voiceStatusText.textContent = `Voice error: ${event.error}`;
            setTimeout(() => {
                stopVoice();
            }, 1500);
        };

        recognition.onend = () => {
            stopVoice();
        };

        btnMic.addEventListener('click', () => {
            if (isListening) {
                recognition.stop();
                stopVoice();
            } else {
                try {
                    recognition.start();
                } catch (e) {
                    console.error(e);
                }
            }
        });
    } else {
        btnMic.title = 'Voice input not supported in this browser';
        btnMic.style.opacity = '0.4';
        btnMic.addEventListener('click', () => {
            showToast('Voice speech recognition not supported in this browser. Please type command.', 'error');
        });
    }

    function stopVoice() {
        isListening = false;
        btnMic.classList.remove('listening');
        setTimeout(() => {
            if (!isListening) {
                voiceStatus.style.display = 'none';
            }
        }, 800);
    }

    // 5. History Feed
    function addHistoryItem(item) {
        const emptyMsg = historyList.querySelector('.empty-history');
        if (emptyMsg) emptyMsg.remove();

        const row = document.createElement('div');
        row.className = 'history-item';
        row.innerHTML = `
            <div class="history-left">
                <div class="history-cmd">"${item.command}"</div>
                <div class="history-meta">${item.time} • ${item.method.replace('_', ' ').toUpperCase()}</div>
            </div>
            <div class="history-badge ${item.success ? 'success' : 'error'}">
                ${item.tool || (item.success ? 'OK' : 'ERR')}
            </div>
        `;
        historyList.insertBefore(row, historyList.firstChild);

        // Keep maximum 15 items
        while (historyList.children.length > 15) {
            historyList.removeChild(historyList.lastChild);
        }
    }

    btnClearHistory.addEventListener('click', () => {
        historyList.innerHTML = '<div class="empty-history">No commands dispatched yet. Speak or type above!</div>';
    });

    // 6. QR Code Pairing Modal
    function openQrModal() {
        qrModal.classList.add('active');
    }

    function closeQrModal() {
        qrModal.classList.remove('active');
    }

    btnQr.addEventListener('click', openQrModal);
    btnCloseModal.addEventListener('click', closeQrModal);
    modalBackdrop.addEventListener('click', closeQrModal);

    // 7. Toast Notifications
    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.innerHTML = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px) scale(0.95)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    function triggerVibrate(pattern) {
        if ('vibrate' in navigator) {
            try { navigator.vibrate(pattern); } catch (e) {}
        }
    }

    // Initial Startup
    loadQuickActions();
    checkStatus();
    setInterval(checkStatus, 8000);
});
