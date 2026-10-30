(function(requirejs, require, define) {
// VideoQualityControl module.
// Modifications Copyright (C) 2026 Robbo. See NOTICE at repository root.
//
// Robbo: YouTube ignores setPlaybackQuality and picks the quality by the size of its iframe, so with
// the small player of a unit the learner got 480p. In HD mode the iframe is rendered HD_SCALE times
// larger and shrunk back with a CSS transform (00_resizer.js), up to HD_MAX_HEIGHT device pixels.
// HD is on by default; the learner's choice is kept in localStorage.

    'use strict';

    define(
        'video/05_video_quality_control.js',
        ['edx-ui-toolkit/js/utils/html-utils'],
        function(HtmlUtils) {
            var HD_SCALE = 2,
                HD_MAX_HEIGHT = 1080,
                HD_STORAGE_KEY = 'robbo.video.hd';

            var template = HtmlUtils.interpolateHtml(
                HtmlUtils.HTML([
                    '<button class="control quality-control is-hidden" aria-disabled="false" title="',
                    '{highDefinition}',
                    '">',
                    '<span class="icon icon-hd" aria-hidden="true">HD</span>',
                    '<span class="sr text-translation">',
                    '{highDefinition}',
                    '</span>&nbsp;',
                    '<span class="sr control-text">',
                    '{off}',
                    '</span>',
                    '</button>'
                ].join('')),
                {
                    highDefinition: gettext('High Definition'),
                    off: gettext('off')
                }
            );

            // VideoQualityControl() function - what this module "exports".
            return function(state) {
                var dfd = $.Deferred();

                // Changing quality for now only works for YouTube videos.
                if (state.videoType !== 'youtube') {
                    return;
                }

                state.videoQualityControl = {};

                _makeFunctionsPublic(state);
                _renderElements(state);
                _bindHandlers(state);

                dfd.resolve();
                return dfd.promise();
            };

            // ***************************************************************
            // Private functions start here.
            // ***************************************************************

            // function _makeFunctionsPublic(state)
            //
            //     Functions which will be accessible via 'state' object. When called, these functions will
            //     get the 'state' object as a context.
            function _makeFunctionsPublic(state) {
                var methodsDict = {
                    destroy: destroy,
                    fetchAvailableQualities: fetchAvailableQualities,
                    onQualityChange: onQualityChange,
                    scale: scale,
                    showQualityControl: showQualityControl,
                    toggleQuality: toggleQuality
                };

                state.bindTo(methodsDict, state.videoQualityControl, state);
            }

            function destroy() {
                this.videoQualityControl.el.off({
                    click: this.videoQualityControl.toggleQuality,
                    destroy: this.videoQualityControl.destroy
                });
                this.el.off('.quality');
                this.videoQualityControl.el.remove();
                delete this.videoQualityControl;
            }

            // function _renderElements(state)
            //
            //     Create any necessary DOM elements, attach them, and set their initial configuration. Also
            //     make the created DOM elements available via the 'state' object. Much easier to work this
            //     way - you don't have to do repeated jQuery element selects.
            function _renderElements(state) {
                // eslint-disable-next-line no-multi-assign
                var element = state.videoQualityControl.el = $(template.toString());
                state.videoQualityControl.quality = null;
                state.videoQualityControl.isHD = _loadHD();
                state.videoQualityControl.maxScaledHeight = HD_MAX_HEIGHT;
                HtmlUtils.append(state.el.find('.secondary-controls'), HtmlUtils.HTML(element));
                _renderHD(state);
            }

            function _loadHD() {
                try {
                    return window.localStorage.getItem(HD_STORAGE_KEY) !== 'off';
                } catch (e) {
                    return true;
                }
            }

            function _saveHD(isHD) {
                try {
                    window.localStorage.setItem(HD_STORAGE_KEY, isHD ? 'on' : 'off');
                } catch (e) {
                    // Private mode or blocked storage: the choice lives until the page reloads.
                }
            }

            function _renderHD(state) {
                var isHD = state.videoQualityControl.isHD;
                state.videoQualityControl.el
                    .toggleClass('active', isHD)
                    .find('.control-text')
                    .text(isHD ? gettext('on') : gettext('off'));
            }

            // function _bindHandlers(state)
            //
            //     Bind any necessary function callbacks to DOM events (click, mousemove, etc.).
            function _bindHandlers(state) {
                state.videoQualityControl.el.on('click',
                    state.videoQualityControl.toggleQuality
                );
                state.el.on('play.quality', _.once(
                    state.videoQualityControl.fetchAvailableQualities
                ));

                state.el.on('destroy.quality', state.videoQualityControl.destroy);
            }

            // ***************************************************************
            // Public functions start here.
            // These are available via the 'state' object. Their context ('this' keyword) is the 'state' object.
            // The magic private function that makes them available and sets up their context is makeFunctionsPublic().
            // ***************************************************************

            /*
     * @desc Shows quality control. This function will only be called if HD
     *       qualities are available.
     *
     * @public
     */
            function showQualityControl() {
                this.videoQualityControl.el.removeClass('is-hidden');
            }

            // This function can only be called once as _.once has been used.
            /*
     * @desc Get the available qualities from YouTube API. Possible values are:
             ['highres', 'hd1080', 'hd720', 'large', 'medium', 'small'].
             HD are: ['highres', 'hd1080', 'hd720'].
     *
     * @public
     */
            function fetchAvailableQualities() {
                var qualities = this.videoPlayer.player.getAvailableQualityLevels();

                this.config.availableHDQualities = _.intersection(
                    qualities, ['highres', 'hd1080', 'hd720']
                );

                // HD qualities are available, show video quality control.
                if (this.config.availableHDQualities.length > 0) {
                    this.trigger('videoQualityControl.showQualityControl');
                }
            }

            /*
     * @desc How many times larger the YouTube iframe is rendered (see 00_resizer.js).
     *
     * @public
     */
            function scale() {
                return this.videoQualityControl.isHD ? HD_SCALE : 1;
            }

            // The quality YouTube actually plays; the button shows the HD mode, not this value.
            function onQualityChange(value) {
                this.videoQualityControl.quality = value;
            }

            function toggleQuality(event) {
                event.preventDefault();

                this.videoQualityControl.isHD = !this.videoQualityControl.isHD;
                _saveHD(this.videoQualityControl.isHD);
                _renderHD(this);

                if (this.resizer) {
                    this.resizer.setScale(this.videoQualityControl.scale()).align();
                }
            }
        });
}(RequireJS.requirejs, RequireJS.require, RequireJS.define));
