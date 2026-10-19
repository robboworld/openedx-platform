/* globals AjaxPrefix */

define([
    'domReady',
    'jquery',
    'underscore',
    'underscore.string',
    'backbone',
    'gettext',
    '../../common/js/components/views/feedback_notification',
    'jquery.cookie'
], function(domReady, $, _, str, Backbone, gettext, NotificationView) {
    'use strict';

    var main, sendJSON, robboDescribeError,
        // Robbo: codes by HTTP status for answers without error_code, as in
        // lms/djangoapps/robbo_errors/catalog.py STATUS_CODES (status 0: no answer at all).
        ROBBO_STATUS_CODES = {
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
        };

    // Modifications Copyright (C) 2026 Robbo. See NOTICE at repository root.
    // Robbo: what a failed AJAX call tells the user (docs/human-errors.md §7 in the meta repo). An answer
    // in the platform's error shape brings its own title, text, code and number; for any other the code
    // comes from the status and the number from Caddy's X-Request-ID. The label is the catalog's ui.code.
    robboDescribeError = function(jqXHR, data) {
        var code, incident, isRobbo = Boolean(data && data.error_code),
            label = (document.documentElement.lang || '').indexOf('en') === 0 ? 'Code' : 'Код';
        if (isRobbo) {
            code = data.error_code;
            incident = data.incident_id;
        } else {
            code = ROBBO_STATUS_CODES[jqXHR.status] || (jqXHR.status >= 500 ? 'SRV-ERROR' : 'BAD-INPUT');
            incident = jqXHR.getResponseHeader('X-Request-ID');
        }
        incident = String(incident || '').replace(/-/g, '').slice(0, 8).toUpperCase();
        return {
            title: isRobbo ? data.user_title : null,
            message: data ? (data.user_message || (typeof data.error === 'string' ? data.error : null)) : null,
            codeLine: label + ': ' + code + (incident.length === 8 ? ' · ' + incident.slice(0, 4) + '-' + incident.slice(4) : '')
        };
    };

    main = function() {
        AjaxPrefix.addAjaxPrefix(jQuery, function() {
            return $("meta[name='path_prefix']").attr('content');
        });
        window.CMS = window.CMS || {};
        window.CMS.URL = window.CMS.URL || {};
        window.onTouchBasedDevice = function() {
            return navigator.userAgent.match(/iPhone|iPod|iPad|Android/i);
        };
        _.extend(window.CMS, Backbone.Events);
        Backbone.emulateHTTP = true;
        $.ajaxSetup({
            headers: {
                'X-CSRFToken': $.cookie('csrftoken')
            },
            dataType: 'json',
            content: {
                script: false
            }
        });
        $(document).ajaxError(function(event, jqXHR, ajaxSettings) {
            var msg, contentType, data, error,
                title = gettext("Studio's having trouble saving your work"),
                message = gettext('This may be happening because of an error with our server or your internet connection. Try refreshing the page or making sure you are online.'); // eslint-disable-line max-len
            if (ajaxSettings.notifyOnError === false) {
                return;
            }
            contentType = jqXHR.getResponseHeader('content-type');
            if (contentType && contentType.indexOf('json') > -1 && jqXHR.responseText) {
                try {
                    data = JSON.parse(jqXHR.responseText);
                } catch (e) {
                    data = null;
                }
            }
            // Robbo: the title, text and code with the incident number of the error answer
            // (lms/djangoapps/robbo_errors; docs/human-errors.md §4 and §7 in the meta repo).
            error = robboDescribeError(jqXHR, data);
            if (error.title) {
                title = error.title;
            }
            if (error.message) {
                message = error.message;
            }
            message = message + ' (' + error.codeLine + ')';
            msg = new NotificationView.Error({
                title: title,
                message: message
            });
            if (window.self !== window.top) {
                try {
                    // The authoring MFE shows customAttributes.httpErrorResponseData's "error"
                    // (src/generic/saving-error-alert/utils.ts).
                    window.parent.postMessage({
                        type: 'studioAjaxError',
                        message: 'Sends a message when an AJAX error occurs',
                        payload: {
                            error: {
                                customAttributes: {
                                    httpErrorStatus: jqXHR.status,
                                    httpErrorResponseData: JSON.stringify({error: message})
                                }
                            }
                        }
                    }, document.referrer);
                } catch (e) {
                    console.error(e);
                }
            }
            console.log('Studio AJAX Error', { // eslint-disable-line no-console
                url: event.currentTarget.URL,
                response: jqXHR.responseText,
                status: jqXHR.status
            });
            return msg.show();
        });
        sendJSON = function(url, data, callback, type) { // eslint-disable-line no-param-reassign
            if ($.isFunction(data)) {
                callback = data;
                data = undefined;
            }
            return $.ajax({
                url: url,
                type: type,
                contentType: 'application/json; charset=utf-8',
                dataType: 'json',
                data: JSON.stringify(data),
                success: callback,
                global: data ? data.global : true // Trigger global AJAX error handler or not
            });
        };
        $.postJSON = function(url, data, callback) { // eslint-disable-line no-param-reassign
            return sendJSON(url, data, callback, 'POST');
        };
        $.patchJSON = function(url, data, callback) { // eslint-disable-line no-param-reassign
            return sendJSON(url, data, callback, 'PATCH');
        };
        return domReady(function() {
            if (window.onTouchBasedDevice()) {
                return $('body').addClass('touch-based-device');
            }
            return null;
        });
    };
    main();
    return main;
});
