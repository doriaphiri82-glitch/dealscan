"""
DealScan AI - Email Delivery System
Sends daily deal alerts to subscribers.
"""
import json
from datetime import datetime
from typing import List, Dict
from config.settings import EMAIL_PROVIDER, EMAIL_API_KEY, EMAIL_FROM, EMAIL_FROM_NAME


def format_deal_for_email(deal: Dict) -> str:
    """Format a single deal as HTML for email."""
    signals = deal.get('motivation_signals', '').split(',')
    signal_badges = ''.join(
        f'<span style="background:#fef3c7;color:#92400e;padding:2px 8px;'
        f'border-radius:12px;font-size:12px;margin:2px;">{s.strip()}</span>'
        for s in signals if s.strip()
    )

    return f"""
    <div style="border:1px solid #e5e7eb;border-radius:12px;padding:20px;margin:16px 0;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <div>
          <h3 style="margin:0;font-size:18px;color:#1f2937;">{deal.get('address', 'N/A')}</h3>
          <p style="margin:4px 0 0;color:#6b7280;font-size:14px;">
            {deal.get('county_id', '').replace('_', ' ').title()} | {deal.get('lot_size_acres', 0)} acres
          </p>
        </div>
        <div style="text-align:center;">
          <div style="font-size:24px;font-weight:900;color:#16a34a;">{deal.get('deal_score', 0)}/100</div>
          <div style="font-size:11px;color:#9ca3af;">Deal Score</div>
        </div>
      </div>
      <table style="width:100%;font-size:14px;">
        <tr><td style="color:#6b7280;padding:4px 0;">Asking Price</td>
            <td style="text-align:right;font-weight:700;color:#16a34a;">${deal.get('asking_price', 0):,.0f}</td></tr>
        <tr><td style="color:#6b7280;padding:4px 0;">Est. ARV</td>
            <td style="text-align:right;">${deal.get('estimated_arv_low', 0):,.0f} - ${deal.get('estimated_arv_high', 0):,.0f}</td></tr>
        <tr><td style="color:#6b7280;padding:4px 0;">Est. Profit</td>
            <td style="text-align:right;font-weight:700;color:#16a34a;">${deal.get('estimated_profit_low', 0):,.0f} - ${deal.get('estimated_profit_high', 0):,.0f}</td></tr>
        <tr><td style="color:#6b7280;padding:4px 0;">Recommended Offer</td>
            <td style="text-align:right;">${deal.get('recommended_offer_low', 0):,.0f} - ${deal.get('recommended_offer_high', 0):,.0f}</td></tr>
      </table>
      <div style="margin-top:12px;">{signal_badges}</div>
    </div>
    """


def build_daily_email(deals: List[Dict], subscriber_name: str = '') -> Dict:
    """Build the full daily deals email."""
    today = datetime.now().strftime('%B %d, %Y')
    deals_html = ''.join(format_deal_for_email(d) for d in deals)

    html = f"""
    <div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;">
      <div style="background:#0f172a;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="color:#22c55e;margin:0;font-size:24px;">DealScan AI</h1>
        <p style="color:#94a3b8;margin:8px 0 0;font-size:14px;">Daily Deal Report - {today}</p>
      </div>
      <div style="background:#ffffff;padding:24px;">
        <p style="color:#374151;font-size:16px;">
          Good morning{' ' + subscriber_name if subscriber_name else ''}! Here are today's top deals:
        </p>
        {deals_html}
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;margin-top:20px;">
          <p style="color:#166534;font-size:14px;margin:0;">
            <strong>Next Steps:</strong> Review each deal, verify comps on Zillow/Redfin,
            then send your offer using our templates. Aim to send 5-10 offers per week.
          </p>
        </div>
      </div>
      <div style="background:#f8fafc;padding:16px;border-radius:0 0 12px 12px;text-align:center;">
        <p style="color:#9ca3af;font-size:12px;margin:0;">
          DealScan AI | You're receiving this because you subscribed.
          <a href="#" style="color:#6b7280;">Unsubscribe</a>
        </p>
      </div>
    </div>
    """

    return {
        'subject': f"🏔️ {len(deals)} New Land Deals | Top Score: {deals[0].get('deal_score', 0)}/100" if deals else "No deals today",
        'html': html,
    }


def send_email(to: str, subject: str, html: str) -> bool:
    """Send email using configured provider."""
    if EMAIL_PROVIDER == 'console':
        print(f"\n[EMAIL] To: {to}")
        print(f"[EMAIL] Subject: {subject}")
        print(f"[EMAIL] Body length: {len(html)} chars")
        print("[EMAIL] (Console mode - not actually sent)")
        return True

    elif EMAIL_PROVIDER == 'resend':
        import requests
        resp = requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {EMAIL_API_KEY}'},
            json={
                'from': f'{EMAIL_FROM_NAME} <{EMAIL_FROM}>',
                'to': [to],
                'subject': subject,
                'html': html,
            }
        )
        return resp.status_code == 200

    elif EMAIL_PROVIDER == 'sendgrid':
        import requests
        resp = requests.post(
            'https://api.sendgrid.com/v3/mail/send',
            headers={'Authorization': f'Bearer {EMAIL_API_KEY}'},
            json={
                'personalizations': [{'to': [{'email': to}]}],
                'from': {'email': EMAIL_FROM, 'name': EMAIL_FROM_NAME},
                'subject': subject,
                'content': [{'type': 'text/html', 'value': html}],
            }
        )
        return resp.status_code in (200, 201, 202)

    return False


def deliver_daily_deals(deals: List[Dict], subscribers: List[Dict]):
    """Send daily deals to all subscribers."""
    if not deals:
        print("No deals to deliver today.")
        return

    email_content = build_daily_email(deals)
    sent = 0
    failed = 0

    for sub in subscribers:
        success = send_email(
            to=sub['email'],
            subject=email_content['subject'],
            html=email_content['html'],
        )
        if success:
            sent += 1
        else:
            failed += 1

    print(f"\nDelivery complete: {sent} sent, {failed} failed")
