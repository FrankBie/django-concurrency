from django.db.models.signals import class_prepared
from concurrency.core import class_prepared_concurrency_handler

class_prepared.connect(class_prepared_concurrency_handler, dispatch_uid='class_prepared_concurrency_handler')
