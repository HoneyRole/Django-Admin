"""
Pagination serializers determine the structure of the output that should
be used for paginated responses.
"""
from __future__ import unicode_literals
from base64 import b64encode, b64decode
from collections import namedtuple
from django.core.paginator import InvalidPage, Paginator as DjangoPaginator
from django.template import Context, loader
from django.utils import six
from django.utils.six.moves.urllib import parse as urlparse
from django.utils.translation import ugettext as _
from rest_framework.compat import OrderedDict
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.utils.urls import (
    replace_query_param, remove_query_param
)


def _strict_positive_int(integer_string, cutoff=None):
    """
    Cast a string to a strictly positive integer.
    """
    ret = int(integer_string)
    if ret <= 0:
        raise ValueError()
    if cutoff:
        ret = min(ret, cutoff)
    return ret


def _divide_with_ceil(a, b):
    """
    Returns 'a' divded by 'b', with any remainder rounded up.
    """
    if a % b:
        return (a // b) + 1
    return a // b


def _get_count(queryset):
    """
    Determine an object count, supporting either querysets or regular lists.
    """
    try:
        return queryset.count()
    except (AttributeError, TypeError):
        return len(queryset)


def _get_displayed_page_numbers(current, final):
    """
    This utility function determines a list of page numbers to display.
    This gives us a nice contextually relevant set of page numbers.

    For example:
    current=14, final=16 -> [1, None, 13, 14, 15, 16]

    This implementation gives one page to each side of the cursor,
    or two pages to the side when the cursor is at the edge, then
    ensures that any breaks between non-continous page numbers never
    remove only a single page.

    For an alernativative implementation which gives two pages to each side of
    the cursor, eg. as in GitHub issue list pagination, see:

    https://gist.github.com/tomchristie/321140cebb1c4a558b15
    """
    assert current >= 1
    assert final >= current

    if final <= 5:
        return list(range(1, final + 1))

    # We always include the first two pages, last two pages, and
    # two pages either side of the current page.
    included = set((
        1,
        current - 1, current, current + 1,
        final
    ))

    # If the break would only exclude a single page number then we
    # may as well include the page number instead of the break.
    if current <= 4:
        included.add(2)
        included.add(3)
    if current >= final - 3:
        included.add(final - 1)
        included.add(final - 2)

    # Now sort the page numbers and drop anything outside the limits.
    included = [
        idx for idx in sorted(list(included))
        if idx > 0 and idx <= final
    ]

    # Finally insert any `...` breaks
    if current > 4:
        included.insert(1, None)
    if current < final - 3:
        included.insert(len(included) - 1, None)
    return included


def _get_page_links(page_numbers, current, url_func):
    """
    Given a list of page numbers and `None` page breaks,
    return a list of `PageLink` objects.
    """
    page_links = []
    for page_number in page_numbers:
        if page_number is None:
            page_link = PAGE_BREAK
        else:
            page_link = PageLink(
                url=url_func(page_number),
                number=page_number,
                is_active=(page_number == current),
                is_break=False
            )
        page_links.append(page_link)
    return page_links


PageLink = namedtuple('PageLink', ['url', 'number', 'is_active', 'is_break'])

PAGE_BREAK = PageLink(url=None, number=None, is_active=False, is_break=True)


class BasePagination(object):
    display_page_controls = False

    def paginate_queryset(self, queryset, request, view=None):  # pragma: no cover
        raise NotImplemented('paginate_queryset() must be implemented.')

    def get_paginated_response(self, data):  # pragma: no cover
        raise NotImplemented('get_paginated_response() must be implemented.')

    def to_html(self):  # pragma: no cover
        raise NotImplemented('to_html() must be implemented to display page controls.')


class PageNumberPagination(BasePagination):
    """
    A simple page number based style that supports page numbers as
    query parameters. For example:

    http://api.example.org/accounts/?page=4
    http://api.example.org/accounts/?page=4&page_size=100
    """
    # The default page size.
    # Defaults to `None`, meaning pagination is disabled.
    paginate_by = api_settings.PAGINATE_BY

    # Client can control the page using this query parameter.
    page_query_param = 'page'

    # Client can control the page size using this query parameter.
    # Default is 'None'. Set to eg 'page_size' to enable usage.
    paginate_by_param = api_settings.PAGINATE_BY_PARAM

    # Set to an integer to limit the maximum page size the client may request.
    # Only relevant if 'paginate_by_param' has also been set.
    max_paginate_by = api_settings.MAX_PAGINATE_BY

    last_page_strings = ('last',)

    template = 'rest_framework/pagination/numbers.html'

    def _handle_backwards_compat(self, view):
        """
        Prior to version 3.1, pagination was handled in the view, and the
        attributes were set there. The attributes should now be set on
        the pagination class, but the old style is still pending deprecation.
        """
        for attr in (
            'paginate_by', 'page_query_param',
            'paginate_by_param', 'max_paginate_by'
        ):
            if hasattr(view, attr):
                setattr(self, attr, getattr(view, attr))

    def paginate_queryset(self, queryset, request, view=None):
        """
        Paginate a queryset if required, either returning a
        page object, or `None` if pagination is not configured for this view.
        """
        self._handle_backwards_compat(view)

        page_size = self.get_page_size(request)
        if not page_size:
            return None

        paginator = DjangoPaginator(queryset, page_size)
        page_number = request.query_params.get(self.page_query_param, 1)
        if page_number in self.last_page_strings:
            page_number = paginator.num_pages

        try:
            self.page = paginator.page(page_number)
        except InvalidPage as exc:
            msg = _('Invalid page "{page_number}": {message}.').format(
                page_number=page_number, message=six.text_type(exc)
            )
            raise NotFound(msg)

        if paginator.count > 1:
            # The browsable API should display pagination controls.
            self.display_page_controls = True

        self.request = request
        return self.page

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))

    def get_page_size(self, request):
        if self.paginate_by_param:
            try:
                return _strict_positive_int(
                    request.query_params[self.paginate_by_param],
                    cutoff=self.max_paginate_by
                )
            except (KeyError, ValueError):
                pass

        return self.paginate_by

    def get_next_link(self):
        if not self.page.has_next():
            return None
        url = self.request.build_absolute_uri()
        page_number = self.page.next_page_number()
        return replace_query_param(url, self.page_query_param, page_number)

    def get_previous_link(self):
        if not self.page.has_previous():
            return None
        url = self.request.build_absolute_uri()
        page_number = self.page.previous_page_number()
        if page_number == 1:
            return remove_query_param(url, self.page_query_param)
        return replace_query_param(url, self.page_query_param, page_number)

    def get_html_context(self):
        base_url = self.request.build_absolute_uri()

        def page_number_to_url(page_number):
            if page_number == 1:
                return remove_query_param(base_url, self.page_query_param)
            else:
                return replace_query_param(base_url, self.page_query_param, page_number)

        current = self.page.number
        final = self.page.paginator.num_pages
        page_numbers = _get_displayed_page_numbers(current, final)
        page_links = _get_page_links(page_numbers, current, page_number_to_url)

        return {
            'previous_url': self.get_previous_link(),
            'next_url': self.get_next_link(),
            'page_links': page_links
        }

    def to_html(self):
        template = loader.get_template(self.template)
        context = Context(self.get_html_context())
        return template.render(context)


class LimitOffsetPagination(BasePagination):
    """
    A limit/offset based style. For example:

    http://api.example.org/accounts/?limit=100
    http://api.example.org/accounts/?offset=400&limit=100
    """
    default_limit = api_settings.PAGINATE_BY
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = None
    template = 'rest_framework/pagination/numbers.html'

    def paginate_queryset(self, queryset, request, view=None):
        self.limit = self.get_limit(request)
        self.offset = self.get_offset(request)
        self.count = _get_count(queryset)
        self.request = request
        if self.count > self.limit:
            self.display_page_controls = True
        return queryset[self.offset:self.offset + self.limit]

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))

    def get_limit(self, request):
        if self.limit_query_param:
            try:
                return _strict_positive_int(
                    request.query_params[self.limit_query_param],
                    cutoff=self.max_limit
                )
            except (KeyError, ValueError):
                pass

        return self.default_limit

    def get_offset(self, request):
        try:
            return _strict_positive_int(
                request.query_params[self.offset_query_param],
            )
        except (KeyError, ValueError):
            return 0

    def get_next_link(self):
        if self.offset + self.limit >= self.count:
            return None

        url = self.request.build_absolute_uri()
        offset = self.offset + self.limit
        return replace_query_param(url, self.offset_query_param, offset)

    def get_previous_link(self):
        if self.offset <= 0:
            return None

        url = self.request.build_absolute_uri()

        if self.offset - self.limit <= 0:
            return remove_query_param(url, self.offset_query_param)

        offset = self.offset - self.limit
        return replace_query_param(url, self.offset_query_param, offset)

    def get_html_context(self):
        base_url = self.request.build_absolute_uri()
        current = _divide_with_ceil(self.offset, self.limit) + 1
        # The number of pages is a little bit fiddly.
        # We need to sum both the number of pages from current offset to end
        # plus the number of pages up to the current offset.
        # When offset is not strictly divisible by the limit then we may
        # end up introducing an extra page as an artifact.
        final = (
            _divide_with_ceil(self.count - self.offset, self.limit) +
            _divide_with_ceil(self.offset, self.limit)
        )

        def page_number_to_url(page_number):
            if page_number == 1:
                return remove_query_param(base_url, self.offset_query_param)
            else:
                offset = self.offset + ((page_number - current) * self.limit)
                return replace_query_param(base_url, self.offset_query_param, offset)

        page_numbers = _get_displayed_page_numbers(current, final)
        page_links = _get_page_links(page_numbers, current, page_number_to_url)

        return {
            'previous_url': self.get_previous_link(),
            'next_url': self.get_next_link(),
            'page_links': page_links
        }

    def to_html(self):
        template = loader.get_template(self.template)
        context = Context(self.get_html_context())
        return template.render(context)


Cursor = namedtuple('Cursor', ['offset', 'reverse', 'position'])


def decode_cursor(encoded):
    tokens = urlparse.parse_qs(b64decode(encoded))
    try:
        offset = int(tokens['offset'][0])
        reverse = bool(int(tokens['reverse'][0]))
        position = tokens['position'][0]
    except (TypeError, ValueError):
        return None

    return Cursor(offset=offset, reverse=reverse, position=position)


def encode_cursor(cursor):
    tokens = {
        'offset': str(cursor.offset),
        'reverse': '1' if cursor.reverse else '0',
        'position': cursor.position
    }
    return b64encode(urlparse.urlencode(tokens, doseq=True))


class CursorPagination(BasePagination):
    # reverse
    # limit
    cursor_query_param = 'cursor'
    page_size = 5

    def paginate_queryset(self, queryset, request, view=None):
        self.base_url = request.build_absolute_uri()
        self.ordering = self.get_ordering()
        encoded = request.query_params.get(self.cursor_query_param)

        if encoded is None:
            cursor = None
        else:
            cursor = decode_cursor(encoded)
            # TODO: Invalid cursors should 404

        if cursor is not None:
            kwargs = {self.ordering + '__gt': cursor.position}
            queryset = queryset.filter(**kwargs)

        results = list(queryset[:self.page_size + 1])
        self.page = results[:self.page_size]
        self.has_next = len(results) > len(self.page)
        return self.page

    def get_next_link(self):
        if not self.has_next:
            return None
        last_item = self.page[-1]
        position = self.get_position_from_instance(last_item, self.ordering)
        cursor = Cursor(offset=0, reverse=False, position=position)
        encoded = encode_cursor(cursor)
        return replace_query_param(self.base_url, self.cursor_query_param, encoded)

    def get_ordering(self):
        return 'created'

    def get_position_from_instance(self, instance, ordering):
        return str(getattr(instance, ordering))

    # def decode_cursor(self, encoded, ordering):
    #     items = urlparse.parse_qs(b64decode(encoded))
    #     return items.get(ordering)[0]

    # def encode_cursor(self, cursor, ordering):
    #     items = [(ordering, cursor)]
    #     return b64encode(urlparse.urlencode(items, doseq=True))
