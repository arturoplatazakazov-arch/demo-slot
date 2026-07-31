# Deploying the demo slots (embed profile)

The games are a **static frontend** (`front/`) that talks to a **FastAPI backend**
(`app/`). To embed them on a site you host both:

- `front/` → **GitHub Pages** (static, free)
- `app/` → **Railway** (one container, SQLite on a volume)

Local development is unchanged: without the production env vars the app keeps its
Postgres defaults, and the games auto-target `http://127.0.0.1:8000`.

---

## 1. Backend on Railway (SQLite, single container)

1. New Railway project → **Deploy from GitHub repo** (it builds from `Dockerfile`,
   which runs `alembic upgrade head` then serves on `$PORT` via `scripts/start.sh`).
2. Add a **Volume** mounted at `/data` (SQLite lives here so it survives redeploys).
3. Set **Variables** (see `.env.production.example`):
   ```
   ENVIRONMENT=production
   DEBUG=false
   DATABASE_URL=sqlite+aiosqlite:////data/demo.db
   DATABASE_URL_SYNC=sqlite:////data/demo.db
   DEFAULT_CURRENCY=FUN
   DEFAULT_STARTING_BALANCE=1000000
   CORS_ALLOW_ORIGINS=https://YOUR_GH_USERNAME.github.io
   CORS_ALLOW_ORIGIN_REGEX=
   ```
   (four slashes in the SQLite URLs = absolute path `/data/demo.db`)
4. Deploy. Note the public URL, e.g. `https://demo-slot-production.up.railway.app`.
5. Smoke test: `curl https://<railway-url>/health` → `{"status":"ok",...}`.

## 2. Point the frontend at the backend

Edit **one file** — `front/js/config.js`:
```js
window.SLOT_CONFIG = {
  apiBaseUrl: 'https://demo-slot-production.up.railway.app/api/v1',
};
```
(The `?api=<url>` query string overrides this for ad-hoc testing.)

## 3. Frontend on GitHub Pages

1. Push the repo (or just `front/`) to GitHub.
2. Settings → Pages → deploy from branch, folder = `/front` (or move `front/`
   contents to the Pages root).
3. Your games are at `https://YOUR_GH_USERNAME.github.io/east-discovery.html`, etc.
4. Confirm `CORS_ALLOW_ORIGINS` on Railway matches this exact origin.

## 4. Embed on your site

```html
<iframe src="https://YOUR_GH_USERNAME.github.io/east-discovery.html"
        style="width:100%;aspect-ratio:16/9;border:0"
        allowfullscreen></iframe>
```

---

## What the embed profile does automatically

- **Dev panels** (mode toggle, forced Big/Epic/Mega Win, feature-buy) are hidden on
  any non-localhost origin. Force with `?dev=1` / `?dev=0`.
- **Fonts** are self-hosted from `front/fonts/` (no Google Fonts CDN dependency).
- **Migrations** run on container boot; SQLite schema is created on first deploy.

## Cost note (cheapest Railway)

One container + a small volume fits the Hobby ($5) plan for low-traffic demo use.
There is no separate Postgres service to pay for in this profile.
