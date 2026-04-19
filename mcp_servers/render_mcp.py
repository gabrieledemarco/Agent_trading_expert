#!/usr/bin/env python3
"""Render MCP Server — exposes Render REST API as MCP tools.

Requires:
  RENDER_API_KEY  — API key from https://dashboard.render.com/u/settings#api-keys
  RENDER_SERVICE_ID (optional) — default service ID (srv-xxxx)

Tools exposed:
  list_services        — list all services in the workspace
  get_service          — get details for a specific service
  list_deploys         — list recent deployments for a service
  get_deploy           — get details for a specific deployment
  list_logs            — retrieve build/app/request logs
  get_metrics          — retrieve CPU, memory, HTTP metrics
  update_env_vars      — set environment variables on a service
  trigger_deploy       — trigger a new deployment
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

RENDER_API = "https://api.render.com/v1"
API_KEY = os.getenv("RENDER_API_KEY", "")
DEFAULT_SERVICE_ID = os.getenv("RENDER_SERVICE_ID", "")

mcp = FastMCP("render", dependencies=["httpx"])


def _headers() -> dict:
    if not API_KEY:
        raise RuntimeError("RENDER_API_KEY environment variable is not set.")
    return {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}


def _get(path: str, params: dict | None = None) -> dict | list:
    r = httpx.get(f"{RENDER_API}{path}", headers=_headers(), params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def _post(path: str, json: dict | None = None) -> dict:
    r = httpx.post(f"{RENDER_API}{path}", headers=_headers(), json=json or {}, timeout=20)
    r.raise_for_status()
    return r.json()


def _put(path: str, json: dict) -> dict:
    r = httpx.put(f"{RENDER_API}{path}", headers=_headers(), json=json, timeout=20)
    r.raise_for_status()
    return r.json()


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_services(include_previews: bool = False) -> str:
    """List all services in the Render workspace."""
    params = {"limit": 50}
    if not include_previews:
        params["type"] = "web_service,static_site,background_worker,cron_job"
    data = _get("/services", params)
    services = data if isinstance(data, list) else data.get("services", data)
    lines = []
    for item in services:
        s = item.get("service", item)
        sid   = s.get("id", "?")
        name  = s.get("name", "?")
        stype = s.get("type", "?")
        status = s.get("suspended", "active")
        repo  = s.get("repo", "")
        lines.append(f"[{sid}] {name} ({stype}) — {status}  {repo}")
    return "\n".join(lines) if lines else "No services found."


@mcp.tool()
def get_service(service_id: str = "") -> str:
    """Get details for a Render service. Uses RENDER_SERVICE_ID if not provided."""
    sid = service_id or DEFAULT_SERVICE_ID
    if not sid:
        return "Provide service_id or set RENDER_SERVICE_ID env var."
    data = _get(f"/services/{sid}")
    s = data.get("service", data)
    lines = [
        f"ID:        {s.get('id')}",
        f"Name:      {s.get('name')}",
        f"Type:      {s.get('type')}",
        f"Repo:      {s.get('repo', 'N/A')}",
        f"Branch:    {s.get('branch', 'N/A')}",
        f"Region:    {s.get('region', 'N/A')}",
        f"Status:    {'suspended' if s.get('suspended') else 'active'}",
        f"URL:       {s.get('serviceDetails', {}).get('url', 'N/A')}",
        f"Created:   {s.get('createdAt', 'N/A')}",
        f"Updated:   {s.get('updatedAt', 'N/A')}",
    ]
    return "\n".join(lines)


@mcp.tool()
def list_deploys(service_id: str = "", limit: int = 10) -> str:
    """List recent deployments for a service."""
    sid = service_id or DEFAULT_SERVICE_ID
    if not sid:
        return "Provide service_id or set RENDER_SERVICE_ID env var."
    limit = max(1, min(limit, 100))
    data = _get(f"/services/{sid}/deploys", {"limit": limit})
    deploys = data if isinstance(data, list) else data.get("deploys", [])
    if not deploys:
        return "No deployments found."
    lines = []
    for item in deploys:
        d = item.get("deploy", item)
        did    = d.get("id", "?")
        status = d.get("status", "?")
        commit = d.get("commit", {})
        sha    = (commit.get("id") or "")[:7]
        msg    = (commit.get("message") or "").split("\n")[0][:60]
        created = d.get("createdAt", "?")[:19].replace("T", " ")
        lines.append(f"[{did}] {status:12s} {created}  {sha} {msg}")
    return "\n".join(lines)


@mcp.tool()
def get_deploy(deploy_id: str, service_id: str = "") -> str:
    """Get details for a specific deployment."""
    sid = service_id or DEFAULT_SERVICE_ID
    if not sid:
        return "Provide service_id or set RENDER_SERVICE_ID env var."
    data = _get(f"/services/{sid}/deploys/{deploy_id}")
    d = data.get("deploy", data)
    commit = d.get("commit", {})
    lines = [
        f"Deploy ID: {d.get('id')}",
        f"Status:    {d.get('status')}",
        f"Created:   {d.get('createdAt', 'N/A')[:19].replace('T',' ')}",
        f"Finished:  {d.get('finishedAt', 'N/A')[:19].replace('T',' ')}",
        f"Commit:    {(commit.get('id') or '')[:7]} — {(commit.get('message') or '').split(chr(10))[0][:80]}",
        f"Author:    {commit.get('authorName', 'N/A')}",
    ]
    return "\n".join(lines)


@mcp.tool()
def list_logs(
    service_id: str = "",
    log_type: str = "app",
    limit: int = 50,
    start_minutes_ago: int = 60,
    text_filter: str = "",
) -> str:
    """Retrieve logs for a service.

    log_type: app | build | request
    text_filter: optional substring to filter log lines
    """
    sid = service_id or DEFAULT_SERVICE_ID
    if not sid:
        return "Provide service_id or set RENDER_SERVICE_ID env var."
    limit = max(1, min(limit, 100))
    now = datetime.now(timezone.utc)
    start = (now - timedelta(minutes=start_minutes_ago)).isoformat()
    params = {
        "resource": [sid],
        "type":     [log_type],
        "limit":    limit,
        "startTime": start,
        "direction": "backward",
    }
    if text_filter:
        params["text"] = [text_filter]
    data = _get("/logs", params)
    logs = data if isinstance(data, list) else data.get("logs", [])
    if not logs:
        return f"No {log_type} logs found for the last {start_minutes_ago} minutes."
    lines = []
    for entry in logs:
        ts  = (entry.get("timestamp") or "")[:19].replace("T", " ")
        msg = entry.get("message", "")
        lvl = entry.get("level", "")
        prefix = f"[{lvl.upper():5s}]" if lvl else ""
        lines.append(f"{ts} {prefix} {msg}")
    return "\n".join(lines)


@mcp.tool()
def get_metrics(
    service_id: str = "",
    metric_types: str = "cpu_usage,memory_usage",
    start_minutes_ago: int = 60,
) -> str:
    """Get performance metrics for a service.

    metric_types: comma-separated list of:
      cpu_usage, cpu_limit, memory_usage, memory_limit,
      http_request_count, http_latency, instance_count
    """
    sid = service_id or DEFAULT_SERVICE_ID
    if not sid:
        return "Provide service_id or set RENDER_SERVICE_ID env var."
    now = datetime.now(timezone.utc)
    start = (now - timedelta(minutes=start_minutes_ago)).isoformat()
    params = {
        "metricType": [m.strip() for m in metric_types.split(",")],
        "startTime":  start,
        "resolution": 60,
    }
    data = _get(f"/metrics/{sid}", params)
    metrics = data if isinstance(data, list) else data.get("metrics", [data])
    lines = []
    for m in metrics:
        mtype  = m.get("metricType", "?")
        points = m.get("dataPoints", [])
        if not points:
            lines.append(f"{mtype}: no data")
            continue
        last   = points[-1]
        val    = last.get("value", 0)
        ts     = (last.get("timestamp") or "")[:19].replace("T", " ")
        unit   = "%" if "usage" in mtype or "limit" in mtype else ""
        lines.append(f"{mtype:30s} {val:.2f}{unit}  (last point: {ts})")
    return "\n".join(lines) if lines else "No metrics returned."


@mcp.tool()
def trigger_deploy(service_id: str = "", clear_cache: bool = False) -> str:
    """Trigger a new deployment for a service."""
    sid = service_id or DEFAULT_SERVICE_ID
    if not sid:
        return "Provide service_id or set RENDER_SERVICE_ID env var."
    payload = {"clearCache": "clear" if clear_cache else "do_not_clear"}
    data = _post(f"/services/{sid}/deploys", payload)
    d = data.get("deploy", data)
    return f"Deploy triggered: [{d.get('id')}] status={d.get('status')} created={d.get('createdAt','?')[:19]}"


@mcp.tool()
def update_env_vars(key: str, value: str, service_id: str = "") -> str:
    """Set or update an environment variable on a service.

    Performs a merge (does not replace other existing variables).
    """
    sid = service_id or DEFAULT_SERVICE_ID
    if not sid:
        return "Provide service_id or set RENDER_SERVICE_ID env var."
    # Fetch existing env vars first
    existing = _get(f"/services/{sid}/env-vars")
    env_list = existing if isinstance(existing, list) else existing.get("envVars", [])
    updated = False
    new_list = []
    for ev in env_list:
        e = ev.get("envVar", ev)
        if e.get("key") == key:
            new_list.append({"key": key, "value": value})
            updated = True
        else:
            new_list.append({"key": e.get("key"), "value": e.get("value", "")})
    if not updated:
        new_list.append({"key": key, "value": value})
    _put(f"/services/{sid}/env-vars", new_list)
    action = "updated" if updated else "added"
    return f"Environment variable '{key}' {action} on service {sid}."


if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: Set RENDER_API_KEY before running.", file=sys.stderr)
        sys.exit(1)
    mcp.run(transport="stdio")
