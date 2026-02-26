# UniFi Maintenance Dashboard

A self-hosted web application for managing and maintaining UniFi network devices. Schedule automated reboots, power cycle PoE ports, and monitor device status from a clean web interface.

## Features

- 📊 **Device Dashboard** - View all UniFi switches, APs, and devices
- 🔄 **Manual Reboots** - Reboot devices on demand
- ⚡ **PoE Power Cycling** - Power cycle individual switch ports
- 📅 **Scheduled Maintenance** - Rolling reboots with configurable schedules
- 📝 **Audit Logging** - Track all manual and automated actions
- 🔍 **Device Monitoring** - Real-time online/offline status
- 🎯 **Rolling Mode** - Reboot devices one at a time, waiting for each to return

## Requirements

- Python 3.10+
- UniFi Network Controller (self-hosted)
- Linux LXC container or VM (recommended)
- Local network access to UniFi controller

## Quick Start

### 1. Clone and Setup

```bash
cd /root/unifi-maintenance-dashboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
nano .env
```

Edit the following required values:
- `UNIFI_BASE_URL` - Your UniFi controller URL (e.g., https://192.168.1.10:8443)
- `UNIFI_USERNAME` - UniFi admin username
- `UNIFI_PASSWORD` - UniFi admin password
- `UNIFI_SITE` - Site name (usually "default")
- `TZ` - Your timezone

### 3. Test Connection

```bash
python test_unifi_connection.py
```

This will verify your UniFi controller credentials and list all devices.

### 4. Run the Application

```bash
# Development mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5. Access Dashboard

Open your browser to: `http://your-lxc-ip:8000`

## Project Structure

```
unifi-maintenance-dashboard/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration and environment validation
│   ├── database.py          # SQLAlchemy database setup
│   ├── models.py            # Database models
│   ├── schemas.py           # Pydantic schemas for API
│   ├── unifi_client.py      # UniFi API client wrapper
│   ├── scheduler.py         # APScheduler job management
│   └── routers/
│       ├── __init__.py
│       ├── devices.py       # Device management endpoints
│       ├── schedules.py     # Schedule management endpoints
│       └── jobs.py          # Job history endpoints
├── static/                  # Frontend assets (CSS, JS)
├── templates/               # HTML templates
├── data/                    # SQLite database (auto-created)
├── logs/                    # Application logs (auto-created)
├── .env                     # Your configuration (DO NOT COMMIT)
├── .env.example             # Example configuration
├── requirements.txt         # Python dependencies
├── test_unifi_connection.py # Connection test script
└── README.md
```

## Configuration Options

See `.env.example` for all available configuration options.

### Key Settings

- **UNIFI_VERIFY_SSL**: Set to `false` for self-signed certificates (development only)
- **DEVICE_ONLINE_TIMEOUT**: Max seconds to wait for device to come back online (default: 300)
- **DEVICE_REBOOT_DELAY**: Seconds to wait between rolling reboots (default: 300)
- **POE_POWER_OFF_DURATION**: Seconds to keep PoE off during power cycle (default: 15)

## Deployment (LXC Container)

### Create LXC Container

```bash
# On Proxmox or LXC host
pct create 200 local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst \
  --hostname unifi-dashboard \
  --memory 2048 \
  --cores 2 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --storage local-lvm \
  --rootfs local-lvm:8

pct start 200
pct enter 200
```

### Install Dependencies

```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git
```

### Setup Application

```bash
cd /root
git clone <your-repo> unifi-maintenance-dashboard
cd unifi-maintenance-dashboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # Configure your settings
```

### Create Systemd Service

```bash
nano /etc/systemd/system/unifi-dashboard.service
```

```ini
[Unit]
Description=UniFi Maintenance Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/unifi-maintenance-dashboard
Environment="PATH=/root/unifi-maintenance-dashboard/venv/bin"
ExecStart=/root/unifi-maintenance-dashboard/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable unifi-dashboard
systemctl start unifi-dashboard
systemctl status unifi-dashboard
```

### View Logs

```bash
journalctl -u unifi-dashboard -f
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://your-ip:8000/docs
- **ReDoc**: http://your-ip:8000/redoc

## Security Notes

### Development
- Default setup allows LAN access without authentication
- Self-signed SSL certificates are accepted (UNIFI_VERIFY_SSL=false)

### Production Recommendations
1. **Add authentication** (implement in Phase 4)
2. **Use Tailscale** for secure remote access
3. **Enable SSL verification** once you have proper certificates
4. **Change APP_SECRET_KEY** to a random value
5. **Restrict firewall** to only allow Tailscale network

## Backup

### Backup Database and Config

```bash
tar -czf unifi-dashboard-backup-$(date +%Y%m%d).tar.gz \
  /root/unifi-maintenance-dashboard/.env \
  /root/unifi-maintenance-dashboard/data/
```

### Restore

```bash
tar -xzf unifi-dashboard-backup-YYYYMMDD.tar.gz -C /
systemctl restart unifi-dashboard
```

## Troubleshooting

### Can't connect to UniFi controller

1. Verify controller URL and credentials in `.env`
2. Check network connectivity: `ping <controller-ip>`
3. Test with: `python test_unifi_connection.py`
4. Check SSL settings: `UNIFI_VERIFY_SSL=false` for self-signed certs

### Devices not showing up

1. Verify site name in `.env` (usually "default")
2. Check UniFi controller is adopted devices
3. Review logs: `tail -f logs/unifi_dashboard.log`

### Scheduled jobs not running

1. Check `SCHEDULER_ENABLED=true` in `.env`
2. Verify timezone setting matches your location
3. Check logs for scheduler errors

## License

MIT License - Use freely for personal or commercial projects.

## Support

For issues or questions, check the logs first:
```bash
tail -f logs/unifi_dashboard.log
```
