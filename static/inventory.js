'use strict';

class InventoryManager {
    constructor() {
        this.sites = [];
        this.assets = [];

        this.siteForm = document.getElementById('siteForm');
        this.assetForm = document.getElementById('assetForm');
        this.siteModal = document.getElementById('siteModal');
        this.assetModal = document.getElementById('assetModal');

        this.init();
    }

    async init() {
        this.setupEventListeners();
        await this.refreshAll();
    }

    setupEventListeners() {
        document.querySelectorAll('.tab-btn').forEach((button) => {
            button.addEventListener('click', () => this.showTab(button.dataset.tab));
        });

        document.getElementById('newSiteBtn').addEventListener('click', () => this.showSiteModal());
        document.getElementById('newAssetBtn').addEventListener('click', () => this.showAssetModal());
        document.getElementById('importSitesBtn').addEventListener('click', () => this.importUniFiSites());

        this.siteForm.addEventListener('submit', (event) => {
            event.preventDefault();
            this.saveSite();
        });

        this.assetForm.addEventListener('submit', (event) => {
            event.preventDefault();
            this.saveAsset();
        });

        ['siteSearchInput', 'clientFilter', 'siteStatusFilter'].forEach((id) => {
            document.getElementById(id).addEventListener('input', () => this.renderSites());
            document.getElementById(id).addEventListener('change', () => this.renderSites());
        });

        ['assetSearchInput', 'assetSiteFilter', 'assetTypeFilter', 'assetPolicyFilter'].forEach((id) => {
            document.getElementById(id).addEventListener('input', () => this.renderAssets());
            document.getElementById(id).addEventListener('change', () => this.renderAssets());
        });

        document.querySelectorAll('.close-btn').forEach((button) => {
            button.addEventListener('click', () => this.closeModals());
        });

        window.addEventListener('click', (event) => {
            if (event.target === this.siteModal || event.target === this.assetModal) {
                this.closeModals();
            }
        });
    }

    async refreshAll() {
        await Promise.all([this.loadSites(), this.loadAssets()]);
        this.renderStats();
        this.populateFilters();
        this.renderSites();
        this.renderAssets();
    }

    async apiRequest(url, options = {}) {
        const response = await fetch(url, options);
        let payload = null;

        try {
            payload = await response.json();
        } catch (error) {
            payload = null;
        }

        if (!response.ok) {
            const detail = payload?.detail || payload?.message || `Request failed (${response.status})`;
            throw new Error(detail);
        }

        return payload;
    }

    async loadSites() {
        this.sites = await this.apiRequest('/api/site-inventory');
    }

    async loadAssets() {
        this.assets = await this.apiRequest('/api/managed-assets');
    }

    renderStats() {
        const activeSites = this.sites.filter((site) => site.is_active).length;
        const safeAssets = this.assets.filter((asset) => asset.auto_cycle_policy === 'safe_to_auto_cycle').length;

        document.getElementById('statSites').textContent = this.sites.length;
        document.getElementById('statActiveSites').textContent = activeSites;
        document.getElementById('statAssets').textContent = this.assets.length;
        document.getElementById('statAutoSafe').textContent = safeAssets;
    }

    populateFilters() {
        const clientFilter = document.getElementById('clientFilter');
        const assetSiteFilter = document.getElementById('assetSiteFilter');
        const assetSiteSelect = document.getElementById('assetSiteSelect');
        const assetTypeFilter = document.getElementById('assetTypeFilter');

        const currentClient = clientFilter.value;
        const currentAssetSite = assetSiteFilter.value;
        const currentAssetType = assetTypeFilter.value;
        const currentAssetModalSite = assetSiteSelect.value;

        const clientNames = [...new Set(this.sites.map((site) => site.client_name).filter(Boolean))]
            .sort((left, right) => left.localeCompare(right));
        const assetTypes = [...new Set(this.assets.map((asset) => asset.asset_type).filter(Boolean))]
            .sort((left, right) => left.localeCompare(right));

        clientFilter.innerHTML = '<option value="">All Clients</option>' + clientNames.map((client) =>
            `<option value="${this.escapeHtml(client)}">${this.escapeHtml(client)}</option>`
        ).join('');

        const siteOptions = this.sites.map((site) =>
            `<option value="${site.id}">${this.escapeHtml(site.name)} (${this.escapeHtml(site.unifi_site_name)})</option>`
        ).join('');

        assetSiteFilter.innerHTML = '<option value="">All Sites</option>' + siteOptions;
        assetSiteSelect.innerHTML = '<option value="">Select site...</option>' + siteOptions;

        assetTypeFilter.innerHTML = '<option value="">All Asset Types</option>' + assetTypes.map((type) =>
            `<option value="${this.escapeHtml(type)}">${this.escapeHtml(this.prettyLabel(type))}</option>`
        ).join('');

        if ([...clientFilter.options].some((option) => option.value === currentClient)) {
            clientFilter.value = currentClient;
        }

        if ([...assetSiteFilter.options].some((option) => option.value === currentAssetSite)) {
            assetSiteFilter.value = currentAssetSite;
        }

        if ([...assetSiteSelect.options].some((option) => option.value === currentAssetModalSite)) {
            assetSiteSelect.value = currentAssetModalSite;
        }

        if ([...assetTypeFilter.options].some((option) => option.value === currentAssetType)) {
            assetTypeFilter.value = currentAssetType;
        }
    }

    showTab(tabId) {
        document.querySelectorAll('.tab-btn').forEach((button) => {
            button.classList.toggle('active', button.dataset.tab === tabId);
        });

        document.querySelectorAll('.tab-content').forEach((panel) => {
            panel.classList.toggle('active', panel.id === tabId);
        });
    }

    filteredSites() {
        const query = document.getElementById('siteSearchInput').value.trim().toLowerCase();
        const client = document.getElementById('clientFilter').value;
        const status = document.getElementById('siteStatusFilter').value;

        return this.sites.filter((site) => {
            if (client && site.client_name !== client) {
                return false;
            }

            if (status === 'active' && !site.is_active) {
                return false;
            }

            if (status === 'inactive' && site.is_active) {
                return false;
            }

            if (!query) {
                return true;
            }

            const haystack = [
                site.name,
                site.unifi_site_name,
                site.client_name,
                site.property_type,
                ...(site.tags || []),
                site.notes,
                site.internal_notes,
            ]
                .filter(Boolean)
                .join(' ')
                .toLowerCase();

            return haystack.includes(query);
        });
    }

    renderSites() {
        const container = document.getElementById('sitesList');
        const sites = this.filteredSites();

        if (!sites.length) {
            container.innerHTML = `
                <div class="empty-state inventory-empty">
                    <div class="empty-state-icon">🏢</div>
                    <p>No site records match the current filters.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = sites.map((site) => `
            <article class="inventory-card">
                <div class="inventory-card-header">
                    <div>
                        <div class="inventory-card-title">${this.escapeHtml(site.name)}</div>
                        <div class="inventory-card-subtitle">${this.escapeHtml(site.unifi_site_name)}</div>
                    </div>
                    <div class="inventory-card-actions">
                        <button class="btn btn-sm" onclick="inventoryManager.showSiteModal(${site.id})">✏️</button>
                        <button class="btn btn-sm" onclick="inventoryManager.deleteSite(${site.id})">🗑️</button>
                    </div>
                </div>
                <div class="inventory-badges">
                    <span class="inventory-badge ${site.is_active ? 'status-active' : 'status-inactive'}">${site.is_active ? 'Active' : 'Inactive'}</span>
                    <span class="inventory-badge">Priority ${site.priority}</span>
                    <span class="inventory-badge">${site.asset_count} assets</span>
                    ${(site.tags || []).map((tag) => `<span class="inventory-badge">${this.escapeHtml(tag)}</span>`).join('')}
                </div>
                <div class="inventory-meta">
                    ${site.client_name ? `<div class="inventory-meta-row"><span class="inventory-meta-label">Client</span><span>${this.escapeHtml(site.client_name)}</span></div>` : ''}
                    ${site.property_type ? `<div class="inventory-meta-row"><span class="inventory-meta-label">Type</span><span>${this.escapeHtml(site.property_type)}</span></div>` : ''}
                    ${site.maintenance_window ? `<div class="inventory-meta-row"><span class="inventory-meta-label">Window</span><span>${this.escapeHtml(site.maintenance_window)}</span></div>` : ''}
                    ${site.service_tier ? `<div class="inventory-meta-row"><span class="inventory-meta-label">Tier</span><span>${this.escapeHtml(site.service_tier)}</span></div>` : ''}
                    ${site.timezone ? `<div class="inventory-meta-row"><span class="inventory-meta-label">Timezone</span><span>${this.escapeHtml(site.timezone)}</span></div>` : ''}
                    ${site.address ? `<div class="inventory-meta-row"><span class="inventory-meta-label">Address</span><span>${this.escapeHtml(site.address)}</span></div>` : ''}
                </div>
                ${site.notes ? `<div class="inventory-notes"><strong>Notes:</strong> ${this.escapeHtml(site.notes)}</div>` : ''}
                ${site.internal_notes ? `<div class="inventory-notes"><strong>Internal:</strong> ${this.escapeHtml(site.internal_notes)}</div>` : ''}
            </article>
        `).join('');
    }

    filteredAssets() {
        const query = document.getElementById('assetSearchInput').value.trim().toLowerCase();
        const siteId = document.getElementById('assetSiteFilter').value;
        const assetType = document.getElementById('assetTypeFilter').value;
        const policy = document.getElementById('assetPolicyFilter').value;

        return this.assets.filter((asset) => {
            if (siteId && String(asset.site_inventory_id) !== siteId) {
                return false;
            }

            if (assetType && asset.asset_type !== assetType) {
                return false;
            }

            if (policy && asset.auto_cycle_policy !== policy) {
                return false;
            }

            if (!query) {
                return true;
            }

            const haystack = [
                asset.name,
                asset.asset_type,
                asset.site_name,
                asset.unifi_site_name,
                asset.device_id,
                asset.device_name,
                asset.port_label,
                asset.location_details,
                asset.recovery_playbook,
                asset.notes,
                ...(asset.tags || []),
            ]
                .filter(Boolean)
                .join(' ')
                .toLowerCase();

            return haystack.includes(query);
        });
    }

    renderAssets() {
        const container = document.getElementById('assetsList');
        const assets = this.filteredAssets();

        if (!assets.length) {
            container.innerHTML = `
                <div class="empty-state inventory-empty">
                    <div class="empty-state-icon">🔌</div>
                    <p>No managed assets match the current filters.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = assets.map((asset) => `
            <article class="inventory-card">
                <div class="inventory-card-header">
                    <div>
                        <div class="inventory-card-title">${this.escapeHtml(asset.name)}</div>
                        <div class="inventory-card-subtitle">${this.escapeHtml(asset.site_name || asset.unifi_site_name || 'Unassigned site')}</div>
                    </div>
                    <div class="inventory-card-actions">
                        <button class="btn btn-sm" onclick="inventoryManager.showAssetModal(${asset.id})">✏️</button>
                        <button class="btn btn-sm" onclick="inventoryManager.deleteAsset(${asset.id})">🗑️</button>
                    </div>
                </div>
                <div class="inventory-badges">
                    <span class="inventory-badge">${this.escapeHtml(this.prettyLabel(asset.asset_type))}</span>
                    <span class="inventory-badge policy-${asset.auto_cycle_policy}">${this.escapeHtml(this.prettyLabel(asset.auto_cycle_policy))}</span>
                    ${asset.is_enabled ? '<span class="inventory-badge status-active">Active</span>' : '<span class="inventory-badge status-inactive">Disabled</span>'}
                    ${(asset.tags || []).map((tag) => `<span class="inventory-badge">${this.escapeHtml(tag)}</span>`).join('')}
                </div>
                <div class="inventory-meta">
                    ${asset.device_name ? `<div class="inventory-meta-row"><span class="inventory-meta-label">Device</span><span>${this.escapeHtml(asset.device_name)}</span></div>` : ''}
                    ${asset.device_id ? `<div class="inventory-meta-row"><span class="inventory-meta-label">Device ID</span><span>${this.escapeHtml(asset.device_id)}</span></div>` : ''}
                    ${asset.port_idx ? `<div class="inventory-meta-row"><span class="inventory-meta-label">Port</span><span>${asset.port_idx}${asset.port_label ? ` (${this.escapeHtml(asset.port_label)})` : ''}</span></div>` : ''}
                    ${asset.vendor || asset.model ? `<div class="inventory-meta-row"><span class="inventory-meta-label">Hardware</span><span>${this.escapeHtml([asset.vendor, asset.model].filter(Boolean).join(' '))}</span></div>` : ''}
                    ${asset.serial_number ? `<div class="inventory-meta-row"><span class="inventory-meta-label">Serial</span><span>${this.escapeHtml(asset.serial_number)}</span></div>` : ''}
                    ${asset.location_details ? `<div class="inventory-meta-row"><span class="inventory-meta-label">Location</span><span>${this.escapeHtml(asset.location_details)}</span></div>` : ''}
                </div>
                ${asset.recovery_playbook ? `<div class="inventory-notes"><strong>Recovery:</strong> ${this.escapeHtml(asset.recovery_playbook)}</div>` : ''}
                ${asset.notes ? `<div class="inventory-notes"><strong>Notes:</strong> ${this.escapeHtml(asset.notes)}</div>` : ''}
            </article>
        `).join('');
    }

    showSiteModal(siteId = null) {
        const title = document.getElementById('siteModalTitle');
        this.siteForm.reset();
        this.siteForm.elements.site_id.value = '';
        this.siteForm.elements.priority.value = 3;
        this.siteForm.elements.is_active.checked = true;

        if (siteId) {
            const site = this.sites.find((item) => item.id === siteId);
            if (!site) {
                this.showAlert('Site record not found.', 'error');
                return;
            }

            title.textContent = 'Edit Site Record';
            this.siteForm.elements.site_id.value = site.id;
            this.siteForm.elements.name.value = site.name || '';
            this.siteForm.elements.unifi_site_name.value = site.unifi_site_name || '';
            this.siteForm.elements.client_name.value = site.client_name || '';
            this.siteForm.elements.property_type.value = site.property_type || '';
            this.siteForm.elements.address.value = site.address || '';
            this.siteForm.elements.timezone.value = site.timezone || '';
            this.siteForm.elements.maintenance_window.value = site.maintenance_window || '';
            this.siteForm.elements.service_tier.value = site.service_tier || '';
            this.siteForm.elements.priority.value = site.priority || 3;
            this.siteForm.elements.tags.value = (site.tags || []).join(', ');
            this.siteForm.elements.notes.value = site.notes || '';
            this.siteForm.elements.internal_notes.value = site.internal_notes || '';
            this.siteForm.elements.is_active.checked = Boolean(site.is_active);
        } else {
            title.textContent = 'New Site Record';
        }

        this.siteModal.style.display = 'block';
    }

    showAssetModal(assetId = null) {
        if (!this.sites.length) {
            this.showAlert('Create or import at least one site before adding managed assets.', 'warning');
            return;
        }

        const title = document.getElementById('assetModalTitle');
        this.assetForm.reset();
        this.assetForm.elements.asset_id.value = '';
        this.assetForm.elements.auto_cycle_policy.value = 'manual_approval_required';
        this.assetForm.elements.is_enabled.checked = true;

        if (assetId) {
            const asset = this.assets.find((item) => item.id === assetId);
            if (!asset) {
                this.showAlert('Managed asset not found.', 'error');
                return;
            }

            title.textContent = 'Edit Managed Asset';
            this.assetForm.elements.asset_id.value = asset.id;
            this.assetForm.elements.site_inventory_id.value = String(asset.site_inventory_id);
            this.assetForm.elements.name.value = asset.name || '';
            this.assetForm.elements.asset_type.value = asset.asset_type || '';
            this.assetForm.elements.device_id.value = asset.device_id || '';
            this.assetForm.elements.device_name.value = asset.device_name || '';
            this.assetForm.elements.port_idx.value = asset.port_idx || '';
            this.assetForm.elements.port_label.value = asset.port_label || '';
            this.assetForm.elements.vendor.value = asset.vendor || '';
            this.assetForm.elements.model.value = asset.model || '';
            this.assetForm.elements.serial_number.value = asset.serial_number || '';
            this.assetForm.elements.location_details.value = asset.location_details || '';
            this.assetForm.elements.recovery_playbook.value = asset.recovery_playbook || '';
            this.assetForm.elements.notes.value = asset.notes || '';
            this.assetForm.elements.tags.value = (asset.tags || []).join(', ');
            this.assetForm.elements.auto_cycle_policy.value = asset.auto_cycle_policy || 'manual_approval_required';
            this.assetForm.elements.is_enabled.checked = Boolean(asset.is_enabled);
        } else {
            title.textContent = 'New Managed Asset';
        }

        this.assetModal.style.display = 'block';
    }

    closeModals() {
        this.siteModal.style.display = 'none';
        this.assetModal.style.display = 'none';
    }

    buildSitePayload() {
        return {
            name: this.siteForm.elements.name.value.trim(),
            unifi_site_name: this.siteForm.elements.unifi_site_name.value.trim(),
            client_name: this.optionalValue(this.siteForm.elements.client_name.value),
            property_type: this.optionalValue(this.siteForm.elements.property_type.value),
            address: this.optionalValue(this.siteForm.elements.address.value),
            timezone: this.optionalValue(this.siteForm.elements.timezone.value),
            maintenance_window: this.optionalValue(this.siteForm.elements.maintenance_window.value),
            service_tier: this.optionalValue(this.siteForm.elements.service_tier.value),
            priority: Number(this.siteForm.elements.priority.value || 3),
            tags: this.parseTags(this.siteForm.elements.tags.value),
            notes: this.optionalValue(this.siteForm.elements.notes.value),
            internal_notes: this.optionalValue(this.siteForm.elements.internal_notes.value),
            is_active: this.siteForm.elements.is_active.checked,
        };
    }

    buildAssetPayload() {
        const portValue = this.assetForm.elements.port_idx.value;

        return {
            site_inventory_id: Number(this.assetForm.elements.site_inventory_id.value),
            name: this.assetForm.elements.name.value.trim(),
            asset_type: this.assetForm.elements.asset_type.value.trim(),
            device_id: this.optionalValue(this.assetForm.elements.device_id.value),
            device_name: this.optionalValue(this.assetForm.elements.device_name.value),
            port_idx: portValue ? Number(portValue) : null,
            port_label: this.optionalValue(this.assetForm.elements.port_label.value),
            vendor: this.optionalValue(this.assetForm.elements.vendor.value),
            model: this.optionalValue(this.assetForm.elements.model.value),
            serial_number: this.optionalValue(this.assetForm.elements.serial_number.value),
            location_details: this.optionalValue(this.assetForm.elements.location_details.value),
            recovery_playbook: this.optionalValue(this.assetForm.elements.recovery_playbook.value),
            notes: this.optionalValue(this.assetForm.elements.notes.value),
            tags: this.parseTags(this.assetForm.elements.tags.value),
            auto_cycle_policy: this.assetForm.elements.auto_cycle_policy.value,
            is_enabled: this.assetForm.elements.is_enabled.checked,
        };
    }

    async saveSite() {
        const siteId = this.siteForm.elements.site_id.value;
        const payload = this.buildSitePayload();
        const url = siteId ? `/api/site-inventory/${siteId}` : '/api/site-inventory';
        const method = siteId ? 'PUT' : 'POST';

        try {
            await this.apiRequest(url, {
                method,
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload),
            });

            this.closeModals();
            await this.refreshAll();
            this.showAlert(siteId ? 'Site record updated.' : 'Site record created.', 'success');
        } catch (error) {
            this.showAlert(error.message, 'error');
        }
    }

    async saveAsset() {
        const assetId = this.assetForm.elements.asset_id.value;
        const payload = this.buildAssetPayload();
        const url = assetId ? `/api/managed-assets/${assetId}` : '/api/managed-assets';
        const method = assetId ? 'PUT' : 'POST';

        try {
            await this.apiRequest(url, {
                method,
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload),
            });

            this.closeModals();
            await this.refreshAll();
            this.showAlert(assetId ? 'Managed asset updated.' : 'Managed asset created.', 'success');
        } catch (error) {
            this.showAlert(error.message, 'error');
        }
    }

    async deleteSite(siteId) {
        if (!window.confirm('Delete this site record? This is blocked if it still has managed assets.')) {
            return;
        }

        try {
            await this.apiRequest(`/api/site-inventory/${siteId}`, {method: 'DELETE'});
            await this.refreshAll();
            this.showAlert('Site record deleted.', 'success');
        } catch (error) {
            this.showAlert(error.message, 'error');
        }
    }

    async deleteAsset(assetId) {
        if (!window.confirm('Delete this managed asset?')) {
            return;
        }

        try {
            await this.apiRequest(`/api/managed-assets/${assetId}`, {method: 'DELETE'});
            await this.refreshAll();
            this.showAlert('Managed asset deleted.', 'success');
        } catch (error) {
            this.showAlert(error.message, 'error');
        }
    }

    async importUniFiSites() {
        const button = document.getElementById('importSitesBtn');
        button.disabled = true;
        button.textContent = 'Importing...';

        try {
            const result = await this.apiRequest('/api/site-inventory/import-unifi-sites', {method: 'POST'});
            await this.refreshAll();

            this.showAlert(
                `Imported ${result.created_count} new site records and skipped ${result.skipped_count} existing records.`,
                result.created_count ? 'success' : 'info'
            );
        } catch (error) {
            this.showAlert(error.message, 'error');
        } finally {
            button.disabled = false;
            button.textContent = '⇅ Import UniFi Sites';
        }
    }

    showAlert(message, type = 'info') {
        const container = document.getElementById('inventoryAlerts');
        container.innerHTML = `<div class="alert alert-${type}">${this.escapeHtml(message)}</div>`;

        window.clearTimeout(this._alertTimer);
        this._alertTimer = window.setTimeout(() => {
            container.innerHTML = '';
        }, 5000);
    }

    parseTags(value) {
        return value
            .split(',')
            .map((tag) => tag.trim())
            .filter(Boolean);
    }

    optionalValue(value) {
        const trimmed = String(value || '').trim();
        return trimmed || null;
    }

    prettyLabel(value) {
        return String(value || '')
            .replace(/_/g, ' ')
            .replace(/\b\w/g, (char) => char.toUpperCase());
    }

    escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
}

const inventoryManager = new InventoryManager();
