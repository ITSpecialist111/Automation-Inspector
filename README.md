# Automation Inspector Add‑on

🏠 **Home Assistant Supervisor Add‑on** that visualises every automation in your instance and the live state of every entity it depends on. Broken or unavailable entities are highlighted so you can spot problems before they break your automations.

<p align="center">
  <a href="https://www.buymeacoffee.com/ITSpecialist" target="_blank">
    <img src="https://img.shields.io/badge/Buy&nbsp;me&nbsp;a&nbsp;coffee-Support&nbsp;Dev-yellow?style=for-the-badge&logo=buy-me-a-coffee" alt="Buy Me A Coffee">
  </a>
</p>

---

## 🏷️ Release v0.3.3 Highlights

- **Ingress & Web UI integration** – works seamlessly via HA’s Ingress (no blank page).  
- **Dark mode support** – full colour theming with CSS variables and forced white text.  
- **Trace & More-Info links** – open `/config/automation/edit/...` and `/developer-tools/state?...` correctly inside HA UI.

See [RELEASE_NOTES.md](RELEASE_NOTES.md) for full changelog.

---

## ✨ Key Features

| Feature | MVP |
|---------|------------|
| 🗺️ Dependency map | Lists **all automations** with the **entities they reference** (triggers, conditions & actions) |
| 🔴 Health flags | Unavailable / unknown entities are coloured **red** |
| 📈 Live values | Shows the current state (e.g. `sensor.modbus_battery_soc : 48`) |
| ▶ Trace link | One‑click **Trace / Edit** in HA UI |
| 🔍 Errors‑only toggle | Hide rows that have no broken dependencies |
| 🔄 Manual refresh | Reload button or browser refresh |
| ☑️ Enabled marker | Disabled automations are greyed out |
| 📊 Banner counts | Total automations · entity count · error totals |
| 🌑 Dark mode | Theme-aware styling + forced white text in dark schemes |

---

## 🚀 Installation

1. **Add repository** in Home Assistant Add‑on Store:
   ```text
   https://github.com/ITSpecialist111/Automation-Inspector
   ```
2. **Reload** the Store ➜ search for **Automation Inspector** ➜ **Install**.
3. Click **Start**.  Open the Web UI via Ingress or direct:
   ```
   http://<HA-IP>:1234
   ```

> **Port note**  
> The add‑on runs on **port 1234** inside Supervisor. All internal links are rewritten to that port to open the core HA UI.

---

## ⚙️ Options

No options yet – it just works. Road‑map items will add:

* Auto-refresh interval  
* Filter presets (area, tag, bad‑only)  
* Lovelace panel integration  

---

## 🛠️ Development & Building

```bash
# clone
git clone https://github.com/ITSpecialist111/Automation-Inspector.git
cd Automation-Inspector/automation_inspector

# build
docker build -t automation_inspector:dev .

docker run --rm -p 8234:1234 \
  -e SUPERVISOR_TOKEN="dummy" \
  -e SUPERVISOR_ENDPOINT="http://host.docker.internal:8123" \
  automation_inspector:dev
```

Provide a valid HA token for full API access in local dev.

### Repo Layout
```
automation_inspector/
 ├─ config.json           # add‑on manifest (version, ingress, flags)
 ├─ Dockerfile            # python 3.11-alpine + FastAPI + Uvicorn
 ├─ requirements.txt      # fastapi, uvicorn, httpx, pyyaml
 ├─ app/
 │   ├─ main.py           # FastAPI entrypoint & routes
 │   └─ dependency_map.py # Core logic to build automation ↔ entities map
 └─ www/
     └─ index.html        # Dashboard UI (vanilla JS + theme-aware CSS)
```

---

## 🗺️ Architecture

1. **/api/states** – fetch all states via Supervisor proxy  
2. Filter to `automation.*` entities  
3. Fetch resolved YAML via `/api/config/automation/config/<id>`  
4. Extract `entity_id` references recursively  
5. Enrich with current `state` & `ok` flag; suppress false positives  
6. Serve JSON at `/dependency_map.json`  
7. Front‑end fetches JSON and renders table with red chips for issues

---

## 🛣️ Road‑map

* 🔄 **Auto-refresh** with configurable interval  
* 🎨 **Custom Lovelace panel** for native theming  
* ⬇ **CSV/Markdown export**  
* 🔍 **Tag/Area filters**  
* 🔔 **Notifications** for dependency failures  

Contributions welcome! Open issues or PRs on [GitHub](https://github.com/ITSpecialist111/Automation-Inspector).

---

## 📄 License

MIT License – © 2025 Graham Hosking & contributors
