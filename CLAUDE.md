# UniFi Maintenance Dashboard - Development Notes

## Project Overview
Self-hosted UniFi device maintenance dashboard for managing network devices across 102 sites.

## Current Status: Production — All Phases Complete

### ✅ Completed Features

#### Phase 1: Backend Foundation
- FastAPI backend with async support
- UniFi API client with authentication
- SQLite database with SQLAlchemy
- Environment configuration via .env
- Logging system (console + file)
- Project structure and dependencies

#### Phase 2: Web Dashboard UI
- Modern responsive web interface
- Device cards with real-time status
- Device filtering (all, online, offline, switches, APs)
- Search functionality
- One-click device reboot
- PoE port control interface (⚡ PoE Cycle per PoE port)
- Full port cycling interface (🔄 Port Cycle on every port)
- Visual countdown timer during port cycles (progress bar, elapsed/total time, status text)

#### Multi-Site Support
- Site selector dropdown (102 sites)
- All API endpoints support optional site parameter
- Switch between sites dynamically

#### Phase 3: Scheduler System
- **Job Execution Engine** (`scheduler_engine.py`)
  - APScheduler integration with async support
  - Rolling reboot mode (one device at a time)
  - Parallel reboot mode (all devices simultaneously)
  - Configurable delays between devices
  - Wait for device online with timeout
  - Continue on failure option
  - PoE/port cycle scheduling
  - Automatic schedule reload on changes

- **Scheduler UI** (`/schedules` page)
  - Schedule creation/edit forms with device selection
  - Site-based device filtering
  - Frequency options (hourly, daily, weekly, monthly)
  - Rolling mode configuration
  - Schedule list with enable/disable toggle
  - Port cycle schedules **grouped by site** (collapsible cards with compact table)
  - Job history viewer with rich display (type icons, source labels, site name, duration)
  - Navigation between 🏠 Dashboard and 📅 Schedules pages

- **Job History & Logging**
  - Manual port cycles write to `job_runs` table (not just `audit_logs`)
  - Job entries show: **switch name + port number**, site name, source (Manual/Scheduled), duration, errors
  - Jobs created as "running" immediately, updated to success/failed on completion
  - Both manual and scheduled cycles use the same logging format

#### Active Schedules
- **Whitlock Mills** (`d30qi0tf`): 19 daily port cycle schedules, 3:00 AM–6:00 AM, 10 min apart
- **Whitlock2** (`1z02qot5`): 19 daily port cycle schedules, 3:00 AM–6:00 AM, 10 min apart

### 🚧 Known Issues

#### Site Selector Not Loading (Minor)
- **Workaround**: Hard refresh browser (Ctrl+Shift+R)
- **Impact**: Low — devices still load from default site

### 📋 TODO

#### Phase 4: Hardening & Deployment
- Retry logic for failed operations
- Rate limiting
- Backup/restore procedures

## Technical Stack

### Backend
- Python 3.13
- FastAPI 0.115.0
- SQLAlchemy 2.0.36 (async)
- httpx 0.28.0 (UniFi API client)
- APScheduler 3.10.4 (job scheduling)
- aiosqlite 0.20.0

### Frontend
- Vanilla JavaScript (ES6+)
- CSS3 with CSS variables
- No framework dependencies

### Database
- SQLite with async support
- Tables: schedules, job_runs, audit_logs, poe_schedules

## Configuration

### Environment Variables (.env)
```
UNIFI_BASE_URL=https://10.91.0.10:8443
UNIFI_USERNAME=unifiAPI
UNIFI_PASSWORD=*ZoEegqNY2ryj9Xwu
UNIFI_SITE=default
UNIFI_VERIFY_SSL=false
APP_HOST=0.0.0.0
APP_PORT=8000
DATABASE_URL=sqlite+aiosqlite:///./data/unifi_dashboard.db
```

## API Endpoints

### Devices
- `GET /api/sites` - List all sites
- `GET /api/devices?site={site}` - List devices
- `GET /api/devices/{id}?site={site}` - Get device details
- `GET /api/devices/{id}/ports?site={site}` - Get switch ports
- `POST /api/devices/reboot` - Reboot device
- `POST /api/devices/poe/control` - Control PoE mode
- `POST /api/devices/poe/power-cycle` - Power cycle PoE port
- `POST /api/devices/port/cycle` - Cycle port (PoE or full)

### Scheduler
- `GET /api/schedules` - List device reboot schedules
- `POST /api/schedules` - Create schedule
- `GET /api/schedules/{id}` - Get schedule
- `PUT /api/schedules/{id}` - Update schedule
- `DELETE /api/schedules/{id}` - Delete schedule
- `POST /api/schedules/{id}/toggle` - Enable/disable schedule
- `GET /api/jobs` - List job history
- `GET /api/jobs/{id}` - Get job details
- `GET /api/poe-schedules` - List port cycle schedules
- `POST /api/poe-schedules` - Create port cycle schedule
- `DELETE /api/poe-schedules/{id}` - Delete port cycle schedule
- `POST /api/poe-schedules/{id}/toggle` - Enable/disable port cycle schedule

## File Structure
```
/root/unifi-maintenance-dashboard/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Settings & validation
│   ├── database.py             # SQLAlchemy setup
│   ├── models.py               # Database models (Schedule, JobRun, AuditLog, PoESchedule)
│   ├── schemas.py              # Pydantic schemas
│   ├── logging_config.py       # Logging setup
│   ├── scheduler_engine.py     # APScheduler job execution engine
│   ├── unifi_client.py         # UniFi API client (port cycling, PoE, reboots)
│   └── routers/
│       ├── __init__.py
│       ├── devices.py          # Device endpoints + manual cycle job logging
│       └── scheduler.py        # Scheduler endpoints + job history
├── static/
│   ├── style.css               # Dashboard styles + port cycle timer CSS
│   ├── app.js                  # Dashboard JavaScript (device cards, port control, timer)
│   ├── schedules.css           # Schedules page styles + grouped card CSS
│   └── schedules.js            # Schedules page JS (grouped schedules, job history display)
├── templates/
│   ├── dashboard.html          # Main dashboard template
│   └── schedules.html          # Schedules management template
├── data/                       # SQLite database
├── logs/                       # Application logs
├── .env                        # Environment config
├── .env.example                # Environment template
├── requirements.txt            # Python dependencies
├── setup.sh                    # Setup script
├── test_unifi_connection.py    # Connection test
├── CLAUDE.md                   # This file — development notes
└── README.md                   # Documentation
```

## Known Issues

### Site Selector Not Updating
- **Symptom**: Dropdown shows "Loading sites..." indefinitely
- **API Status**: Working (curl returns all 102 sites)
- **JavaScript**: loadSites() function is called but dropdown doesn't update
- **Next Steps**: Check browser console for errors, verify DOM is ready

## Authentication Notes

### UniFi API Authentication
- Requires LOCAL admin account (not Ubiquiti Cloud/SSO)
- Current account: `unifiAPI` (local, remote access disabled)
- Authentication method: POST to `/api/login` with JSON credentials
- Session maintained via cookies

### Account Creation Process
- Initial attempt with `unifiALI` failed (was SSO account)
- Created local `unifiAPI` account with remote access disabled
- This resolved all authentication issues

## Development Commands

### Start Application (systemd — production)
```bash
systemctl start unifi-dashboard
systemctl status unifi-dashboard
journalctl -u unifi-dashboard -f    # live logs
```

### Start Application (manual — development)
```bash
cd /root/unifi-maintenance-dashboard
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Test UniFi Connection
```bash
source venv/bin/activate
python test_unifi_connection.py
```

### Tailscale Serve Management
```bash
tailscale serve status               # check current config
tailscale serve --bg http://127.0.0.1:8000   # start proxy
tailscale serve --https=443 off      # stop proxy
```

### Access Points
- **Dashboard (Tailscale)**: https://unifirebootmanager.tail7e0d.ts.net/
- **Dashboard (localhost)**: http://127.0.0.1:8000
- **API Docs**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc
- **Health check**: http://127.0.0.1:8000/health

## Deployment Architecture

### Network Access
- **uvicorn** binds to `127.0.0.1:8000` (localhost only — not reachable from LAN)
- **Tailscale serve** proxies `https://unifirebootmanager.tail7e0d.ts.net/` → `http://127.0.0.1:8000`
- Tailscale provides automatic HTTPS certs (Let's Encrypt via Tailscale)
- Only devices on the Tailscale tailnet can reach the dashboard
- No ports exposed to the public internet or LAN

### Systemd Service
- Unit file: `/etc/systemd/system/unifi-dashboard.service`
- Enabled on boot, auto-restarts on failure (5s delay)
- Depends on `tailscaled.service`
- Runs as root (needed for UniFi API access and Tailscale)

### Tailscale Serve
- Config persists across Tailscale restarts
- Serves HTTPS on port 443 via Tailscale's MagicDNS
- Proxies to plain HTTP on localhost:8000

## Notes for Future Development

- Consider adding WebSocket support for real-time device status
- Rolling reboots should wait for each device to come back online before proceeding
- Job history should be retained for audit purposes

---

## Latest Session Handoff (2026-02-25, evening)

### What Was Implemented This Session

#### Port Cycle UI Enhancements
- Added 🔄 Port Cycle button on every port (not just PoE ports)
- Added ⚡ PoE Cycle button on PoE ports
- Renamed "PoE Control" to "Port Control" in device cards
- Added visual **countdown timer** during port cycles:
  - Fixed progress bar at top of page with elapsed/total time
  - Status text updates through cycle phases (disabling → waiting → holding → re-enabling)
  - Green on success, red on failure, auto-dismiss after 10s

#### Port Schedule Grouping
- Port cycle schedules are now **grouped by site** in the Schedules UI
- One collapsible card per site instead of 19+ individual cards
- Click to expand → compact table with Name, Port, Time, Type, Enabled toggle, Edit/Delete
- Badges show total ports and active count per site

#### Job History Improvements
- Manual port cycles now write to `job_runs` table (previously only `audit_logs`)
- Job entries display: switch name + port number, friendly type label, source (👤 Manual / 🤖 Scheduled), 🌐 site name, formatted duration, error messages
- Both manual and scheduled cycles share the same logging format
- Jobs created as "running" immediately, updated on completion

#### Navigation
- Added 🏠 Dashboard and 📅 Schedules nav links to both pages

#### Bulk Schedule Creation
- Created 19 daily port cycle schedules for **Whitlock Mills** (`d30qi0tf`), 3:00–6:00 AM
- Created 19 daily port cycle schedules for **Whitlock2** (`1z02qot5`), 3:00–6:00 AM

### ✅ CRITICAL FIX: Port Cycle VLAN Restoration (2026-02-25)

#### Bug
When a port cycle failed (timeout) or completed, the port's VLAN was being set to "none" because:
1. The old code only saved 2 fields (`native_networkconf_id` and `name`) before disabling
2. The restore method hardcoded `forward: "all"`, but ports configured as `forward: "customize"` (custom VLAN profiles) lost their VLAN assignment
3. If the override's `native_networkconf_id` was empty (already modified by a prior failed cycle), the save captured empty string

#### Fix
- **Deep-copy the entire original `port_overrides` entry** before any changes
- **Restore it exactly** on re-enable or failure via `_restore_port_override()`
- Preserves: `forward` mode (customize/all), `native_networkconf_id`, `excluded_networkconf_ids`, `tagged_vlan_mgmt`, and all other fields
- Old `_enable_port_with_saved_config()` replaced with `_restore_port_override()`

### Port Cycling Architecture (Definitive)

#### How It Works
1. **Save**: Deep-copy entire `port_overrides` entry for the target port
2. **Disable**: Write full override with `forward: "disabled"`, `port_security_enabled: true`, `native_networkconf_id: ""`, `tagged_vlan_mgmt: "block_all"` — **no force-provision**
3. **Wait**: Poll every 10s for up to 3 min until `port_table[].up == false`
4. **Hold disabled**: Default 30 seconds
5. **Restore**: Put back the **exact original override** (preserves forward mode, VLAN, everything) — **no force-provision**
6. **Wait**: Poll every 10s for up to 5 min until `port_table[].up == true`
7. **On failure**: Same restore runs, so VLAN is always preserved

#### Critical Rules
- **Save the FULL override before disable** — not just individual fields
- **Restore the EXACT saved override** — do not reconstruct with hardcoded values
- **Do NOT use `force-provision`** — switch applies config via inform cycle
- **Full cycle takes 4-8 minutes** — normal for US8P60 on controller 10.0.162
- **Timeouts**: 3 min disable, 5 min re-enable, 10s poll interval

#### Key Methods in `unifi_client.py`
- `set_port_config()` — writes full port_overrides payload for disable
- `_restore_port_override()` — puts back exact saved override for re-enable/recovery
- `cycle_port()` — orchestrates save → disable → wait → hold → restore → wait
- `wait_for_port_state()` — polls port_table for link state changes

#### Code Path (shared by manual + scheduled)
```
Manual:  devices.py cycle_port endpoint → UniFiClient.cycle_port()
Sched:   scheduler_engine._execute_poe_schedule() → UniFiClient.cycle_port()
```
Both paths use the same `cycle_port()` method — fixes apply to both automatically.
