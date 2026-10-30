// Modifications Copyright (C) 2026 Robbo. See NOTICE at repository root.
// eslint-disable-next-line no-shadow-restricted-names
(function(undefined) {
    describe('VideoQualityControl', function() {
        var state, qualityControl, videoPlayer, player;

        afterEach(function() {
            window.localStorage.removeItem('robbo.video.hd');
            $('source').remove();
            if (state.storage) {
                state.storage.clear();
            }
            state.videoPlayer.destroy();
        });

        describe('constructor, YouTube mode', function() {
            beforeEach(function() {
                state = jasmine.initializePlayerYouTube();
                qualityControl = state.videoQualityControl;
                videoPlayer = state.videoPlayer;
                player = videoPlayer.player;

                // Define empty methods in YouTube stub
                player.quality = 'large';
                player.setPlaybackQuality.and.callFake(function(quality) {
                    player.quality = quality;
                });
            });

            it('contains the quality control and is initially hidden',
                function() {
                    expect(qualityControl.el).toHaveClass(
                        'quality-control is-hidden'
                    );
                });

            it('add ARIA attributes to quality control', function() {
                expect(qualityControl.el).toHaveAttrs({
                    'aria-disabled': 'false'
                });
            });

            it('bind the quality control', function() {
                expect(qualityControl.el).toHandleWith('click',
                    qualityControl.toggleQuality
                );

                expect(state.el).toHandle('play');
            });

            it('calls fetchAvailableQualities only once', function() {
                expect(player.getAvailableQualityLevels.calls.count())
                    .toEqual(0);

                videoPlayer.onPlay();
                videoPlayer.onPlay();

                expect(player.getAvailableQualityLevels.calls.count())
                    .toEqual(1);
            });

            it('starts in HD mode and does not call setPlaybackQuality', function() {
                videoPlayer.onPlay();

                expect(qualityControl.isHD).toBe(true);
                expect(qualityControl.scale()).toBe(2);
                expect(qualityControl.el).toHaveClass('active');
                expect(player.setPlaybackQuality).not.toHaveBeenCalled();
            });

            it('shows the quality control on play if HD is available',
                function() {
                    videoPlayer.onPlay();

                    expect(qualityControl.el).not.toHaveClass('is-hidden');
                });

            it('leaves quality control hidden on play if HD is not available',
                function() {
                    player.getAvailableQualityLevels.and.returnValue(
                        ['large', 'medium', 'small']
                    );

                    videoPlayer.onPlay();
                    expect(qualityControl.el).toHaveClass('is-hidden');
                });

            it('toggles HD mode, rescales the player and remembers the choice', function() {
                videoPlayer.onPlay();
                spyOn(state.resizer, 'setScale').and.callThrough();

                qualityControl.el.click();
                expect(qualityControl.isHD).toBe(false);
                expect(qualityControl.el).not.toHaveClass('active');
                expect(state.resizer.setScale).toHaveBeenCalledWith(1);
                expect(window.localStorage.getItem('robbo.video.hd')).toBe('off');

                qualityControl.el.click();
                expect(qualityControl.isHD).toBe(true);
                expect(qualityControl.el).toHaveClass('active');
                expect(state.resizer.setScale).toHaveBeenCalledWith(2);
                expect(window.localStorage.getItem('robbo.video.hd')).toBe('on');
            });

            it('keeps the button state when YouTube reports a quality', function() {
                videoPlayer.onPlay();

                qualityControl.onQualityChange('large');
                expect(qualityControl.quality).toBe('large');
                expect(qualityControl.el).toHaveClass('active');
            });

            it('can destroy itself', function() {
                state.videoQualityControl.destroy();
                expect(state.videoQualityControl).toBeUndefined();
                expect($('.quality-control')).not.toExist();
            });
        });

        describe('constructor, HTML5 mode', function() {
            it('does not contain the quality control', function() {
                state = jasmine.initializePlayer();

                expect(state.el.find('.quality-control').length).toBe(0);
            });
        });
    });
}).call(this);
