Django REST framework
=====================

Django REST framework makes it easy to build well-connected, self-describing RESTful Web APIs.

Features:

* Creates awesome self-describing *web browse-able* APIs.
* Clean, modular design, using Django's class based views.
* Easily extended for custom content types, serialization formats and authentication policies. 
* Stable, well tested code-base.
* Active developer community.

Full documentation for the project is available at http://django-rest-framework.org

Issue tracking is on `GitHub <https://github.com/tomchristie/django-rest-framework/issues>`_.
General questions should be taken to the `discussion group <http://groups.google.com/group/django-rest-framework>`_.

Requirements:

* Python (2.5, 2.6, 2.7 supported)
* Django (1.2, 1.3 supported)


Installation Notes
==================

To clone the project from GitHub using git::

    git clone git@github.com:tomchristie/django-rest-framework.git


To clone the project from Bitbucket using mercurial::

    hg clone https://tomchristie@bitbucket.org/tomchristie/django-rest-framework


To install django-rest-framework in a virtualenv environment::

    cd django-rest-framework
    virtualenv --no-site-packages --distribute --python=python2.6 env
    source env/bin/activate
    pip install -r requirements.txt # django, coverage


To run the tests::

    export PYTHONPATH=.    # Ensure djangorestframework is on the PYTHONPATH
    python djangorestframework/runtests/runtests.py


To run the test coverage report::

    export PYTHONPATH=.    # Ensure djangorestframework is on the PYTHONPATH
    python djangorestframework/runtests/runcoverage.py


To run the examples::

    pip install -r examples/requirements.txt # pygments, httplib2, markdown
    cd examples
    export PYTHONPATH=..
    python manage.py syncdb
    python manage.py runserver


To build the documentation::

    pip install -r docs/requirements.txt   # sphinx
    sphinx-build -c docs -b html -d docs/build docs html


To run the tests against the full set of supported configurations::

    deactivate  # Ensure we are not currently running in a virtualenv
    tox


To create the sdist packages::

    python setup.py sdist --formats=gztar,zip



Release Notes
=============

0.2.3

* Fix some throttling bugs.
* ``X-Throttle`` header on throttling.
* Support for nesting resources on related models.

0.2.2

* Throttling support complete.

0.2.1

* Couple of simple bugfixes over 0.2.0
  
0.2.0

* Big refactoring changes since 0.1.0, ask on the discussion group if anything isn't clear.
  The public API has been massively cleaned up.  Expect it to be fairly stable from here on in.

* ``Resource`` becomes decoupled into ``View`` and ``Resource``, your views should now inherit from ``View``, not ``Resource``.

* The handler functions on views ``.get() .put() .post()`` etc, no longer have the ``content`` and ``auth`` args.
  Use ``self.CONTENT`` inside a view to access the deserialized, validated content.
  Use ``self.user`` inside a view to access the authenticated user.

* ``allowed_methods`` and ``anon_allowed_methods`` are now defunct.  if a method is defined, it's available.
  The ``permissions`` attribute on a ``View`` is now used to provide generic permissions checking.
  Use permission classes such as ``FullAnonAccess``, ``IsAuthenticated`` or ``IsUserOrIsAnonReadOnly`` to set the permissions.

* The ``authenticators`` class becomes ``authentication``.  Class names change to ``Authentication``.

* The ``emitters`` class becomes ``renderers``.  Class names change to ``Renderers``.

* ``ResponseException`` becomes ``ErrorResponse``.

* The mixin classes have been nicely refactored, the basic mixins are now ``RequestMixin``, ``ResponseMixin``, ``AuthMixin``, and ``ResourceMixin``
  You can reuse these mixin classes individually without using the ``View`` class.

0.1.1

* Final build before pulling in all the refactoring changes for 0.2, in case anyone needs to hang on to 0.1.

0.1.0

* Initial release.