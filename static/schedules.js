// Schedules Management

class SchedulesManager {
    constructor() {
        this.schedules = [];
        this.poeSchedules = [];
        this.jobs = [];
        this.templates = [];
        this.jobsRefreshIntervalMs = 15000;
        this.jobsRefreshTimer = null;
        this.sites = [];
        this.devices = [];
        this.currentSite = null;
        this.schedulerTimezone = document.body.dataset.schedulerTimezone || 'UTC';
        this.editingScheduleId = null;
        this.editingDeviceIds = [];
        this.editingPoeScheduleId = null;
        this.editingTemplateId = null;
        this._templatePickerForType = null;
        this.init();
    }

    async init() {
        console.log('Initializing schedules manager...');
        this.setupEventListeners();
        await this.loadSites();
        await this.loadSchedules();
        await this.loadPoeSchedules();
        await this.loadJobs();
        await this.loadTemplates();
        this.startJobsAutoRefresh();
    }

    setupEventListeners() {
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

                e.target.classList.add('active');
                const tabId = e.target.dataset.tab;
                document.getElementById(tabId).classList.add('active');

                if (tabId === 'job-history') {
                    this.loadJobs();
                } else if (tabId === 'templates') {
                    this.loadTemplates();
                }
            });
        });

        // New schedule button
        document.getElementById('newScheduleBtn').addEventListener('click', () => {
            this.showScheduleModal();
        });

        // New port schedule button
        document.getElementById('newPortScheduleBtn').addEventListener('click', () => {
            this.showPortScheduleModal();
        });

        // Schedule form
        document.getElementById('scheduleForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.createSchedule();
        });

        // Port schedule form
        document.getElementById('portScheduleForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.createPortSchedule();
        });

        // Frequency change
        document.getElementById('frequencySelect').addEventListener('change', (e) => {
            this.updateFrequencyFields(e.target.value);
        });

        // Rolling mode toggle
        document.getElementById('rollingModeCheck').addEventListener('change', (e) => {
            document.getElementById('rollingOptions').style.display = e.target.checked ? 'block' : 'none';
        });

        // Site selector in modal
        document.getElementById('scheduleSiteSelector').addEventListener('change', (e) => {
            this.currentSite = e.target.value;
            if (this.currentSite) {
                localStorage.setItem('selectedSite', this.currentSite);
            }
            this.loadDevicesForSchedule();
        });

        // Port schedule site selector
        document.getElementById('portScheduleSiteSelector').addEventListener('change', (e) => {
            this.loadDevicesForPortSchedule(e.target.value);
        });

        // Port schedule frequency
        document.getElementById('portFrequencySelect').addEventListener('change', (e) => {
            this.updatePortFrequencyFields(e.target.value);
        });

        // Modal close
        document.querySelectorAll('.close-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.closeModal();
            });
        });

        // Templates
        const newTemplateBtn = document.getElementById('newTemplateBtn');
        if (newTemplateBtn) {
            newTemplateBtn.addEventListener('click', () => this.showTemplateModal());
        }

        const templateForm = document.getElementById('templateForm');
        if (templateForm) {
            templateForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveTemplate();
            });
        }

        const templateTypeSelect = document.getElementById('templateTypeSelect');
        if (templateTypeSelect) {
            templateTypeSelect.addEventListener('change', (e) => {
                this.updateTemplateTypeFields(e.target.value);
            });
        }

        const templateFreqSelect = document.getElementById('templateFrequencySelect');
        if (templateFreqSelect) {
            templateFreqSelect.addEventListener('change', (e) => {
                this.updateTemplateFrequencyFields(e.target.value);
            });
        }

        const tmplRollingMode = document.getElementById('tmplRollingMode');
        if (tmplRollingMode) {
            tmplRollingMode.addEventListener('change', (e) => {
                document.getElementById('tmplRollingOptions').style.display = e.target.checked ? 'block' : 'none';
            });
        }

        // Load Template buttons in create modals
        const loadTmplForSchedule = document.getElementById('loadTemplateForSchedule');
        if (loadTmplForSchedule) {
            loadTmplForSchedule.addEventListener('click', () => this.showTemplatePicker('device_reboot'));
        }

        const loadTmplForPort = document.getElementById('loadTemplateForPort');
        if (loadTmplForPort) {
            loadTmplForPort.addEventListener('click', () => this.showTemplatePicker('port_cycle'));
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
            
            const selector = document.getElementById('scheduleSiteSelector');
            if (selector && this.sites.length > 0) {
                selector.innerHTML = '<option value="">Select site...</option>' + 
                    this.sites.map(site => 
                        `<option value="${site.name}">${site.desc || site.name}</option>`
                    ).join('');
                
                // Pre-select last used site from localStorage
                const lastSite = localStorage.getItem('selectedSite');
                if (lastSite && this.sites.find(s => s.name === lastSite)) {
                    selector.value = lastSite;
                    this.currentSite = lastSite;
                    this.loadDevicesForSchedule();
                }
            }
        } catch (error) {
            console.error('Error loading sites:', error);
            this.showAlert('Failed to load sites', 'error');
        }
    }

    async loadDevicesForSchedule() {
        const container = document.getElementById('deviceSelector');
        if (!this.currentSite) {
            container.innerHTML = '<div class="empty-state">Please select a site first</div>';
            return;
        }

        container.innerHTML = '<div class="loading">Loading devices...</div>';

        try {
            const response = await fetch(`/api/devices?site=${encodeURIComponent(this.currentSite)}`);
            if (!response.ok) throw new Error('Failed to fetch devices');
            
            this.devices = await response.json();
            
            // Filter to only switches and sort alphabetically by display name.
            const switches = this.devices
                .filter(d => d.is_switch)
                .sort((a, b) => (a.name || '').localeCompare((b.name || ''), undefined, { sensitivity: 'base' }));
            
            if (switches.length === 0) {
                container.innerHTML = '<div class="empty-state">No switches found in this site</div>';
                return;
            }

            container.innerHTML = switches.map(device => {
                const isChecked = this.editingDeviceIds.includes(device.id) ? 'checked' : '';
                return `
                    <div class="device-checkbox">
                        <input type="checkbox" id="device_${device.id}" value="${device.id}" ${isChecked}>
                        <label for="device_${device.id}">${device.name} (${device.model})</label>
                    </div>
                `;
            }).join('');
        } catch (error) {
            console.error('Error loading devices:', error);
            container.innerHTML = '<div class="alert alert-error">Failed to load devices</div>';
        }
    }

    updateFrequencyFields(frequency) {
        const dayOfWeekGroup = document.getElementById('dayOfWeekGroup');
        const dayOfMonthGroup = document.getElementById('dayOfMonthGroup');
        
        dayOfWeekGroup.style.display = frequency === 'weekly' ? 'block' : 'none';
        dayOfMonthGroup.style.display = frequency === 'monthly' ? 'block' : 'none';
    }

    async loadSchedules() {
        try {
            const response = await fetch('/api/schedules');
            if (!response.ok) throw new Error('Failed to fetch schedules');
            
            this.schedules = await response.json();
            this.renderSchedules();
        } catch (error) {
            console.error('Error loading schedules:', error);
            document.getElementById('schedulesList').innerHTML = 
                '<div class="alert alert-error">Failed to load schedules</div>';
        }
    }

    renderSchedules() {
        const container = document.getElementById('schedulesList');
        
        if (this.schedules.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📅</div>
                    <p>No schedules created yet</p>
                    <button class="btn btn-primary" onclick="schedulesManager.showScheduleModal()">Create First Schedule</button>
                </div>
            `;
            return;
        }

        container.innerHTML = this.schedules.map(schedule => `
            <div class="schedule-card">
                <div class="schedule-info">
                    <div class="schedule-name">${this.escapeHtml(schedule.name)}</div>
                    ${schedule.description ? `<div class="schedule-description">${this.escapeHtml(schedule.description)}</div>` : ''}
                    <div class="schedule-details">
                        <div class="schedule-detail">
                            <span>📅</span>
                            <span>${this.formatFrequency(schedule)}</span>
                        </div>
                        <div class="schedule-detail">
                            <span>🔄</span>
                            <span>${this.formatScheduleTargets(schedule)}</span>
                        </div>
                        ${schedule.site_name ? `<div class="schedule-detail"><span>🌐</span><span>${this.escapeHtml(schedule.site_name)}</span></div>` : ''}
                        ${schedule.rolling_mode ? '<div class="schedule-detail"><span>⏱️</span><span>Rolling Mode</span></div>' : ''}
                        ${schedule.last_run_at ? `<div class="schedule-detail"><span>🕐</span><span>Last run: ${this.formatDateTime(schedule.last_run_at)}</span></div>` : ''}
                    </div>
                </div>
                <div class="schedule-actions">
                    <label class="toggle-switch">
                        <input type="checkbox" ${schedule.enabled ? 'checked' : ''} 
                               onchange="schedulesManager.toggleSchedule(${schedule.id})">
                        <span class="toggle-slider"></span>
                    </label>
                    <button class="btn btn-sm" onclick="schedulesManager.editSchedule(${schedule.id})" title="Edit">✏️</button>
                    <button class="btn btn-sm" onclick="schedulesManager.deleteSchedule(${schedule.id})" title="Delete">🗑️</button>
                </div>
            </div>
        `).join('');
    }

    async loadPoeSchedules() {
        try {
            const response = await fetch('/api/poe-schedules');
            if (!response.ok) throw new Error('Failed to fetch PoE schedules');
            
            this.poeSchedules = await response.json();
            this.renderPoeSchedules();
        } catch (error) {
            console.error('Error loading PoE schedules:', error);
            document.getElementById('poeSchedulesList').innerHTML = 
                '<div class="alert alert-error">Failed to load port schedules</div>';
        }
    }

    renderPoeSchedules() {
        const container = document.getElementById('poeSchedulesList');
        
        if (this.poeSchedules.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">⚡</div>
                    <p>No port cycle schedules created yet</p>
                </div>
            `;
            return;
        }

        // Group schedules by site_name
        const groups = {};
        for (const schedule of this.poeSchedules) {
            const key = schedule.site_name || 'Ungrouped';
            if (!groups[key]) groups[key] = [];
            groups[key].push(schedule);
        }

        // Resolve site display name from cached sites list
        const siteDisplayName = (siteKey) => {
            if (siteKey === 'Ungrouped') return 'Ungrouped';
            const site = this.sites.find(s => s.name === siteKey);
            return site ? (site.desc || site.name) : siteKey;
        };

        container.innerHTML = Object.entries(groups).map(([siteKey, schedules]) => {
            const enabledCount = schedules.filter(s => s.enabled).length;
            const totalCount = schedules.length;
            const allEnabled = enabledCount === totalCount;
            const freq = this.formatFrequency(schedules[0]);

            // Sort schedules by time_of_day then name
            schedules.sort((a, b) => (a.time_of_day || '').localeCompare(b.time_of_day || '') || a.name.localeCompare(b.name));

            return `
                <div class="schedule-card schedule-group">
                    <div class="schedule-group-header" onclick="schedulesManager.toggleGroup(this)">
                        <div class="schedule-group-title">
                            <span class="schedule-group-arrow">▶</span>
                            <span class="schedule-group-icon">🌐</span>
                            <span class="schedule-group-name">${this.escapeHtml(siteDisplayName(siteKey))}</span>
                            <span class="schedule-group-badge">${totalCount} port${totalCount !== 1 ? 's' : ''}</span>
                            <span class="schedule-group-badge ${allEnabled ? 'badge-ok' : 'badge-warn'}">${enabledCount}/${totalCount} active</span>
                        </div>
                        <div class="schedule-group-actions" onclick="event.stopPropagation()">
                            <button class="btn btn-sm btn-run-all" onclick="schedulesManager.runAllForSite('${siteKey}')" title="Run all ${enabledCount} enabled schedules now">
                                🚀 Run All Now
                            </button>
                        </div>
                        <div class="schedule-group-summary">${freq}</div>
                    </div>
                    <div class="schedule-group-body" style="display:none;">
                        <table class="port-schedule-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Port</th>
                                    <th>Time</th>
                                    <th>Type</th>
                                    <th>Enabled</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                ${schedules.map(s => `
                                    <tr class="${s.enabled ? '' : 'row-disabled'}">
                                        <td>${this.escapeHtml(s.name)}</td>
                                        <td>${s.port_idx}</td>
                                        <td>${s.time_of_day || '-'}</td>
                                        <td>${s.poe_only ? '⚡ PoE' : '🔗 Full'}</td>
                                        <td>
                                            <label class="toggle-switch toggle-sm">
                                                <input type="checkbox" ${s.enabled ? 'checked' : ''} 
                                                       onchange="schedulesManager.togglePoeSchedule(${s.id})">
                                                <span class="toggle-slider"></span>
                                            </label>
                                        </td>
                                        <td>
                                            <button class="btn btn-xs" onclick="schedulesManager.editPoeSchedule(${s.id})" title="Edit">✏️</button>
                                            <button class="btn btn-xs" onclick="schedulesManager.deletePoeSchedule(${s.id})" title="Delete">🗑️</button>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }).join('');
    }

    async runAllForSite(siteKey) {
        // Find the site display name
        const site = this.sites.find(s => s.name === siteKey);
        const siteName = site ? (site.desc || site.name) : siteKey;
        const enabledCount = this.poeSchedules.filter(s => s.site_name === siteKey && s.enabled).length;

        if (!confirm(`Run all ${enabledCount} enabled port cycles for "${siteName}" right now?\n\nAll ports will be cycled in parallel. This will take 4-8 minutes.`)) {
            return;
        }

        const btn = document.querySelector(`button[onclick*="runAllForSite('${siteKey}')"]`);
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '⏳ Running...';
        }

        try {
            const response = await fetch(`/api/poe-schedules/run-site/${encodeURIComponent(siteKey)}`, {
                method: 'POST'
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || 'Failed to start bulk run');
            }

            const result = await response.json();
            this.showAlert(`✅ ${result.message}\n\nCheck Job History for progress.`, 'success');

            if (btn) {
                btn.innerHTML = '✅ Started';
                setTimeout(() => {
                    btn.disabled = false;
                    btn.innerHTML = '🚀 Run All Now';
                }, 10000);
            }

            // Switch to job history tab after a moment
            setTimeout(() => this.loadJobs(), 2000);

        } catch (error) {
            this.showAlert(`❌ ${error.message}`, 'error');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '🚀 Run All Now';
            }
        }
    }

    toggleGroup(headerEl) {
        const body = headerEl.nextElementSibling;
        const arrow = headerEl.querySelector('.schedule-group-arrow');
        if (body.style.display === 'none') {
            body.style.display = 'block';
            arrow.textContent = '▼';
        } else {
            body.style.display = 'none';
            arrow.textContent = '▶';
        }
    }

    async loadJobs() {
        try {
            const response = await fetch('/api/jobs?limit=50');
            if (!response.ok) throw new Error('Failed to fetch jobs');
            
            this.jobs = await response.json();
            this.renderJobs();
        } catch (error) {
            console.error('Error loading jobs:', error);
            document.getElementById('jobsList').innerHTML = 
                '<div class="alert alert-error">Failed to load job history</div>';
        }
    }

    renderJobs() {
        const container = document.getElementById('jobsList');
        
        if (this.jobs.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📋</div>
                    <p>No jobs have been executed yet</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.jobs.map(job => {
            const typeLabel = this.formatJobType(job);
            const durationLabel = job.duration_seconds != null ? this.formatDuration(job.duration_seconds) : '';
            const sourceLabel = job.job_metadata && job.job_metadata.source === 'manual' ? '👤 Manual' : '🤖 Scheduled';
            const siteName = job.job_metadata && job.job_metadata.site_name ? job.job_metadata.site_name : '';
            return `
                <div class="job-item">
                    <div class="job-info">
                        <div class="job-device">${job.device_name || job.device_id}</div>
                        <div class="job-meta">
                            ${typeLabel} • ${sourceLabel}${siteName ? ` • 🌐 ${this.escapeHtml(siteName)}` : ''} • ${this.formatDateTime(job.started_at)}
                            ${durationLabel ? ` • ${durationLabel}` : ''}
                        </div>
                        ${job.error_message ? `<div class="job-error">${this.escapeHtml(job.error_message)}</div>` : ''}
                    </div>
                    <span class="job-status ${job.status}">${job.status}</span>
                </div>
            `;
        }).join('');
    }

    startJobsAutoRefresh() {
        if (this.jobsRefreshTimer) {
            clearInterval(this.jobsRefreshTimer);
        }

        this.jobsRefreshTimer = setInterval(() => {
            const jobTab = document.getElementById('job-history');
            if (jobTab && jobTab.classList.contains('active')) {
                this.loadJobs();
            }
        }, this.jobsRefreshIntervalMs);

        document.addEventListener('visibilitychange', () => {
            const jobTab = document.getElementById('job-history');
            if (!document.hidden && jobTab && jobTab.classList.contains('active')) {
                this.loadJobs();
            }
        });
    }

    formatFrequency(schedule) {
        let freq = schedule.frequency.charAt(0).toUpperCase() + schedule.frequency.slice(1);
        
        if (schedule.time_of_day) {
            freq += ` at ${schedule.time_of_day} (${this.schedulerTimezone})`;
        }
        
        if (schedule.frequency === 'weekly' && schedule.day_of_week !== null) {
            const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
            freq += ` (${days[schedule.day_of_week]})`;
        }
        
        if (schedule.frequency === 'monthly' && schedule.day_of_month) {
            freq += ` (Day ${schedule.day_of_month})`;
        }
        
        return freq;
    }

    formatScheduleTargets(schedule) {
        if (schedule.device_names && schedule.device_names.length > 0) {
            return [...schedule.device_names]
                .sort((a, b) => (a || '').localeCompare((b || ''), undefined, { sensitivity: 'base' }))
                .map(name => this.escapeHtml(name))
                .join(', ');
        }
        if (schedule.device_ids && schedule.device_ids.length > 0) {
            return schedule.device_ids.map(id => this.escapeHtml(id)).join(', ');
        }
        return 'No switches selected';
    }

    showScheduleModal(scheduleId = null) {
        const modal = document.getElementById('scheduleModal');
        const form = document.getElementById('scheduleForm');
        
        modal.classList.add('active');
        form.reset();
        document.getElementById('rollingOptions').style.display = 'none';
        
        if (scheduleId) {
            // Edit mode
            document.querySelector('#scheduleModal h3').textContent = 'Edit Device Reboot Schedule';
            document.querySelector('#scheduleModal button[type="submit"]').textContent = 'Update Schedule';
            this.loadScheduleForEdit(scheduleId);
        } else {
            // Create mode
            document.querySelector('#scheduleModal h3').textContent = 'Create Device Reboot Schedule';
            document.querySelector('#scheduleModal button[type="submit"]').textContent = 'Create Schedule';
            document.getElementById('deviceSelector').innerHTML = '<div class="empty-state">Please select a site first</div>';
            this.currentSite = null;
            this.editingScheduleId = null;
        }
    }
    
    async loadScheduleForEdit(scheduleId) {
        try {
            let schedule = this.schedules.find(s => s.id === scheduleId);
            if (!schedule) {
                const response = await fetch(`/api/schedules/${scheduleId}`);
                if (!response.ok) throw new Error('Failed to load schedule');
                schedule = await response.json();
            }

            this.editingScheduleId = scheduleId;
            this.editingDeviceIds = schedule.device_ids;
            
            // Fill form fields
            document.querySelector('input[name="name"]').value = schedule.name;
            document.querySelector('textarea[name="description"]').value = schedule.description || '';
            document.querySelector('select[name="frequency"]').value = schedule.frequency;
            document.querySelector('input[name="time_of_day"]').value = schedule.time_of_day || '';
            
            if (schedule.day_of_week !== null) {
                document.querySelector('select[name="day_of_week"]').value = schedule.day_of_week;
            }
            if (schedule.day_of_month !== null) {
                document.querySelector('input[name="day_of_month"]').value = schedule.day_of_month;
            }
            
            document.querySelector('input[name="rolling_mode"]').checked = schedule.rolling_mode;
            document.querySelector('input[name="delay_between_devices"]').value = schedule.delay_between_devices;
            document.querySelector('input[name="max_wait_time"]').value = schedule.max_wait_time;
            document.querySelector('input[name="continue_on_failure"]').checked = schedule.continue_on_failure;
            
            // Update frequency fields visibility
            this.updateFrequencyFields(schedule.frequency);
            
            // Show rolling options if enabled
            document.getElementById('rollingOptions').style.display = schedule.rolling_mode ? 'block' : 'none';
            
            // Fast path: use stored site name when available.
            const siteSelector = document.getElementById('scheduleSiteSelector');
            if (schedule.site_name && this.sites.find(s => s.name === schedule.site_name)) {
                siteSelector.value = schedule.site_name;
                this.currentSite = schedule.site_name;
                localStorage.setItem('selectedSite', schedule.site_name);
                await this.loadDevicesForSchedule();
                return;
            }

            // Fallback for legacy schedules that do not have site_name saved yet.
            document.getElementById('deviceSelector').innerHTML =
                '<div class="loading">Auto-detecting site...</div>';
            await this.detectSiteForDevices(schedule.device_ids);
            
        } catch (error) {
            console.error('Error loading schedule for edit:', error);
            this.showAlert('Failed to load schedule for editing', 'error');
            this.closeModal();
        }
    }
    
    async detectSiteForDevices(deviceIds) {
        if (deviceIds.length === 0) return;
        
        console.log('Auto-detecting site for devices:', deviceIds);
        const targetDeviceId = deviceIds[0];
        
        // Use cached device map if available
        if (!this.deviceSiteCache) {
            this.deviceSiteCache = new Map();
        }
        
        // Check cache first
        if (this.deviceSiteCache.has(targetDeviceId)) {
            const siteName = this.deviceSiteCache.get(targetDeviceId);
            console.log(`✅ Found site in cache: ${siteName}`);
            const siteSelector = document.getElementById('scheduleSiteSelector');
            siteSelector.value = siteName;
            this.currentSite = siteName;
            await this.loadDevicesForSchedule();
            return;
        }
        
        try {
            // Check sites in parallel (larger batches since we're caching)
            const batchSize = 20;
            for (let i = 0; i < this.sites.length; i += batchSize) {
                const batch = this.sites.slice(i, i + batchSize);
                console.log(`Checking batch ${Math.floor(i/batchSize) + 1}/${Math.ceil(this.sites.length/batchSize)}`);
                
                // Check all sites in this batch in parallel
                const results = await Promise.all(
                    batch.map(async (site) => {
                        try {
                            const response = await fetch(`/api/devices?site=${encodeURIComponent(site.name)}`);
                            if (!response.ok) return null;
                            
                            const devices = await response.json();
                            
                            // Cache all device->site mappings
                            devices.forEach(d => {
                                this.deviceSiteCache.set(d.id, site.name);
                            });
                            
                            const deviceIdSet = new Set(devices.map(d => d.id));
                            
                            if (deviceIdSet.has(targetDeviceId)) {
                                return site;
                            }
                            return null;
                        } catch (error) {
                            console.error(`Error checking site ${site.name}:`, error);
                            return null;
                        }
                    })
                );
                
                // Check if we found the site in this batch
                const foundSite = results.find(site => site !== null);
                if (foundSite) {
                    console.log(`✅ Found site: ${foundSite.desc || foundSite.name}`);
                    const siteSelector = document.getElementById('scheduleSiteSelector');
                    siteSelector.value = foundSite.name;
                    this.currentSite = foundSite.name;
                    localStorage.setItem('selectedSite', foundSite.name);
                    
                    // Load devices for this site
                    await this.loadDevicesForSchedule();
                    console.log('Devices loaded and pre-selected');
                    return;
                }
            }
            
            // If we get here, couldn't find the site
            console.warn('Could not auto-detect site for devices:', deviceIds);
            document.getElementById('deviceSelector').innerHTML = 
                '<div class="alert alert-error">Could not auto-detect site. Please select site manually.</div>';
            
        } catch (error) {
            console.error('Error detecting site:', error);
            document.getElementById('deviceSelector').innerHTML = 
                '<div class="alert alert-error">Error detecting site. Please select site manually.</div>';
        }
    }
    
    async editSchedule(scheduleId) {
        this.showScheduleModal(scheduleId);
    }

    closeModal() {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.classList.remove('active');
        });
        this.editingScheduleId = null;
        this.editingPoeScheduleId = null;
    }

    async createSchedule() {
        const form = document.getElementById('scheduleForm');
        const formData = new FormData(form);
        
        // Get selected devices
        const deviceIds = Array.from(document.querySelectorAll('#deviceSelector input:checked'))
            .map(input => input.value);
        
        if (deviceIds.length === 0) {
            this.showAlert('Please select at least one device', 'error');
            return;
        }

        const scheduleData = {
            name: formData.get('name'),
            description: formData.get('description') || null,
            frequency: formData.get('frequency'),
            time_of_day: formData.get('time_of_day') || null,
            day_of_week: formData.get('frequency') === 'weekly' ? parseInt(formData.get('day_of_week')) : null,
            day_of_month: formData.get('frequency') === 'monthly' ? parseInt(formData.get('day_of_month')) : null,
            device_ids: deviceIds,
            site_name: this.currentSite || null,
            rolling_mode: formData.get('rolling_mode') === 'on',
            delay_between_devices: parseInt(formData.get('delay_between_devices')) || 60,
            max_wait_time: parseInt(formData.get('max_wait_time')) || 300,
            continue_on_failure: formData.get('continue_on_failure') === 'on',
            enabled: true
        };

        try {
            let response;
            if (this.editingScheduleId) {
                // Update existing schedule
                response = await fetch(`/api/schedules/${this.editingScheduleId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(scheduleData)
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to update schedule');
                }
                
                this.showAlert('✅ Schedule updated successfully', 'success');
            } else {
                // Create new schedule
                response = await fetch('/api/schedules', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(scheduleData)
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to create schedule');
                }

                this.showAlert('✅ Schedule created successfully', 'success');
            }

            this.closeModal();
            await this.loadSchedules();
        } catch (error) {
            console.error('Error saving schedule:', error);
            this.showAlert('❌ Failed to save schedule: ' + error.message, 'error');
        }
    }

    async toggleSchedule(scheduleId) {
        try {
            const response = await fetch(`/api/schedules/${scheduleId}/toggle`, {
                method: 'POST'
            });

            if (!response.ok) throw new Error('Failed to toggle schedule');

            const result = await response.json();
            this.showAlert(`Schedule ${result.enabled ? 'enabled' : 'disabled'}`, 'success');
            await this.loadSchedules();
        } catch (error) {
            console.error('Error toggling schedule:', error);
            this.showAlert('Failed to toggle schedule', 'error');
            await this.loadSchedules();
        }
    }

    async deleteSchedule(scheduleId) {
        if (!confirm('Are you sure you want to delete this schedule?')) {
            return;
        }

        try {
            const response = await fetch(`/api/schedules/${scheduleId}`, {
                method: 'DELETE'
            });

            if (!response.ok) throw new Error('Failed to delete schedule');

            this.showAlert('✅ Schedule deleted', 'success');
            await this.loadSchedules();
        } catch (error) {
            console.error('Error deleting schedule:', error);
            this.showAlert('❌ Failed to delete schedule', 'error');
        }
    }

    async togglePoeSchedule(scheduleId) {
        try {
            const response = await fetch(`/api/poe-schedules/${scheduleId}/toggle`, {
                method: 'POST'
            });

            if (!response.ok) throw new Error('Failed to toggle PoE schedule');

            const result = await response.json();
            this.showAlert(`Port schedule ${result.enabled ? 'enabled' : 'disabled'}`, 'success');
            await this.loadPoeSchedules();
        } catch (error) {
            console.error('Error toggling PoE schedule:', error);
            this.showAlert('Failed to toggle port schedule', 'error');
            await this.loadPoeSchedules();
        }
    }

    async deletePoeSchedule(scheduleId) {
        if (!confirm('Are you sure you want to delete this port schedule?')) {
            return;
        }

        try {
            const response = await fetch(`/api/poe-schedules/${scheduleId}`, {
                method: 'DELETE'
            });

            if (!response.ok) throw new Error('Failed to delete port schedule');

            this.showAlert('✅ Port schedule deleted', 'success');
            await this.loadPoeSchedules();
        } catch (error) {
            console.error('Error deleting port schedule:', error);
            this.showAlert('❌ Failed to delete port schedule', 'error');
        }
    }

    showAlert(message, type = 'info') {
        // Simple alert for now - could be improved with toast notifications
        const alertClass = type === 'error' ? 'alert-error' : type === 'success' ? 'alert-success' : 'alert-info';
        console.log(`[${type.toUpperCase()}] ${message}`);
        alert(message);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatJobType(job) {
        const types = {
            'port_cycle': '🔄 Port Cycle',
            'poe_cycle': '⚡ PoE Cycle',
            'scheduled_reboot': '🔄 Reboot',
            'manual_reboot': '🔄 Reboot',
            'reboot': '🔄 Reboot',
        };
        return types[job.job_type] || job.job_type;
    }

    formatDuration(seconds) {
        if (seconds == null) return '';
        if (seconds < 60) return `${seconds}s`;
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
    }

    formatDateTime(dateString) {
        if (!dateString) return 'Never';

        let normalized = dateString;
        const hasTimezoneInfo = /(?:Z|[+-]\d{2}:\d{2})$/i.test(normalized);
        if (!hasTimezoneInfo) {
            // Backend stores UTC datetimes without timezone suffix; treat them as UTC.
            normalized = `${normalized}Z`;
        }

        const date = new Date(normalized);
        if (Number.isNaN(date.getTime())) {
            return dateString;
        }

        // Always render in the browser's local timezone.
        return date.toLocaleString('en-US', {
            month: '2-digit',
            day: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: true,
            timeZoneName: 'short'
        });
    }

    // Port Schedule Methods
    showPortScheduleModal(scheduleId = null) {
        const modal = document.getElementById('portScheduleModal');
        const form = document.getElementById('portScheduleForm');
        modal.classList.add('active');
        form.reset();
        
        // Populate site selector
        const siteSelector = document.getElementById('portScheduleSiteSelector');
        if (this.sites.length > 0) {
            siteSelector.innerHTML = '<option value="">Select site...</option>' + 
                this.sites.map(site => 
                    `<option value="${site.name}">${site.desc || site.name}</option>`
                ).join('');
            
            // Pre-select last used site
            const lastSite = localStorage.getItem('selectedSite');
            if (lastSite && this.sites.find(s => s.name === lastSite)) {
                siteSelector.value = lastSite;
                this.loadDevicesForPortSchedule(lastSite);
            }
        }

        if (scheduleId) {
            this.editingPoeScheduleId = scheduleId;
            document.querySelector('#portScheduleModal h3').textContent = 'Edit Port Cycle Schedule';
            document.querySelector('#portScheduleModal button[type="submit"]').textContent = 'Update Schedule';
            this.loadPortScheduleForEdit(scheduleId);
        } else {
            this.editingPoeScheduleId = null;
            document.querySelector('#portScheduleModal h3').textContent = 'Create Port Cycle Schedule';
            document.querySelector('#portScheduleModal button[type="submit"]').textContent = 'Create Schedule';
        }
    }

    async loadDevicesForPortSchedule(siteName, selectedDeviceId = null) {
        const deviceSelector = document.getElementById('portScheduleDeviceSelector');
        
        if (!siteName) {
            deviceSelector.disabled = true;
            deviceSelector.innerHTML = '<option value="">Select site first...</option>';
            return;
        }
        
        deviceSelector.disabled = true;
        deviceSelector.innerHTML = '<option value="">Loading devices...</option>';
        
        try {
            const response = await fetch(`/api/devices?site=${encodeURIComponent(siteName)}`);
            if (!response.ok) throw new Error('Failed to fetch devices');
            
            const devices = await response.json();
            const switches = devices
                .filter(d => d.is_switch)
                .sort((a, b) => (a.name || '').localeCompare((b.name || ''), undefined, { sensitivity: 'base' }));
            
            if (switches.length === 0) {
                deviceSelector.innerHTML = '<option value="">No switches found</option>';
                return;
            }
            
            deviceSelector.disabled = false;
            deviceSelector.innerHTML = '<option value="">Select device...</option>' +
                switches.map(device => 
                    `<option value="${device.id}">${device.name} (${device.model})</option>`
                ).join('');

            if (selectedDeviceId) {
                deviceSelector.value = selectedDeviceId;
            }
                
        } catch (error) {
            console.error('Error loading devices for port schedule:', error);
            deviceSelector.innerHTML = '<option value="">Error loading devices</option>';
        }
    }

    async loadPortScheduleForEdit(scheduleId) {
        try {
            const schedule = this.poeSchedules.find(s => s.id === scheduleId);
            if (!schedule) throw new Error('Port schedule not found');

            const form = document.getElementById('portScheduleForm');
            form.querySelector('input[name="name"]').value = schedule.name;
            form.querySelector('textarea[name="description"]').value = schedule.description || '';
            form.querySelector('input[name="port_idx"]').value = schedule.port_idx;
            form.querySelector('select[name="poe_only"]').value = schedule.poe_only ? 'true' : 'false';
            form.querySelector('select[name="frequency"]').value = schedule.frequency;
            form.querySelector('input[name="time_of_day"]').value = schedule.time_of_day || '';
            form.querySelector('input[name="off_duration"]').value = schedule.off_duration || 15;

            if (schedule.day_of_week !== null) {
                form.querySelector('select[name="day_of_week"]').value = schedule.day_of_week;
            }
            if (schedule.day_of_month !== null) {
                form.querySelector('input[name="day_of_month"]').value = schedule.day_of_month;
            }

            this.updatePortFrequencyFields(schedule.frequency);

            const siteSelector = document.getElementById('portScheduleSiteSelector');
            if (schedule.site_name && this.sites.find(s => s.name === schedule.site_name)) {
                siteSelector.value = schedule.site_name;
                localStorage.setItem('selectedSite', schedule.site_name);
                await this.loadDevicesForPortSchedule(schedule.site_name, schedule.device_id);
                return;
            }

            // Fallback for older schedules without persisted site_name.
            for (const site of this.sites) {
                await this.loadDevicesForPortSchedule(site.name, schedule.device_id);
                const deviceSelector = document.getElementById('portScheduleDeviceSelector');
                if (deviceSelector.value === schedule.device_id) {
                    siteSelector.value = site.name;
                    localStorage.setItem('selectedSite', site.name);
                    return;
                }
            }
        } catch (error) {
            console.error('Error loading port schedule for edit:', error);
            this.showAlert('Failed to load port schedule for editing', 'error');
            this.closeModal();
        }
    }

    editPoeSchedule(scheduleId) {
        this.showPortScheduleModal(scheduleId);
    }

    updatePortFrequencyFields(frequency) {
        const dayOfWeekGroup = document.getElementById('portDayOfWeekGroup');
        const dayOfMonthGroup = document.getElementById('portDayOfMonthGroup');
        
        dayOfWeekGroup.style.display = frequency === 'weekly' ? 'block' : 'none';
        dayOfMonthGroup.style.display = frequency === 'monthly' ? 'block' : 'none';
    }

    async createPortSchedule() {
        const form = document.getElementById('portScheduleForm');
        const formData = new FormData(form);
        
        const deviceId = document.getElementById('portScheduleDeviceSelector').value;
        if (!deviceId) {
            this.showAlert('Please select a device', 'error');
            return;
        }
        
        const scheduleData = {
            name: formData.get('name'),
            description: formData.get('description') || null,
            device_id: deviceId,
            site_name: document.getElementById('portScheduleSiteSelector').value || null,
            port_idx: parseInt(formData.get('port_idx')),
            poe_only: formData.get('poe_only') === 'true',
            frequency: formData.get('frequency'),
            time_of_day: formData.get('time_of_day') || null,
            day_of_week: formData.get('frequency') === 'weekly' ? parseInt(formData.get('day_of_week')) : null,
            day_of_month: formData.get('frequency') === 'monthly' ? parseInt(formData.get('day_of_month')) : null,
            off_duration: parseInt(formData.get('off_duration')) || 15,
            enabled: this.editingPoeScheduleId
                ? (this.poeSchedules.find(s => s.id === this.editingPoeScheduleId)?.enabled ?? true)
                : true
        };
        
        try {
            const isEdit = Boolean(this.editingPoeScheduleId);
            const endpoint = isEdit ? `/api/poe-schedules/${this.editingPoeScheduleId}` : '/api/poe-schedules';
            const method = isEdit ? 'PUT' : 'POST';
            const response = await fetch(endpoint, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(scheduleData)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to create port schedule');
            }
            
            this.showAlert(
                isEdit ? '✅ Port cycle schedule updated successfully' : '✅ Port cycle schedule created successfully',
                'success'
            );
            this.closeModal();
            this.editingPoeScheduleId = null;
            await this.loadPoeSchedules();
            
        } catch (error) {
            console.error('Error saving port schedule:', error);
            this.showAlert('❌ Failed to save port schedule: ' + error.message, 'error');
        }
    }

    // ─── Schedule Templates ────────────────────────────────────────────────

    async loadTemplates() {
        try {
            const response = await fetch('/api/schedule-templates');
            if (!response.ok) throw new Error('Failed to fetch templates');
            this.templates = await response.json();
            this.renderTemplates();
        } catch (error) {
            console.error('Error loading templates:', error);
            const list = document.getElementById('templatesList');
            if (list) list.innerHTML = '<p style="color:var(--text-secondary)">Failed to load templates.</p>';
        }
    }

    renderTemplates() {
        const container = document.getElementById('templatesList');
        if (!container) return;

        if (this.templates.length === 0) {
            container.innerHTML = `
                <div style="text-align:center;padding:40px;color:var(--text-secondary);">
                    <div style="font-size:40px;margin-bottom:12px;opacity:0.4">📋</div>
                    <p>No templates yet. Create one to save a reusable schedule configuration.</p>
                </div>`;
            return;
        }

        container.innerHTML = this.templates.map(t => {
            const typeLabel = t.template_type === 'device_reboot' ? 'Device Reboot' : 'Port Cycle';
            const typeClass = t.template_type === 'device_reboot' ? 'tmpl-type-reboot' : 'tmpl-type-port';
            const freqLabel = t.frequency.charAt(0).toUpperCase() + t.frequency.slice(1);
            const timeStr = t.time_of_day ? ` @ ${t.time_of_day}` : '';
            return `
                <div class="template-card">
                    <div class="template-card-header">
                        <span class="template-type-badge ${typeClass}">${typeLabel}</span>
                        <div class="template-card-actions">
                            <button class="btn btn-sm" onclick="schedulesManager.showTemplateModal(${t.id})">Edit</button>
                            <button class="btn btn-sm btn-danger" onclick="schedulesManager.deleteTemplate(${t.id})">Delete</button>
                        </div>
                    </div>
                    <div class="template-card-name">${this.escapeHtml(t.name)}</div>
                    ${t.description ? `<div class="template-card-desc">${this.escapeHtml(t.description)}</div>` : ''}
                    <div class="template-card-meta">
                        <span>🕐 ${freqLabel}${timeStr}</span>
                        ${t.template_type === 'device_reboot' && t.rolling_mode ? '<span>🔄 Rolling</span>' : ''}
                        ${t.template_type === 'port_cycle' ? `<span>${t.poe_only ? '⚡ PoE Only' : '🔌 Full Port'}</span>` : ''}
                        ${t.template_type === 'port_cycle' && t.off_duration ? `<span>${t.off_duration}s off</span>` : ''}
                    </div>
                </div>`;
        }).join('');
    }

    showTemplateModal(templateId = null) {
        const modal = document.getElementById('templateModal');
        const form = document.getElementById('templateForm');
        form.reset();
        this.editingTemplateId = templateId;

        document.getElementById('tmplRollingOptions').style.display = 'none';
        document.getElementById('tmplDayOfWeekGroup').style.display = 'none';
        document.getElementById('tmplDayOfMonthGroup').style.display = 'none';
        this.updateTemplateTypeFields('device_reboot');

        if (templateId) {
            const t = this.templates.find(t => t.id === templateId);
            if (!t) return;

            document.getElementById('templateModalTitle').textContent = 'Edit Template';
            document.getElementById('templateSubmitBtn').textContent = 'Update Template';

            form.querySelector('input[name="name"]').value = t.name;
            form.querySelector('textarea[name="description"]').value = t.description || '';
            form.querySelector('select[name="template_type"]').value = t.template_type;
            form.querySelector('select[name="frequency"]').value = t.frequency;
            if (t.time_of_day) form.querySelector('input[name="time_of_day"]').value = t.time_of_day;
            if (t.day_of_week != null) form.querySelector('select[name="day_of_week"]').value = t.day_of_week;
            if (t.day_of_month != null) form.querySelector('input[name="day_of_month"]').value = t.day_of_month;

            this.updateTemplateTypeFields(t.template_type);
            this.updateTemplateFrequencyFields(t.frequency);

            if (t.template_type === 'device_reboot') {
                const rollingCb = document.getElementById('tmplRollingMode');
                rollingCb.checked = t.rolling_mode ?? false;
                document.getElementById('tmplRollingOptions').style.display = rollingCb.checked ? 'block' : 'none';
                if (t.delay_between_devices != null) form.querySelector('input[name="delay_between_devices"]').value = t.delay_between_devices;
                if (t.max_wait_time != null) form.querySelector('input[name="max_wait_time"]').value = t.max_wait_time;
                if (t.continue_on_failure) form.querySelector('input[name="continue_on_failure"]').checked = t.continue_on_failure;
            } else {
                if (t.poe_only != null) form.querySelector('select[name="poe_only"]').value = t.poe_only ? 'true' : 'false';
                if (t.off_duration != null) form.querySelector('input[name="off_duration"]').value = t.off_duration;
            }
        } else {
            document.getElementById('templateModalTitle').textContent = 'New Schedule Template';
            document.getElementById('templateSubmitBtn').textContent = 'Save Template';
        }

        modal.classList.add('active');
    }

    updateTemplateTypeFields(type) {
        document.getElementById('tmplDeviceRebootFields').style.display = type === 'device_reboot' ? 'block' : 'none';
        document.getElementById('tmplPortCycleFields').style.display = type === 'port_cycle' ? 'block' : 'none';
    }

    updateTemplateFrequencyFields(frequency) {
        document.getElementById('tmplDayOfWeekGroup').style.display = frequency === 'weekly' ? 'block' : 'none';
        document.getElementById('tmplDayOfMonthGroup').style.display = frequency === 'monthly' ? 'block' : 'none';
    }

    async saveTemplate() {
        const form = document.getElementById('templateForm');
        const formData = new FormData(form);
        const type = formData.get('template_type');
        const freq = formData.get('frequency');

        const payload = {
            name: formData.get('name'),
            description: formData.get('description') || null,
            template_type: type,
            frequency: freq,
            time_of_day: formData.get('time_of_day') || null,
            day_of_week: freq === 'weekly' ? parseInt(formData.get('day_of_week')) : null,
            day_of_month: freq === 'monthly' ? parseInt(formData.get('day_of_month')) : null,
            rolling_mode: null,
            delay_between_devices: null,
            max_wait_time: null,
            continue_on_failure: null,
            poe_only: null,
            off_duration: null,
        };

        if (type === 'device_reboot') {
            payload.rolling_mode = formData.get('rolling_mode') === 'on';
            if (payload.rolling_mode) {
                payload.delay_between_devices = parseInt(formData.get('delay_between_devices')) || 60;
                payload.max_wait_time = parseInt(formData.get('max_wait_time')) || 300;
                payload.continue_on_failure = formData.get('continue_on_failure') === 'on';
            }
        } else {
            payload.poe_only = formData.get('poe_only') === 'true';
            payload.off_duration = parseInt(formData.get('off_duration')) || 15;
        }

        try {
            const isEdit = Boolean(this.editingTemplateId);
            const endpoint = isEdit ? `/api/schedule-templates/${this.editingTemplateId}` : '/api/schedule-templates';
            const method = isEdit ? 'PUT' : 'POST';
            const response = await fetch(endpoint, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Failed to save template');
            }

            this.showAlert(isEdit ? '✅ Template updated' : '✅ Template created', 'success');
            this.closeModal();
            this.editingTemplateId = null;
            await this.loadTemplates();
        } catch (error) {
            console.error('Error saving template:', error);
            this.showAlert('❌ Failed to save template: ' + error.message, 'error');
        }
    }

    async deleteTemplate(templateId) {
        const t = this.templates.find(t => t.id === templateId);
        if (!confirm(`Delete template "${t?.name}"?`)) return;

        try {
            const response = await fetch(`/api/schedule-templates/${templateId}`, { method: 'DELETE' });
            if (!response.ok) throw new Error('Failed to delete template');
            this.showAlert('✅ Template deleted', 'success');
            await this.loadTemplates();
        } catch (error) {
            this.showAlert('❌ Failed to delete template: ' + error.message, 'error');
        }
    }

    showTemplatePicker(forType) {
        this._templatePickerForType = forType;
        const filtered = this.templates.filter(t => t.template_type === forType);
        const container = document.getElementById('templatePickerList');

        if (filtered.length === 0) {
            container.innerHTML = `<p style="color:var(--text-secondary);padding:12px;">No ${forType === 'device_reboot' ? 'device reboot' : 'port cycle'} templates yet. Create one in the Templates tab.</p>`;
        } else {
            container.innerHTML = filtered.map(t => {
                const freqLabel = t.frequency.charAt(0).toUpperCase() + t.frequency.slice(1);
                const timeStr = t.time_of_day ? ` @ ${t.time_of_day}` : '';
                return `
                    <div class="template-picker-item" onclick="schedulesManager.applyTemplate(${t.id})">
                        <div class="template-picker-name">${this.escapeHtml(t.name)}</div>
                        <div class="template-picker-meta">
                            ${freqLabel}${timeStr}
                            ${t.template_type === 'device_reboot' && t.rolling_mode ? ' · Rolling' : ''}
                            ${t.template_type === 'port_cycle' ? ` · ${t.poe_only ? 'PoE Only' : 'Full Port'} · ${t.off_duration}s` : ''}
                        </div>
                        ${t.description ? `<div class="template-picker-desc">${this.escapeHtml(t.description)}</div>` : ''}
                    </div>`;
            }).join('');
        }

        document.getElementById('templatePickerModal').classList.add('active');
    }

    applyTemplate(templateId) {
        const t = this.templates.find(t => t.id === templateId);
        if (!t) return;

        this.closeModal();

        if (t.template_type === 'device_reboot') {
            const form = document.getElementById('scheduleForm');
            form.querySelector('select[name="frequency"]').value = t.frequency;
            if (t.time_of_day) form.querySelector('input[name="time_of_day"]').value = t.time_of_day;
            if (t.day_of_week != null) form.querySelector('select[name="day_of_week"]').value = t.day_of_week;
            if (t.day_of_month != null) form.querySelector('input[name="day_of_month"]').value = t.day_of_month;
            this.updateFrequencyFields(t.frequency);

            const rollingCb = document.getElementById('rollingModeCheck');
            rollingCb.checked = t.rolling_mode ?? false;
            document.getElementById('rollingOptions').style.display = rollingCb.checked ? 'block' : 'none';
            if (t.rolling_mode) {
                if (t.delay_between_devices != null) form.querySelector('input[name="delay_between_devices"]').value = t.delay_between_devices;
                if (t.max_wait_time != null) form.querySelector('input[name="max_wait_time"]').value = t.max_wait_time;
                if (t.continue_on_failure != null) form.querySelector('input[name="continue_on_failure"]').checked = t.continue_on_failure;
            }
            document.getElementById('scheduleModal').classList.add('active');
        } else {
            const form = document.getElementById('portScheduleForm');
            form.querySelector('select[name="frequency"]').value = t.frequency;
            if (t.time_of_day) form.querySelector('input[name="time_of_day"]').value = t.time_of_day;
            if (t.day_of_week != null) form.querySelector('select[name="day_of_week"]').value = t.day_of_week;
            if (t.day_of_month != null) form.querySelector('input[name="day_of_month"]').value = t.day_of_month;
            this.updatePortFrequencyFields(t.frequency);
            if (t.poe_only != null) form.querySelector('select[name="poe_only"]').value = t.poe_only ? 'true' : 'false';
            if (t.off_duration != null) form.querySelector('input[name="off_duration"]').value = t.off_duration;
            document.getElementById('portScheduleModal').classList.add('active');
        }
    }
}

// Initialize when DOM is ready
const schedulesManager = new SchedulesManager();
