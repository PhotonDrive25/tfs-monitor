# TFS Competitor Monitor — Setup Guide

## What this does
Automatically scrapes The Perfume Shop, Boots, and Superdrug every morning at 8am.
Results are saved and shown on a dashboard you can open on your phone.
**Total cost: £0. Runs forever for free on GitHub.**

---

## Setup (takes about 10 minutes)

### Step 1 — Create a GitHub account
1. Go to **github.com**
2. Click **Sign up** — use any email
3. Verify your email

### Step 2 — Create a new repository
1. Once logged in, click the **+** icon (top right) → **New repository**
2. Name it: `tfs-monitor`
3. Set it to **Public** *(required for free GitHub Pages)*
4. Tick **Add a README file**
5. Click **Create repository**

### Step 3 — Upload the files
Upload these files maintaining the folder structure:

```
tfs-monitor/
├── scraper.py
├── requirements.txt
├── data/
│   └── results.json
├── docs/
│   └── index.html
└── .github/
    └── workflows/
        └── scrape.yml
```

To upload:
1. In your repo, click **Add file** → **Upload files**
2. Drag all files in — GitHub will preserve folder structure
3. Click **Commit changes**

### Step 4 — Enable GitHub Pages (your phone dashboard)
1. In your repo, go to **Settings** → **Pages** (left sidebar)
2. Under **Source**, select **Deploy from a branch**
3. Branch: **main**, Folder: **/docs**
4. Click **Save**
5. Wait 2 minutes, then your dashboard is live at:
   **https://YOUR-USERNAME.github.io/tfs-monitor/**

### Step 5 — Run the scraper manually for the first time
1. In your repo, click the **Actions** tab
2. Click **Daily Competitor Scrape** (left sidebar)
3. Click **Run workflow** → **Run workflow**
4. Watch it run — takes about 2 minutes
5. When it's done (green tick), refresh your dashboard

---

## That's it! 🎉

From now on, every morning at 8am the scraper runs automatically.
Open your dashboard URL on your phone before your shift to see:
- Current promotions at TPS, Boots, Superdrug
- Price comparisons vs TFS
- What changed since yesterday (highlighted in red)

---

## Updating TFS prices

When TFS prices change, open `docs/index.html` and find this section near the top of the `<script>` tag:

```javascript
const TFS_PRICES = {
  "Dior Sauvage": 85.00,
  "Chanel No 5": 98.00,
  ...
};
```

Edit the prices and commit the change. Done.

---

## Adding or removing tracked products

Open `scraper.py` and find:

```python
TRACKED_PRODUCTS = [
    "Dior Sauvage",
    "Chanel No 5",
    ...
]
```

Add or remove products as needed, commit, and it takes effect on the next scrape.

---

## Troubleshooting

**Dashboard shows "Could not load data"**
→ The scraper hasn't run yet. Go to Actions tab and run it manually.

**Scraper shows errors for a competitor**
→ That website may have blocked the scraper temporarily. It will retry tomorrow.
→ The dashboard will show "Partial" status for that competitor.

**I want to add a competitor**
→ Open `scraper.py`, find the `COMPETITORS` dictionary, and add a new entry following the same format.
