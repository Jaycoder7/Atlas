#!/usr/bin/env python3
"""Submit deterministic lab results to Atlas."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
import uuid


API_URL = os.getenv("ATLAS_API_URL", "http://localhost:8000/api/v1")


def request_json(url: str, *, method: str = "GET", payload: dict | None = None, token: str = "") -> dict | list:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def auth_token() -> str:
    client_id = os.getenv("ATLAS_CLIENT_ID")
    client_secret = os.getenv("ATLAS_CLIENT_SECRET")
    domain = os.getenv("AUTH0_DOMAIN")
    audience = os.getenv("AUTH0_AUDIENCE", "https://api.atlas.local")
    if not all([client_id, client_secret, domain]):
        return ""
    result = request_json(
        f"https://{domain}/oauth/token",
        method="POST",
        payload={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "audience": audience,
        },
    )
    return str(result["access_token"])


def submit(program_id: str, test_code: str, serial: str, status: str, values: dict, token: str) -> dict:
    return request_json(
        f"{API_URL}/test-runs",
        method="POST",
        token=token,
        payload={
            "external_run_id": f"sim-{test_code.lower()}-{uuid.uuid4()}",
            "program_id": program_id,
            "test_code": test_code,
            "hardware_serial": serial,
            "status": status,
            "measured_value": values,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=["thermal-failure", "passing-suite"])
    args = parser.parse_args()
    token = auth_token()
    programs = request_json(f"{API_URL}/programs", token=token)
    if not programs:
        raise SystemExit("No Atlas program exists; run the seed command first.")
    program_id = programs[0]["id"]
    if args.scenario == "thermal-failure":
        result = submit(
            program_id,
            "TEST-021",
            "P1-003",
            "fail",
            {"temperature_c": 52.8, "regulator_voltage_v": 2.71, "limit_v": 3.1},
            token,
        )
        print(json.dumps(result, indent=2))
        print("Rev C thermal failure submitted. Open /dashboard and /changes to inspect propagation.")
    else:
        for number in range(20, 25):
            result = submit(program_id, f"TEST-{number:03d}", "P1-003", "pass", {"value": 1.0}, token)
            print(f"TEST-{number:03d}: {'created' if result['created'] else 'duplicate'}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Simulator failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

