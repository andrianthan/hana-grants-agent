#!/usr/bin/env python3
"""Email notifications for the evaluation pipeline.

Sends daily grant alerts and weekly Friday digest emails via Amazon SES.
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import boto3

logger = logging.getLogger(__name__)

from sheets import get_sheet_url

SES_REGION = os.environ.get("AWS_REGION_NAME", "us-west-2")
SENDER_EMAIL = os.environ.get("NOTIFICATION_SENDER")
RECIPIENT_EMAIL = os.environ.get("NOTIFICATION_RECIPIENT")
SCORE_THRESHOLD = 6.0


def _get_ses_client():
    return boto3.client("ses", region_name=SES_REGION)


def send_daily_alert(conn, pipeline_result: dict):
    """Send daily email summarizing today's grant scoring results.

    Always sends — subject line shows count at a glance so you know
    without opening whether new grants were found.
    """
    cur = conn.cursor()
    # Get all grants scored today (above threshold)
    cur.execute(
        """
        SELECT title, funder, score, score_reasoning, deadline, grant_id, source_url
        FROM grants
        WHERE score >= %s
          AND scored_at >= NOW() - INTERVAL '24 hours'
        ORDER BY score DESC
        """,
        (SCORE_THRESHOLD,),
    )
    above_grants = cur.fetchall()

    # Get grants scored today but below threshold
    cur.execute(
        """
        SELECT title, funder, score, score_reasoning, deadline, grant_id, source_url
        FROM grants
        WHERE score < %s
          AND score IS NOT NULL
          AND scored_at >= NOW() - INTERVAL '24 hours'
        ORDER BY score DESC
        """,
        (SCORE_THRESHOLD,),
    )
    below_grants = cur.fetchall()
    cur.close()

    total_scored = len(above_grants) + len(below_grants)

    # Subject line tells you everything at a glance
    if above_grants:
        subject = f"Hanna Grants: {len(above_grants)} new grant{'s' if len(above_grants) != 1 else ''} found today ({total_scored} scored)"
    elif total_scored > 0:
        subject = f"Hanna Grants: 0 new grants today ({total_scored} scored, none above 6.0)"
    else:
        subject = "Hanna Grants: 0 new grants today (no new grants to score)"

    # Build HTML body
    today_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    sheet_url = get_sheet_url()

    if not above_grants and not below_grants:
        # No grants scored at all
        html_body = f"""
        <html>
        <body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;">
            <h2 style="color:#1a237e;">Daily Grant Report — {today_str}</h2>
            <div style="background:#f5f5f5;padding:20px;border-radius:8px;text-align:center;">
                <p style="font-size:16px;color:#666;margin:0;">No new grants were found or scored today.</p>
                <p style="font-size:13px;color:#999;margin-top:8px;">The pipeline ran but found no new grants to evaluate.</p>
            </div>
            <p style="margin-top:20px;font-size:12px;color:#999;">Hanna Grants Agent</p>
        </body>
        </html>
        """
        text_body = f"Daily Grant Report — {today_str}\nNo new grants were found or scored today.\n"
    else:
        # Build grant table
        rows_html = ""
        for title, funder, score, reasoning, deadline, grant_id, source_url in above_grants:
            deadline_str = deadline.strftime("%b %d, %Y") if deadline else "No deadline"
            reasoning_short = (reasoning or "")[:200]
            title_html = (
                f'<a href="{_esc(source_url)}" style="color:#1a237e;text-decoration:none;">{_esc(title or "Untitled")}</a>'
                if source_url
                else f'{_esc(title or "Untitled")}'
            )
            rows_html += f"""
            <tr>
                <td style="padding:12px;border-bottom:1px solid #eee;">
                    <strong>{title_html}</strong><br>
                    <span style="color:#666;font-size:13px;">{_esc(funder or 'Unknown funder')}</span>
                </td>
                <td style="padding:12px;border-bottom:1px solid #eee;text-align:center;">
                    <span style="font-size:20px;font-weight:bold;color:{'#2e7d32' if score >= 7.0 else '#f57f17'};">{score:.1f}</span>
                </td>
                <td style="padding:12px;border-bottom:1px solid #eee;font-size:13px;color:#555;">
                    {deadline_str}
                </td>
            </tr>
            <tr>
                <td colspan="3" style="padding:4px 12px 12px;border-bottom:2px solid #ddd;font-size:12px;color:#777;">
                    {_esc(reasoning_short)}
                    {'<br><a href="' + _esc(source_url) + '" style="color:#1565c0;font-size:12px;margin-top:6px;display:inline-block;">View Grant &rarr;</a>' if source_url else ''}
                </td>
            </tr>
            """

        html_body = f"""
        <html>
        <body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;">
            <h2 style="color:#1a237e;">Daily Grant Report — {today_str}</h2>

            <div style="background:#e8f5e9;padding:15px;border-radius:8px;margin-bottom:20px;">
                <strong>{len(above_grants)}</strong> above threshold (6.0+) &nbsp;|&nbsp;
                <strong>{len(below_grants)}</strong> below threshold &nbsp;|&nbsp;
                <strong>{total_scored}</strong> total scored
            </div>
            {'<div style="background:#e3f2fd;padding:12px;border-radius:8px;margin-bottom:20px;text-align:center;"><a href="' + _esc(sheet_url) + '" style="color:#1565c0;font-weight:bold;text-decoration:none;font-size:15px;">Open Grants Tracker &rarr;</a><br><span style="font-size:12px;color:#666;">Review, approve, or skip grants in Google Sheets</span></div>' if sheet_url else ''}
        """

        if above_grants:
            html_body += f"""
            <h3 style="color:#2e7d32;">Recommended Grants</h3>
            <table style="width:100%;border-collapse:collapse;">
                <tr style="background:#f5f5f5;">
                    <th style="padding:10px;text-align:left;">Grant</th>
                    <th style="padding:10px;text-align:center;width:60px;">Score</th>
                    <th style="padding:10px;text-align:left;width:100px;">Deadline</th>
                </tr>
                {rows_html}
            </table>
            """

        if below_grants:
            below_html = ""
            for title, funder, score, reasoning, deadline, grant_id, source_url in below_grants:
                below_html += f"""
                <tr>
                    <td style="padding:6px 12px;border-bottom:1px solid #eee;font-size:13px;">
                        {_esc(title or 'Untitled')} ({_esc(funder or 'Unknown')})
                    </td>
                    <td style="padding:6px;border-bottom:1px solid #eee;text-align:center;font-size:13px;color:#999;">
                        {score:.1f}
                    </td>
                </tr>
                """
            html_body += f"""
            <h3 style="color:#999;margin-top:25px;font-size:14px;">Below Threshold ({len(below_grants)})</h3>
            <table style="width:100%;border-collapse:collapse;">{below_html}</table>
            """

        html_body += """
            <p style="margin-top:20px;font-size:12px;color:#999;">Hanna Grants Agent</p>
        </body>
        </html>
        """

        text_body = f"Daily Grant Report — {today_str}\n"
        text_body += f"{len(above_grants)} above threshold | {len(below_grants)} below | {total_scored} total\n\n"
        if above_grants:
            text_body += "=== RECOMMENDED (6.0+) ===\n"
            for title, funder, score, reasoning, deadline, grant_id, source_url in above_grants:
                deadline_str = deadline.strftime("%b %d, %Y") if deadline else "No deadline"
                text_body += f"- {title} ({funder}) — Score: {score:.1f} — Deadline: {deadline_str}\n"
                if source_url:
                    text_body += f"  Link: {source_url}\n"
                text_body += f"  {(reasoning or '')[:150]}\n\n"
        if below_grants:
            text_body += "=== BELOW THRESHOLD ===\n"
            for title, funder, score, reasoning, deadline, grant_id, source_url in below_grants:
                text_body += f"  {title} — {score:.1f}\n"

    _send_email(subject, html_body, text_body)
    logger.info("Daily alert sent: %d above, %d below, %d total to %s",
                len(above_grants), len(below_grants), total_scored, RECIPIENT_EMAIL)


def send_weekly_digest(conn):
    """Send weekly Friday digest of all grants scored in the past 7 days.

    Includes all scored grants (above and below threshold) grouped by profile,
    sorted by score descending.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT title, funder, score, score_reasoning, deadline,
               scored_by_profiles, grant_id, score_flags, source_url
        FROM grants
        WHERE scored_at >= NOW() - INTERVAL '7 days'
          AND score IS NOT NULL
        ORDER BY score DESC
        """,
    )
    grants = cur.fetchall()
    cur.close()

    if not grants:
        # Still send an email so staff knows the pipeline is running
        week_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
        _send_email(
            "Hanna Grants Weekly Digest: No new grants this week",
            f"""
            <html>
            <body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;">
                <h2 style="color:#1a237e;">Weekly Grant Digest</h2>
                <p style="color:#555;">Week ending {week_str}</p>
                <div style="background:#f5f5f5;padding:20px;border-radius:8px;text-align:center;">
                    <p style="font-size:16px;color:#666;margin:0;">No new grants were scored this week.</p>
                    <p style="font-size:13px;color:#999;margin-top:8px;">The pipeline ran daily but found no new grants to evaluate.</p>
                </div>
                <p style="margin-top:20px;font-size:12px;color:#999;">Hanna Grants Agent</p>
            </body>
            </html>
            """,
            f"Weekly Grant Digest — Week ending {week_str}\nNo new grants were scored this week.\n",
        )
        logger.info("Weekly digest sent: no grants this week")
        return

    above = [g for g in grants if g[2] >= SCORE_THRESHOLD]
    below = [g for g in grants if g[2] < SCORE_THRESHOLD]

    subject = f"Hanna Grants Weekly Digest: {len(above)} promising grants this week"
    sheet_url = get_sheet_url()

    # Build HTML
    html_body = f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;">
        <h2 style="color:#1a237e;">Weekly Grant Digest</h2>
        <p style="color:#555;">Week ending {datetime.now(timezone.utc).strftime('%B %d, %Y')}</p>

        <div style="background:#e8f5e9;padding:15px;border-radius:8px;margin-bottom:20px;">
            <strong>{len(above)}</strong> grants above threshold (6.0+) &nbsp;|&nbsp;
            <strong>{len(below)}</strong> below threshold &nbsp;|&nbsp;
            <strong>{len(grants)}</strong> total scored
        </div>
        {'<div style="background:#e3f2fd;padding:12px;border-radius:8px;margin-bottom:20px;text-align:center;"><a href="' + _esc(sheet_url) + '" style="color:#1565c0;font-weight:bold;text-decoration:none;font-size:15px;">Open Grants Tracker &rarr;</a><br><span style="font-size:12px;color:#666;">Review, approve, or skip grants in Google Sheets</span></div>' if sheet_url else ''}
    """

    if above:
        html_body += """
        <h3 style="color:#2e7d32;">Recommended Grants (Score 6.0+)</h3>
        <table style="width:100%;border-collapse:collapse;">
        """
        for title, funder, score, reasoning, deadline, profiles, gid, flags, source_url in above:
            deadline_str = deadline.strftime("%b %d, %Y") if deadline else "No deadline"
            profiles_str = ", ".join(profiles) if profiles else "N/A"
            title_html = (
                f'<a href="{_esc(source_url)}" style="color:#1a237e;text-decoration:none;">{_esc(title or "Untitled")}</a>'
                if source_url
                else f'{_esc(title or "Untitled")}'
            )
            html_body += f"""
            <tr style="background:#f9f9f9;">
                <td style="padding:12px;border-bottom:1px solid #ddd;" colspan="2">
                    <strong style="font-size:15px;">{title_html}</strong><br>
                    <span style="color:#666;font-size:13px;">{_esc(funder or 'Unknown')}</span>
                    &nbsp;&bull;&nbsp;
                    <span style="font-size:13px;">Deadline: {deadline_str}</span>
                </td>
                <td style="padding:12px;border-bottom:1px solid #ddd;text-align:center;vertical-align:top;">
                    <span style="font-size:22px;font-weight:bold;color:#2e7d32;">{score:.1f}</span>
                </td>
            </tr>
            <tr>
                <td colspan="3" style="padding:8px 12px 16px;border-bottom:2px solid #eee;">
                    <div style="font-size:13px;color:#555;margin-bottom:6px;">{_esc((reasoning or '')[:300])}</div>
                    <div style="font-size:11px;color:#999;">Profiles: {_esc(profiles_str)}</div>
                    {'<a href="' + _esc(source_url) + '" style="color:#1565c0;font-size:12px;margin-top:6px;display:inline-block;">View Grant &rarr;</a>' if source_url else ''}
                </td>
            </tr>
            """
        html_body += "</table>"

    if below:
        html_body += f"""
        <h3 style="color:#f57f17;margin-top:30px;">Below Threshold ({len(below)} grants)</h3>
        <table style="width:100%;border-collapse:collapse;">
        """
        for title, funder, score, reasoning, deadline, profiles, gid, flags, source_url in below:
            html_body += f"""
            <tr>
                <td style="padding:8px 12px;border-bottom:1px solid #eee;font-size:13px;">
                    {_esc(title or 'Untitled')} ({_esc(funder or 'Unknown')})
                </td>
                <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;font-size:13px;color:#f57f17;">
                    {score:.1f}
                </td>
            </tr>
            """
        html_body += "</table>"

    html_body += """
        <p style="margin-top:30px;font-size:12px;color:#999;">
            Generated by Hanna Grants Agent. Review recommended grants and reach out to funders for promising opportunities.
        </p>
    </body>
    </html>
    """

    text_body = f"Weekly Grant Digest — Week ending {datetime.now(timezone.utc).strftime('%B %d, %Y')}\n"
    text_body += f"{len(above)} above threshold | {len(below)} below | {len(grants)} total\n\n"
    text_body += "=== RECOMMENDED (6.0+) ===\n"
    for title, funder, score, reasoning, deadline, profiles, gid, flags, source_url in above:
        text_body += f"\n{title} ({funder}) — Score: {score:.1f}\n"
        if source_url:
            text_body += f"  Link: {source_url}\n"
        text_body += f"  {(reasoning or '')[:200]}\n"
    if below:
        text_body += "\n=== BELOW THRESHOLD ===\n"
        for title, funder, score, reasoning, deadline, profiles, gid, flags, source_url in below:
            text_body += f"  {title} — {score:.1f}\n"

    _send_email(subject, html_body, text_body)
    logger.info("Weekly digest sent: %d grants (%d above threshold) to %s",
                len(grants), len(above), RECIPIENT_EMAIL)


def _send_email(subject: str, html_body: str, text_body: str):
    """Send an email via SES."""
    if not SENDER_EMAIL or not RECIPIENT_EMAIL:
        raise RuntimeError(
            "NOTIFICATION_SENDER and NOTIFICATION_RECIPIENT environment variables are required"
        )
    ses = _get_ses_client()
    try:
        ses.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": [RECIPIENT_EMAIL]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                },
            },
        )
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        raise


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
