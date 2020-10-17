from django.apps import AppConfig as BaseAppConfig
from django.utils.translation import ugettext_lazy as _


class AppConfig(BaseAppConfig):

    name = "pinax.notifications"
    label = "pinax_notifications"
    verbose_name = _("Pinax Notifications")

    def ready(self):
        from django.conf import settings
        from .models import deliver_counter

        for backend in settings.PINAX_NOTIFICATIONS_BACKENDS.values():
            deliver_counter.labels(backend.__class__.__name__)
