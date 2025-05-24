import yaml

def lovelace_from_map(dep_map: dict) -> str:
    view = {
        "title": "Automation Inspector",
        "path": "automation-inspector",
        "icon": "mdi:robot-industrial",
        "cards": [],
    }

    for auto_id, info in dep_map.items():
        # Build the list of entity IDs for the entities card
        entities = [auto_id] + [e["id"] for e in info["entities"]]

        # 1) the original entities card, unchanged except using our entities list
        card = {
            "type": "entities",
            "title": info["friendly_name"],
            "entities": entities,
            "footer": {
                "type": "buttons",
                "entities": [
                    {
                        "name": "Trace",
                        "tap_action": {
                            "action": "navigate",
                            "navigation_path": f"/config/automation/edit/{info.get('config_id') or auto_id}"
                        },
                        "icon": "mdi:timeline-clock-outline"
                    }
                ]
            },
        }
        view["cards"].append(card)

        # 2) a small markdown card that shows the last‐triggered time
        last = info.get("last_triggered") or "never"
        view["cards"].append({
            "type": "markdown",
            "content": (
                f"**Last run:** {last}  \n"
                f"**Enabled:** {'yes' if info.get('enabled') else 'no'}"
            )
        })

    # YAML dump with block style for readability
    return yaml.dump({"views": [view]}, sort_keys=False, default_flow_style=False)
