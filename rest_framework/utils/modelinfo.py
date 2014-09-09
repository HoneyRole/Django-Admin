"""
Helper functions for returning the field information that is associated
with a model class.
"""
from collections import namedtuple, OrderedDict
from django.db import models
from django.utils import six
import inspect

FieldInfo = namedtuple('FieldResult', ['pk', 'fields', 'forward_relations', 'reverse_relations'])
RelationInfo = namedtuple('RelationInfo', ['field', 'related', 'to_many', 'has_through_model'])


def _resolve_model(obj):
    """
    Resolve supplied `obj` to a Django model class.

    `obj` must be a Django model class itself, or a string
    representation of one.  Useful in situtations like GH #1225 where
    Django may not have resolved a string-based reference to a model in
    another model's foreign key definition.

    String representations should have the format:
        'appname.ModelName'
    """
    if isinstance(obj, six.string_types) and len(obj.split('.')) == 2:
        app_name, model_name = obj.split('.')
        return models.get_model(app_name, model_name)
    elif inspect.isclass(obj) and issubclass(obj, models.Model):
        return obj
    raise ValueError("{0} is not a Django model".format(obj))


def get_field_info(model):
    """
    Given a model class, returns a `FieldInfo` instance containing metadata
    about the various field types on the model.
    """
    opts = model._meta.concrete_model._meta

    # Deal with the primary key.
    pk = opts.pk
    while pk.rel and pk.rel.parent_link:
        # If model is a child via multitable inheritance, use parent's pk.
        pk = pk.rel.to._meta.pk

    # Deal with regular fields.
    fields = OrderedDict()
    for field in [field for field in opts.fields if field.serialize and not field.rel]:
        fields[field.name] = field

    # Deal with forward relationships.
    forward_relations = OrderedDict()
    for field in [field for field in opts.fields if field.serialize and field.rel]:
        forward_relations[field.name] = RelationInfo(
            field=field,
            related=_resolve_model(field.rel.to),
            to_many=False,
            has_through_model=False
        )

    # Deal with forward many-to-many relationships.
    for field in [field for field in opts.many_to_many if field.serialize]:
        forward_relations[field.name] = RelationInfo(
            field=field,
            related=_resolve_model(field.rel.to),
            to_many=True,
            has_through_model=(
                not field.rel.through._meta.auto_created
            )
        )

    # Deal with reverse relationships.
    reverse_relations = OrderedDict()
    for relation in opts.get_all_related_objects():
        accessor_name = relation.get_accessor_name()
        reverse_relations[accessor_name] = RelationInfo(
            field=None,
            related=relation.model,
            to_many=relation.field.rel.multiple,
            has_through_model=False
        )

    # Deal with reverse many-to-many relationships.
    for relation in opts.get_all_related_many_to_many_objects():
        accessor_name = relation.get_accessor_name()
        reverse_relations[accessor_name] = RelationInfo(
            field=None,
            related=relation.model,
            to_many=True,
            has_through_model=(
                hasattr(relation.field.rel, 'through') and
                not relation.field.rel.through._meta.auto_created
            )
        )

    return FieldInfo(pk, fields, forward_relations, reverse_relations)
