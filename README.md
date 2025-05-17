# Automation Inspector Add‑on

🏠 **Home Assistant Supervisor Add‑on** that visualises every automation in your instance and the live state of every entity it depends on. Broken or unavailable entities are highlighted so you can spot problems before they break your automations.

<p align="center">
  <a href="https://www.buymeacoffee.com/ITSpecialist" target="_blank">
    <img src="https://img.shields.io/badge/Buy&nbsp;me&nbsp;a&nbsp;coffee-Support&nbsp;Dev-yellow?style=for-the-badge&logo=buy-me-a-coffee" alt="Buy Me A Coffee">
  </a>
</p>

---
## Important note: if you are using a proxy to access HASS this may not report correctly because of HASS security. Use internal IP address to access.

## ✨ Key Features

| Feature | MVP v0.3.2 |
|---------|-----------|
| 🗺️ Dependency map | Lists **all automations** with the **entities they reference** (triggers, conditions & actions) |
| 🔴 Health flags | Unavailable / unknown entities are coloured **red** |
| 📈 Live values | Shows the current state (e.g. `sensor.modbus_battery_soc : 48`) |
| ▶ Trace link | One‑click **Trace / Edit** in HA UI |
| 🔍 Errors‑only toggle | Hide rows that have no broken dependencies |
| 🔄 Manual refresh | Reload button or browser refresh (auto‑refresh planned) |
| ☑️ Enabled marker | Disabled automations are greyed out |
| 📊 Banner counts | Total automations · entity count · error totals |

---

## 📷 Screenshot
*(Dark‑theme screenshot pending)*
![Automation Inspector screenshot](https://github.com/ITSpecialist111/Automation-Inspector/blob/main/screenshot-light.png)

---

## 🚀 Installation

1. **Add repository** in Home Assistant Add‑on Store
   ```text
   https://github.com/ITSpecialist111/Automation-Inspector
   ```
2. **Reload** the Store ➜ search for **Automation Inspector** ➜ **Install**.
3. Click **Start**.  Open the Web UI (Ingress) or direct:
   ```
   http://<HA-IP>:8123
   ```

> **Port note**  
> The add‑on runs on **port 8123** inside Supervisor.  All internal links (Trace, entity more‑info) are rewritten to that port so they open the core HA UI – no 401 errors.

---

## ⚙️ Options

No options yet – it just works.  Road‑map items will add:

* Refresh interval (auto‑reload)
* Theme / dark‑mode toggle
* Filter presets (area, tag, bad‑only)

---

## 🛠️ Development & Building

```bash
# clone
git clone https://github.com/ITSpecialist111/Automation-Inspector.git
cd Automation-Inspector/automation_inspector

# build local dev container
docker build -t automation_inspector:dev .

docker run --rm -p 8234:1234 \
  -e SUPERVISOR_TOKEN="dummy" \
  -e SUPERVISOR_ENDPOINT="http://host.docker.internal:8123" \
  automation_inspector:dev
```

The container expects `SUPERVISOR_TOKEN`; for local testing pass a long‑lived HA token instead and set `Authorization: Bearer <token>`.

### Repo Layout
```
automation_inspector/
 ├─ config.json           # add‑on manifest (version, ports, flags)
 ├─ Dockerfile            # alpine + python 3.11 + uvicorn + fastapi
 ├─ requirements.txt      # fastapi, uvicorn, httpx, pyyaml
 ├─ app/
 │   ├─ main.py           # FastAPI entry, routes
 │   └─ dependency_map.py # ← API crawler & parser (core logic)
 └─ www/
     └─ index.html        # lightweight dashboard (no framework)
```

---

## 🗺️ Architecture

1. **/api/states** – full state dump (Supervisor proxy)  
2. Filter → `automation.*` rows  
3. For each automation, try resolved YAML via `/api/config/automation/config/<id>`  
4. Recursively extract **entity_ids** (regex)  
5. Enrich each ID with `state`, `ok` flag  
6. Expose as `/dependency_map.json`  
7. Front‑end fetches JSON ➜ renders table; red chips if `ok == false`.

No database, no polling – one shot per page load (next release adds 15 s auto‑refresh).

---

## 🛣️ Road‑map

* 🔄 **Auto‑refresh** every N seconds (configurable)
* 🎨 Dark‑mode & HA theme colours (migrate to LitElement panel)
* ⬇ Export CSV / Markdown report
* 🏷️ Area / Tag filters
* 📊 Compact card view for Lovelace dashboards
* 🔔 Optional notification when a dependency goes unavailable

Contributions & PRs are very welcome – please open an issue first if the change is large.

---

## 📄 License
MIT License  – © 2025 Graham Hosking & contributors
