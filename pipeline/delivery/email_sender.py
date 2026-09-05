"""Optional email transport, disabled by default and never a publication path.

Provider acceptance is not proof of inbox delivery. Automated CLI delivery stays
unavailable until consent, unsubscribe and delivery-event operations are wired.
"""
from __future__ import annotations
import os
import re
from datetime import datetime, timezone
from html import escape
from urllib.parse import urlsplit
import requests
from normalization import number, sale_date
from config.settings import EMAIL_PROVIDER, EMAIL_API_KEY, EMAIL_FROM, EMAIL_FROM_NAME


def _url(value):
    try:
        url=urlsplit(str(value))
        return str(value) if url.scheme=='https' and url.hostname and not url.username and not url.password else None
    except ValueError: return None


def _current(deal):
    expiry=sale_date(deal.get('verification_expires_at'))
    return deal.get('verification_status')=='verified' and bool(deal.get('verified_at')) and expiry and expiry>datetime.now(timezone.utc)


def _money(value):
    parsed=number(value)
    return f'${parsed:,.0f}' if parsed is not None else 'Not published'


def format_deal_for_email(deal: dict) -> str:
    if not _current(deal): raise ValueError('Only current, verified opportunities may be rendered')
    source=_url(deal.get('source_url'))
    if not source: raise ValueError('A source URL is required')
    heading=escape(str(deal.get('address') or deal.get('apn') or 'Parcel'))
    county=escape(str(deal.get('county_id') or ''))
    return (f'<article><h2>{heading}</h2><p>{county}</p><dl>'
        f'<dt>Asking price</dt><dd>{_money(deal.get("asking_price"))}</dd>'
        f'<dt>Estimated costs</dt><dd>{_money(deal.get("estimated_costs"))}</dd>'
        f'<dt>Estimated ARV</dt><dd>{_money(deal.get("estimated_arv_low"))} – {_money(deal.get("estimated_arv_high"))}</dd>'
        f'</dl><a href="{escape(source,quote=True)}">Review source evidence</a></article>')


def build_daily_email(deals: list[dict],subscriber_name: str='',*,unsubscribe_url: str | None=None) -> dict:
    unsubscribe=_url(unsubscribe_url)
    if not unsubscribe: raise ValueError('A real HTTPS unsubscribe URL is required')
    if not deals: raise ValueError('No verified opportunities to include')
    body=''.join(format_deal_for_email(deal) for deal in deals)
    return {'subject':f'DealScan: {len(deals)} verified opportunities to research',
        'html':f'<main><h1>DealScan research</h1><p>Hello {escape(subscriber_name)}.</p>{body}'
            '<p>Screening estimates are not guarantees. Verify title, access, zoning, sales and costs independently.</p>'
            f'<p><a href="{escape(unsubscribe,quote=True)}">Unsubscribe</a></p></main>'}


def send_email(to: str,subject: str,html: str,*,consented: bool=False,unsubscribe_url: str | None=None) -> bool:
    if os.getenv('ENABLE_EMAIL_DELIVERY')!='true' or not consented or not _url(unsubscribe_url): return False
    if not EMAIL_API_KEY or not EMAIL_FROM or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',to): return False
    if EMAIL_PROVIDER=='resend':
        endpoint='https://api.resend.com/emails'
        payload={'from':f'{EMAIL_FROM_NAME} <{EMAIL_FROM}>','to':[to],'subject':subject,'html':html}
    elif EMAIL_PROVIDER=='sendgrid':
        endpoint='https://api.sendgrid.com/v3/mail/send'
        payload={'personalizations':[{'to':[{'email':to}]}],'from':{'email':EMAIL_FROM,'name':EMAIL_FROM_NAME},
                 'subject':subject,'content':[{'type':'text/html','value':html}]}
    else:
        # Console output is not a sent message; never log recipients or bodies.
        return False
    try:
        response=requests.post(endpoint,headers={'Authorization':f'Bearer {EMAIL_API_KEY}'},json=payload,
                               timeout=(5,15),allow_redirects=False)
        return response.status_code in (200,201,202)
    except requests.RequestException:
        return False


def deliver_daily_deals(deals: list[dict],subscribers: list[dict]) -> dict:
    if os.getenv('ENABLE_EMAIL_DELIVERY')!='true': return {'status':'disabled','accepted':0,'failed':0,'skipped':len(subscribers)}
    # Never send an arbitrary supplied bundle. Re-read current verified records.
    from database import get_top_deals
    requested={(deal.get('county_id'),deal.get('apn')) for deal in deals}
    current=[row for row in get_top_deals(limit=100) if (row.get('county_id'),row.get('apn')) in requested and _current(row)][:10]
    if not current: return {'status':'no_verified_opportunities','accepted':0,'failed':0,'skipped':len(subscribers)}
    if len(subscribers)>100: raise ValueError('Email batch exceeds the manual safety limit')
    accepted=failed=skipped=0
    for subscriber in subscribers:
        consent=sale_date(subscriber.get('consented_at'))
        unsubscribe=_url(subscriber.get('unsubscribe_url'))
        if subscriber.get('is_active') not in (True,1) or not consent or consent>datetime.now(timezone.utc) or not unsubscribe:
            skipped+=1
            continue
        try:
            content=build_daily_email(current,subscriber.get('name') or '',unsubscribe_url=unsubscribe)
            ok=send_email(subscriber.get('email') or '',**content,consented=True,unsubscribe_url=unsubscribe)
        except ValueError: ok=False
        if ok: accepted+=1
        else: failed+=1
    return {'status':'partial' if accepted and (failed or skipped) else 'accepted_by_provider' if accepted else 'failed',
            'accepted':accepted,'failed':failed,'skipped':skipped}
