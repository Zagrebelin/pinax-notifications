import pickle
import logging
import sys
import time
import traceback

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.mail import mail_admins
from django.db.models import Q
from django.utils import timezone

from . import models as notification
from .conf import settings
from .lockfile import AlreadyLocked, FileLock, LockTimeout
from .models import NoticeQueueBatch
from .signals import emitted_notices


logger = logging.getLogger('pinax.engine')


def acquire_lock(*args):
    if len(args) == 1:
        lock = FileLock(args[0])
    else:
        lock = FileLock("send_notices")

    logger.debug("acquiring lock...")
    try:
        lock.acquire(settings.PINAX_NOTIFICATIONS_LOCK_WAIT_TIMEOUT)
    except AlreadyLocked:
        logger.debug("lock already in place. quitting.")
        return
    except LockTimeout:
        logger.debug("waiting for the lock timed out. quitting.")
        return
    logger.debug("acquired.")
    return lock


def send_all(*args):
    lock = acquire_lock(*args)
    if lock is None:
        logger.debug("no lock acquired. skipping sending.")
        return
    batches, sent, sent_actual = 0, 0, 0
    start_time = time.time()
    now = timezone.now()

    try:
        for queued_batch in NoticeQueueBatch.objects\
                .filter(Q(send_till__isnull=True) | Q(send_till__gt=now))\
                .filter(Q(send_after__isnull=True) | Q(send_after__lte=now))\
                .all():
            was_sent = False
            notices = pickle.loads(base64.b64decode(queued_batch.pickled_data))
            for (ct, ct_id), label, extra_context, sender in notices:
                try:
                    user = ct.get_object_for_this_type(pk=ct_id)
                    logger.info("emitting notice {0} to {1}".format(label, user))
                    # call this once per user to be atomic and allow for logger.to
                    # accurately show how long each takes.
                    if notification.send_now([user], label, extra_context, sender):
                        sent_actual += 1
                        was_sent = True
                except get_user_model().DoesNotExist:
                    # Ignore deleted users, just warn about them
                    logger.warning("not emitting notice %s to user [%s id=%d] since it does not exist",
                        label, ct, ct_id)
                except Exception as e:
                    logger.exception('not emitting notice %s: %s', label, e)
                sent += 1
            if was_sent:
                queued_batch.delete()
            batches += 1
        emitted_notices.send(
            sender=NoticeQueueBatch,
            batches=batches,
            sent=sent,
            sent_actual=sent_actual,
            run_time="%.2f seconds" % (time.time() - start_time)
        )
    except Exception:  # pylint: disable-msg=W0703
        # get the exception
        _, e, _ = sys.exc_info()
        # email people
        current_site = Site.objects.get_current()
        subject = "[{0} emit_notices] {1}".format(current_site.name, e)
        message = "\n".join(
            traceback.format_exception(*sys.exc_info())  # pylint: disable-msg=W0142
        )
        mail_admins(subject, message, fail_silently=True)
        # log it as critical
        logger.critical("an exception occurred: {0}".format(e))
    finally:
        logger.debug("releasing lock...")
        lock.release()
        logger.debug("released.")

    _, expired = NoticeQueueBatch.objects.filter(send_till__lt=now).delete()
    expired = expired['pinax_notifications.NoticeQueueBatch']
    logger.info("{0} batches, {1} sent, {2} expired".format(batches, sent, expired))
    logger.info("done in {0:.2f} seconds".format(time.time() - start_time))
