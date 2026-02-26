// UniFi Maintenance Dashboard - Main Application

class UniFiDashboard {
    constructor() {
        this.devices = [];
        this.filteredDevices = [];
        this.currentFilter = 'all';
        this.searchQuery = '';
        this.currentSite = null;
        this.sites = [];
        this.selectedDevices = new Set();
        this.init();
    }

    async init() {
        console.log('Dashboard initializing...');
        this.setupEventListeners();
        console.log('Event listeners set up');
        await this.loadSites();
        console.log('Sites loaded');
        await this.loadDevices();
        console.log('Devices loaded');
        this.renderDevices();
        console.log('Dashboard initialized');
    }

    setupEventListeners() {
        // Site selector
        const siteSelector = document.getElementById('siteSelector');
        if (siteSelector) {
            siteSelector.addEventListener('change', (e) => {
                this.currentSite = e.target.value || null;
                // Save selected site to localStorage
                if (this.currentSite) {
                    localStorage.setItem('selectedSite', this.currentSite);
                }
                this.loadDevices();
            });
        }

        // Filter buttons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.currentFilter = e.target.dataset.filter;
                this.filterDevices();
            });
        });

        // Search
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchQuery = e.target.value.toLowerCase();
                this.filterDevices();
            });
        }

        // Refresh button
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadDevices());
        }

        // Modal close
        document.querySelectorAll('.close-btn, .modal').forEach(el => {
            el.addEventListener('click', (e) => {
                if (e.target === el) {
                    this.closeAllModals();
                }
            });
        });

        // Bulk reboot confirm
        const confirmBulkReboot = document.getElementById('confirmBulkReboot');
        if (confirmBulkReboot) {
            confirmBulkReboot.addEventListener('click', () => this.executeBulkReboot());
        }
    }

    async loadSites() {
        try {
            const response = await fetch('/api/sites');
            if (!response.ok) throw new Error('Failed to fetch sites');
            
            this.sites = await response.json();
            
            // Sort sites alphabetically by description
            this.sites.sort((a, b) => {
                const nameA = (a.desc || a.name || '').toLowerCase();
                const nameB = (b.desc || b.name || '').toLowerCase();
                return nameA.localeCompare(nameB);
            });
            
            console.log('Loaded sites:', this.sites.length);
            
            const siteSelector = document.getElementById('siteSelector');
            if (siteSelector && this.sites.length > 0) {
                // Simple approach without escapeHtml to avoid issues
                siteSelector.innerHTML = this.sites.map(site => {
                    const name = String(site.name || '').replace(/"/g, '&quot;');
                    const desc = String(site.desc || site.name || '').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                    return `<option value="${name}">${desc}</option>`;
                }).join('');
                
                // Restore last selected site from localStorage, or use first site
                const lastSite = localStorage.getItem('selectedSite');
                if (lastSite && this.sites.find(s => s.name === lastSite)) {
                    this.currentSite = lastSite;
                    siteSelector.value = lastSite;
                } else {
                    this.currentSite = this.sites[0].name;
                }
                console.log('Site selector updated, current site:', this.currentSite);
            }
        } catch (error) {
            console.error('Error loading sites:', error);
            this.showAlert('Failed to load sites: ' + error.message, 'error');
        }
    }

    async loadDevices() {
        const loading = document.getElementById('loading');
        const devicesContainer = document.getElementById('devicesContainer');

        // Clear selection when loading new devices
        this.selectedDevices.clear();
        this.updateBulkToolbar();

        if (loading) loading.style.display = 'block';
        if (devicesContainer) devicesContainer.style.display = 'none';

        try {
            const url = this.currentSite ? `/api/devices?site=${encodeURIComponent(this.currentSite)}` : '/api/devices';
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to fetch devices');
            
            this.devices = await response.json();
            this.filterDevices();
            this.updateStats();
            
            if (loading) loading.style.display = 'none';
            if (devicesContainer) devicesContainer.style.display = 'block';
        } catch (error) {
            console.error('Error loading devices:', error);
            this.showAlert('Failed to load devices: ' + error.message, 'error');
            if (loading) loading.style.display = 'none';
        }
    }

    filterDevices() {
        this.filteredDevices = this.devices.filter(device => {
            // Filter by status
            if (this.currentFilter === 'online' && !device.online) return false;
            if (this.currentFilter === 'offline' && device.online) return false;
            if (this.currentFilter === 'switches' && !device.is_switch) return false;
            if (this.currentFilter === 'aps' && !device.is_ap) return false;

            // Filter by search
            if (this.searchQuery) {
                const searchable = `${device.name} ${device.model} ${device.ip} ${device.mac}`.toLowerCase();
                if (!searchable.includes(this.searchQuery)) return false;
            }

            return true;
        });

        this.renderDevices();
    }

    updateStats() {
        const onlineCount = this.devices.filter(d => d.online).length;
        const offlineCount = this.devices.filter(d => !d.online).length;
        const switchCount = this.devices.filter(d => d.is_switch).length;

        document.getElementById('totalDevices').textContent = this.devices.length;
        document.getElementById('onlineDevices').textContent = onlineCount;
        document.getElementById('offlineDevices').textContent = offlineCount;
        document.getElementById('switchCount').textContent = switchCount;
    }

    renderDevices() {
        const container = document.getElementById('devicesGrid');
        if (!container) return;

        if (this.filteredDevices.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📡</div>
                    <h3>No devices found</h3>
                    <p>Try adjusting your filters or search query</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.filteredDevices.map(device => this.renderDeviceCard(device)).join('');
        
        // Attach event listeners to action buttons
        this.attachDeviceActions();
    }

    renderDeviceCard(device) {
        const statusClass = device.online ? 'status-online' : 'status-offline';
        const statusText = device.online ? 'Online' : 'Offline';
        const deviceIcon = device.is_switch ? '🔀' : device.is_ap ? '📡' : '❓';
        const deviceType = device.is_switch ? 'Switch' : device.is_ap ? 'Access Point' : 'Device';
        const isSelected = this.selectedDevices.has(device.id);

        const uptime = device.online ? this.formatUptime(device.uptime) : 'N/A';

        return `
            <div class="device-card selectable${isSelected ? ' selected' : ''}" data-device-id="${device.id}">
                <label class="device-select-area" title="Select for bulk action">
                    <input type="checkbox" class="device-select-cb" data-device-id="${device.id}" ${isSelected ? 'checked' : ''}>
                </label>
                <div class="device-header">
                    <div class="device-info">
                        <h3>${this.escapeHtml(device.name)}</h3>
                        <div class="device-model">${this.escapeHtml(device.model)}</div>
                    </div>
                    <span class="status-badge ${statusClass}">${statusText}</span>
                </div>

                <div class="device-type">
                    <span>${deviceIcon}</span>
                    <span>${deviceType}</span>
                    ${device.is_switch ? `<span>(${device.port_count} ports)</span>` : ''}
                </div>

                <div class="device-details">
                    <div class="detail-row">
                        <span class="detail-label">IP Address</span>
                        <span class="detail-value">${device.ip}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">MAC Address</span>
                        <span class="detail-value">${device.mac}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Firmware</span>
                        <span class="detail-value">${device.version}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Uptime</span>
                        <span class="detail-value">${uptime}</span>
                    </div>
                </div>

                <div class="device-actions">
                    <button class="btn btn-primary btn-sm reboot-btn" data-device-id="${device.id}" data-device-name="${this.escapeHtml(device.name)}">
                        🔄 Reboot
                    </button>
                    ${device.is_switch ? `
                        <button class="btn btn-sm poe-btn" data-device-id="${device.id}" data-device-name="${this.escapeHtml(device.name)}">
                            ⚡ Port Control
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }

    attachDeviceActions() {
        // Reboot buttons
        document.querySelectorAll('.reboot-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const deviceId = btn.dataset.deviceId;
                const deviceName = btn.dataset.deviceName;
                this.showRebootModal(deviceId, deviceName);
            });
        });

        // PoE buttons
        document.querySelectorAll('.poe-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const deviceId = btn.dataset.deviceId;
                const deviceName = btn.dataset.deviceName;
                await this.showPoeModal(deviceId, deviceName);
            });
        });

        // Selection checkboxes
        document.querySelectorAll('.device-select-cb').forEach(cb => {
            cb.addEventListener('change', (e) => {
                e.stopPropagation();
                this.toggleDeviceSelection(cb.dataset.deviceId);
            });
        });

        // Card click toggles selection (ignore clicks on buttons/checkboxes)
        document.querySelectorAll('.device-card.selectable').forEach(card => {
            card.addEventListener('click', (e) => {
                if (e.target.closest('button') || e.target.closest('.device-select-area')) return;
                this.toggleDeviceSelection(card.dataset.deviceId);
            });
        });
    }

    toggleDeviceSelection(deviceId) {
        if (this.selectedDevices.has(deviceId)) {
            this.selectedDevices.delete(deviceId);
        } else {
            this.selectedDevices.add(deviceId);
        }
        this.updateBulkToolbar();

        // Update this card's visual state without re-rendering
        const card = document.querySelector(`.device-card[data-device-id="${deviceId}"]`);
        if (card) {
            card.classList.toggle('selected', this.selectedDevices.has(deviceId));
            const cb = card.querySelector('.device-select-cb');
            if (cb) cb.checked = this.selectedDevices.has(deviceId);
        }
    }

    updateBulkToolbar() {
        const count = this.selectedDevices.size;
        const toolbar = document.getElementById('bulkToolbar');
        const countBadge = document.getElementById('bulkCount');

        if (!toolbar) return;

        if (count > 0) {
            toolbar.classList.add('visible');
            countBadge.textContent = `${count} device${count !== 1 ? 's' : ''} selected`;
        } else {
            toolbar.classList.remove('visible');
        }
    }

    selectAllByType(type) {
        this.filteredDevices.forEach(device => {
            let match = false;
            if (type === 'ap') match = device.is_ap;
            else if (type === 'switch') match = device.is_switch;
            else if (type === 'online') match = device.online;
            if (match) this.selectedDevices.add(device.id);
        });
        // Re-render to sync checkbox + selected states
        this.renderDevices();
        this.updateBulkToolbar();
    }

    clearSelection() {
        this.selectedDevices.clear();
        this.updateBulkToolbar();
        document.querySelectorAll('.device-card.selected').forEach(c => c.classList.remove('selected'));
        document.querySelectorAll('.device-select-cb').forEach(cb => { cb.checked = false; });
    }

    showBulkRebootModal() {
        const count = this.selectedDevices.size;
        if (count === 0) return;

        const selectedObjs = this.devices.filter(d => this.selectedDevices.has(d.id));
        const list = document.getElementById('bulkRebootDeviceList');
        list.innerHTML = selectedObjs.map(d =>
            `<li>${this.escapeHtml(d.name || d.id)} <span style="color:var(--text-secondary);font-size:13px">(${this.escapeHtml(d.model)})</span></li>`
        ).join('');

        document.getElementById('bulkRebootCount').textContent = count;
        document.getElementById('bulkRebootModal').classList.add('active');
    }

    async executeBulkReboot() {
        const deviceIds = Array.from(this.selectedDevices);
        if (deviceIds.length === 0) return;

        const btn = document.getElementById('confirmBulkReboot');
        btn.disabled = true;
        btn.textContent = 'Sending reboot commands...';

        try {
            const response = await fetch('/api/devices/bulk-reboot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    device_ids: deviceIds,
                    site: this.currentSite,
                    wait_for_online: false
                })
            });

            const data = await response.json();
            this.closeAllModals();
            this.clearSelection();

            const successCount = data.rebooted?.length ?? 0;
            const failCount = data.failed?.length ?? 0;

            if (successCount > 0) {
                const msg = failCount > 0
                    ? `Reboot sent to ${successCount} device(s). ${failCount} failed.`
                    : `Reboot command sent to ${successCount} device(s).`;
                this.showAlert(`✅ ${msg}`, failCount > 0 ? 'warning' : 'success');
            } else {
                this.showAlert('❌ Bulk reboot failed — no devices rebooted.', 'error');
            }

            setTimeout(() => this.loadDevices(), 3000);
        } catch (error) {
            this.showAlert(`❌ Bulk reboot request failed: ${error.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = '🔄 Reboot All Selected';
        }
    }

    showRebootModal(deviceId, deviceName) {
        const modal = document.getElementById('rebootModal');
        document.getElementById('rebootDeviceName').textContent = deviceName;
        
        const confirmBtn = document.getElementById('confirmReboot');
        confirmBtn.onclick = () => this.rebootDevice(deviceId, deviceName);
        
        modal.classList.add('active');
    }

    async showPoeModal(deviceId, deviceName) {
        const modal = document.getElementById('poeModal');
        document.getElementById('poeDeviceName').textContent = deviceName;
        
        // Load ports
        const portsContainer = document.getElementById('portsList');
        portsContainer.innerHTML = '<div class="loading"><div class="spinner"></div>Loading ports...</div>';
        
        modal.classList.add('active');

        try {
            const url = this.currentSite ? `/api/devices/${deviceId}/ports?site=${encodeURIComponent(this.currentSite)}` : `/api/devices/${deviceId}/ports`;
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to load ports');
            
            const ports = await response.json();
            this.renderPorts(deviceId, ports);
        } catch (error) {
            portsContainer.innerHTML = `<div class="alert alert-error">Failed to load ports: ${error.message}</div>`;
        }
    }

    renderPorts(deviceId, ports) {
        const container = document.getElementById('portsList');
        
        if (!ports || ports.length === 0) {
            container.innerHTML = '<div class="empty-state">No ports available</div>';
            return;
        }

        container.innerHTML = ports.map(port => {
            const poeEnabled = port.poe_enable || false;
            const portUp = port.up || false;
            
            return `
                <div class="port-item">
                    <div class="port-info">
                        <div class="port-name">Port ${port.port_idx}${port.name ? ': ' + this.escapeHtml(port.name) : ''}</div>
                        <div class="port-status">
                            ${portUp ? '🟢' : '🔴'} ${portUp ? 'Up' : 'Down'} | 
                            PoE: ${poeEnabled ? '⚡' : '❌'} ${poeEnabled ? port.poe_power ? `${port.poe_power}W` : 'On' : 'Off'}
                        </div>
                    </div>
                    <div class="port-actions">
                        ${poeEnabled ? `
                            <button class="btn btn-sm btn-warning power-cycle-btn" 
                                    data-device-id="${deviceId}" 
                                    data-port-idx="${port.port_idx}">
                                ⚡ PoE Cycle
                            </button>
                        ` : ''}
                        <button class="btn btn-sm btn-danger port-cycle-btn" 
                                data-device-id="${deviceId}" 
                                data-port-idx="${port.port_idx}">
                            🔄 Port Cycle
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        // Attach power cycle handlers
        document.querySelectorAll('.power-cycle-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const deviceId = e.target.dataset.deviceId;
                const portIdx = e.target.dataset.portIdx;
                this.powerCyclePort(deviceId, portIdx);
            });
        });

        // Attach port cycle handlers
        document.querySelectorAll('.port-cycle-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const deviceId = e.target.dataset.deviceId;
                const portIdx = e.target.dataset.portIdx;
                this.portCyclePort(deviceId, portIdx);
            });
        });
    }

    async rebootDevice(deviceId, deviceName) {
        this.closeAllModals();
        this.showAlert(`Rebooting ${deviceName}...`, 'info');

        try {
            const response = await fetch('/api/devices/reboot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    device_id: deviceId, 
                    wait_for_online: false,
                    site: this.currentSite
                })
            });

            if (!response.ok) throw new Error('Reboot command failed');
            
            const result = await response.json();
            this.showAlert(`✅ Reboot command sent to ${deviceName}`, 'success');
            
            // Refresh devices after a delay
            setTimeout(() => this.loadDevices(), 3000);
        } catch (error) {
            this.showAlert(`❌ Failed to reboot ${deviceName}: ${error.message}`, 'error');
        }
    }

    async powerCyclePort(deviceId, portIdx) {
        this.closeAllModals();
        this.showAlert(`PoE cycling port ${portIdx}...`, 'info');

        try {
            const response = await fetch('/api/devices/poe/power-cycle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    device_id: deviceId, 
                    port_idx: parseInt(portIdx),
                    site: this.currentSite
                })
            });

            if (!response.ok) throw new Error('PoE cycle failed');
            
            this.showAlert(`✅ Port ${portIdx} PoE cycle initiated`, 'success');
        } catch (error) {
            this.showAlert(`❌ Failed to PoE cycle port: ${error.message}`, 'error');
        }
    }

    async portCyclePort(deviceId, portIdx) {
        if (!confirm(`Port cycle port ${portIdx}?\n\nThis will disable and re-enable the port link. It takes 4-8 minutes to complete. The port will be down for ~30 seconds.`)) {
            return;
        }
        this.closeAllModals();

        const timer = this.showCycleTimer(portIdx);

        try {
            const response = await fetch('/api/devices/port/cycle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    device_id: deviceId, 
                    port_idx: parseInt(portIdx),
                    off_duration: 30,
                    poe_only: false,
                    site: this.currentSite
                })
            });

            timer.stop(true);

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || 'Port cycle failed');
            }
            
            this.showAlert(`✅ Port ${portIdx} cycle completed`, 'success');
        } catch (error) {
            timer.stop(false);
            this.showAlert(`❌ Failed to cycle port ${portIdx}: ${error.message}`, 'error');
        }
    }

    showCycleTimer(portIdx) {
        const TOTAL_SECONDS = 5 * 60;

        // Remove any existing timer
        const existing = document.getElementById('cycleTimer');
        if (existing) existing.remove();

        const timerEl = document.createElement('div');
        timerEl.id = 'cycleTimer';
        timerEl.innerHTML = `
            <div class="cycle-timer-content">
                <div class="cycle-timer-header">
                    <span class="cycle-timer-icon">🔄</span>
                    <span class="cycle-timer-title">Port ${portIdx} Cycling</span>
                    <span class="cycle-timer-elapsed" id="cycleTimerElapsed">0:00</span>
                    <span class="cycle-timer-sep">/</span>
                    <span class="cycle-timer-total">5:00</span>
                </div>
                <div class="cycle-timer-bar-bg">
                    <div class="cycle-timer-bar-fill" id="cycleTimerFill"></div>
                </div>
                <div class="cycle-timer-status" id="cycleTimerStatus">Disabling port — waiting for switch to apply...</div>
            </div>
        `;
        document.body.prepend(timerEl);

        const startTime = Date.now();
        const elapsedEl = document.getElementById('cycleTimerElapsed');
        const fillEl = document.getElementById('cycleTimerFill');
        const statusEl = document.getElementById('cycleTimerStatus');

        const interval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            elapsedEl.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;

            const pct = Math.min((elapsed / TOTAL_SECONDS) * 100, 100);
            fillEl.style.width = `${pct}%`;

            // Update status text based on elapsed time
            if (elapsed < 10) {
                statusEl.textContent = 'Disabling port — waiting for switch to apply...';
            } else if (elapsed < 120) {
                statusEl.textContent = 'Waiting for port to go down (up to ~2 min)...';
            } else if (elapsed < 150) {
                statusEl.textContent = 'Port should be down — holding disabled for 30s...';
            } else if (elapsed < 160) {
                statusEl.textContent = 'Re-enabling port...';
            } else {
                statusEl.textContent = 'Waiting for port to come back up...';
            }
        }, 1000);

        return {
            stop: (success) => {
                clearInterval(interval);
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                const mins = Math.floor(elapsed / 60);
                const secs = elapsed % 60;
                elapsedEl.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
                fillEl.style.width = '100%';

                if (success) {
                    timerEl.classList.add('cycle-timer-success');
                    statusEl.textContent = `✅ Completed in ${mins}m ${secs}s`;
                    fillEl.style.background = 'var(--success, #28a745)';
                } else {
                    timerEl.classList.add('cycle-timer-error');
                    statusEl.textContent = `❌ Failed after ${mins}m ${secs}s`;
                    fillEl.style.background = 'var(--danger, #dc3545)';
                }

                // Auto-remove after 10 seconds
                setTimeout(() => {
                    timerEl.style.transition = 'opacity 0.5s';
                    timerEl.style.opacity = '0';
                    setTimeout(() => timerEl.remove(), 500);
                }, 10000);
            }
        };
    }

    closeAllModals() {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.classList.remove('active');
        });
    }

    showAlert(message, type = 'info') {
        const alertsContainer = document.getElementById('alerts');
        if (!alertsContainer) return;

        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.textContent = message;
        
        alertsContainer.appendChild(alert);

        setTimeout(() => {
            alert.remove();
        }, 5000);
    }

    formatUptime(seconds) {
        if (!seconds) return 'N/A';
        
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);

        if (days > 0) return `${days}d ${hours}h`;
        if (hours > 0) return `${hours}h ${minutes}m`;
        return `${minutes}m`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new UniFiDashboard();
});
