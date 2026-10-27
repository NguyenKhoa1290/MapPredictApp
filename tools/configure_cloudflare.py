"""Provision only this application's tunnel and DNS, without printing tokens."""
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def configure(account, hostname, zone_name):
    secret_folder = ROOT / ".secrets"
    token = (secret_folder / "cloudflare-api-token").read_text().strip()

    def api(method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = Request("https://api.cloudflare.com/client/v4" + path, data=data, method=method,
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"Cloudflare {method} request failed, HTTP {error.code}") from None
        if not payload.get("success"):
            raise RuntimeError("Cloudflare rejected the requested configuration")
        return payload["result"]

    zones = api("GET", "/zones?" + urlencode({"name": zone_name}))
    zones = [zone for zone in zones if zone["account"]["id"] == account]
    if len(zones) != 1:
        raise RuntimeError("Expected exactly one matching zone in the specified account")
    zone_id = zones[0]["id"]
    dns_path = f"/zones/{zone_id}/dns_records"
    records = api("GET", dns_path + "?" + urlencode({"name": hostname}))
    tunnel_path = f"/accounts/{account}/cfd_tunnel"
    name = "map-predict-app-" + hostname.replace(".", "-")
    tunnels = api("GET", tunnel_path + "?is_deleted=false")
    matches = [tunnel for tunnel in tunnels if tunnel["name"] == name]
    if len(matches) > 1:
        raise RuntimeError("Ambiguous tunnel name, no configuration changed")
    if records and not matches:
        raise RuntimeError("Hostname already has DNS records, refusing to replace another application's route")
    tunnel = matches[0] if matches else api("POST", tunnel_path, {"name": name, "config_src": "cloudflare"})
    tunnel_id = tunnel["id"]
    target = tunnel_id + ".cfargotunnel.com"
    if any(record["type"] != "CNAME" or record["content"] != target for record in records):
        raise RuntimeError("Hostname points elsewhere, existing DNS records were preserved")
    connector_token = api("GET", f"{tunnel_path}/{tunnel_id}/token")
    (secret_folder / "cloudflared-token").write_text(connector_token, encoding="utf-8")
    api("PUT", f"{tunnel_path}/{tunnel_id}/configurations", {"config": {"ingress": [
        {"hostname": hostname, "service": "http://app:8000", "originRequest": {}},
        {"service": "http_status:404"},
    ]}})
    if not records:
        records = [api("POST", dns_path, {"type": "CNAME", "name": hostname,
                                         "content": target, "proxied": True, "ttl": 1})]
    metadata = {"hostname": hostname, "tunnel_id": tunnel_id, "tunnel_name": name,
                "account_id": account, "zone_id": zone_id, "dns_record_id": records[0]["id"],
                "origin": "http://app:8000"}
    (secret_folder / "tunnel-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps({"hostname": hostname, "tunnel_name": name, "configured": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--zone", required=True)
    args = parser.parse_args()
    configure(args.account_id, args.hostname, args.zone)
