from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.conf.urls import include, url

from rest_framework import routers

from .api import views


router = routers.DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'groups', views.GroupViewSet)
router.register(r'polls', views.PollViewSet)

urlpatterns = [
    url(r'', include('tracpro.baseline.urls')),
    url(r'', include('tracpro.contacts.urls')),
    url(r'', include('tracpro.groups.urls')),
    url(r'', include('tracpro.home.urls')),
    url(r'', include('tracpro.msgs.urls')),
    url(r'', include('tracpro.polls.urls')),
    url(r'', include('tracpro.profiles.urls')),
    url(r'^manage/', include('tracpro.orgs_ext.urls')),
    url(r'^users/', include('dash.users.urls')),
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^chaining/', include('smart_selects.urls')),
    # Wire up our API using automatic URL routing.
    # Additionally, we include login URLs for the browsable API.
    url(r'^', include(router.urls)),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework'))
]

if settings.DEBUG:  # pragma: no cover
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
        url(r'^media/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),
        url(r'', include('django.contrib.staticfiles.urls')),
    ] + urlpatterns
