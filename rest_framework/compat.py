"""
The `compat` module provides support for backwards compatibility with older
versions of django/python, and compatibility wrappers around optional packages.
"""

# flake8: noqa
from __future__ import unicode_literals

from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.utils import six
import django
import inspect


# Handle django.utils.encoding rename in 1.5 onwards.
# smart_unicode -> smart_text
# force_unicode -> force_text
try:
    from django.utils.encoding import smart_text
except ImportError:
    from django.utils.encoding import smart_unicode as smart_text
try:
    from django.utils.encoding import force_text
except ImportError:
    from django.utils.encoding import force_unicode as force_text


# OrderedDict only available in Python 2.7.
# This will always be the case in Django 1.7 and above, as these versions
# no longer support Python 2.6.
# For Django <= 1.6 and Python 2.6 fall back to OrderedDict.
try:
    from collections import OrderedDict
except:
    from django.utils.datastructures import SortedDict as OrderedDict


# HttpResponseBase only exists from 1.5 onwards
try:
    from django.http.response import HttpResponseBase
except ImportError:
    from django.http import HttpResponse as HttpResponseBase


# django-filter is optional
try:
    import django_filters
except ImportError:
    django_filters = None


if django.VERSION >= (1, 6):
    def clean_manytomany_helptext(text):
        return text
else:
    # Up to version 1.5 many to many fields automatically suffix
    # the `help_text` attribute with hardcoded text.
    def clean_manytomany_helptext(text):
        if text.endswith(' Hold down "Control", or "Command" on a Mac, to select more than one.'):
            text = text[:-69]
        return text

# Django-guardian is optional. Import only if guardian is in INSTALLED_APPS
# Fixes (#1712). We keep the try/except for the test suite.
guardian = None
if 'guardian' in settings.INSTALLED_APPS:
    try:
        import guardian
        import guardian.shortcuts  # Fixes #1624
    except ImportError:
        pass


# cStringIO only if it's available, otherwise StringIO
try:
    import cStringIO.StringIO as StringIO
except ImportError:
    StringIO = six.StringIO

BytesIO = six.BytesIO


# urlparse compat import (Required because it changed in python 3.x)
try:
    from urllib import parse as urlparse
except ImportError:
    import urlparse

# UserDict moves in Python 3
try:
    from UserDict import UserDict
    from UserDict import DictMixin
except ImportError:
    from collections import UserDict
    from collections import MutableMapping as DictMixin


def get_model_name(model_cls):
    try:
        return model_cls._meta.model_name
    except AttributeError:
        # < 1.6 used module_name instead of model_name
        return model_cls._meta.module_name


def get_concrete_model(model_cls):
    try:
        return model_cls._meta.concrete_model
    except AttributeError:
        # 1.3 does not include concrete model
        return model_cls


# View._allowed_methods only present from 1.5 onwards
if django.VERSION >= (1, 5):
    from django.views.generic import View
else:
    from django.views.generic import View as DjangoView

    class View(DjangoView):
        def _allowed_methods(self):
            return [m.upper() for m in self.http_method_names if hasattr(self, m)]



# MinValueValidator, MaxValueValidator et al. only accept `message` in 1.8+
if django.VERSION >= (1, 8):
    from django.core.validators import MinValueValidator, MaxValueValidator
    from django.core.validators import MinLengthValidator, MaxLengthValidator
else:
    from django.core.validators import MinValueValidator as DjangoMinValueValidator
    from django.core.validators import MaxValueValidator as DjangoMaxValueValidator
    from django.core.validators import MinLengthValidator as DjangoMinLengthValidator
    from django.core.validators import MaxLengthValidator as DjangoMaxLengthValidator

    class MinValueValidator(DjangoMinValueValidator):
        def __init__(self, *args, **kwargs):
            self.message = kwargs.pop('message', self.message)
            super(MinValueValidator, self).__init__(*args, **kwargs)

    class MaxValueValidator(DjangoMaxValueValidator):
        def __init__(self, *args, **kwargs):
            self.message = kwargs.pop('message', self.message)
            super(MaxValueValidator, self).__init__(*args, **kwargs)

    class MinLengthValidator(DjangoMinLengthValidator):
        def __init__(self, *args, **kwargs):
            self.message = kwargs.pop('message', self.message)
            super(MinLengthValidator, self).__init__(*args, **kwargs)

    class MaxLengthValidator(DjangoMaxLengthValidator):
        def __init__(self, *args, **kwargs):
            self.message = kwargs.pop('message', self.message)
            super(MaxLengthValidator, self).__init__(*args, **kwargs)


# URLValidator only accepts `message` in 1.6+
if django.VERSION >= (1, 6):
    from django.core.validators import URLValidator
else:
    from django.core.validators import URLValidator as DjangoURLValidator

    class URLValidator(DjangoURLValidator):
        def __init__(self, *args, **kwargs):
            self.message = kwargs.pop('message', self.message)
            super(URLValidator, self).__init__(*args, **kwargs)


# EmailValidator requires explicit regex prior to 1.6+
if django.VERSION >= (1, 6):
    from django.core.validators import EmailValidator
else:
    from django.core.validators import EmailValidator as DjangoEmailValidator
    from django.core.validators import email_re

    class EmailValidator(DjangoEmailValidator):
        def __init__(self, *args, **kwargs):
            super(EmailValidator, self).__init__(email_re, *args, **kwargs)


# PATCH method is not implemented by Django
if 'patch' not in View.http_method_names:
    View.http_method_names = View.http_method_names + ['patch']


# RequestFactory only provides `generic` from 1.5 onwards
from django.test.client import RequestFactory as DjangoRequestFactory
from django.test.client import FakePayload
try:
    # In 1.5 the test client uses force_bytes
    from django.utils.encoding import force_bytes as force_bytes_or_smart_bytes
except ImportError:
    # In 1.4 the test client just uses smart_str
    from django.utils.encoding import smart_str as force_bytes_or_smart_bytes

class RequestFactory(DjangoRequestFactory):
    def generic(self, method, path,
            data='', content_type='application/octet-stream', **extra):
        parsed = urlparse.urlparse(path)
        data = force_bytes_or_smart_bytes(data, settings.DEFAULT_CHARSET)
        r = {
            'PATH_INFO':      self._get_path(parsed),
            'QUERY_STRING':   force_text(parsed[4]),
            'REQUEST_METHOD': six.text_type(method),
        }
        if data:
            r.update({
                'CONTENT_LENGTH': len(data),
                'CONTENT_TYPE':   six.text_type(content_type),
                'wsgi.input':     FakePayload(data),
            })
        elif django.VERSION <= (1, 4):
            # For 1.3 we need an empty WSGI payload
            r.update({
                'wsgi.input': FakePayload('')
            })
        r.update(extra)
        return self.request(**r)


# Markdown is optional
try:
    import markdown

    def apply_markdown(text):
        """
        Simple wrapper around :func:`markdown.markdown` to set the base level
        of '#' style headers to <h2>.
        """

        extensions = ['headerid(level=2)']
        safe_mode = False
        md = markdown.Markdown(extensions=extensions, safe_mode=safe_mode)
        return md.convert(text)
except ImportError:
    apply_markdown = None


# Yaml is optional
try:
    import yaml
except ImportError:
    yaml = None


# `seperators` argument to `json.dumps()` differs between 2.x and 3.x
# See: http://bugs.python.org/issue22767
if six.PY3:
    SHORT_SEPARATORS = (',', ':')
    LONG_SEPARATORS = (', ', ': ')
else:
    SHORT_SEPARATORS = (b',', b':')
    LONG_SEPARATORS = (b', ', b': ')


# Handle lazy strings across Py2/Py3
from django.utils.functional import Promise

if six.PY3:
    def is_non_str_iterable(obj):
        if (isinstance(obj, str) or
            (isinstance(obj, Promise) and obj._delegate_text)):
            return False
        return hasattr(obj, '__iter__')
else:
    def is_non_str_iterable(obj):
        return hasattr(obj, '__iter__')


try:
    from django.utils.encoding import python_2_unicode_compatible
except ImportError:
    def python_2_unicode_compatible(klass):
        """
        A decorator that defines __unicode__ and __str__ methods under Python 2.
        Under Python 3 it does nothing.

        To support Python 2 and 3 with a single code base, define a __str__ method
        returning text and apply this decorator to the class.
        """
        if '__str__' not in klass.__dict__:
            raise ValueError("@python_2_unicode_compatible cannot be applied "
                             "to %s because it doesn't define __str__()." %
                             klass.__name__)
        klass.__unicode__ = klass.__str__
        klass.__str__ = lambda self: self.__unicode__().encode('utf-8')
        return klass
