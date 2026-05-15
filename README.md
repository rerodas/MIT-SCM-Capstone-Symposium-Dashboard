# Hidden Value of E2E Supply Chain Visibility — Symposium Dashboard

Mobile-responsive Streamlit app to share capstone results with the symposium audience via QR code.

## What's in this folder

```
E2E_CapstoneApp/
├── CapstoneResults.py          # Main app (run this)
├── requirements.txt            # Python deps
├── supply_chain.db             # Updated DB (you supply this)
├── DSCTL_logo.png              # Sidebar logo (optional)
├── MOND_network_map.json       # Network for Mondelez
├── DANO_network_map.json       # Network for Danone
├── NVID_network_map.json       # Network for NVIDIA
├── INTE_network_map.json       # Network for Intel
└── .streamlit/
    └── config.toml             # Theme + server config
```

The app auto-discovers network files using the first 4 letters of the focal company name (uppercased). If your existing files use a different prefix (e.g., `MONDELEZ_network_map.json`), the app also tries the company short name — see `find_network_file()` in the code.

## Run locally

```bash
pip install -r requirements.txt
streamlit run CapstoneResults.py
```

Open http://localhost:8501.

## Deploy to Streamlit Community Cloud (free, ~5 min)

This is the fastest path for a one-week symposium demo.

1. **Push this folder to a public GitHub repo.**
   ```bash
   cd E2E_CapstoneApp
   git init
   git add .
   git commit -m "Capstone symposium dashboard"
   git remote add origin https://github.com/<your-user>/<repo>.git
   git push -u origin main
   ```

2. **Sign in at https://share.streamlit.io** with your GitHub account.

3. **New app** → pick your repo, branch `main`, main file `CapstoneResults.py`.

4. Click **Deploy**. First build takes ~2 minutes. You'll get a URL like:
   `https://<your-app-name>.streamlit.app`

5. **Generate the QR code** — any free generator works:
   - https://www.qr-code-generator.com (paste the Streamlit URL)
   - Or, on macOS, the `qrencode` CLI: `brew install qrencode && qrencode -o qr.png "https://<your-app>.streamlit.app"`

   Print it on your title slide or hand-out.

## Notes on the DB

The app expects the same schema as your existing setup:
- `model_runs` (focal_company, model_run_id, industry_margin, avg_disruption_duration)
- `voi_log` (focal_company, model_run_id, voi_s2, voi_s3)
- `bbn_p_matrix` (model_run_id, supplier_id, p_scenario_1, p_scenario_2, p_scenario_3)
- `inv_alloc_audit` (optional, not required for the simplified symposium view)

The simplified app drops the model-run-ID picker and instead **aggregates across all safety-stock levels** for each company, so the VOI chart shows the full S2/S3 curve at 10%/20%/30%/40% SS — matching slide 14 of the deck.

## Mobile responsiveness

- Sidebar starts **collapsed** on mobile (hamburger menu).
- Company picker uses **segmented radio buttons** that wrap to 2 columns on phones.
- KPI tiles stack vertically below 640px.
- Network SVG uses `viewBox` for proper scaling; touch events trigger highlight on tap.
- Plotly toolbars hidden; charts have generous tap targets.

Test it: open the deployed URL on your phone with the browser DevTools mobile emulator, then in actual mobile Safari/Chrome.
