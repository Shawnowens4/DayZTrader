# DXEMB - DayZ Xbox Escrow Marketplace Bot

## Browser Demo and Hosting

DXEMB currently supports a local Docker-based web baseline with PostgreSQL and
the Flask admin surface. The least invasive supported Phase 1 startup path is
to run the database and web services only.

### Local browser demo

Windows PowerShell with Docker Desktop in Linux-container mode:

```powershell
Copy-Item .env.example .env
docker compose up -d --build db web
.\scripts\web_smoke.ps1
```

Open `http://localhost:5000/`. The dashboard and top navigation link directly
to the catalog, vehicles, demo player wallet, admin wallet, operations evidence,
and map preview. The query-string identities are deliberately local-safe demo
hints, not production authentication. Stop with `docker compose down`.

The bot is not required for the browser demo.

### Hosted browser demo

On a Docker host, create the server environment and validate it before startup:

```powershell
Copy-Item .env.host.example .env.host
# Edit .env.host and replace every CHANGE_ME value.
.\scripts\host_preflight.ps1
docker compose --env-file .env.host -f docker-compose.host.yml up -d --build
docker compose --env-file .env.host -f docker-compose.host.yml ps
.\scripts\web_smoke.ps1 -BaseUrl http://127.0.0.1:5000
```

The host Compose file starts only PostgreSQL and the browser-facing web app. It
does not publish PostgreSQL, does not mount source code into the web container,
and binds the web port to `127.0.0.1:5000` by default for a same-host reverse
proxy. Data persists in the `dxemb_host_db_data` volume. Normal
`docker compose ... down` does not delete that volume.

Required values are in `.env.host`:

- `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`
- `DATABASE_URL`, using the same credentials and `db` as the hostname
- `WEB_BIND_ADDRESS` and `WEB_PORT` for the reverse-proxy upstream

Do not commit `.env.host`. If the password contains URL-special characters,
URL-encode it only in `DATABASE_URL`.

### `tz420.ninja` reverse proxy

Point the DNS `A`/`AAAA` record for `tz420.ninja` (or a demo subdomain) at the
server. Terminate HTTPS in Caddy, Nginx, or the existing host proxy and forward
to `http://127.0.0.1:5000`. Keep port 5000 and PostgreSQL closed externally;
publish only ports 80/443 through the proxy.

Minimal Caddy site block:

```caddyfile
tz420.ninja {
    reverse_proxy 127.0.0.1:5000
}
```

After DNS and TLS are active:

```powershell
.\scripts\web_smoke.ps1 -BaseUrl https://tz420.ninja
```

### Verification

`.\scripts\web_smoke.ps1` verifies the health endpoint and every main browser
demo page. `.\scripts\host_preflight.ps1` validates placeholders and hosted
Compose without changing containers.

### Local release acceptance gate

From PowerShell, run `.\scripts\local_acceptance.ps1`. The command validates
the Compose configuration, starts the existing PostgreSQL service without
resetting its volume, waits for readiness, runs harness and schema smoke checks,
and runs the broad web regression suite. It exits nonzero on any failure and
leaves the database service running for inspection; use `docker compose down`
when finished.

### Safety notes

- This Phase 1 baseline does not change vehicle compatibility approvals.
- Blocked/review-required compatibility records remain blocked.
- Role and player query hints are local demo conveniences, not production auth.
- Put the site behind access control at the reverse proxy if it is reachable
  from the public internet.

See `docs/TODO_ROADMAP.md` for the current local-release roadmap.
