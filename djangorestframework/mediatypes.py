"""
Handling of media types, as found in HTTP Content-Type and Accept headers.

See http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.7
"""

from django.http.multipartparser import parse_header


class MediaType(object):
    def __init__(self, media_type_str):
        self.orig = media_type_str
        self.media_type, self.params = parse_header(media_type_str)
        self.main_type, sep, self.sub_type = self.media_type.partition('/')

    def match(self, other):
        """Return true if this MediaType satisfies the constraint of the given MediaType."""
        for key in other.params.keys():
            if key != 'q' and other.params[key] != self.params.get(key, None):
                return False

        if other.sub_type != '*' and other.sub_type != self.sub_type:
            return False

        if other.main_type != '*' and other.main_type != self.main_type:
            return False

        return True

    def precedence(self):
        """
        Return a precedence level for the media type given how specific it is.
        """
        if self.main_type == '*':
            return 1
        elif self.sub_type == '*':
            return 2
        elif not self.params or self.params.keys() == ['q']:
            return 3
        return 4

    def quality(self):
        """
        Return a quality level for the media type.
        """
        try:
            return Decimal(self.params.get('q', '1.0'))
        except:
            return Decimal(0)
    
    def score(self):
        """
        Return an overall score for a given media type given it's quality and precedence.
        """
        # NB. quality values should only have up to 3 decimal points
        # http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.9
        return self.quality * 10000 + self.precedence

    def is_form(self):
        """
        Return True if the MediaType is a valid form media type as defined by the HTML4 spec.
        (NB. HTML5 also adds text/plain to the list of valid form media types, but we don't support this here)
        """
        return self.media_type == 'application/x-www-form-urlencoded' or \
               self.media_type == 'multipart/form-data'

    def as_tuple(self):
        return (self.main_type, self.sub_type, self.params)

    def __repr__(self):
        return "<MediaType %s>" % (self.as_tuple(),)

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __unicode__(self):
        return self.orig

