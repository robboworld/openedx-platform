/**
 * Copyright (C) 2026 Robbo <https://robbo.ru>
 * SPDX-License-Identifier: AGPL-3.0-only
 * Part of the Robbo Open edX distribution. See NOTICE at repository root.
 *
 * RobboFooter for Authoring (Studio) via studio_footer PLUGIN_SLOT.
 * Markup/classes match LMS theme + bind-mounted MFE robbo-layout.
 * RobboStudioHelpContent replaces default Studio help buttons only.
 */
import React from 'react';
import { getConfig } from '@edx/frontend-platform';
import { FormattedMessage } from '@edx/frontend-platform/i18n';
import { ActionRow, Button } from '@openedx/paragon';

import './footer.css';
import './studio-header.css';

const MailIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="M4 6h16v12H4V6zm0 0l8 7 8-7" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const GlobeIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" fill="none" />
    <path d="M3 12h18M12 3c2.5 2.5 4 5.5 4 9s-1.5 6.5-4 9c-2.5-2.5-4-5.5-4-9s1.5-6.5 4-9z" stroke="currentColor" strokeWidth="1.8" fill="none" />
  </svg>
);

const SupportIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <circle cx="12" cy="8" r="3" stroke="currentColor" strokeWidth="1.8" fill="none" />
    <path d="M6 19c1.5-3 4-4.5 6-4.5S16.5 16 18 19" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" />
    <path d="M12 14v-1a3 3 0 013-3" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" />
  </svg>
);

// Cyrillic via escapes so this file stays ASCII under Tutor Jinja templates/.
const WORDMARK = '\u0420\u041E\u0411\u0411\u041E';
const TAGLINE = '\u041E\u0431\u0440\u0430\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u044C\u043D\u0430\u044F \u043F\u043B\u0430\u0442\u0444\u043E\u0440\u043C\u0430 \u0420\u041E\u0411\u0411\u041E';
const COPYRIGHT_PREFIX = '\u00A9 \u041E\u041E\u041E \u00AB\u0420\u041E\u0411\u0411\u041E \u0422\u0415\u0425\u041D\u041E\u041B\u041E\u0413\u0418\u0418\u00BB, ';
const DOCS_HEADING = '\u0414\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u044B';
const CONTACTS_HEADING = '\u041A\u043E\u043D\u0442\u0430\u043A\u0442\u044B';
const POLICY_LABEL = '\u041F\u043E\u043B\u0438\u0442\u0438\u043A\u0430 \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u043A\u0438 \u043F\u0435\u0440\u0441\u043E\u043D\u0430\u043B\u044C\u043D\u044B\u0445 \u0434\u0430\u043D\u043D\u044B\u0445';
const CONSENT_LABEL = '\u0421\u043E\u0433\u043B\u0430\u0441\u0438\u0435 \u043D\u0430 \u043E\u0431\u0440\u0430\u0431\u043E\u0442\u043A\u0443 \u043F\u0435\u0440\u0441\u043E\u043D\u0430\u043B\u044C\u043D\u044B\u0445 \u0434\u0430\u043D\u043D\u044B\u0445';
const FASIE_ALT = '\u0424\u043E\u043D\u0434 \u0441\u043E\u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044F \u0438\u043D\u043D\u043E\u0432\u0430\u0446\u0438\u044F\u043C';

const SUPPORT_URL = 'https://support.robbo.world/';

/** Replaces default Studio help buttons (docs + demo course) with Robbo support. */
export function RobboStudioHelpContent() {
  return (
    <ActionRow key="help-link-button-row" className="py-4" data-testid="helpButtonRow">
      <ActionRow.Spacer />
      <Button
        as="a"
        href={SUPPORT_URL}
        size="sm"
        target="_blank"
        rel="noopener noreferrer"
      >
        <FormattedMessage
          id="authoring.footer.help.educatorsDocs.button.label"
          defaultMessage="ROBBO Support"
          description="Label for Robbo support button in Studio help section"
        />
      </Button>
      <ActionRow.Spacer />
    </ActionRow>
  );
}

export function RobboFooter() {
  const lmsBase = (getConfig().LMS_BASE_URL || '').replace(/\/$/, '');
  const fasieLogo = `${lmsBase}/static/robbo-theme/images/partners/fasie.png`;
  const year = new Date().getFullYear();

  return (
    <div className="wrapper wrapper-footer robbo-studio-footer-wrap">
      <footer id="footer" className="robbo-site-footer" role="contentinfo">
        <div className="robbo-site-footer__inner">
          <div className="robbo-footer__main">
            <div className="robbo-footer__brand-col">
              <div className="robbo-footer__brand">
                <span className="robbo-footer__logo" aria-label={WORDMARK}>
                  {WORDMARK}
                  <sup className="robbo-footer__reg" aria-hidden="true">{'\u00AE'}</sup>
                </span>
              </div>
              <p className="robbo-footer__tagline">{TAGLINE}</p>
              <p className="robbo-footer__copyright">
                {COPYRIGHT_PREFIX}
                {year}
              </p>
            </div>
            <div className="robbo-footer__partner-col">
              <div className="robbo-footer__partner">
                <a
                  className="robbo-footer__partner-link"
                  href="https://fasie.ru"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <img className="robbo-footer__partner-logo" src={fasieLogo} alt={FASIE_ALT} />
                </a>
              </div>
            </div>
            <nav className="robbo-footer__col" aria-label={DOCS_HEADING}>
              <h2 className="robbo-footer__heading">{DOCS_HEADING}</h2>
              <ul className="robbo-footer__links">
                <li>
                  <a href="https://robbo.ru/wp-content/uploads/policy.pdf" target="_blank" rel="noopener noreferrer">
                    {POLICY_LABEL}
                  </a>
                </li>
                <li>
                  <a href="https://robbo.ru/wp-content/uploads/agree.pdf" target="_blank" rel="noopener noreferrer">
                    {CONSENT_LABEL}
                  </a>
                </li>
              </ul>
            </nav>
            <div className="robbo-footer__col robbo-footer__contacts-col">
              <h2 className="robbo-footer__heading">{CONTACTS_HEADING}</h2>
              <ul className="robbo-footer__contacts-list">
                <li className="robbo-footer__contacts-item">
                  <span className="robbo-footer__contacts-icon" aria-hidden="true"><MailIcon /></span>
                  <a className="robbo-footer__contacts-link" href="mailto:info@robbo.ru">info@robbo.ru</a>
                </li>
                <li className="robbo-footer__contacts-item">
                  <span className="robbo-footer__contacts-icon" aria-hidden="true"><GlobeIcon /></span>
                  <a className="robbo-footer__contacts-link" href="https://robbo.ru" target="_blank" rel="noopener noreferrer">robbo.ru</a>
                </li>
                <li className="robbo-footer__contacts-item">
                  <span className="robbo-footer__contacts-icon" aria-hidden="true"><SupportIcon /></span>
                  <a className="robbo-footer__contacts-link" href="https://support.robbo.world/" target="_blank" rel="noopener noreferrer">support.robbo.world</a>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default RobboFooter;
