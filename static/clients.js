'use strict';

class ClientsManager {
    constructor() {
        this.clients = [];
        this.blocked = [];
        this.sites = [];
        this.selected = new Set();
        this.currentSite = null;

        this._siteFilter = document.getElementById('siteFilter');
        this._searchInput = document.getElementById('searchInput');
        this._clientsGrid = document.getElementById('clientsGrid');
        this._blockedGrid = document.getElementById('blockedGrid');
        this._bulkBlockBtn = document.getElementById('bulkBlockBtn');
        this._bulkCount = document.getElementById('bulkCount');
        this._selectAllCb = document.getElementById('selectAllCb');

        this._siteFilter.addEventListener('change', () => {
            this.currentSite = this._siteFilter.value || null;
            this.load();
        });
        this._searchInput.addEventListener('input', () => this._render());

        this._loadSites().then(() => this.load());
    }

    async _loadSites() {
        try {
            const res = await fetch('/api/sites');
            const sites = await res.json();
            this.sites = sites;
            this._siteFilter.innerHTML = sites.map(s =>
                `<option value="${s.name}">${s.desc || s.name}</option>`
            ).join('');
            this.currentSite = sites[0]?.name || null;
        } catch (e) {
            this._siteFilter.innerHTML = '<option value="">Default site</option>';
        }
    }

    async load() {
        this._clientsGrid.innerHTML = '<div class="loading-msg">Loading…</div>';
        this._blockedGrid.innerHTML = '<div class="loading-msg">Loading…</div>';
        this.selected.clear();
        this._updateBulkBar();

        const qs = this.currentSite ? `?site=${encodeURIComponent(this.currentSite)}` : '';
        try {
            const [cRes, bRes] = await Promise.all([
                fetch(`/api/clients${qs}`),
                fetch(`/api/clients/blocked${qs}`)
            ]);
            this.clients = await cRes.json();
            this.blocked = await bRes.json();
        } catch (e) {
            this.clients = [];
            this.blocked = [];
        }

        this._render();
        this._updateStats();
    }

    _filteredClients() {
        const q = this._searchInput.value.trim().toLowerCase();
        if (!q) return this.clients;
        return this.clients.filter(c =>
            c.hostname.toLowerCase().includes(q) ||
            c.mac.toLowerCase().includes(q) ||
            c.ip.toLowerCase().includes(q) ||
            c.essid.toLowerCase().includes(q)
        );
    }

    _render() {
        const filtered = this._filteredClients();

        if (!filtered.length) {
            this._clientsGrid.innerHTML = '<div class="empty-msg">No connected clients found</div>';
        } else {
            this._clientsGrid.innerHTML = filtered.map(c => this._clientCard(c)).join('');
        }

        if (!this.blocked.length) {
            this._blockedGrid.innerHTML = '<div class="empty-msg">No blocked clients</div>';
        } else {
            this._blockedGrid.innerHTML = this.blocked.map(c => this._blockedCard(c)).join('');
        }
    }

    _signalBars(signal) {
        if (signal == null) return '<span style="color:var(--text-muted)">—</span>';
        // signal is typically negative dBm; -50 great, -70 ok, -85 poor
        const s = Math.abs(signal);
        let bars = s < 60 ? 4 : s < 70 ? 3 : s < 80 ? 2 : 1;
        const cls = s < 70 ? 'active' : s < 80 ? 'active warn' : 'active bad';
        return `<span class="signal-bar">
            ${[1,2,3,4].map(i => `<span class="${i <= bars ? cls : ''}"></span>`).join('')}
        </span> ${signal} dBm`;
    }

    _fmtBytes(b) {
        if (!b) return '0 B';
        const units = ['B','KB','MB','GB'];
        let i = 0;
        while (b >= 1024 && i < units.length - 1) { b /= 1024; i++; }
        return `${b.toFixed(1)} ${units[i]}`;
    }

    _fmtUptime(s) {
        if (!s) return '—';
        const h = Math.floor(s / 3600);
        const m = Math.floor((s % 3600) / 60);
        return h ? `${h}h ${m}m` : `${m}m`;
    }

    _clientCard(c) {
        const sel = this.selected.has(c.mac);
        return `
        <div class="client-card${sel ? ' selected' : ''}" id="card-${c.mac.replace(/:/g,'_')}">
            <input type="checkbox" class="client-select-cb"
                ${sel ? 'checked' : ''}
                onchange="clientsManager.toggleSelect('${c.mac}', this.checked)">
            <div class="client-hostname" title="${c.hostname}">${this._esc(c.hostname)}</div>
            <div class="client-mac">${c.mac}</div>
            <div class="client-meta">
                <div class="client-meta-row">
                    <span class="label">IP</span>${c.ip || '—'}
                </div>
                <div class="client-meta-row">
                    <span class="label">SSID</span>${this._esc(c.essid) || '—'}
                </div>
                <div class="client-meta-row">
                    <span class="label">Sig</span>${this._signalBars(c.signal)}
                </div>
                <div class="client-meta-row">
                    <span class="label">Up</span>${this._fmtUptime(c.uptime)}
                    &nbsp;↑${this._fmtBytes(c.tx_bytes)} ↓${this._fmtBytes(c.rx_bytes)}
                </div>
                ${c.oui ? `<div><span class="oui-badge">${this._esc(c.oui)}</span></div>` : ''}
            </div>
            <div class="client-actions">
                <button class="btn-block" onclick="clientsManager.blockOne('${c.mac}', '${this._esc(c.hostname)}', this)">
                    🚫 Block
                </button>
            </div>
        </div>`;
    }

    _blockedCard(c) {
        return `
        <div class="client-card blocked-card">
            <div class="client-hostname" title="${c.hostname}">${this._esc(c.hostname)}</div>
            <div class="client-mac">${c.mac}</div>
            ${c.oui ? `<div><span class="oui-badge">${this._esc(c.oui)}</span></div>` : ''}
            <div class="client-actions" style="margin-top:12px;">
                <button class="btn-unblock" onclick="clientsManager.unblockOne('${c.mac}', '${this._esc(c.hostname)}', this)">
                    ✅ Unblock
                </button>
            </div>
        </div>`;
    }

    toggleSelect(mac, checked) {
        if (checked) this.selected.add(mac);
        else this.selected.delete(mac);

        const card = document.getElementById(`card-${mac.replace(/:/g,'_')}`);
        if (card) card.classList.toggle('selected', checked);

        this._updateBulkBar();
    }

    toggleSelectAll(checked) {
        const filtered = this._filteredClients();
        filtered.forEach(c => {
            if (checked) this.selected.add(c.mac);
            else this.selected.delete(c.mac);
            const card = document.getElementById(`card-${c.mac.replace(/:/g,'_')}`);
            if (card) {
                card.classList.toggle('selected', checked);
                const cb = card.querySelector('.client-select-cb');
                if (cb) cb.checked = checked;
            }
        });
        this._updateBulkBar();
    }

    _updateBulkBar() {
        const n = this.selected.size;
        this._bulkCount.textContent = n;
        this._bulkBlockBtn.style.display = n > 0 ? 'inline-flex' : 'none';
    }

    _updateStats() {
        const wifi = this.clients.filter(c => !c.is_wired).length;
        document.getElementById('statConnected').textContent = this.clients.length;
        document.getElementById('statWifi').textContent = wifi;
        document.getElementById('statBlocked').textContent = this.blocked.length;
    }

    async blockOne(mac, hostname, btn) {
        btn.disabled = true;
        btn.textContent = 'Blocking…';
        const site = this.currentSite;
        try {
            const res = await fetch('/api/clients/block', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({mac, site})
            });
            if (!res.ok) throw new Error(await res.text());
            await this.load();
        } catch (e) {
            btn.disabled = false;
            btn.textContent = '🚫 Block';
            alert(`Failed to block ${hostname}: ${e.message}`);
        }
    }

    async unblockOne(mac, hostname, btn) {
        btn.disabled = true;
        btn.textContent = 'Unblocking…';
        const site = this.currentSite;
        try {
            const res = await fetch('/api/clients/unblock', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({mac, site})
            });
            if (!res.ok) throw new Error(await res.text());
            await this.load();
        } catch (e) {
            btn.disabled = false;
            btn.textContent = '✅ Unblock';
            alert(`Failed to unblock ${hostname}: ${e.message}`);
        }
    }

    showBulkBlockModal() {
        const macs = [...this.selected];
        const clientMap = Object.fromEntries(this.clients.map(c => [c.mac, c]));
        const list = document.getElementById('bulkBlockList');
        list.innerHTML = macs.map(mac => {
            const c = clientMap[mac] || {hostname: mac};
            return `<li>${this._esc(c.hostname)}<span>${mac}</span></li>`;
        }).join('');
        document.getElementById('bulkBlockModal').style.display = 'flex';
    }

    closeBulkModal() {
        document.getElementById('bulkBlockModal').style.display = 'none';
    }

    async executeBulkBlock() {
        const macs = [...this.selected];
        const site = this.currentSite;
        this.closeBulkModal();
        try {
            const res = await fetch('/api/clients/bulk-block', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({macs, site})
            });
            const data = await res.json();
            await this.load();
            if (data.failed?.length) {
                alert(`Blocked ${data.blocked.length}. Failed: ${data.failed.map(f=>f.mac).join(', ')}`);
            }
        } catch (e) {
            alert(`Bulk block failed: ${e.message}`);
        }
    }

    _esc(s) {
        return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }
}

const clientsManager = new ClientsManager();
