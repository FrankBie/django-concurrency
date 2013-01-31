from functools import update_wrapper
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections, router
from django.utils.translation import ugettext as _
from django.conf import settings

__all__ = []


class RecordModifiedError(DatabaseError):
    pass


def apply_concurrency_check(model, fieldname, versionclass):
    """
    Apply concurrency management to existing Models.

    :param model: Model class to update
    :type model: django.db.Model

    :param fieldname: name of the field
    :type fieldname: basestring

    :param versionclass:
    :type versionclass: concurrency.fields.VersionField subclass
    """
    if hasattr(model, 'RevisionMetaInfo'):
        raise ImproperlyConfigured("%s is already under concurrency management" % model)

    ver = versionclass()
    ver.contribute_to_class(model, fieldname)
    model.RevisionMetaInfo.field = ver

    if not model.RevisionMetaInfo.versioned_save:
        old_save = getattr(model, 'save')
        setattr(model, 'save', _wrap_save(old_save))
        model.RevisionMetaInfo.versioned_save = True


def concurrency_check(model_instance, force_insert=False, force_update=False, using=None, **kwargs):
    if model_instance.pk and not force_insert:
        _select_lock(model_instance)
    # field = self.RevisionMetaInfo.field
    # setattr(self, field.attname, field.get_new_value(self))


def _select_lock(model_instance, version_value=None):
    version_field = model_instance.RevisionMetaInfo.field
    kwargs = {'pk': model_instance.pk,
              version_field.name: version_value or getattr(model_instance, version_field.name)}
    alias = router.db_for_write(model_instance)
    NOWAIT = connections[alias].features.has_select_for_update_nowait
    # print 1111111, alias, NOWAIT
    # from django.db import connection
    # connections['mydb'].
    # self.connection.features.has_select_for_update_nowait
    # print 111, obj.__class__.objects.connection
    entry = model_instance.__class__.objects.select_for_update(nowait=NOWAIT).filter(**kwargs)
    if not entry:
        value = getattr(model_instance, version_field.name)
        if value != version_field.get_default():
            raise RecordModifiedError(_('Version field is set (%s) but record has `pk`.' % value))
        raise RecordModifiedError(_('Record has been modified'))


def _wrap_save(func):
    def inner(self, force_insert=False, force_update=False, using=None, **kwargs):
        concurrency_check(self, force_insert, force_update, using, **kwargs)
        return func(self, force_insert, force_update, using, **kwargs)

    return update_wrapper(inner, func)


def _versioned_save(self, force_insert=False, force_update=False, using=None):
    if force_insert and force_update:
        raise ValueError("Cannot force both insert and updating in model saving.")
    concurrency_check(self, force_insert, force_update, using)
    self.save_base(using=using, force_insert=force_insert, force_update=force_update)


def class_prepared_concurrency_handler(sender, **kwargs):
    if hasattr(sender, 'RevisionMetaInfo') and not (sender.RevisionMetaInfo.manually or
                                                    sender.RevisionMetaInfo.versioned_save):
        old_save = getattr(sender, 'save')
        setattr(sender, 'save', _wrap_save(old_save))
        sender.RevisionMetaInfo.versioned_save = True


class RevisionMetaInfo:
    field = None
    versioned_save = False
    manually = False

