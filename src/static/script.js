document.addEventListener('DOMContentLoaded', () => {
    // Element references
    const monitorStatus = document.getElementById('monitor-status');
    const lastCheck = document.getElementById('last-check');
    const epicCount = document.getElementById('epic-count');
    const epicList = document.getElementById('epic-list');
    const configContent = document.getElementById('config-content');
    const logContent = document.getElementById('log-content');
    const loadingOverlay = document.getElementById('loading-overlay');
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toast-message');
    
    // Metric elements
    const totalChecksEl = document.getElementById('total-checks');
    const changesDetectedEl = document.getElementById('changes-detected');
    const uptimeEl = document.getElementById('uptime');
    const activeEpicsEl = document.getElementById('active-epics');
    
    // Metrics
    let metrics = {
        totalChecks: 0,
        changesDetected: 0,
        startTime: Date.now(),
        activeEpics: 0
    };

    // Utility functions
    const showToast = (message) => {
        toastMessage.textContent = message;
        toast.style.display = 'block';
        setTimeout(() => {
            toast.style.display = 'none';
        }, 3000);
    };

    const showLoading = (flag) => {
        loadingOverlay.style.display = flag ? 'flex' : 'none';
    };

    const updateStatus = async () => {
        showLoading(true);
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            monitorStatus.textContent = data.is_running ? 'Running' : 'Stopped';
            epicCount.textContent = data.monitored_epics ? data.monitored_epics.length : 0;
        } catch (err) {
            showToast('Failed to fetch status');
        } finally {
            showLoading(false);
        }
    };

    const updateEpics = async () => {
        showLoading(true);
        try {
            const response = await fetch('/api/epics');
            const data = await response.json();
            if (data.epics && data.epics.length > 0) {
                epicList.innerHTML = '';
                data.epics.forEach(epic => {
                    const epicElement = document.createElement('div');
                    epicElement.className = 'epic-item';
                    epicElement.innerHTML = `
                        <span class="epic-id">${epic}</span>
                        <button class="btn btn-danger btn-sm" onclick="removeEpic('${epic}')">
                            <i class="fas fa-trash"></i> Remove
                        </button>
                    `;
                    epicList.appendChild(epicElement);
                });
                epicCount.textContent = data.epics.length;
            } else {
                epicList.innerHTML = '<p class="no-epics">No EPICs being monitored</p>';
                epicCount.textContent = '0';
            }
        } catch (err) {
            showToast('Failed to fetch EPICs');
        } finally {
            showLoading(false);
        }
    };

    // Store current config for editing
    let currentConfig = {};

    const updateConfig = async () => {
        try {
            const response = await fetch('/api/config');
            const data = await response.json();
            if (data.config) {
                currentConfig = data.config;
                configContent.innerHTML = `
                    <div class="config-item">
                        <span class="config-label">Poll Interval:</span>
                        <span class="config-value">${data.config.poll_interval_seconds}s</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">Auto Sync:</span>
                        <span class="config-value">${data.config.auto_sync ? 'Enabled' : 'Disabled'}</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">Snapshot Directory:</span>
                        <span class="config-value">${data.config.snapshot_directory}</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">Log Level:</span>
                        <span class="config-value">${data.config.log_level}</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">EPIC IDs:</span>
                        <span class="config-value">${data.config.epic_ids ? data.config.epic_ids.join(', ') : 'None'}</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">Max Concurrent Syncs:</span>
                        <span class="config-value">${data.config.max_concurrent_syncs}</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">Retry Attempts:</span>
                        <span class="config-value">${data.config.retry_attempts}</span>
                    </div>
                `;
            }
        } catch (err) {
            configContent.innerHTML = '<p>Failed to load configuration</p>';
        }
    };

    const addLogEntry = (message, type = 'info') => {
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        const timestamp = new Date().toLocaleTimeString();
        logEntry.innerHTML = `
            <span class="log-time">[${timestamp}]</span>
            <span class="log-message log-${type}">${message}</span>
        `;
        logContent.appendChild(logEntry);
        logContent.scrollTop = logContent.scrollHeight;
    };

    // Load logs from server
    const loadServerLogs = async () => {
        try {
            const response = await fetch('/api/logs?lines=50');
            const data = await response.json();
            if (data.success && data.logs) {
                logContent.innerHTML = '';
                data.logs.forEach(logLine => {
                    if (logLine.trim()) {
                        const logEntry = document.createElement('div');
                        logEntry.className = 'log-entry';
                        logEntry.innerHTML = `<span class="log-message">${logLine}</span>`;
                        logContent.appendChild(logEntry);
                    }
                });
                logContent.scrollTop = logContent.scrollHeight;
            }
        } catch (err) {
            addLogEntry('Failed to load server logs', 'error');
        }
    };

    // Health check function
    const performHealthCheck = async () => {
        try {
            const response = await fetch('/api/health');
            const data = await response.json();
            document.getElementById('api-status').textContent = data.status || 'Unknown';
            document.getElementById('last-health-check').textContent = new Date().toLocaleTimeString();
            addLogEntry(`Health check: ${data.status}`, 'info');
            return data;
        } catch (err) {
            document.getElementById('api-status').textContent = 'Error';
            document.getElementById('last-health-check').textContent = new Date().toLocaleTimeString();
            addLogEntry('Health check failed', 'error');
            throw err;
        }
    };

    // Show API documentation
    const showApiDocs = async () => {
        try {
            const response = await fetch('/api/docs');
            const data = await response.json();
            let docsHtml = `
                <h3>${data.name} v${data.version}</h3>
                <h4>Available Endpoints:</h4>
                <ul>
            `;
            Object.entries(data.endpoints).forEach(([endpoint, description]) => {
                docsHtml += `<li><strong>${endpoint}</strong>: ${description}</li>`;
            });
            docsHtml += `
                </ul>
                <p><strong>Monitor Status:</strong> ${data.monitor_status ? 'Running' : 'Stopped'}</p>
            `;
            
            // Create a modal or show in toast (simplified approach)
            const modal = document.createElement('div');
            modal.style.cssText = `
                position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                max-width: 600px; max-height: 80vh; overflow-y: auto; z-index: 2000;
            `;
            modal.innerHTML = `
                ${docsHtml}
                <button onclick="this.parentElement.remove()" style="margin-top: 15px; padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">Close</button>
            `;
            document.body.appendChild(modal);
            
            addLogEntry('API documentation displayed', 'info');
        } catch (err) {
            showToast('Failed to load API documentation');
            addLogEntry('Failed to load API docs', 'error');
        }
    };

    // Global function for removing EPICs
    window.removeEpic = async (epicId) => {
        if (!confirm(`Are you sure you want to remove EPIC ${epicId} from monitoring?`)) {
            return;
        }
        showLoading(true);
        try {
            const response = await fetch(`/api/epics/${epicId}`, { method: 'DELETE' });
            const data = await response.json();
            showToast(data.message);
            addLogEntry(`EPIC ${epicId} removed from monitoring`, 'warning');
            updateEpics();
        } catch (err) {
            showToast('Failed to remove EPIC');
            addLogEntry(`Failed to remove EPIC ${epicId}`, 'error');
        } finally {
            showLoading(false);
        }
    };


    // Update metrics
    const updateMetrics = () => {
        // Update total checks
        metrics.totalChecks++;
        totalChecksEl.textContent = metrics.totalChecks;
        
        // Update uptime
        const uptime = Date.now() - metrics.startTime;
        const hours = Math.floor(uptime / (1000 * 60 * 60));
        const minutes = Math.floor((uptime % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((uptime % (1000 * 60)) / 1000);
        uptimeEl.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        
        // Update active EPICs count
        activeEpicsEl.textContent = metrics.activeEpics;
        
        // Update changes detected
        changesDetectedEl.textContent = metrics.changesDetected;
    };

    // Enhanced updateStatus function
    const enhancedUpdateStatus = async () => {
        await updateStatus();
        
        // Update metrics
        try {
            const response = await fetch('/api/epics');
            const data = await response.json();
            metrics.activeEpics = data.epics ? data.epics.length : 0;
        } catch (err) {
            console.error('Failed to fetch EPICs for metrics');
        }
        
        updateMetrics();
    };

    // Initial page load
    enhancedUpdateStatus();
    updateEpics();
    updateConfig();

    // Button actions
    document.getElementById('refresh-status').addEventListener('click', updateStatus);
    document.getElementById('start-monitor').addEventListener('click', async () => {
        showLoading(true);
        try {
            const response = await fetch('/api/start', { method: 'POST' });
            const data = await response.json();
            showToast(data.message);
            addLogEntry('Monitoring started', 'success');
            updateStatus();
        } catch (err) {
            showToast('Failed to start monitoring');
        } finally {
            showLoading(false);
        }
    });
    document.getElementById('stop-monitor').addEventListener('click', async () => {
        showLoading(true);
        try {
            const response = await fetch('/api/stop', { method: 'POST' });
            const data = await response.json();
            showToast(data.message);
            addLogEntry('Monitoring stopped', 'warning');
            updateStatus();
        } catch (err) {
            showToast('Failed to stop monitoring');
        } finally {
            showLoading(false);
        }
    });
    document.getElementById('force-check').addEventListener('click', async () => {
        showLoading(true);
        try {
            const response = await fetch('/api/check', { method: 'POST' });
            const data = await response.json();
            showToast('Check complete');
            addLogEntry('Force check executed', 'info');
            console.log(data.results);
        } catch (err) {
            showToast('Check failed');
        } finally {
            showLoading(false);
        }
    });
    document.getElementById('add-epic').addEventListener('click', async () => {
        const epicIdField = document.getElementById('new-epic-id');
        const epicId = epicIdField.value.trim();
        if (!epicId) {
            showToast('Please enter an EPIC ID');
            return;
        }
        showLoading(true);
        try {
            const response = await fetch(`/api/epics/${epicId}`, { method: 'POST' });
            const data = await response.json();
            showToast(data.message);
            addLogEntry(`EPIC ${epicId} added to monitoring`, 'success');
            updateEpics();
        } catch (err) {
            showToast('Failed to add EPIC');
        } finally {
            showLoading(false);
            epicIdField.value = '';
        }
    });
    document.getElementById('clear-log').addEventListener('click', () => {
        logContent.innerHTML = '<div class="log-entry"><span class="log-time">[System]</span><span class="log-message">Log cleared</span></div>';
    });
    
    document.getElementById('toast-close').addEventListener('click', () => {
        toast.style.display = 'none';
    });
    
    // Config editing functionality
    document.getElementById('edit-config').addEventListener('click', () => {
        // Show editor, populate with current values
        document.getElementById('config-content').style.display = 'none';
        document.getElementById('config-editor').style.display = 'block';
        document.getElementById('edit-config').style.display = 'none';
        document.getElementById('save-config').style.display = 'inline-block';
        document.getElementById('cancel-config').style.display = 'inline-block';
        
        // Populate current values
        document.getElementById('edit-poll-interval').value = currentConfig.poll_interval_seconds || 60;
        document.getElementById('edit-auto-sync').checked = currentConfig.auto_sync || false;
        document.getElementById('edit-epic-ids').value = currentConfig.epic_ids ? currentConfig.epic_ids.join(',') : '';
    });
    
    document.getElementById('cancel-config').addEventListener('click', () => {
        // Hide editor, show read-only view
        document.getElementById('config-content').style.display = 'block';
        document.getElementById('config-editor').style.display = 'none';
        document.getElementById('edit-config').style.display = 'inline-block';
        document.getElementById('save-config').style.display = 'none';
        document.getElementById('cancel-config').style.display = 'none';
    });
    
    document.getElementById('save-config').addEventListener('click', async () => {
        showLoading(true);
        try {
            const updatedConfig = {
                poll_interval_seconds: parseInt(document.getElementById('edit-poll-interval').value),
                auto_sync: document.getElementById('edit-auto-sync').checked,
                epic_ids: document.getElementById('edit-epic-ids').value.split(',').map(id => id.trim()).filter(id => id)
            };
            
            const response = await fetch('/api/config', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updatedConfig)
            });
            
            const data = await response.json();
            if (data.success) {
                showToast(data.message);
                addLogEntry('Configuration updated', 'success');
                updateConfig(); // Refresh the config display
                
                // Hide editor
                document.getElementById('config-content').style.display = 'block';
                document.getElementById('config-editor').style.display = 'none';
                document.getElementById('edit-config').style.display = 'inline-block';
                document.getElementById('save-config').style.display = 'none';
                document.getElementById('cancel-config').style.display = 'none';
            } else {
                showToast('Failed to update configuration');
                addLogEntry('Configuration update failed', 'error');
            }
        } catch (err) {
            showToast('Failed to update configuration');
            addLogEntry('Configuration update error', 'error');
        } finally {
            showLoading(false);
        }
    });
    
    // Log functionality
    document.getElementById('refresh-logs').addEventListener('click', async () => {
        showLoading(true);
        try {
            await loadServerLogs();
            addLogEntry('Server logs refreshed', 'info');
        } catch (err) {
            showToast('Failed to refresh logs');
        } finally {
            showLoading(false);
        }
    });
    
    // System functionality
    document.getElementById('health-check').addEventListener('click', async () => {
        showLoading(true);
        try {
            await performHealthCheck();
            showToast('Health check completed');
        } catch (err) {
            showToast('Health check failed');
        } finally {
            showLoading(false);
        }
    });
    
    document.getElementById('api-docs').addEventListener('click', showApiDocs);
    
    // Initial health check
    setTimeout(performHealthCheck, 1000);
    
    // Load server logs on startup
    setTimeout(loadServerLogs, 1500);
    
    // Auto-refresh status every 30 seconds
    setInterval(() => {
        updateStatus();
    }, 30000);
    
    // Auto-refresh health check every 60 seconds
    setInterval(performHealthCheck, 60000);
});
