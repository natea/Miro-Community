# Copyright 2009 - Participatory Culture Foundation
# 
# This file is part of Miro Community.
# 
# Miro Community is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
# 
# Miro Community is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Miro Community.  If not, see <http://www.gnu.org/licenses/>.

from django.conf.urls.defaults import patterns

from localtv import models

urlpatterns = patterns(
    'localtv.inline_edit',
    (r'^feed/(?P<id>[0-9]+)/name/$', 'simple.edit_field',
     {'model': models.Feed, 'field': 'name'}, 'localtv_admin_feed_edit_name'),
    (r'^feed/(?P<id>[0-9]+)/auto_categories/$',
     'feed_views.edit_auto_categories',
     {}, 'localtv_admin_feed_edit_auto_categories'),
    (r'^feed/(?P<id>[0-9]+)/auto_authors/$', 'feed_views.edit_auto_authors',
     {}, 'localtv_admin_feed_edit_auto_authors'),
    (r'^video/(?P<id>[0-9]+)/name/$', 'simple.edit_field',
     {'model': models.Video, 'field': 'name'},
     'localtv_admin_video_edit_name'),
    (r'^video/(?P<id>[0-9]+)/when_published/$', 'simple.edit_field',
     {'model': models.Video, 'field': 'when_published'},
     'localtv_admin_video_edit_when_published'),
    (r'^video/(?P<id>[0-9]+)/authors/$', 'simple.edit_field',
     {'model': models.Video, 'field': 'authors'},
     'localtv_admin_video_edit_authors'),
    (r'^video/(?P<id>[0-9]+)/categories/$', 'simple.edit_field',
    {'model': models.Video, 'field': 'categories'},
     'localtv_admin_video_edit_categories'),
    (r'^video/(?P<id>[0-9]+)/tags/$', 'simple.edit_field',
    {'model': models.Video, 'field': 'tags'},
     'localtv_admin_video_edit_tags'),
    (r'^video/(?P<id>[0-9]+)/description/$', 'simple.edit_field',
     {'model': models.Video, 'field': 'description'},
     'localtv_admin_video_edit_description'),
    (r'^video/(?P<id>[0-9]+)/website_url/$', 'simple.edit_field',
     {'model': models.Video, 'field': 'website_url'},
     'localtv_admin_video_edit_website_url'))
