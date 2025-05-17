import yaml

def lovelace_from_map(dep_map: dict) -> str:
    view = {
        "title": "Automation Inspector",
        "path": "automation-inspector",
        "icon": "mdi:robot-industrial",
        "cards": [],
    }
    for auto_id, info in dep_map.items():
        card = {
            "type": "entities",
            "title": info["friendly_name"],
            "entities": [auto_id] + info["entities"],
            "footer": {
                "type": "buttons",
                "entities": [
                    {
                        "name": "Trace",
                        "tap_action": {
                            "action": "navigate",
                            "navigation_path": f"/config/automation/edit/{auto_id}"
                        },
                        "icon": "mdi:timeline-clock-outline"
                    }
                ]
            },
        }
        view["cards"].append(card)
    # YAML dump with block style for readability
    return yaml.dump({"views": [view]}, sort_keys=False, default_flow_style=False)
