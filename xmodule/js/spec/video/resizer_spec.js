(function(require) {
    'use strict';

    // Modifications Copyright (C) 2026 Robbo. See NOTICE at repository root.

    require(
        ['video/00_resizer.js', 'underscore'],
        function(Resizer, _) {
            describe('Resizer', function() {
                var html = [
                        '<div '
                    + 'class="rszr-wrapper" '
                    + 'style="width:200px; height: 200px;"'
                + '>',
                        '<div '
                        + 'class="rszr-el" '
                        + 'style="width:100px; height: 150px;"'
                    + '>',
                        'Content',
                        '</div>',
                        '</div>'
                    ].join(''),
                    config, $container, $element;

                beforeEach(function() {
                    setFixtures(html);

                    $container = $('.rszr-wrapper');
                    $element = $('.rszr-el');
                    config = {
                        container: $container,
                        element: $element
                    };

                    spyOn(console, 'log');
                });

                it('When Initialize without required parameters, log message is shown',
                    function() {
                        // eslint-disable-next-line no-new
                        new Resizer({ });
                        expect(console.log).toHaveBeenCalled();
                    }
                );

                it('`alignByWidthOnly` works correctly', function() {
                    var resizer = new Resizer(config).alignByWidthOnly(),
                        expectedWidth = $container.width(),
                        realWidth = $element.width();

                    expect(realWidth).toBe(expectedWidth);
                });

                it('`alignByHeightOnly` works correctly', function() {
                    var resizer = new Resizer(config).alignByHeightOnly(),
                        expectedHeight = $container.height(),
                        realHeight = $element.height();

                    expect(realHeight).toBe(expectedHeight);
                });

                it('`align` works correctly', function() {
                    var resizer = new Resizer(config).align(),
                        expectedHeight = $container.height(),
                        realHeight = $element.height(),
                        expectedWidth = 50,
                        realWidth;

                    // containerRatio >= elementRatio
                    expect(realHeight).toBe(expectedHeight);

                    // containerRatio < elementRatio
                    $container.width(expectedWidth);
                    resizer.align();
                    realWidth = $element.width();

                    expect(realWidth).toBe(expectedWidth);
                });

                it('`setMode` works correctly', function() {
                    var resizer = new Resizer(config).setMode('height'),
                        expectedHeight = $container.height(),
                        realHeight = $element.height(),
                        expectedWidth = 50,
                        realWidth;

                    // containerRatio >= elementRatio
                    expect(realHeight).toBe(expectedHeight);

                    // containerRatio < elementRatio
                    $container.width(expectedWidth);
                    resizer.setMode('width');
                    realWidth = $element.width();

                    expect(realWidth).toBe(expectedWidth);
                });

                it('`setElement` works correctly', function() {
                    var $newElement,
                        expectedHeight;

                    $container.append('<div '
                + 'id="Another-el" '
                + 'style="width:100px; height: 150px;"'
            + '>');
                    $newElement = $('#Another-el');
                    expectedHeight = $container.height();

                    new Resizer(config).setElement($newElement).alignByHeightOnly();
                    expect($element.height()).not.toBe(expectedHeight);
                    expect($newElement.height()).toBe(expectedHeight);
                });

                it('`setScale` renders the element larger and shrinks it back', function() {
                    var resizer = new Resizer(config).setScale(2).alignByWidthOnly(),
                        rect;

                    // jQuery reports the layout size, getBoundingClientRect the visible one.
                    expect($element.width()).toBe(2 * $container.width());
                    rect = $element[0].getBoundingClientRect();
                    expect(rect.width).toBe($container.width());
                    expect($element[0].offsetHeight + parseFloat($element.css('margin-bottom')))
                        .toBe(rect.height);

                    resizer.setScale(1).alignByWidthOnly();
                    expect($element.width()).toBe($container.width());
                    expect($element[0].style.transform).toBe('');
                });

                it('`setScale` keeps the element within the maximum height', function() {
                    spyOnProperty(window, 'devicePixelRatio', 'get').and.returnValue(1);
                    // Visible 200x300: four times larger would be 1200 high, the limit is 600.
                    // eslint-disable-next-line no-new
                    new Resizer(config).setScale(4, 600).alignByWidthOnly();

                    expect($element.height()).toBe(600);
                    expect($element[0].getBoundingClientRect().height).toBe(300);
                });

                describe('Callbacks', function() {
                    var resizer,
                        spiesList = [];

                    beforeEach(function() {
                        var spiesCount = _.range(3);

                        spiesList = $.map(spiesCount, function() {
                            return jasmine.createSpy();
                        });

                        resizer = new Resizer(config);
                    });

                    it('callbacks are called', function() {
                        $.each(spiesList, function(index, spy) {
                            resizer.callbacks.add(spy);
                        });

                        resizer.align();

                        $.each(spiesList, function(index, spy) {
                            expect(spy).toHaveBeenCalled();
                        });
                    });

                    it('callback called just once', function() {
                        resizer.callbacks.once(spiesList[0]);

                        resizer
                            .align()
                            .alignByHeightOnly();

                        expect(spiesList[0].calls.count()).toEqual(1);
                    });

                    it('all callbacks are removed', function() {
                        $.each(spiesList, function(index, spy) {
                            resizer.callbacks.add(spy);
                        });

                        resizer.callbacks.removeAll();
                        resizer.align();

                        $.each(spiesList, function(index, spy) {
                            expect(spy).not.toHaveBeenCalled();
                        });
                    });

                    it('specific callback is removed', function() {
                        $.each(spiesList, function(index, spy) {
                            resizer.callbacks.add(spy);
                        });

                        resizer.callbacks.remove(spiesList[1]);
                        resizer.align();

                        expect(spiesList[1]).not.toHaveBeenCalled();
                    });

                    it(
                        'Error message is shown when wrong argument type is passed',
                        function() {
                            var methods = ['add', 'once'],
                                errorMessage = '[Video info]: TypeError: Argument is not a function.',
                                arg = {};

                            spyOn(console, 'error');

                            $.each(methods, function(index, methodName) {
                                resizer.callbacks[methodName](arg);
                                expect(console.error).toHaveBeenCalledWith(errorMessage);
                                // reset spy
                                console.log.calls.reset();
                            });
                        });
                });

                describe('Delta', function() {
                    var resizer;

                    beforeEach(function() {
                        resizer = new Resizer(config);
                    });

                    it('adding delta align correctly by height', function() {
                        var delta = 100,
                            expectedHeight = $container.height() + delta,
                            realHeight;

                        resizer
                            .delta.add(delta, 'height')
                            .setMode('height');

                        realHeight = $element.height();

                        expect(realHeight).toBe(expectedHeight);
                    });

                    it('adding delta align correctly by width', function() {
                        var delta = 100,
                            expectedWidth = $container.width() + delta,
                            realWidth;

                        resizer
                            .delta.add(delta, 'width')
                            .setMode('width');

                        realWidth = $element.width();

                        expect(realWidth).toBe(expectedWidth);
                    });

                    it('substract delta align correctly by height', function() {
                        var delta = 100,
                            expectedHeight = $container.height() - delta,
                            realHeight;

                        resizer
                            .delta.substract(delta, 'height')
                            .setMode('height');

                        realHeight = $element.height();

                        expect(realHeight).toBe(expectedHeight);
                    });

                    it('substract delta align correctly by width', function() {
                        var delta = 100,
                            expectedWidth = $container.width() - delta,
                            realWidth;

                        resizer
                            .delta.substract(delta, 'width')
                            .setMode('width');

                        realWidth = $element.width();

                        expect(realWidth).toBe(expectedWidth);
                    });

                    it('reset delta', function() {
                        var delta = 100,
                            expectedWidth = $container.width(),
                            realWidth;

                        resizer
                            .delta.substract(delta, 'width')
                            .delta.reset()
                            .setMode('width');

                        realWidth = $element.width();

                        expect(realWidth).toBe(expectedWidth);
                    });
                });
            });
        });
}(require));
