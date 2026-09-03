"""
DealScan - Admin coverage dashboard page.

Shows national county coverage, health status, and pipeline metrics.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from pipeline.dashboard.data import build_dashboard_payload

router = APIRouter()


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DealScan Admin - Coverage Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 0; padding: 24px; background: #f8fafc; color: #0f172a; }
    h1 { font-size: 20px; margin: 0 0 16px; }
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 24px; }
    .card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
    .card .label { color: #64748b; font-size: 12px; }
    .card .value { color: #0f172a; font-size: 24px; font-weight: 700; margin-top: 4px; }
    table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; }
    th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #e5e7eb; font-size: 14px; }
    th { background: #f1f5f9; color: #334155; font-weight: 600; }
    tr:last-child td { border-bottom: none; }
    .ok { color: #16a34a; }
    .error { color: #dc2626; }
    .skipped { color: #f59e0b; }
  </style>
</head>
<body>
  <h1>DealScan Admin — Coverage Dashboard</h1>
  <div class="stats" id="stats"></div>
  <table>
    <thead>
      <tr>
        <th>Status</th>
        <th>County</th>
        <th>State</th>
        <th>Tier</th>
        <th>Records Stored</th>
        <th>Published</th>
        <th>Last Run</th>
        <th>Rejection Reasons</th>
      </tr>
    </thead>
    <tbody id="counties"></tbody>
  </table>
  <script>
    async function load() {
      const res = await fetch('/api/admin/coverage');
      const data = await res.json();
      const stats = data.coverage_summary || {};
      document.getElementById('stats').innerHTML = `
        <div class="card"><div class="label">Total Counties</div><div class="value">${stats.total ?? data.total_counties ?? 0}</div></div>
        <div class="card"><div class="label">Active</div><div class="value ok">${stats.active ?? 0}</div></div>
        <div class="card"><div class="label">Degraded</div><div class="value" style="color:#f59e0b">${stats.degraded ?? 0}</div></div>
        <div class="card"><div class="label">Failed</div><div class="value error">${stats.failed ?? 0}</div></div>
        <div class="card"><div class="label">Not Implemented</div><div class="value">${stats.not_implemented ?? 0}</div></div>
        <div class="card"><div class="label">Skipped</div><div class="value" style="color:#f59e0b">${stats.skipped ?? 0}</div></div>
      `;
      const rows = (data.counties || []).map(c => `
        <tr>
          <td>${c.symbol || ''} ${c.status || ''}</td>
          <td>${c.county_name ?? c.county_id}</td>
          <td>${c.state ?? ''}</td>
          <td>${c.tier_name ?? c.tier ?? ''}</td>
          <td>${c.records ?? 0}</td>
          <td>${c.published ?? 0}</td>
          <td>${c.last_run ? new Date(c.last_run).toLocaleString() : '-'}</td>
          <td>${(c.rejection_reasons || {}).hasOwnProperty('') ? '' : JSON.stringify(c.rejection_reasons || {})}</td>
        </tr>
      `).join('');
      document.getElementById('counties').innerHTML = rows || '<tr><td colspan="8">No county data yet.</td></tr>';
    }
    load();
  </script>
</body>
</html>
"""


@router.get("/admin/coverage", response_class=HTMLResponse)
async def coverage_page(request: Request) -> HTMLResponse:
    return HTMLResponse(content=DASHBOARD_HTML)
