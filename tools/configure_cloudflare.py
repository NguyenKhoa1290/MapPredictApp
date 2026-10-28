"""Provision only this application's tunnel and DNS, without printing tokens."""
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def cloudflare_api(method, path, body=None):
    token = (ROOT / '.secrets/cloudflare-api-token').read_text().strip()
    request = Request('https://api.cloudflare.com/client/v4' + path,
                      data=json.dumps(body).encode() if body is not None else None, method=method,
                      headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise RuntimeError(f'Cloudflare request failed, HTTP {error.code}') from None
    if not payload.get('success'):
        raise RuntimeError('Cloudflare rejected the configuration')
    return payload['result']


def with_hostname(config, hostname, origin):
    """Preserve the existing routes, catch-all and every tunnel-level option."""
    import copy
    result = copy.deepcopy(config)
    ingress = result.setdefault('ingress', [])
    matches = [row for row in ingress if row.get('hostname') == hostname]
    if matches:
        if len(matches) != 1 or matches[0].get('service') != origin:
            raise RuntimeError('Existing hostname points elsewhere, keeping its route')
        return result
    position = next((index for index, row in enumerate(ingress) if not row.get('hostname')), len(ingress))
    ingress.insert(position, {'hostname': hostname, 'service': origin, 'originRequest': {}})
    return result


def add_hostname(hostname):
    import re
    if not re.fullmatch(r'[a-z0-9]+(?:[a-z0-9.-]*[a-z0-9])?', hostname):
        raise ValueError('Invalid hostname')
    path = ROOT / '.secrets/tunnel-metadata.json'
    metadata = json.loads(path.read_text())
    dns_path = f"/zones/{metadata['zone_id']}/dns_records"
    records = cloudflare_api('GET', dns_path + '?' + urlencode({'name': hostname}))
    target = metadata['tunnel_id'] + '.cfargotunnel.com'
    if any(row['type'] != 'CNAME' or row['content'] != target for row in records):
        raise RuntimeError('Hostname has another DNS target, no changes made')
    config_path = f"/accounts/{metadata['account_id']}/cfd_tunnel/{metadata['tunnel_id']}/configurations"
    previous = cloudflare_api('GET', config_path)['config']
    updated = with_hostname(previous, hostname, metadata['origin'])
    if updated != previous:
        cloudflare_api('PUT', config_path, {'config': updated})
    if not records:
        cloudflare_api('POST', dns_path, {'type': 'CNAME', 'name': hostname,
                                        'content': target, 'proxied': True, 'ttl': 1})
    elif not records[0].get('proxied'):
        cloudflare_api('PATCH', dns_path + '/' + records[0]['id'], {'proxied': True})
    metadata['additional_hostnames'] = sorted(set(metadata.get('additional_hostnames', [])) | {hostname})
    path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps({'hostname': hostname, 'configured': True}))


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
    current = (api('GET', f'{tunnel_path}/{tunnel_id}/configurations').get('config') if matches else None) or {'ingress': [{'service': 'http_status:404'}]}
    api('PUT', f'{tunnel_path}/{tunnel_id}/configurations', {'config': with_hostname(current, hostname, 'http://app:8000')})
    if not records:
        records = [api("POST", dns_path, {"type": "CNAME", "name": hostname,
                                         "content": target, "proxied": True, "ttl": 1})]
    metadata = {"hostname": hostname, "tunnel_id": tunnel_id, "tunnel_name": name,
                "account_id": account, "zone_id": zone_id, "dns_record_id": records[0]["id"],
                "origin": "http://app:8000"}
    metadata['additional_hostnames'] = [row['hostname'] for row in current.get('ingress', []) if row.get('hostname') and row['hostname'] != hostname]
    (secret_folder / "tunnel-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps({"hostname": hostname, "tunnel_name": name, "configured": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--add-hostname', help='Add a hostname to the existing application tunnel')
    parser.add_argument("--account-id")
    parser.add_argument("--hostname")
    parser.add_argument("--zone")
    args = parser.parse_args()
    if args.add_hostname:
        add_hostname(args.add_hostname)
    elif args.account_id and args.hostname and args.zone:
        configure(args.account_id, args.hostname, args.zone)
    else:
        parser.error('Supply --add-hostname or all of --account-id, --hostname and --zone')
