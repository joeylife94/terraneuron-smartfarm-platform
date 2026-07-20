#!/usr/bin/env python3
"""End-to-end checks for the dashboard interactive authentication boundary."""

from __future__ import annotations

import os

import requests


BASE_URL = os.getenv("DASHBOARD_BASE_URL", "http://localhost:3001")
TIMEOUT = float(os.getenv("DASHBOARD_AUTH_TIMEOUT_SECONDS", "10"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    session = requests.Session()

    rejected = requests.post(
        f"{BASE_URL}/api/dashboard-auth/login",
        json={"username": "operator", "password": "operator123"},
        headers={"Origin": "https://attacker.invalid"},
        timeout=TIMEOUT,
    )
    require(rejected.status_code == 403, "cross-origin login must be rejected")

    login = session.post(
        f"{BASE_URL}/api/dashboard-auth/login",
        json={"username": "operator", "password": "operator123"},
        headers={"Origin": BASE_URL},
        timeout=TIMEOUT,
    )
    require(login.status_code == 200, f"dashboard login failed: {login.status_code} {login.text}")
    payload = login.json()
    require(payload.get("authenticated") is True, "login response must mark the session authenticated")
    require(payload.get("user", {}).get("username") == "operator", "login must return the authenticated user")
    require("access_token" not in payload and "refresh_token" not in payload, "browser JSON must not expose JWT values")

    set_cookie = login.headers.get("Set-Cookie", "")
    require("HttpOnly" in set_cookie, "session cookies must be HttpOnly")
    require("SameSite=strict" in set_cookie or "SameSite=Strict" in set_cookie, "session cookies must use SameSite=Strict")
    require("Path=/api" in set_cookie, "session cookies must be scoped to Dashboard API handlers")
    require("terraneuron_access_token" in session.cookies, "access cookie was not issued")
    require("terraneuron_refresh_token" in session.cookies, "refresh cookie was not issued")

    current = session.get(f"{BASE_URL}/api/dashboard-auth/session", timeout=TIMEOUT)
    require(current.status_code == 200, f"session validation failed: {current.status_code} {current.text}")
    require(current.json().get("user", {}).get("username") == "operator", "session user mismatch")

    protected = session.get(f"{BASE_URL}/api/dashboard-ops/actions/statistics", timeout=TIMEOUT)
    require(protected.status_code == 200, f"protected Terra-Ops proxy failed: {protected.status_code} {protected.text}")
    require(isinstance(protected.json(), dict), "action statistics response must be JSON")

    blocked_route = session.get(f"{BASE_URL}/api/dashboard-ops/auth/validate", timeout=TIMEOUT)
    require(blocked_route.status_code == 404, "BFF must not expose arbitrary Terra-Ops auth paths")

    logout = session.post(
        f"{BASE_URL}/api/dashboard-auth/logout",
        headers={"Origin": BASE_URL},
        timeout=TIMEOUT,
    )
    require(logout.status_code == 204, f"dashboard logout failed: {logout.status_code} {logout.text}")

    after_logout = session.get(f"{BASE_URL}/api/dashboard-auth/session", timeout=TIMEOUT)
    require(after_logout.status_code == 401, "logged-out session must not validate")

    protected_after_logout = session.get(
        f"{BASE_URL}/api/dashboard-ops/actions/statistics",
        timeout=TIMEOUT,
    )
    require(protected_after_logout.status_code == 401, "logged-out session must not reach protected Terra-Ops APIs")

    print("[PASS] dashboard interactive authentication E2E")


if __name__ == "__main__":
    main()
