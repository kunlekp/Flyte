# Uploading Flyte to GitHub and deploying it

Part 1 puts your code on GitHub. Part 2 puts the app online. Part 3 lists what still
separates the deployed app from a real airline product.

Hosting prices and limits below were checked in October 2026. Re-check the provider's
pricing page before you pay for anything.

---

## Part 1: Upload to GitHub

### What gets uploaded (and what doesn't)
The included `.gitignore` already keeps these **out** of GitHub:
- `.venv/`: your installed packages. Anyone can recreate them from `requirements.txt`.
- `data/`: the database and email outbox. These contain passenger data, so never commit them.
- `.env`: your secrets (SECRET_KEY, admin password, SMTP password).

### Option 1: Easiest, from inside VS Code
1. Create a free account at github.com if you don't have one.
2. In VS Code, click the **Source Control** icon on the left (or press Ctrl+Shift+G).
3. Click **Publish to GitHub**. Sign in when the browser opens, then choose **Public** (for a portfolio) or **Private**.
4. VS Code creates the repository, makes the first commit and uploads everything.
5. For later changes, type a message in the Source Control box, click **✓ Commit**, then **Sync Changes**.

### Option 2: Command line
1. On github.com click **New repository**. Name it `flyte`, leave *"Add a README"* **unticked** (you already have one), and click **Create repository**.
2. In the VS Code terminal, inside the `flyte` folder:

```bash
git init
git add .
git commit -m "Flyte: airline booking + analytics web app"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/flyte.git
git push -u origin main
```

3. If Git asks for a password, a normal GitHub password won't work. Either:
   - install **GitHub CLI** and run `gh auth login`, or
   - create a **Personal access token** (GitHub → Settings → Developer settings → Personal access tokens → Fine-grained) with *Contents: Read and write* on this repo, and paste it as the password.

4. After any change:
```bash
git add .
git commit -m "Describe what you changed"
git push
```

### After the first push
- Open the **Actions** tab on GitHub. The included workflow (`.github/workflows/tests.yml`) runs all tests on every push. A green tick means everything passed. Add the badge to your README for a portfolio touch.
- Before pushing, run `git status` and make sure `data/` and `.env` are not listed.

---

## Part 2: Deploy online

The app keeps its data in memory and writes it through to a SQLite file. That means **two hard
requirements** for any host:

1. **A disk that survives restarts.** Otherwise every booking is lost when the server restarts.
2. **Exactly one app process (worker).** Threads are fine. Two workers would each keep their own copy of the data.

| Option | Cost | Disk survives restarts? | Best for |
|---|---|---|---|
| **A. PythonAnywhere** | Free tier | Yes | Free demo link for your CV or a class presentation |
| **B. Render** | $7/month instance + $0.25/GB/month disk | Yes (paid only) | A real always-on deployment from GitHub |
| **C. Docker / any VPS** | Varies | Yes, with a volume | Full control |

**Avoid free hosts with temporary storage** (for example Render's free instances). They delete
local files on redeploy, restart or spin-down, so all bookings would disappear.

---

### Option A: PythonAnywhere (free)

Free accounts currently include one web app with a single worker (which suits Flyte), 512 MiB
of storage, and HTTPS on `yourname.pythonanywhere.com`. Free web apps **expire after one
month** unless you log in and extend them from the **Web** tab. Free accounts also limit
outgoing internet access, so real email may not send. Emails stay in `data/outbox.log`.

1. **Sign up** at pythonanywhere.com (Beginner/free account).
2. Open **Consoles → Bash** and get your code:
   ```bash
   git clone https://github.com/YOUR-USERNAME/flyte.git
   cd flyte
   ```
   (For a private repo, use a personal access token as the password, or upload the zip on the **Files** tab and run `unzip flyte.zip`.)
3. **Create a virtual environment.** Use the newest `python3.x` PythonAnywhere offers. `--system-site-packages` reuses their pre-installed pandas and numpy, which saves most of your 512 MiB:
   ```bash
   mkvirtualenv --system-site-packages --python=/usr/bin/python3.12 flyte-venv
   pip install -r requirements.txt
   ```
4. **Create your settings file:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   Set at least:
   ```ini
   APP_ENV=production
   SECRET_KEY=<paste output of: python -c "import secrets; print(secrets.token_hex(32))">
   FLASK_DEBUG=0
   SEED_DEMO=1                # keep 1 for a demo site with sample data; 0 for an empty real one
   ADMIN_EMAIL=you@example.com
   ADMIN_PASSWORD=<a strong password>
   ```
   Save with Ctrl+O, Enter, Ctrl+X.
5. **Build the database now** so the website doesn't time out building it on first visit:
   ```bash
   python manage.py reset-demo        # demo data (or skip this if SEED_DEMO=0)
   python manage.py create-admin you@example.com "your-strong-password"
   ```
6. On the **Web** tab click **Add a new web app → Manual configuration** and pick the same Python version.
7. On the web app's page:
   - **Virtualenv:** `/home/YOURUSERNAME/.virtualenvs/flyte-venv`
   - **Source code:** `/home/YOURUSERNAME/flyte`
   - **WSGI configuration file:** click the link, delete everything, and paste the contents of `deploy/pythonanywhere_wsgi.py` (change `YOURUSERNAME`).
   - **Static files:** URL `/static/` → Directory `/home/YOURUSERNAME/flyte/web/static`
   - **Force HTTPS:** turn on.
8. Click the big green **Reload** button and open `https://YOURUSERNAME.pythonanywhere.com`.

**To update after you push new code:**
```bash
cd ~/flyte && git pull && workon flyte-venv && pip install -r requirements.txt
```
Then click **Reload** on the Web tab.

**If something breaks,** the **Error log** link on the Web tab shows the Python traceback.
A `RuntimeError: Production settings incomplete` means `.env` is missing `SECRET_KEY` or the admin details.

> With `SEED_DEMO=1` the demo accounts (`admin@flyte.ng` / `FlyteAdmin2026`) exist and are shown on the
> login page. That's fine for a showcase. For anything real, set `SEED_DEMO=0`, delete `data/flyte.db`,
> and use your own admin.

---

### Option B: Render (paid, deploys from GitHub)

The repo includes `render.yaml`, which describes the whole service: one gunicorn worker,
health check, a 1 GB persistent disk at `/var/data`, and a generated `SECRET_KEY`.

1. Push the code to GitHub (Part 1).
2. At render.com: **New → Blueprint**, connect GitHub and pick the `flyte` repo.
3. Render reads `render.yaml`. When asked, fill in `ADMIN_EMAIL` and `ADMIN_PASSWORD`.
4. Click **Apply**. The first build takes a few minutes. Your app appears at `https://flyte-xxxx.onrender.com`.
5. Every `git push` to `main` redeploys automatically. The database on `/var/data` is kept between deploys.

To launch with an empty database instead of demo data, change `SEED_DEMO` to `"0"` in the Render dashboard.
To add your own domain: **Settings → Custom Domains**.

---

### Option C: Docker (any VPS or cloud)

```bash
docker build -t flyte .
docker run -d -p 80:8000 \
  -e SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
  -e ADMIN_EMAIL=you@example.com -e ADMIN_PASSWORD='strong-password' \
  -e DATABASE_URL=sqlite:////app/data/flyte.db \
  -v flyte-data:/app/data --restart unless-stopped flyte
```
Put a reverse proxy with HTTPS in front of it (Caddy is the simplest), and keep `--workers 1`.

---

## Part 3: Limitations before it's a fully functional airline product

The deployed app works end to end: search, book, pay (test mode), check in, cancel with
refund, and the admin dashboards. These are the gaps between that and real customers paying
real money, roughly in order of importance.

| # | Limitation | Why it matters | What to do |
|---|---|---|---|
| 1 | **Payments are simulated** (`MockPaymentGateway`) | No money moves. The card form also sends card numbers to your server, which a live site must never do (PCI-DSS) | Write a `PaystackGateway(PaymentGateway)` class using Paystack's hosted checkout (initialize transaction → redirect → verify on callback/webhook), so cards never touch your server. Needs a registered business and Paystack keys |
| 2 | **Single process, SQLite** | Fine for hundreds of users a day. It can't run more than one worker or server | Add a `PostgresStorage(StorageBackend)` and load per request (or cache with invalidation). The abstract `StorageBackend` was designed for exactly this swap |
| 3 | **Fictional airlines, no real inventory** | Harmattan Air, Lagoon Airways, Savannah Express and Zuma Jet are made-up demo carriers with made-up prices. Flights are whatever an admin types in, with no link to real schedules | Real airlines connect to a PSS/GDS (e.g. Amadeus, Sabre, Navitaire). This is a business partnership, not just code |
| 4 | **Email is a log file unless SMTP is set** | Customers won't get confirmations | Set `SMTP_*` env vars, or use a transactional email service (Brevo, Postmark, SES) |
| 5 | **No password reset or email verification** | Users who forget their password are stuck | Add a reset-token flow (needs #4) |
| 6 | **Demo data and demo admin** when `SEED_DEMO=1` | The demo admin password is public | Use `SEED_DEMO=0` and your own admin for any real launch |
| 7 | **One passenger per booking** | No booking for family or friends, no infant fares, no return trips in one checkout | Extend `Booking` into a `Reservation` with multiple `Ticket`s |
| 8 | **Backups are manual** | A disk failure loses everything | Schedule a daily copy of `flyte.db` (Render and PythonAnywhere both let you download files; Postgres hosts back up automatically) |
| 9 | **Legal and privacy** | You store names, passport numbers and phone numbers. Nigeria's Data Protection Act (NDPA) applies | Add a privacy policy, terms, data-deletion on request, and encrypt the disk |
| 10 | **Basic monitoring** | You'll only notice crashes if you check the logs | Add an error tracker (e.g. Sentry free tier) and uptime pings to `/api/health` |
| 11 | **Free PythonAnywhere quirks** | The app expires monthly, CPU is limited and outgoing internet is restricted | Fine for a demo. Upgrade or move to Option B for anything real |

**Already handled:** hashed passwords, CSRF tokens, login rate-limiting, a strict
Content-Security-Policy, secure cookies in production, open-redirect protection, server-side
pricing (the browser can't change the price), seat double-booking protection, refusal to
start in production without a proper `SECRET_KEY`, correct Lagos time on UTC servers,
a health-check endpoint, and automated tests on every push.
