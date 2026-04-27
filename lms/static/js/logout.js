/**
 * Logout page: wait for IDA logout iframes (if any), then redirect to `data-redirect-url`.
 * Vanilla JS — jQuery 3 removed jQuery.fn.load(), which broke the previous allLoaded helper
 * when iframes were present.
 */
(function () {
    'use strict';

    function onReady(fn) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fn);
        } else {
            fn();
        }
    }

    onReady(function () {
        var container = document.getElementById('iframeContainer');
        if (!container) {
            return;
        }
        var redirectUrl = container.getAttribute('data-redirect-url') || '/';
        var iframes = container.querySelectorAll('iframe');
        /** Upper bound (ms) while waiting on IDA logout iframes; matches the copy in logout.html */
        var maxWaitMs = 5000;
        var didRedirect = false;

        function go() {
            if (didRedirect) {
                return;
            }
            didRedirect = true;
            window.location.assign(redirectUrl);
        }

        if (iframes.length === 0) {
            go();
            return;
        }

        var waiting = iframes.length;
        function onIframeDone() {
            waiting -= 1;
            if (waiting <= 0) {
                go();
            }
        }

        for (var i = 0; i < iframes.length; i += 1) {
            iframes[i].addEventListener('load', onIframeDone);
        }

        setTimeout(go, maxWaitMs);
    });
}());
