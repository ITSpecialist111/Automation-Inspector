"""
renderer.py – turn the dependency map into a Lovelace dashboard YAML
"""

from __future__ import annotations

import yaml
from typing import Any


def lovelace_from_map(dep_map: dict[str, Any]) -> str:
    view = {
        "title": "Automation Inspector",
        "path":  "automation_inspector",
        "cards": [],
    }

    # sort by friendly name
    for auto_id, info in sorted(dep_map.items(), key=lambda i: i[1]["friendly_name"].lower()):
        card = {
            "type": "entities",
            "title": info["friendly_name"],
            "entities": [auto_id],
        }

        # normal referenced entities
        if info["entities"]:
            card["entities"] += info["entities"]

        # scripts subsection
        scripts = [e for e in info["entities"] if e.startswith("script.")]
        if scripts:
            card["entities"] += [{"type": "divider"}, *scripts]

        # unknown triggers
        if info.get("unknown_triggers"):
            card["entities"] += [
                {"type": "divider"},
                *[
                    {
                        "entity": ut,
                        "name": f"⚠ {ut} (unknown)",
                        "icon": "mdi:alert",
                        "state_color": True,
                    }
                    for ut in info["unknown_triggers"]
                ],
            ]
            card["icon"] = "mdi:alert"
            card["icon_color"] = "red"

        # offline group members
        if info.get("offline_members"):
            card["entities"] += [
                {"type": "divider"},
                *[
                    {
                        "entity": om,
                        "name": f"⚠ {om} offline",
                        "icon": "mdi:account-off",
                        "state_color": True,
                    }
                    for om in info["offline_members"]
                ],
            ]
            card.setdefault("icon", "mdi:account-off")
            card.setdefault("icon_color", "orange")

        # stale
        if info.get("stale_days") is not None and \
           info["stale_days"] >= info["stale_threshold"]:
            card["icon"]       = "mdi:clock-alert"
            card["icon_color"] = "purple"

        view["cards"].append(card)

    return yaml.dump({"views": [view]}, sort_keys=False, default_flow_style=False)
