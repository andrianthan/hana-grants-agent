#!/usr/bin/env python3
"""Microsoft Excel Online integration for the grants pipeline.

Appends scored grants to a shared Excel workbook in OneDrive/SharePoint
and syncs approvals back to RDS via Microsoft Graph API.

Uses Azure AD app registration (client credentials flow) for auth.

Excel workbook structure:
  - "Grants" worksheet with columns:
    Date | Title | Funder | Deadline | Score | Reasoning | Profile |
    Source Link | Status | Skip Reason | Grant ID

Environment Variables:
    MS_TENANT_ID: Azure AD tenant ID
    MS_CLIENT_ID: Azure AD app registration client ID
    MS_CLIENT_SECRET: Azure AD app client secret
        OR
    MS_CREDENTIALS_SECRET_ARN: Secrets Manager ARN containing JSON with
        tenant_id, client_id, client_secret
    MS_DRIVE_ID: OneDrive/SharePoint drive ID (optional — uses default if not set)
    MS_WORKBOOK_PATH: Path to Excel file in OneDrive (e.g. "/Grants/HannaGrantsTracker.xlsx")
        OR
    MS_WORKBOOK_ID: Item ID of the Excel file in OneDrive
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3
import requests

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
SCORE_THRESHOLD = 6.0

SHEET_HEADERS = [
    "Date", "Title", "Funder", "Deadline", "Score", "Reasoning",
    "Profile", "Source Link", "Status", "Skip Reason", "Grant ID",
]


def _get_credentials() -> dict:
    """Load MS credentials from env vars or Secrets Manager."""
    # Try direct env vars first
    tenant_id = os.environ.get("MS_TENANT_ID")
    client_id = os.environ.get("MS_CLIENT_ID")
    client_secret = os.environ.get("MS_CLIENT_SECRET")

    if tenant_id and client_id and client_secret:
        return {
            "tenant_id": tenant_id,
            "client_id": client_id,
            "client_secret": client_secret,
        }

    # Fall back to Secrets Manager
    secret_arn = os.environ.get("MS_CREDENTIALS_SECRET_ARN")
    if secret_arn:
        region = os.environ.get("AWS_REGION_NAME", "us-west-2")
        sm = boto3.client("secretsmanager", region_name=region)
        resp = sm.get_secret_value(SecretId=secret_arn)
        return json.loads(resp["SecretString"])

    raise RuntimeError(
        "No Microsoft credentials found. Set MS_TENANT_ID/MS_CLIENT_ID/MS_CLIENT_SECRET "
        "or MS_CREDENTIALS_SECRET_ARN."
    )


def _get_access_token() -> str:
    """Get an OAuth2 access token using client credentials flow."""
    creds = _get_credentials()
    url = TOKEN_URL.format(tenant_id=creds["tenant_id"])
    resp = requests.post(url, data={
        "grant_type": "client_credentials",
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "scope": "https://graph.microsoft.com/.default",
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def _graph_headers() -> dict:
    """Return auth headers for Graph API calls."""
    token = _get_access_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _get_workbook_url(headers: dict = None) -> str:
    """Build the Graph API URL for the Excel workbook.

    With Sites.Selected file-level permission, the app can ONLY access the
    specific file by its direct drive+item URL. Both MS_DRIVE_ID and
    MS_WORKBOOK_ID must be provided.
    """
    drive_id = os.environ.get("MS_DRIVE_ID")
    workbook_id = os.environ.get("MS_WORKBOOK_ID")

    if not drive_id or not workbook_id:
        raise RuntimeError(
            "MS_DRIVE_ID and MS_WORKBOOK_ID environment variables are required. "
            "With Sites.Selected file-level permission, the app can only access "
            "the specific file by its direct URL."
        )

    return f"{GRAPH_BASE}/drives/{drive_id}/items/{workbook_id}/workbook"


def get_sheet_url() -> str:
    """Return the browser URL to the Excel workbook."""
    workbook_id = os.environ.get("MS_WORKBOOK_ID")
    drive_id = os.environ.get("MS_DRIVE_ID")

    if workbook_id and drive_id:
        # Try to get the web URL via Graph
        try:
            headers = _graph_headers()
            resp = requests.get(
                f"{GRAPH_BASE}/drives/{drive_id}/items/{workbook_id}",
                headers=headers,
                params={"$select": "webUrl"},
            )
            if resp.status_code == 200:
                return resp.json().get("webUrl", "")
        except Exception:
            pass

    # Fallback — return empty (emails will skip the link)
    return os.environ.get("MS_WORKBOOK_URL", "")


def _ensure_headers(workbook_url: str, headers: dict):
    """Ensure the Grants worksheet exists and has headers."""
    # Check if worksheet exists
    resp = requests.get(
        f"{workbook_url}/worksheets",
        headers=headers,
    )
    resp.raise_for_status()
    worksheets = resp.json().get("value", [])
    sheet_names = [ws["name"] for ws in worksheets]

    if "Grants" not in sheet_names:
        # Create the worksheet
        resp = requests.post(
            f"{workbook_url}/worksheets",
            headers=headers,
            json={"name": "Grants"},
        )
        resp.raise_for_status()
        logger.info("Created 'Grants' worksheet")

    # Check if headers are already there
    resp = requests.get(
        f"{workbook_url}/worksheets/Grants/range(address='A1:K1')",
        headers=headers,
    )
    if resp.status_code == 200:
        values = resp.json().get("values", [[]])
        if values and values[0] and values[0][0] == "Date":
            return  # Headers already exist

    # Write headers
    resp = requests.patch(
        f"{workbook_url}/worksheets/Grants/range(address='A1:K1')",
        headers=headers,
        json={"values": [SHEET_HEADERS]},
    )
    resp.raise_for_status()
    logger.info("Wrote headers to Grants worksheet")


def append_scored_grants(conn) -> int:
    """Append newly scored grants to the Excel workbook."""
    workbook_id = os.environ.get("MS_WORKBOOK_ID")
    workbook_path = os.environ.get("MS_WORKBOOK_PATH")
    if not workbook_id and not workbook_path:
        logger.info("MS_WORKBOOK_ID/MS_WORKBOOK_PATH not set — skipping Excel append")
        return 0

    headers = _graph_headers()
    workbook_url = _get_workbook_url(headers)
    _ensure_headers(workbook_url, headers)

    # Get existing grant IDs from column K to avoid duplicates
    existing_ids = set()
    try:
        resp = requests.get(
            f"{workbook_url}/worksheets/Grants/usedRange",
            headers=headers,
            params={"$select": "values"},
        )
        if resp.status_code == 200:
            all_values = resp.json().get("values", [])
            # Grant ID is column K (index 10)
            for row in all_values[1:]:  # Skip header
                if len(row) > 10 and row[10]:
                    existing_ids.add(str(row[10]))
    except Exception as e:
        logger.warning("Could not read existing grant IDs: %s", e)

    # Fetch grants scored in the last 24 hours
    cur = conn.cursor()
    cur.execute(
        """
        SELECT grant_id, title, funder, deadline, score, score_reasoning,
               scored_by_profiles, source_url, approval_status
        FROM grants
        WHERE score IS NOT NULL
          AND scored_at >= NOW() - INTERVAL '24 hours'
        ORDER BY score DESC
        """,
    )
    grants = cur.fetchall()
    cur.close()

    rows_to_add = []
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for grant_id, title, funder, deadline, score, reasoning, profiles, source_url, status in grants:
        if str(grant_id) in existing_ids:
            continue

        deadline_str = deadline.strftime("%Y-%m-%d") if deadline else ""
        profiles_str = ", ".join(profiles) if profiles else ""
        reasoning_short = (reasoning or "")[:300]

        rows_to_add.append([
            today_str,
            title or "Untitled",
            funder or "Unknown",
            deadline_str,
            float(score) if score else 0,
            reasoning_short,
            profiles_str,
            source_url or "",
            status or "",
            "",  # Skip Reason — staff fills this in
            str(grant_id),
        ])

    if rows_to_add:
        # Graph API: add rows to the table
        resp = requests.post(
            f"{workbook_url}/worksheets/Grants/tables/add",
            headers=headers,
            json={
                "address": "A1:K1",
                "hasHeaders": True,
            },
        )
        # Table might already exist — that's fine

        # Append rows using range API
        # Find the next empty row
        resp = requests.get(
            f"{workbook_url}/worksheets/Grants/usedRange",
            headers=headers,
            params={"$select": "rowCount"},
        )
        if resp.status_code == 200:
            used_rows = resp.json().get("rowCount", 1)
        else:
            used_rows = 1

        start_row = used_rows + 1
        end_row = start_row + len(rows_to_add) - 1
        range_addr = f"A{start_row}:K{end_row}"

        resp = requests.patch(
            f"{workbook_url}/worksheets/Grants/range(address='{range_addr}')",
            headers=headers,
            json={"values": rows_to_add},
        )
        resp.raise_for_status()
        logger.info("Appended %d grants to Excel workbook", len(rows_to_add))
    else:
        logger.info("No new grants to append to Excel workbook")

    return len(rows_to_add)


def sync_approvals_from_sheet(conn) -> int:
    """Read approval decisions from the Excel workbook back into RDS."""
    workbook_id = os.environ.get("MS_WORKBOOK_ID")
    workbook_path = os.environ.get("MS_WORKBOOK_PATH")
    if not workbook_id and not workbook_path:
        logger.info("MS_WORKBOOK_ID/MS_WORKBOOK_PATH not set — skipping approval sync")
        return 0

    headers = _graph_headers()
    workbook_url = _get_workbook_url(headers)

    # Read all data from the Grants worksheet
    resp = requests.get(
        f"{workbook_url}/worksheets/Grants/usedRange",
        headers=headers,
        params={"$select": "values"},
    )
    if resp.status_code != 200:
        logger.warning("Could not read Excel workbook: %s", resp.text)
        return 0

    all_rows = resp.json().get("values", [])
    if len(all_rows) <= 1:
        return 0

    header = all_rows[0]
    try:
        status_idx = header.index("Status")
        skip_reason_idx = header.index("Skip Reason")
        grant_id_idx = header.index("Grant ID")
    except ValueError:
        logger.warning("Excel sheet missing expected columns — skipping sync")
        return 0

    cur = conn.cursor()
    synced = 0

    for row in all_rows[1:]:
        if len(row) <= grant_id_idx:
            continue

        grant_id = str(row[grant_id_idx]).strip()
        status = str(row[status_idx]).strip().lower()
        skip_reason = str(row[skip_reason_idx]).strip().lower() if len(row) > skip_reason_idx else ""

        if not grant_id or not status:
            continue

        if status in ("approved", "approve", "yes"):
            cur.execute(
                "UPDATE grants SET approval_status = 'approved' WHERE grant_id = %s AND approval_status IS DISTINCT FROM 'approved'",
                (grant_id,),
            )
            if cur.rowcount > 0:
                synced += 1

        elif status in ("skip", "skipped", "no", "deny", "denied"):
            reason = skip_reason or "other"
            cur.execute(
                "UPDATE grants SET approval_status = 'skipped', skip_reason = %s WHERE grant_id = %s AND approval_status IS DISTINCT FROM 'skipped'",
                (reason, grant_id),
            )
            if cur.rowcount > 0:
                synced += 1

    conn.commit()
    cur.close()

    if synced:
        logger.info("Synced %d approval decisions from Excel workbook", synced)
    return synced
