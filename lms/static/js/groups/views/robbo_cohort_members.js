/**
 * Copyright (C) 2026 Robbo <https://robbo.ru>
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Part of the Robbo Open edX distribution (course groups). See NOTICE at repository root.
 *
 * Instructor dashboard «Группы», cohort editor tab «Управление слушателями»: who is in the group, with search,
 * «Показать ещё», «Убрать из группы» and «Удалить с курса» (lms/djangoapps/robbo_groups/views.py:cohort_members).
 * A learner removed from a group goes to an automatic group, so an automatic group has no «Убрать из группы».
 * After a removal the editor refreshes the cohort counts and renders again; `state` carries the search
 * and the message over to the new view.
 */
(function(define) {
    'use strict';

    define(['backbone', 'jquery', 'underscore', 'gettext', 'edx-ui-toolkit/js/utils/html-utils',
        'edx-ui-toolkit/js/utils/string-utils'],
    function(Backbone, $, _, gettext, HtmlUtils, StringUtils) {
        var RobboCohortMembersView = Backbone.View.extend({

            events: {
                'input .robbo-cohort-members-search': 'onSearchInput',
                'keydown .robbo-cohort-members-search': 'onSearchKeydown',
                'click .robbo-cohort-members-more': 'showMore',
                'click .robbo-cohort-member-remove': 'removeMember',
                'click .robbo-cohort-member-unenroll': 'unenrollMember'
            },

            initialize: function(options) {
                var state = options.state || {};
                this.url = options.url;
                this.cohortName = options.cohortName;
                this.isAutomatic = options.isAutomatic;
                this.onRemoved = options.onRemoved;
                this.template = HtmlUtils.template($('#robbo-cohort-members-tpl').text());
                this.query = state.query || '';
                this.pendingStatus = state.status || '';
                this.members = [];
                this.count = 0;
                this.page = 0;
                this.hasMore = false;
                this.request = null;
                this.searchLater = _.debounce(_.bind(function() {
                    this.fetch(1);
                }, this), 300);
            },

            load: function() {
                this.$('.robbo-cohort-members-search').val(this.query);
                this.fetch(1);
            },

            fetch: function(page) {
                var self = this;
                if (this.request) {
                    this.request.abort();
                }
                this.request = $.getJSON(this.url, {q: this.query, page: page})
                    .done(function(data) {
                        self.members = page === 1 ? data.members : self.members.concat(data.members);
                        self.count = data.count;
                        self.page = page;
                        self.hasMore = data.has_more;
                        self.render();
                    })
                    .fail(function(xhr, textStatus) {
                        if (textStatus !== 'abort') {
                            self.showStatus(gettext('Could not load the group members.'));
                        }
                    });
            },

            render: function() {
                var isEmptyGroup = this.members.length === 0 && !this.query;
                HtmlUtils.setHtml(this.$('.robbo-cohort-members-body'), this.template({
                    members: this.members,
                    count: this.count,
                    query: this.query,
                    hasMore: this.hasMore,
                    isAutomatic: this.isAutomatic
                }));
                // nothing to search in an empty group
                this.$('.robbo-cohort-members-search').toggleClass('is-hidden', isEmptyGroup);
                this.showStatus(this.pendingStatus);
                this.pendingStatus = '';
                return this;
            },

            showStatus: function(status) {
                this.$('.robbo-cohort-members-status').text(status);
            },

            onSearchInput: function(event) {
                this.query = $(event.currentTarget).val().trim();
                this.searchLater();
            },

            onSearchKeydown: function(event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    this.searchLater.cancel();
                    this.fetch(1);
                }
            },

            showMore: function(event) {
                event.preventDefault();
                $(event.currentTarget).prop('disabled', true);
                this.fetch(this.page + 1);
            },

            // The member of a row button: attr, not data(), since jQuery turns a username like "2024" into a number.
            memberOf: function($button) {
                var username = $button.attr('data-username'),
                    member = _.findWhere(this.members, {username: username}) || {username: username};
                return _.extend({displayName: member.name || username}, member);
            },

            // A second POST for someone moved or removed by another member of the course team meanwhile
            // just refreshes the list.
            post: function($button, data, doneStatus) {
                var self = this,
                    name = this.memberOf($button).displayName;
                $button.prop('disabled', true);
                return $.post(this.url, data)
                    .done(function(response) {
                        self.onRemoved({query: self.query, status: doneStatus(response)});
                    })
                    .fail(function(xhr) {
                        if (xhr.status === 409) {
                            self.onRemoved({
                                query: self.query,
                                status: StringUtils.interpolate(
                                    gettext('{name} is not in this group any more.'), {name: name}
                                )
                            });
                            return;
                        }
                        $button.prop('disabled', false);
                        self.showStatus(gettext('Could not change the group. Try again.'));
                    });
            },

            unenrollMember: function(event) {
                var $button = $(event.currentTarget),
                    member = this.memberOf($button),
                    message = StringUtils.interpolate(
                        gettext('Remove {name} from the course? They lose access to the course and leave the group '
                            + '«{group}». Their progress is kept: enrolled again, they go on where they stopped.'),
                        {name: member.displayName, group: this.cohortName}
                    );
                event.preventDefault();
                if (member.is_paid) {
                    message += ' ' + gettext('The course is paid: the payment is not refunded.');
                }
                // eslint-disable-next-line no-alert
                if (!window.confirm(message)) {
                    return;
                }
                this.post($button, {action: 'unenroll', username: member.username}, function() {
                    return StringUtils.interpolate(
                        gettext('Learner {name} is removed from the course.'), {name: member.displayName}
                    );
                });
            },

            removeMember: function(event) {
                var self = this,
                    $button = $(event.currentTarget),
                    member = this.memberOf($button),
                    name = member.displayName;
                event.preventDefault();
                // eslint-disable-next-line no-alert
                if (!window.confirm(StringUtils.interpolate(
                    gettext('Remove {name} from the group «{group}»? They stay in the course and move to '
                        + 'an automatic group (such as «Default Group»). The access restrictions of «{group}» '
                        + 'no longer apply to them.'),
                    {name: name, group: this.cohortName}
                ))) {
                    return;
                }
                this.post($button, {action: 'remove', username: member.username}, function(data) {
                    // no new group for someone who left the course: placed when they come back
                    return data.new_group
                        ? StringUtils.interpolate(
                            gettext('{name} is no longer in the group «{group}» and is now in «{newGroup}».'),
                            {name: name, group: self.cohortName, newGroup: data.new_group}
                        )
                        : StringUtils.interpolate(gettext('{name} is no longer in the group.'), {name: name});
                });
            }
        });
        return RobboCohortMembersView;
    });
}).call(this, define || RequireJS.define);
