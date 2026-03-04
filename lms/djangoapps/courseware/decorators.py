"""
Decorators for courseware views.
"""
import functools

from django.shortcuts import redirect
from opaque_keys.edx.keys import CourseKey
from openedx_filters.learning.filters import CoursewareViewRedirectURL


def courseware_view_redirect(view_func):
    """
    Decorator that calls the CoursewareViewRedirectURL filter before rendering a courseware view.

    If any pipeline step returns a non-empty list of redirect URLs, the user is redirected
    to the first URL in the list. Otherwise, the original view is rendered normally.

    Usage::

        @courseware_view_redirect
        def my_view(request, course_id, ...):
            ...

    Works with both function-based views and ``method_decorator``-wrapped class-based views.
    The decorator extracts the ``course_id`` or ``course_key`` from the view arguments.
    """
    @functools.wraps(view_func)
    def _wrapper(request_or_self, *args, **kwargs):
        # Support both function views (request as first arg) and method views
        # (self as first arg, request as second arg).
        if hasattr(request_or_self, 'method'):
            # Function-based view: first arg is request
            request = request_or_self
        else:
            # Class-based view via method_decorator: first arg is self, second is request
            request = args[0] if args else kwargs.get('request')

        course_id = kwargs.get('course_id') or (args[0] if args and not hasattr(request_or_self, 'method') else None)
        try:
            course_key = CourseKey.from_string(str(course_id)) if course_id else None
        except Exception:  # pylint: disable=broad-except
            course_key = None

        if course_key is not None:
            redirect_urls, _request, _course_key = CoursewareViewRedirectURL.run_filter(
                redirect_urls=[],
                request=request,
                course_key=course_key,
            )
            if redirect_urls:
                return redirect(redirect_urls[0])

        return view_func(request_or_self, *args, **kwargs)

    return _wrapper
