/**
 * Copyright (C) 2026 Robbo <https://robbo.ru>
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Part of the Robbo Open edX distribution (human-readable errors). See NOTICE at repository root.
 *
 * The code line of a failed AJAX call on LMS pages: «Код: CODE · XXXX-XXXX» (docs/human-errors.md §2 in the
 * meta repo). An answer in the error contract (lms/djangoapps/robbo_errors) brings its own code and number;
 * for any other answer the code comes from the status and the number from Caddy's X-Request-ID. The same
 * rules as Studio's robboDescribeError (cms/static/cms/js/main.js).
 */
(function(define) {
    'use strict';

    define([], function() {
        // Codes by HTTP status, as lms/djangoapps/robbo_errors/catalog.py STATUS_CODES (status 0: no answer at all).
        var STATUS_CODES = {
                0: 'NET-OFFLINE',
                400: 'BAD-INPUT',
                401: 'SESSION-EXPIRED',
                403: 'ACCESS-DENIED',
                404: 'NOT-FOUND',
                413: 'UPLOAD-SIZE',
                429: 'TOO-MANY',
                502: 'SRV-RESTART',
                503: 'SRV-RESTART',
                504: 'SRV-RESTART'
            },
            codeFor = function(status) {
                if (status >= 200 && status < 300) {
                    // A JSON call answered with a page: an expired session redirected to the login form.
                    return 'SESSION-EXPIRED';
                }
                return STATUS_CODES[status] || (status >= 500 ? 'SRV-ERROR' : 'BAD-INPUT');
            },
            codeLine = function(xhr) {
                var data = xhr && xhr.responseJSON && xhr.responseJSON.error_code ? xhr.responseJSON : null,
                    label = (document.documentElement.lang || '').indexOf('en') === 0 ? 'Code' : 'Код',
                    code = data ? data.error_code : codeFor(xhr ? xhr.status : 0),
                    incident = data ? data.incident_id : (xhr && xhr.getResponseHeader
                        && xhr.getResponseHeader('X-Request-ID'));
                incident = String(incident || '').replace(/-/g, '').slice(0, 8).toUpperCase();
                return label + ': ' + code
                    + (incident.length === 8 ? ' · ' + incident.slice(0, 4) + '-' + incident.slice(4) : '');
            };

        return {
            codeLine: codeLine,
            // «Не удалось … (Код: SRV-ERROR · 7F3A-29C1)» for plain-text status lines.
            withCode: function(message, xhr) {
                return message + ' (' + codeLine(xhr) + ')';
            }
        };
    });
}).call(this, define || RequireJS.define);
