# tutor-plugin-robbo-payments

Tutor plugin for Robbo YooKassa commerce (native LMS checkout).

Install on the host where `tutor` runs:

```bash
./scripts/install-robbo-payments-plugin.sh
tutor plugins enable robbo-payments
tutor config save
```

Set secrets in Tutor `config.yml`:

```yaml
YOOKASSA_SHOP_ID: "your-shop-id"
YOOKASSA_SECRET_KEY: "your-secret-key"
```

After deploy, enable commerce checkout in LMS:

```bash
tutor local run lms ./manage.py lms configure_robbo_commerce
```

Register webhook URL in YooKassa cabinet:

`https://<LMS_HOST>/payments/yookassa/webhook/`

See `docs/commerce-yookassa.md` in the meta-repo.
