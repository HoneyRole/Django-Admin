from django.core.handlers.wsgi import STATUS_CODE_TEXT

__all__ =['Response', 'ErrorResponse']

# TODO: remove raw_content/cleaned_content and just use content?

class Response(object):
    """An HttpResponse that may include content that hasn't yet been serialized."""
    def __init__(self, status=200, content=None, headers={}):
        self.status = status
        self.has_content_body = content is not None
        self.raw_content = content      # content prior to filtering
        self.cleaned_content = content  # content after filtering
        self.headers = headers
 
    @property
    def status_text(self):
        """Return reason text corresponding to our HTTP response status code.
        Provided for convenience."""
        return STATUS_CODE_TEXT.get(self.status, '')


class ErrorResponse(BaseException):
    """An exception representing an HttpResponse that should be returned immediatley."""
    def __init__(self, status, content=None, headers={}):
        self.response = Response(status, content=content, headers=headers)
