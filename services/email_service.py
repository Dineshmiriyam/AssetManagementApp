"""
Email notification service — Gmail SMTP.
Sends SLA alert reports to Admin and Operations users.
"""

import os
import smtplib
import logging
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config.constants import EMAIL_CONFIG, SLA_CONFIG
from services.sla_service import get_sla_breached_assets, get_sla_counts

logger = logging.getLogger(__name__)


def _get_email_credentials():
    """Return (email_address, app_password) from environment or None."""
    address = os.getenv("EMAIL_ADDRESS", "").strip()
    password = os.getenv("EMAIL_APP_PASSWORD", "").strip()
    if not address or not password:
        return None, None
    return address, password


def _get_notification_recipients():
    """Fetch email addresses for active Admin and Operations users."""
    try:
        from database.auth import get_all_users
        users = get_all_users()
        recipients = []
        for u in users:
            role = (u.get("role") or "").lower()
            is_active = u.get("is_active", False)
            email = (u.get("email") or "").strip()
            if is_active and email and role in ("admin", "operations"):
                recipients.append(email)
        return recipients
    except Exception as e:
        logger.error(f"Failed to fetch notification recipients: {e}")
        return []


def _build_sla_email_html(breached_assets, sla_counts):
    """Build HTML email body for SLA report."""
    today_str = date.today().strftime("%B %d, %Y")
    critical = sla_counts.get("critical", 0)
    warning = sla_counts.get("warning", 0)
    ok = sla_counts.get("ok", 0)

    # Summary section
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
        <div style="background: #1e293b; color: white; padding: 20px 24px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0; font-size: 20px;">NXTBY — SLA Alert Report</h2>
            <p style="margin: 4px 0 0; font-size: 13px; color: #94a3b8;">{today_str}</p>
        </div>

        <div style="background: #f8fafc; padding: 20px 24px; border: 1px solid #e2e8f0;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="text-align: center; padding: 12px;">
                        <div style="font-size: 32px; font-weight: 700; color: #dc2626;">{critical}</div>
                        <div style="font-size: 12px; color: #6b7280; margin-top: 4px;">Critical</div>
                    </td>
                    <td style="text-align: center; padding: 12px;">
                        <div style="font-size: 32px; font-weight: 700; color: #f59e0b;">{warning}</div>
                        <div style="font-size: 12px; color: #6b7280; margin-top: 4px;">Warning</div>
                    </td>
                    <td style="text-align: center; padding: 12px;">
                        <div style="font-size: 32px; font-weight: 700; color: #16a34a;">{ok}</div>
                        <div style="font-size: 12px; color: #6b7280; margin-top: 4px;">OK</div>
                    </td>
                </tr>
            </table>
        </div>
    """

    if breached_assets:
        html += """
        <div style="padding: 20px 24px; border: 1px solid #e2e8f0; border-top: none;">
            <h3 style="margin: 0 0 12px; font-size: 15px; color: #1e293b;">Assets Needing Attention</h3>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead>
                    <tr style="background: #f1f5f9;">
                        <th style="padding: 8px 10px; text-align: left; border-bottom: 2px solid #e2e8f0;">Serial</th>
                        <th style="padding: 8px 10px; text-align: left; border-bottom: 2px solid #e2e8f0;">Status</th>
                        <th style="padding: 8px 10px; text-align: center; border-bottom: 2px solid #e2e8f0;">Days</th>
                        <th style="padding: 8px 10px; text-align: left; border-bottom: 2px solid #e2e8f0;">Client</th>
                        <th style="padding: 8px 10px; text-align: center; border-bottom: 2px solid #e2e8f0;">SLA</th>
                    </tr>
                </thead>
                <tbody>
        """
        for asset in breached_assets:
            level = asset["sla_level"]
            if level == "critical":
                badge_bg, badge_color = "#fef2f2", "#dc2626"
                badge_text = "CRITICAL"
            else:
                badge_bg, badge_color = "#fffbeb", "#d97706"
                badge_text = "WARNING"

            status_display = asset["status"].replace("_", " ").title()

            html += f"""
                    <tr style="border-bottom: 1px solid #f1f5f9;">
                        <td style="padding: 8px 10px; font-weight: 600;">{asset['serial']}</td>
                        <td style="padding: 8px 10px;">{status_display}</td>
                        <td style="padding: 8px 10px; text-align: center; font-weight: 600;">{asset['days']}</td>
                        <td style="padding: 8px 10px;">{asset['client']}</td>
                        <td style="padding: 8px 10px; text-align: center;">
                            <span style="background: {badge_bg}; color: {badge_color}; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">{badge_text}</span>
                        </td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
        </div>
        """
    else:
        html += """
        <div style="padding: 20px 24px; border: 1px solid #e2e8f0; border-top: none; text-align: center; color: #16a34a;">
            <p style="font-size: 14px;">All assets are within SLA thresholds.</p>
        </div>
        """

    # SLA thresholds reference
    html += """
        <div style="padding: 16px 24px; background: #f8fafc; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
            <p style="font-size: 11px; color: #94a3b8; margin: 0;">SLA Thresholds — """
    threshold_parts = []
    for status, config in SLA_CONFIG.items():
        name = status.replace("_", " ").title()
        threshold_parts.append(f"{name}: {config['warning']}d warn / {config['critical']}d critical")
    html += " | ".join(threshold_parts)
    html += """</p>
            <p style="font-size: 11px; color: #94a3b8; margin: 4px 0 0;">This is an automated report from NXTBY Asset Management System.</p>
        </div>
    </div>
    """
    return html


def send_sla_report(assets_df):
    """
    Build and send SLA report email to Admin + Operations users.
    Returns (success_count, fail_count, error_message).
    """
    sender, password = _get_email_credentials()
    if not sender or not password:
        return 0, 0, "Email not configured. Set EMAIL_ADDRESS and EMAIL_APP_PASSWORD in environment variables."

    recipients = _get_notification_recipients()
    if not recipients:
        return 0, 0, "No active Admin or Operations users with email addresses found."

    # Build report data
    sla_counts = get_sla_counts(assets_df)
    breached_assets = get_sla_breached_assets(assets_df)

    # Build email
    critical = sla_counts.get("critical", 0)
    warning = sla_counts.get("warning", 0)
    today_str = date.today().strftime("%b %d, %Y")

    if critical > 0:
        subject = f"{EMAIL_CONFIG['subject_prefix']} SLA Alert: {critical} Critical, {warning} Warning — {today_str}"
    elif warning > 0:
        subject = f"{EMAIL_CONFIG['subject_prefix']} SLA Warning: {warning} assets approaching threshold — {today_str}"
    else:
        subject = f"{EMAIL_CONFIG['subject_prefix']} SLA Report: All OK — {today_str}"

    html_body = _build_sla_email_html(breached_assets, sla_counts)

    # Send to each recipient
    success_count = 0
    fail_count = 0

    try:
        server = smtplib.SMTP(EMAIL_CONFIG["smtp_host"], EMAIL_CONFIG["smtp_port"], timeout=EMAIL_CONFIG["timeout"])
        server.starttls()
        server.login(sender, password)

        for recipient in recipients:
            try:
                msg = MIMEMultipart("alternative")
                msg["From"] = sender
                msg["To"] = recipient
                msg["Subject"] = subject
                msg.attach(MIMEText(html_body, "html"))
                server.sendmail(sender, recipient, msg.as_string())
                success_count += 1
                logger.info(f"SLA report sent to {recipient}")
            except Exception as e:
                fail_count += 1
                logger.error(f"Failed to send SLA report to {recipient}: {e}")

        server.quit()
    except smtplib.SMTPAuthenticationError:
        return 0, len(recipients), "Gmail authentication failed. Check EMAIL_ADDRESS and EMAIL_APP_PASSWORD."
    except Exception as e:
        logger.error(f"SMTP connection error: {e}")
        return success_count, len(recipients) - success_count, f"SMTP error: {str(e)}"

    return success_count, fail_count, None
