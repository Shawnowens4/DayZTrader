# DayZ Trader Bot 🦖

A full-featured Discord bot for DayZ console servers — shop, economy, casino, raffle, player marketplace, CE delivery queue, and a Flask web dashboard.

## Quick Links
- [Local Setup](#local-setup)
- [Cloudflare Tunnel (public dashboard)](#cloudflare-tunnel-setup)
- [Bot Commands](#bot-commands)
- [Configuration](#configuration)

---

## Project Structure

```
DayZTrader/
├── main.py                  # Bot entry point
├── requirements.txt
├── .env.example             # Copy to .env and fill in secrets
├── config/
│   └── settings.yaml          # Bot settings (prefix, roles, channels)
├── bot/
│   ├── cogs/                  # Discord slash-command cogs
│   │   ├── admin.py
│   │   ├── casino.py
│   │   ├── market.py
│   │   ├── raffle.py
│   │   └── trader.py
│   └── services/              # Business logic layer
│       ├── casino.py
│       ├── delivery.py
│       ├── delivery_queue.py
│       ├── economy.py
│       ├── market.py
│       ├── raffle.py
│       ├── security.py
│       └── shop.py
├── db/
│   └── schema.sql             # SQLite schema (run once on first start)
├── web/
│   ├── app.py                 # Flask API + dashboard server
│   ├── templates/
│   │   ├── dashboard.html
│   │   └── map.html
│   └── static/
├── cloudflared/
│   ├── tunnel.yml             # Cloudflare tunnel config template
│   └── README.md
├── setup.ps1               # Windows one-click setup
└── manage.ps1              # Windows start/stop/restart helpers
```

---

## Local Setup

### Prerequisites
- Python 3.11 or 3.12 (3.13 not yet supported by discord.py)
- Git
- A Discord Application + Bot token ([Discord Developer Portal](https://discord.com/developers/applications))

### Step 1 — Clone the repo
```bash
git clone https://github.com/Shawnowens4/DayZTrader.git
cd DayZTrader
git checkout main-clean
```

### Step 2 — Create virtual environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Configure environment
```bash
# Copy the example and fill in your values
cp .env.example .env
notepad .env        # Windows
nano .env           # Linux/macOS
```

Required `.env` values:
```
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_discord_server_id
WEB_API_KEY=choose_a_strong_random_key
FLASK_PORT=5000
```

### Step 5 — Review config/settings.yaml
Edit `config/settings.yaml` to set your admin role name, log channel name,
announcement channel, and other server-specific settings.

### Step 6 — Initialize the database
```bash
# The bot auto-creates the DB on first run, but you can also run manually:
sqlite3 db/trader.db < db/schema.sql
```

### Step 7 — Start the bot
```bash
# Bot only
python main.py

# Web dashboard only (separate terminal)
python web/app.py

# Both together (Windows PowerShell)
.\manage.ps1 start
```

The dashboard will be available at `http://localhost:5000`

---

## Cloudflare Tunnel Setup

Cloudflare Tunnel lets you expose your local Flask dashboard to the internet
with HTTPS, **without opening any firewall ports or having a static IP**.

### Why Cloudflare Tunnel?
- Free with a Cloudflare account
- Auto-HTTPS (no certificate needed)
- Hides your real IP
- Works through CGNAT (common with ISPs)
- Survives reboots with a system service

---

### Part 1 — Cloudflare Account & Domain

1. Go to [cloudflare.com](https://cloudflare.com) and create a **free account**.
2. Add your domain to Cloudflare **or** use a free subdomain via Cloudflare for Teams.
   - If you don’t own a domain, you can use a `*.trycloudflare.com` temporary URL
     (no account needed, see Quick Test below).

---

### Part 2 — Install cloudflared

**Windows:**
```powershell
# Option A — winget (recommended)
winget install Cloudflare.cloudflared

# Option B — direct download
# Download from: https://github.com/cloudflare/cloudflared/releases/latest
# Get: cloudflared-windows-amd64.exe
# Rename to cloudflared.exe and place in C:\Windows\System32\ or add to PATH
```

**Ubuntu / Debian Linux:**
```bash
# Add Cloudflare GPG key and apt repo
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | sudo tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null

echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] \
https://pkg.cloudflare.com/cloudflared any main' \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list

sudo apt update && sudo apt install cloudflared
```

**macOS:**
```bash
brew install cloudflared
```

Verify installation:
```bash
cloudflared --version
# cloudflared version 2024.x.x
```

---

### Part 3 — Authenticate cloudflared to your Cloudflare account

```bash
cloudflared tunnel login
```

This opens a browser window. Log in to Cloudflare, then select the domain
you want to use. A credentials file is saved to `~/.cloudflared/cert.pem`.

---

### Part 4 — Create the tunnel

```bash
cloudflared tunnel create dayztrader
```

Output will include a **Tunnel UUID** like:
```
Created tunnel dayztrader with id a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

A credentials JSON file is written to:
- Windows: `C:\Users\YOU\.cloudflared\a1b2c3d4-....json`
- Linux/macOS: `~/.cloudflared/a1b2c3d4-....json`

Copy that JSON file into your project:
```bash
# Windows (PowerShell)
Copy-Item "$env:USERPROFILE\.cloudflared\a1b2c3d4-....json" .\cloudflared\

# Linux / macOS
cp ~/.cloudflared/a1b2c3d4-....json ./cloudflared/
```

> **Important:** The `.json` credentials file is in `.gitignore` —
> never commit it to the repo, it contains your private tunnel key.

---

### Part 5 — Edit the tunnel config

Open `cloudflared/tunnel.yml` and replace the placeholders:

```yaml
tunnel: a1b2c3d4-e5f6-7890-abcd-ef1234567890
credentials-file: /full/path/to/DayZTrader/cloudflared/a1b2c3d4-....json

ingress:
  - hostname: dashboard.yourdomain.com
    service: http://localhost:5000
  - service: http_status:404
```

- `tunnel:` → your Tunnel UUID
- `credentials-file:` → **absolute path** to the `.json` file you copied in
- `hostname:` → the subdomain you want (e.g., `dashboard.yourdomain.com`)

---

### Part 6 — Add DNS record in Cloudflare

```bash
cloudflared tunnel route dns dayztrader dashboard.yourdomain.com
```

This creates a CNAME record in your Cloudflare DNS pointing
`dashboard.yourdomain.com` → your tunnel.

Verify it appears in your Cloudflare dashboard under **DNS → Records**.

---

### Part 7 — Run the tunnel

**One-time test (foreground):**
```bash
# Make sure Flask is already running in another terminal first!
cloudflared tunnel --config cloudflared/tunnel.yml run
```

You should see:
```
INF Connection a1b2c3d4 registered connIndex=0 ip=198.41.x.x
```

Now visit `https://dashboard.yourdomain.com` — it routes to your local
Flask server!

---

### Part 8 — Run as a persistent background service

So the tunnel survives reboots:

**Windows (runs as a Windows Service):**
```powershell
# Run as Administrator
cloudflared service install --config C:\full\path\to\DayZTrader\cloudflared\tunnel.yml
Net-Service cloudflared start
# Verify
Get-Service cloudflared
```

To stop/remove:
```powershell
Net-Service cloudflared stop
cloudflared service uninstall
```

**Linux (systemd service):**
```bash
# Copy config to the system location cloudflared expects
sudo mkdir -p /etc/cloudflared
sudo cp cloudflared/tunnel.yml /etc/cloudflared/config.yml
sudo cp cloudflared/*.json /etc/cloudflared/

# Install and enable
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared

# Check status
sudo systemctl status cloudflared
journalctl -u cloudflared -f
```

---

### Quick Test (No domain needed)

If you just want to test publicly without a domain:
```bash
# Make sure Flask is running first, then:
cloudflared tunnel --url http://localhost:5000
```

Cloudflare gives you a temporary public URL like:
```
https://random-words-here.trycloudflare.com
```
This works for testing but the URL changes every time you restart.

---

### Running Everything Together (Windows)

The `manage.ps1` script handles starting both the bot and Flask:
```powershell
.\manage.ps1 start      # Start bot + web server
.\manage.ps1 stop       # Stop all
.\manage.ps1 restart    # Restart all
.\manage.ps1 status     # Show running processes
```

For the tunnel, run it separately in a third terminal:
```powershell
cloudflared tunnel --config cloudflared/tunnel.yml run
```
Or set it up as a Windows Service (see Part 8) so it runs automatically.

---

### Securing the Dashboard

The dashboard is protected by an API key (`WEB_API_KEY` in `.env`).
All admin endpoints require the `X-API-Key` header.

For extra protection, consider adding **Cloudflare Access** (free):
1. In Zero Trust dashboard → **Access → Applications → Add an application**
2. Select your tunnel hostname
3. Add a policy (e.g., email allowlist or One-Time PIN)

This adds a login page in front of your entire dashboard.

---

## Bot Commands

| Command | Description |
|---------|-------------|
| `/buy` | Purchase items from the shop |
| `/shop` | Browse available items |
| `/balance` | Check your credit balance |
| `/daily` | Claim daily credits |
| `/blackjack` | Play blackjack |
| `/poker` | Play Texas Hold’em vs AI |
| `/slots` | Play slot machines |
| `/roulette` | Play roulette |
| `/horse_race` | Bet on a horse race |
| `/raffle` | Enter/info/odds for the weekly car raffle |
| `/market` | List/buy/sell in the player marketplace |
| `/admin` | Admin-only management commands |

---

## Configuration

All server-specific settings live in `config/settings.yaml`:

```yaml
bot:
  prefix: "!"
  admin_role: "Admin"           # Discord role name for admin commands
  log_channel: "admin-logs"     # Channel for admin/audit logs
  announcement_channel: "general"
  guild_id: 0                   # Your Discord server ID

economy:
  starting_balance: 1000
  daily_amount: 250
  max_balance: 10000000

shop:
  max_purchase_quantity: 10
  delivery_timeout_seconds: 7200
```

---

## Troubleshooting

**Bot won’t start — `ModuleNotFoundError`**
```bash
# Make sure your venv is active and dependencies are installed
pip install -r requirements.txt
```

**`OperationalError: no such column: job_type`**
```bash
# Re-run the schema (safe, uses IF NOT EXISTS)
sqlite3 db/trader.db < db/schema.sql
# Or delete the old DB to start fresh (LOSES ALL DATA):
rm db/trader.db && python main.py
```

**Cloudflare tunnel shows `ERR_CONNECTION_REFUSED`**
- Make sure Flask (`web/app.py`) is running **before** starting the tunnel
- Confirm Flask is listening on port 5000: `netstat -an | grep 5000`
- Check the `service: http://localhost:5000` line in `tunnel.yml`

**Slash commands not showing in Discord**
- The bot syncs commands on startup; wait up to 1 hour for global sync
- For instant sync on a single server, check `main.py` for guild-scoped sync

**`Unauthorized` on web API calls**
- Every protected endpoint needs header: `X-API-Key: your_key_from_.env`
