/**
 * Copyright (C) 2026 Robbo <https://robbo.ru>
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Part of the Robbo Open edX distribution (course groups). See NOTICE at repository root.
 *
 * Instructor dashboard «Группы», cohort editor tab «Ссылка-приглашение»: the group's invite link
 * from lms/djangoapps/robbo_groups/views.py:cohort_invite. Loaded when the tab is opened.
 * Failed requests say what failed with the code and number (js/robbo-errors).
 */
(function(define) {
    'use strict';

    define(['backbone', 'jquery', 'gettext', 'edx-ui-toolkit/js/utils/html-utils', 'js/robbo-errors'],
        function(Backbone, $, gettext, HtmlUtils, RobboErrors) {
            var RobboCohortInviteView = Backbone.View.extend({

                events: {
                    'click .robbo-cohort-invite-issue': 'issue',
                    'click .robbo-cohort-invite-replace': 'replace',
                    'click .robbo-cohort-invite-enable': 'enable',
                    'click .robbo-cohort-invite-disable': 'disable',
                    'click .robbo-cohort-invite-copy': 'copy'
                },

                initialize: function(options) {
                    this.url = options.url;
                    this.template = HtmlUtils.template($('#robbo-cohort-invite-tpl').text());
                    this.invite = null;
                },

                load: function() {
                    var self = this;
                    if (this.invite) {
                        return;
                    }
                    $.getJSON(this.url)
                        .done(function(invite) {
                            self.show(invite, '');
                        })
                        .fail(function(xhr) {
                            self.showStatus(RobboErrors.withCode(gettext('Could not load the invite link.'), xhr));
                        });
                },

                show: function(invite, status) {
                    this.invite = invite;
                    HtmlUtils.setHtml(this.$('.robbo-cohort-invite-body'), this.template({invite: invite}));
                    this.showStatus(status);
                },

                showStatus: function(status) {
                    this.$('.robbo-cohort-invite-status').text(status);
                },

                change: function(action, status) {
                    var self = this;
                    $.post(this.url, {action: action})
                        .done(function(invite) {
                            self.show(invite, status);
                        })
                        .fail(function(xhr) {
                            self.showStatus(RobboErrors.withCode(gettext('Could not change the invite link.'), xhr));
                        });
                },

                issue: function(event) {
                    event.preventDefault();
                    this.change('issue', gettext('The link is ready. Send it to the learners.'));
                },

                replace: function(event) {
                    event.preventDefault();
                    // eslint-disable-next-line no-alert
                    if (window.confirm(gettext('The current link will stop working. Replace it?'))) {
                        this.change('issue', gettext('A new link is ready, the old one no longer works.'));
                    }
                },

                enable: function(event) {
                    event.preventDefault();
                    this.change('enable', gettext('The link is switched on.'));
                },

                disable: function(event) {
                    event.preventDefault();
                    this.change('disable', gettext('The link is switched off.'));
                },

                copy: function(event) {
                    var self = this,
                        $input = this.$('.robbo-cohort-invite-url'),
                        copied = function() {
                            self.showStatus(gettext('The link is copied.'));
                        },
                        selectForManualCopy = function() {
                            $input.trigger('focus').trigger('select');
                            self.showStatus(gettext('Press Ctrl+C to copy the link.'));
                        };
                    event.preventDefault();
                    // The Clipboard API needs HTTPS; the local stack is plain HTTP.
                    if (navigator.clipboard && window.isSecureContext) {
                        navigator.clipboard.writeText($input.val()).then(copied, selectForManualCopy);
                        return;
                    }
                    $input.trigger('focus').trigger('select');
                    try {
                        if (document.execCommand('copy')) {
                            copied();
                            return;
                        }
                    } catch (err) {
                        // fall through to manual copy
                    }
                    selectForManualCopy();
                }
            });
            return RobboCohortInviteView;
        });
}).call(this, define || RequireJS.define);
