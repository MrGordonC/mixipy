from django.contrib import admin
from .models import Page, Platform, RequestLog

admin.site.register(Page)
admin.site.register(Platform)
admin.site.register(RequestLog)


