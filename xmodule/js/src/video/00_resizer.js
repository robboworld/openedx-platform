(function(requirejs, require, define) {
    // Modifications Copyright (C) 2026 Robbo. See NOTICE at repository root.
    define(
        'video/00_resizer.js',
        [],
        function() {
            var Resizer = function(params) {
                var defaults = {
                        container: window,
                        element: null,
                        containerRatio: null,
                        elementRatio: null
                    },
                    callbacksList = [],
                    delta = {
                        height: 0,
                        width: 0
                    },
                    module = {},
                    mode = null,
                    // Robbo: the element is rendered ``scale`` times larger and shrunk back with a CSS
                    // transform, so it keeps its place on the page. YouTube picks the quality by the size
                    // of its iframe and ignores setPlaybackQuality, so this is how the HD button works.
                    scale = 1,
                    maxScaledHeight = Infinity,
                    config;

                // eslint-disable-next-line no-shadow
                var initialize = function(params) {
                    if (!config) {
                        config = defaults;
                    }

                    config = $.extend(true, {}, config, params);

                    if (!config.element) {
                        console.log(
                            'Required parameter `element` is not passed.'
                        );
                    }

                    return module;
                };

                var getData = function() {
                    var $container = $(config.container),
                        containerWidth = $container.width() + delta.width,
                        containerHeight = $container.height() + delta.height,
                        containerRatio = config.containerRatio,

                        $element = $(config.element),
                        elementRatio = config.elementRatio;

                    if (!containerRatio) {
                        containerRatio = containerWidth / containerHeight;
                    }

                    if (!elementRatio) {
                        elementRatio = $element.width() / $element.height();
                    }

                    return {
                        containerWidth: containerWidth,
                        containerHeight: containerHeight,
                        containerRatio: containerRatio,
                        element: $element,
                        elementRatio: elementRatio
                    };
                };

                var align = function() {
                    var data = getData();

                    switch (mode) {
                    case 'height':
                        alignByHeightOnly();
                        break;

                    case 'width':
                        alignByWidthOnly();
                        break;

                    default:
                        if (data.containerRatio >= data.elementRatio) {
                            alignByHeightOnly();
                        } else {
                            alignByWidthOnly();
                        }
                        break;
                    }

                    fireCallbacks();

                    return module;
                };

                // Robbo: negative right/bottom margins give back the extra layout space, the transform
                // origin at the top left corner keeps ``top``/``left`` as computed for the visible box.
                var setSize = function($element, size) {
                    // No larger than ``maxScaledHeight`` device pixels: YouTube already counts them.
                    var factor = Math.min(scale, Math.max(1,
                        maxScaledHeight / (size.height * (window.devicePixelRatio || 1))
                    ));

                    if (factor === 1) {
                        $element.css($.extend(size, {
                            transform: '', transformOrigin: '', marginRight: '', marginBottom: ''
                        }));
                        return;
                    }

                    $element.css({
                        height: size.height * factor,
                        width: size.width * factor,
                        top: size.top,
                        left: size.left,
                        transform: 'scale(' + (1 / factor) + ')',
                        transformOrigin: '0 0',
                        marginRight: size.width * (1 - factor),
                        marginBottom: size.height * (1 - factor)
                    });
                };

                var setScale = function(value, maxHeight) {
                    if (_.isNumber(value) && value >= 1) {
                        scale = value;
                    }
                    if (_.isNumber(maxHeight) && maxHeight > 0) {
                        maxScaledHeight = maxHeight;
                    }

                    return module;
                };

                var alignByWidthOnly = function() {
                    var data = getData(),
                        height = data.containerWidth / data.elementRatio;

                    setSize(data.element, {
                        height: height,
                        width: data.containerWidth,
                        top: 0.5 * (data.containerHeight - height),
                        left: 0
                    });

                    return module;
                };

                var alignByHeightOnly = function() {
                    var data = getData(),
                        width = data.containerHeight * data.elementRatio;

                    setSize(data.element, {
                        height: data.containerHeight,
                        width: data.containerHeight * data.elementRatio,
                        top: 0,
                        left: 0.5 * (data.containerWidth - width)
                    });

                    return module;
                };

                var setMode = function(param) {
                    if (_.isString(param)) {
                        mode = param;
                        align();
                    }

                    return module;
                };

                var setElement = function(element) {
                    config.element = element;

                    return module;
                };

                var addCallback = function(func) {
                    if ($.isFunction(func)) {
                        callbacksList.push(func);
                    } else {
                        console.error('[Video info]: TypeError: Argument is not a function.');
                    }

                    return module;
                };

                var addOnceCallback = function(func) {
                    if ($.isFunction(func)) {
                        var decorator = function() {
                            func();
                            removeCallback(func);
                        };

                        addCallback(decorator);
                    } else {
                        console.error('TypeError: Argument is not a function.');
                    }

                    return module;
                };

                var fireCallbacks = function() {
                    $.each(callbacksList, function(index, callback) {
                        callback();
                    });
                };

                var removeCallbacks = function() {
                    callbacksList.length = 0;

                    return module;
                };

                var removeCallback = function(func) {
                    var index = $.inArray(func, callbacksList);

                    if (index !== -1) {
                        return callbacksList.splice(index, 1);
                    }
                };

                var resetDelta = function() {
                    // eslint-disable-next-line no-multi-assign
                    delta.height = delta.width = 0;

                    return module;
                };

                var addDelta = function(value, side) {
                    if (_.isNumber(value) && _.isNumber(delta[side])) {
                        delta[side] += value;
                    }

                    return module;
                };

                var substractDelta = function(value, side) {
                    if (_.isNumber(value) && _.isNumber(delta[side])) {
                        delta[side] -= value;
                    }

                    return module;
                };

                var destroy = function() {
                    var data = getData();
                    data.element.css({
                        height: '',
                        width: '',
                        top: '',
                        left: '',
                        transform: '',
                        transformOrigin: '',
                        marginRight: '',
                        marginBottom: ''
                    });
                    removeCallbacks();
                    resetDelta();
                    mode = null;
                };

                initialize.apply(module, arguments);

                return $.extend(true, module, {
                    align: align,
                    alignByWidthOnly: alignByWidthOnly,
                    alignByHeightOnly: alignByHeightOnly,
                    destroy: destroy,
                    setParams: initialize,
                    setMode: setMode,
                    setElement: setElement,
                    setScale: setScale,
                    callbacks: {
                        add: addCallback,
                        once: addOnceCallback,
                        remove: removeCallback,
                        removeAll: removeCallbacks
                    },
                    delta: {
                        add: addDelta,
                        substract: substractDelta,
                        reset: resetDelta
                    }
                });
            };

            return Resizer;
        });
}(RequireJS.requirejs, RequireJS.require, RequireJS.define));
