import base64
import pickle
import pprint

from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import NoticeQueueBatch, NoticeSetting, NoticeType


class NoticeQueueBatchAdmin(admin.ModelAdmin):
    fields = ['pickled_data', 'unpickled_data', 'send_till', 'send_after']
    readonly_fields = ['unpickled_data']

    def unpickled_data(self, b):
        if b.pickled_data:
            data = pickle.loads(base64.b64decode(b.pickled_data))
            data = pprint.pformat(data)
            return mark_safe(''.join(("<pre>", data, "</pre>")))
        else:
            return ''


class NoticeTypeAdmin(admin.ModelAdmin):
    list_display = ["label", "display", "description", "default"]


class NoticeSettingAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "notice_type", "medium", "scoping", "send"]


admin.site.register(NoticeQueueBatch, NoticeQueueBatchAdmin)
admin.site.register(NoticeType, NoticeTypeAdmin)
admin.site.register(NoticeSetting, NoticeSettingAdmin)
