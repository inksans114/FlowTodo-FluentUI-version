"""Select a real, active LAN interface before VPN and VM adapters."""
from __future__ import annotations

from phone_camera_server import private_host


def ranked_interfaces(rows):
    candidates = {}
    for row in rows:
        if not row.get("up") or not row.get("running"):
            continue
        try:
            host = private_host(row["ip"])
        except (ValueError, KeyError):
            continue
        name = row.get("name", "")
        kind = row.get("type", "Unknown")
        virtual = kind == "Virtual" or any(part in name.lower() for part in
            ("vmware", "vmnet", "virtual", "vethernet", "hyper-v", "tailscale", "vpn", "mihomo", "docker", "wsl", "tun", "tap"))
        rank = 10 if virtual else 0 if kind == "Wifi" else 1 if kind == "Ethernet" else 3
        label = f"{name} · {host}" + ("（虚拟网卡，不建议）" if virtual else "")
        candidate = {"ip": host, "name": name, "label": label, "rank": rank}
        if host not in candidates or rank < candidates[host]["rank"]:
            candidates[host] = candidate
    return sorted(candidates.values(), key=lambda row: (row["rank"], row["name"], row["ip"]))
