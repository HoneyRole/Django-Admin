"""
Renderers are used to serialize a View's output into specific media types.

Django REST framework also provides HTML and PlainText renderers that help self-document the API,
by serializing the output along with documentation regarding the View, output status and headers,
and providing forms and links depending on the allowed methods, renderers and parsers on the View. 
"""
from django import forms
from django.conf import settings
from django.template import RequestContext, loader
from django.utils import simplejson as json

from djangorestframework import status
from djangorestframework.compat import apply_markdown
from djangorestframework.utils import dict2xml, url_resolves
from djangorestframework.utils.breadcrumbs import get_breadcrumbs
from djangorestframework.utils.description import get_name, get_description
from djangorestframework.utils.mediatypes import get_media_type_params, add_media_type_param

from decimal import Decimal
import re
import string
from urllib import quote_plus

__all__ = (
    'BaseRenderer',
    'TemplateRenderer',
    'JSONRenderer',
    'DocumentingHTMLRenderer',
    'DocumentingXHTMLRenderer',
    'DocumentingPlainTextRenderer',
    'XMLRenderer'
)


class BaseRenderer(object):
    """
    All renderers must extend this class, set the media_type attribute,
    and override the render() function.
    """
    media_type = None

    def __init__(self, view):
        self.view = view

    def render(self, obj=None, media_type=None):
        """
        Given an object render it into a string.

        The requested media type is also passed to this method,
        as it may contain parameters relevant to how the parser
        should render the output.
        EG: 'application/json; indent=4'

        By default render simply returns the ouput as-is.
        Override this method to provide for other behavior.
        """
        if obj is None:
            return ''
        
        return str(obj)


class TemplateRenderer(BaseRenderer):
    """
    A Base class provided for convenience.

    Render the object simply by using the given template.
    To create a template renderer, subclass this, and set
    the ``media_type`` and ``template`` attributes
    """
    media_type = None
    template = None

    def render(self, obj=None, media_type=None):
        if obj is None:
            return ''

        context = RequestContext(self.request, obj)
        return self.template.render(context)


class DocumentingTemplateRenderer(BaseRenderer):
    """
    Base class for renderers used to self-document the API.
    Implementing classes should extend this class and set the template attribute.
    """
    template = None

    def _get_content(self, view, request, obj, media_type):
        """
        Get the content as if it had been rendered by a non-documenting renderer.

        (Typically this will be the content as it would have been if the Resource had been
        requested with an 'Accept: */*' header, although with verbose style formatting if appropriate.)
        """

        # Find the first valid renderer and render the content. (Don't use another documenting renderer.)
        renderers = [renderer for renderer in view.renderers if not isinstance(renderer, DocumentingTemplateRenderer)]
        if not renderers:
            return '[No renderers were found]'

        media_type = add_media_type_param(media_type, 'indent', '4')
        content = renderers[0](view).render(obj, media_type)
        if not all(char in string.printable for char in content):
            return '[%d bytes of binary content]'
            
        return content


    def _get_form_instance(self, view):
        """
        Get a form, possibly bound to either the input or output data.
        In the absence on of the Resource having an associated form then
        provide a form that can be used to submit arbitrary content.
        """

        # Get the form instance if we have one bound to the input
        form_instance = getattr(view, 'bound_form_instance', None)

        if not form_instance and hasattr(view, 'get_bound_form'):
            # Otherwise if we have a response that is valid against the form then use that
            if view.response.has_content_body:
                try:
                    form_instance = view.get_bound_form(view.response.cleaned_content)
                    if form_instance and not form_instance.is_valid():
                        form_instance = None
                except:
                    form_instance = None
            
        # If we still don't have a form instance then try to get an unbound form
        if not form_instance:
            try:
                form_instance = view.get_bound_form()
            except:
                pass

        # If we still don't have a form instance then try to get an unbound form which can tunnel arbitrary content types
        if not form_instance:
            form_instance = self._get_generic_content_form(view)
        
        return form_instance


    def _get_generic_content_form(self, view):
        """
        Returns a form that allows for arbitrary content types to be tunneled via standard HTML forms
        (Which are typically application/x-www-form-urlencoded)
        """

        # If we're not using content overloading there's no point in supplying a generic form,
        # as the view won't treat the form's value as the content of the request.
        if not getattr(view, '_USE_FORM_OVERLOADING', False):
            return None

        # NB. http://jacobian.org/writing/dynamic-form-generation/
        class GenericContentForm(forms.Form):
            def __init__(self, view):
                """We don't know the names of the fields we want to set until the point the form is instantiated,
                as they are determined by the Resource the form is being created against.
                Add the fields dynamically."""
                super(GenericContentForm, self).__init__()

                contenttype_choices = [(media_type, media_type) for media_type in view.parsed_media_types]
                initial_contenttype = view.default_parser.media_type

                self.fields[view._CONTENTTYPE_PARAM] = forms.ChoiceField(label='Content Type',
                                                                         choices=contenttype_choices,
                                                                         initial=initial_contenttype)
                self.fields[view._CONTENT_PARAM] = forms.CharField(label='Content',
                                                                   widget=forms.Textarea)

        # If either of these reserved parameters are turned off then content tunneling is not possible
        if self.view._CONTENTTYPE_PARAM is None or self.view._CONTENT_PARAM is None:
            return None

        # Okey doke, let's do it
        return GenericContentForm(view)


    def render(self, obj=None, media_type=None):
        content = self._get_content(self.view, self.view.request, obj, media_type)
        form_instance = self._get_form_instance(self.view)

        if url_resolves(settings.LOGIN_URL) and url_resolves(settings.LOGOUT_URL):
            login_url = "%s?next=%s" % (settings.LOGIN_URL, quote_plus(self.view.request.path))
            logout_url = "%s?next=%s" % (settings.LOGOUT_URL, quote_plus(self.view.request.path))
        else:
            login_url = None
            logout_url = None

        name = get_name(self.view)
        description = get_description(self.view)

        markeddown = None
        if apply_markdown:
            try:
                markeddown = apply_markdown(description)
            except AttributeError:
                markeddown = None

        breadcrumb_list = get_breadcrumbs(self.view.request.path)

        template = loader.get_template(self.template)
        context = RequestContext(self.view.request, {
            'content': content,
            'resource': self.view,        # TODO: rename to view
            'request': self.view.request, # TODO: remove
            'response': self.view.response,
            'description': description,
            'name': name,
            'markeddown': markeddown,
            'breadcrumblist': breadcrumb_list,
            'form': form_instance,
            'login_url': login_url,
            'logout_url': logout_url,
            'ADMIN_MEDIA_PREFIX': settings.ADMIN_MEDIA_PREFIX
        })
        
        ret = template.render(context)

        # Munge DELETE Response code to allow us to return content
        # (Do this *after* we've rendered the template so that we include
        # the normal deletion response code in the output)
        if self.view.response.status == 204:
            self.view.response.status = 200

        return ret


class JSONRenderer(BaseRenderer):
    """
    Renderer which serializes to JSON
    """
    media_type = 'application/json'

    def render(self, obj=None, media_type=None):
        if obj is None:
            return ''

        indent = get_media_type_params(media_type).get('indent', None)
        if indent is not None:
            try:
                indent = int(indent)
            except ValueError:
                indent = None

        sort_keys = indent and True or False
        return json.dumps(obj, indent=indent, sort_keys=sort_keys)


class XMLRenderer(BaseRenderer):
    """
    Renderer which serializes to XML.
    """
    media_type = 'application/xml'

    def render(self, obj=None, media_type=None):
        if obj is None:
            return ''
        return dict2xml(obj)


class DocumentingHTMLRenderer(DocumentingTemplateRenderer):
    """
    Renderer which provides a browsable HTML interface for an API.
    See the examples at http://api.django-rest-framework.org to see this in action.
    """
    media_type = 'text/html'
    template = 'renderer.html'


class DocumentingXHTMLRenderer(DocumentingTemplateRenderer):
    """
    Identical to DocumentingHTMLRenderer, except with an xhtml media type.
    We need this to be listed in preference to xml in order to return HTML to WebKit based browsers,
    given their Accept headers.
    """
    media_type = 'application/xhtml+xml'
    template = 'renderer.html'


class DocumentingPlainTextRenderer(DocumentingTemplateRenderer):
    """
    Renderer that serializes the object with the default renderer, but also provides plain-text
    documentation of the returned status and headers, and of the resource's name and description.
    Useful for browsing an API with command line tools.
    """
    media_type = 'text/plain'
    template = 'renderer.txt'


DEFAULT_RENDERERS = ( JSONRenderer,
                      DocumentingHTMLRenderer,
                      DocumentingXHTMLRenderer,
                      DocumentingPlainTextRenderer,
                      XMLRenderer )


