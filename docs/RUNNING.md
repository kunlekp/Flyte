# Running Flyte locally (VS Code)

This guide takes you from the zip file to a working app in your browser, then walks you
through a 5-minute demo. Commands are shown for **Windows (PowerShell)** first and
**macOS / Linux** second.

---

## 1. Install the tools (once)

| Tool | Where | Notes |
|---|---|---|
| Python 3.10 – 3.13 | python.org/downloads | On Windows, tick **"Add python.exe to PATH"** on the first installer screen |
| VS Code | code.visualstudio.com | |
| VS Code **Python** extension | Extensions panel (Ctrl+Shift+X), search "Python" by Microsoft | It installs the debugger too |
| Git (needed later for GitHub) | git-scm.com | Optional for running locally |

Check Python works by opening a new terminal and typing `python --version` (macOS: `python3 --version`).
On Windows, if typing `python` opens the Microsoft Store, reinstall Python from python.org with
"Add to PATH" ticked. Or turn off *Settings → Apps → Advanced app settings → App execution aliases → python.exe*.

---

## 2. Open the project

1. Unzip `flyte.zip` somewhere simple, e.g. `Documents\flyte`.
2. In VS Code: **File → Open Folder…** and pick the `flyte` folder (the one containing `app.py`).
3. Open a terminal inside VS Code: **Terminal → New Terminal** (Ctrl+`).

---

## 3. Create a virtual environment and install packages

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If PowerShell says *"running scripts is disabled on this system"*, run this once and try again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You know it worked when your prompt starts with `(.venv)`.
Then tell VS Code to use that Python: press **Ctrl+Shift+P → "Python: Select Interpreter"** and choose the
one that shows `.venv`.

Optional: copy the settings file so you can change things later.
```powershell
copy .env.example .env      # Windows
cp .env.example .env        # macOS / Linux
```

---

## 4. Start the app

Either press **F5** and choose **"Flyte: web app"**, or type:

```bash
python app.py
```

The first start prints `Seeding demo data – first run takes ~10 seconds…`. When you see
`Running on http://127.0.0.1:5000`, open that address in your browser.

The demo data is saved in `data/flyte.db`, so later starts are instant.

### Other things you can run

| What | Command | VS Code (F5 menu) |
|---|---|---|
| Original console menu (same database) | `python -m airline.cli` | "Flyte: console app (original UI)" |
| All 33 automated tests | `python -m unittest discover -s tests -v` | "Flyte: run tests" |
| Wipe and regenerate demo data | `python manage.py reset-demo` | Terminal → Run Task → "Reset demo data" |
| KPIs in the terminal | `python manage.py stats` | |

Stop the server with **Ctrl+C** in the terminal, or the red square in the debug toolbar.

---

## 5. A 5-minute demo script

Use this when presenting.

**As a traveller.** Log in with `ada@flyte.ng` / `Demo1234`.
1. **Home page.** Point out the animated route map and the "Leaving soon" cards. Each card shows how full the flight is and whether fares are rising.
2. Search **Lagos → Abuja**. Point out the **Our pick** card and its reason, then the row of airline cards: each airline's cheapest fare and how many bags it includes. Click one airline to filter, then **All airlines** to go back.
3. Click **Book this flight** on the pick. **Step 1, cabin:** switch between Economy, Business and First and watch the price on the right update.
4. **Step 2, seat:** click a window seat (A or F). Seats in other cabins are greyed out.
5. **Step 3, luggage:** press **+** twice. The airline's bag fee appears in the total on the right.
6. Point at the **Fare forecast** card ("Book now: fares likely up X% within 3 days").
7. **Step 4:** add Basic Medical cover. **Step 5:** click the *declined* test card and Pay to show the error, then the *approved* card and Pay. You get confetti and a boarding pass showing the airline and your checked bags.
8. **Back on the home page, pick Return**, choose Lagos → Abuja and two dates, then **Use our picks** and **Continue**. Point out the 8% return discount, pick a seat on each flight, pay once, and show the trip page with both flights.
9. **My trips → Lagos to Abuja** (tomorrow's Lagoon Airways flight). Click **Check in now** to get a boarding group.
10. **Miles:** the tier ring and stats.

**As ops staff.** Log out, then log in with `admin@flyte.ng` / `FlyteAdmin2026`.
1. **Insights:** walk through the KPI tiles and the 30-day comparisons, then the **Airlines on Flyte** table (cheap airlines fill more seats; the premium one runs most on time).
2. **Demand forecast:** the dashed line is the model and the shaded band is the 80% range. The Model card shows its backtest error.
3. **When people book / What they pay:** booking early is cheaper. This is the dynamic pricing at work.
4. **Customer segments:** the four groups found by K-means.
5. **Departures board** (split-flap animation) and **Flights selling slowly.**
6. **Flights tab:** open *Manage* on a flight, set a 30-minute delay, then cancel a flight to show automatic refunds.
7. **Export bookings CSV** and open it in Excel or Jupyter.

---

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: flask` (or pandas) | The virtual environment isn't active. Run the activate command again and check VS Code's interpreter is `.venv` |
| `Address already in use` / port 5000 busy | Another app is using port 5000 (on macOS it's often AirPlay). Run `$env:PORT=5050; python app.py` (PowerShell) or `PORT=5050 python app.py` |
| Fonts look plain | You're offline. The app falls back to system fonts and still works |
| Boarding pass shows the reference instead of a QR code | `segno` isn't installed. Run `pip install -r requirements.txt` again |
| Want fresh demo data | `python manage.py reset-demo` (stop the server first) |
| Times look an hour off | Set `APP_TIMEZONE` in `.env` (default `Africa/Lagos`) |
| Changed a CSS/JS file but nothing changed | Hard refresh: Ctrl+F5 (Cmd+Shift+R on macOS) |
