import logging

from django.core.management.base import BaseCommand

from pinax.notifications.engine import send_all


class Command(BaseCommand):
    help = "Emit queued notices."

    def handle(self, *args, **options):
        logging.basicConfig(level=logging.DEBUG, format="%(message)s")
        logging.getLogger('pinax').info("-" * 72)
        send_all(*args)
