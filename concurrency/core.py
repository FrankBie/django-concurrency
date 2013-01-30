from django.db import DatabaseError
from django.utils.translation import ugettext as _
from django.conf import settings


class RecordModifiedError(DatabaseError):
    pass


def _select_lock(obj, version=None):
    kwargs = {'pk': obj.pk, obj.RevisionMetaInfo.field.name: version or getattr(obj, obj.RevisionMetaInfo.field.name)}
    # mysql do not support no wait
    # see https://docs.djangoproject.com/en/dev/ref/models/querysets/#django.db.models.query.QuerySet.select_for_update
    entry = None
    if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.mysql':
        entry = obj.__class__.objects.select_for_update().filter(**kwargs)
    else:
        entry = obj.__class__.objects.select_for_update(nowait=True).filter(**kwargs)
    if not entry:
        if getattr(obj, obj.RevisionMetaInfo.field.name) == 0:
            raise RecordModifiedError(_('Version field is 0 but record has `pk`.'))
        raise RecordModifiedError(_('Record has been modified'))


def concurrency_check(self, force_insert=False, force_update=False, using=None):
    if self.pk and not force_insert:
        _select_lock(self)
    field = self.RevisionMetaInfo.field
    setattr(self, field.attname, field.get_new_value(self))


def _versioned_save(self, force_insert=False, force_update=False, using=None):
    if force_insert and force_update:
        raise ValueError("Cannot force both insert and updating in model saving.")
    concurrency_check(self, force_insert, force_update, using)
    self.save_base(using=using, force_insert=force_insert, force_update=force_update)


class RevisionMetaInfo:
    field = None
    versioned_save = False

def class_prepared_handler(sender, **kwargs):
    old_save = getattr(sender, 'save', None)
    setattr(sender, 'save', _versioned_save)


class VersionFieldMixin(object):
    def __init__(self, **kwargs):
        verbose_name = kwargs.get('verbose_name', None)
        name = kwargs.get('name', None)
        db_tablespace = kwargs.get('db_tablespace', None)
        db_column = kwargs.get('db_column', None)
        help_text = kwargs.get('help_text', _('record revision number'))
        self.custom_save= kwargs.pop('custom_save', False)
        super(VersionFieldMixin, self).__init__(verbose_name, name, editable=True,
                                                help_text=help_text, null=False, blank=False, default=1,
                                                db_tablespace=db_tablespace, db_column=db_column)

#    def contribute_to_class(self, cls, name):
#        super(VersionFieldMixin, self).contribute_to_class(cls, name)
#        if hasattr(cls, 'RevisionMetaInfo'):
#            return
#        if not self.custom_save:
#            setattr(cls, 'save', _versioned_save)
#        setattr(cls, 'RevisionMetaInfo', RevisionMetaInfo())
#        cls.RevisionMetaInfo.field = self

    def get_default(self):
        return 0
