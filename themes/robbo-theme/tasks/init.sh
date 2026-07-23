# Assign robbo-theme to LMS/CMS/preview sites and seed platform-wide HTML certificate config.
# Runs on Tutor init; safe to re-run (updates existing SiteTheme rows).
./manage.py lms shell -c "
from django.contrib.sites.models import Site
from lms.djangoapps.certificates.models import CertificateHtmlViewConfiguration
import json

def assign_theme(domain):
    if not domain:
        return
    site, _ = Site.objects.get_or_create(domain=domain)
    themes = list(site.themes.all())
    if themes:
        for t in themes:
            if t.theme_dir_name != 'robbo-theme':
                t.theme_dir_name = 'robbo-theme'
                t.save()
    else:
        site.themes.create(theme_dir_name='robbo-theme')

for domain in (
    'local.openedx.io',
    'local.openedx.io:8000',
    'studio.local.openedx.io',
    'studio.local.openedx.io:8001',
    'preview.local.openedx.io',
    'preview.local.openedx.io:8000',
):
    assign_theme(domain)

# One certificate look for the whole platform (visuals come from robbo-theme templates).
robbo_html_view = {
    'default': {
        'accomplishment_class_append': 'accomplishment-certificate',
        'platform_name': 'РОББО',
        'company_about_url': 'https://robbo.ru',
        'company_privacy_url': 'https://robbo.ru/wp-content/uploads/policy.pdf',
        'company_tos_url': 'https://robbo.ru/wp-content/uploads/agree.pdf',
        'company_verified_certificate_url': 'https://robbo.ru',
        'logo_src': '/static/robbo-theme/images/certificates/robbo-cert-logo.svg',
        'logo_url': 'https://robbo.ru',
    },
    'honor': {
        'certificate_type': 'honor',
        'certificate_title': 'Сертификат о прохождении курса',
        'document_body_class_append': 'is-honorcode',
    },
    'verified': {
        'certificate_type': 'verified',
        'certificate_title': 'Сертификат о прохождении курса',
        'document_body_class_append': 'is-idverified',
    },
    'audit': {
        'certificate_type': 'audit',
        'certificate_title': 'Сертификат о прохождении курса',
        'document_body_class_append': 'is-audit',
    },
}
current = CertificateHtmlViewConfiguration.current()
payload = json.dumps(robbo_html_view, ensure_ascii=False)
if not current or not current.enabled or current.configuration != payload:
    CertificateHtmlViewConfiguration.objects.create(enabled=True, configuration=payload)
    print('CertificateHtmlViewConfiguration: seeded/updated')
else:
    print('CertificateHtmlViewConfiguration: already current')
"
