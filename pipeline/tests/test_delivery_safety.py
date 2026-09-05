from datetime import datetime,timedelta,timezone
import pytest
from delivery import email_sender as mail
from models import Deal,Subscriber


def current():
    return {'apn':'fixture','county_id':'fixture','address':'<script>unsafe</script>',
        'verification_status':'verified','verified_at':datetime.now(timezone.utc).isoformat(),
        'verification_expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
        'source_url':'https://county.example/record'}


def test_no_fake_prices_preferences_or_default_consent():
    assert Deal().asking_price is None and Deal().competition_level is None
    assert Subscriber().is_active is False and Subscriber().consented_at is None
    assert Subscriber().budget_min is None


def test_renderer_escapes_source_content_and_requires_current_verification():
    html=mail.format_deal_for_email(current())
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert '$0' not in html and 'Not published' in html
    with pytest.raises(ValueError): mail.format_deal_for_email({**current(),'verification_status':'pending_review'})
    with pytest.raises(ValueError): mail.build_daily_email([current()],unsubscribe_url='#')


def test_disabled_or_console_transport_cannot_report_sent_or_log_recipients(monkeypatch,capsys):
    monkeypatch.delenv('ENABLE_EMAIL_DELIVERY',raising=False)
    assert mail.send_email('private@example.com','test','private') is False
    monkeypatch.setenv('ENABLE_EMAIL_DELIVERY','true');monkeypatch.setattr(mail,'EMAIL_PROVIDER','console')
    assert mail.send_email('private@example.com','test','private',consented=True,unsubscribe_url='https://app.example/unsubscribe') is False
    assert 'private' not in capsys.readouterr().out


def test_provider_calls_are_opt_in_bounded_and_never_follow_credential_redirects(monkeypatch):
    monkeypatch.setenv('ENABLE_EMAIL_DELIVERY','true')
    monkeypatch.setattr(mail,'EMAIL_PROVIDER','resend');monkeypatch.setattr(mail,'EMAIL_API_KEY','ephemeral')
    monkeypatch.setattr(mail,'EMAIL_FROM','sender@example.com')
    calls=[]
    class Response: status_code=202
    monkeypatch.setattr(mail.requests,'post',lambda *a,**kw:calls.append(kw) or Response())
    assert mail.send_email('person@example.com','subject','body') is False
    assert not calls
    assert mail.send_email('person@example.com','subject','body',consented=True,unsubscribe_url='https://app.example/unsubscribe')
    assert calls[0]['timeout']==(5,15) and calls[0]['allow_redirects'] is False
