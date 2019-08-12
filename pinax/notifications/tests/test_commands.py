import os
import datetime

from django.contrib.auth import get_user_model
from django.core import mail, management
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from ..models import NoticeType, queue


class TestManagementCmd(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("test_user", "test@user.com", "123456")
        self.user2 = get_user_model().objects.create_user("test_user2", "test2@user.com", "123456")
        NoticeType.create("label", "display", "description")

    @override_settings(SITE_ID=1)
    def test_emit_notices(self):
        users = [self.user, self.user2]
        queue(users, "label")
        management.call_command("emit_notices")
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn(self.user.email, mail.outbox[0].to)
        self.assertIn(self.user2.email, mail.outbox[1].to)

    def test_emit_expired(self):
        users = [self.user, self.user2]
        till = timezone.now() - datetime.timedelta(hours=1)
        queue(users, 'label', send_till=till)
        management.call_command('emit_notices')
        self.assertEqual(len(mail.outbox), 0)

    def test_emit_not_expired(self):
        users = [self.user, self.user2]
        till = timezone.now() + datetime.timedelta(hours=1)
        queue(users, 'label', send_till=till)
        management.call_command('emit_notices')
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn(self.user.email, mail.outbox[0].to)
        self.assertIn(self.user2.email, mail.outbox[1].to)

    def test_emit_broken_queue(self):
        """
        Try to send message to 2 users.
        Fail in template rendering on the first recipient, but send message to second one.
        :return:
        """
        template_filename = 'pinax/notifications/templates/pinax/notifications/short.txt'
        os.makedirs('pinax/notifications/templates/pinax/notifications', exist_ok=True)
        import logging
        logging.getLogger('pinax.engine').info('It is ok to have exception below:')
        with open(template_filename, 'w') as f:
            print('''{% if recipient.username == 'test_user' %}
    {% for _ in recipient.id %} {% endfor %}
{% else %}
    {{ recipient.username }}
{% endif %}''', file=f)
        queue([self.user], 'label')
        queue([self.user2], 'label')
        management.call_command('emit_notices')
        logging.getLogger('pinax.engine').info('It is ok to have exception above')
        os.unlink(template_filename)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user2.email, mail.outbox[0].to)

    def test_emit_too_early(self):
        users = [self.user, self.user2]
        after = timezone.now() + datetime.timedelta(hours=1)
        queue(users, 'label', send_after=after)
        management.call_command('emit_notices')
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(SITE_ID=1)
    def test_emit_removed_user(self):
        # default behaviout, send_now
        users = [self.user, self.user2]
        queue(users, "label")
        self.user.delete()
        management.call_command('emit_notices')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user2.email, mail.outbox[0].to)
