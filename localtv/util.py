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

import hashlib
import re
import string
import urllib

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.db.models import get_model, Q
from django.utils.encoding import force_unicode

import tagging
import vidscraper
from notification import models as notification

VIDEO_EXTENSIONS = [
    '.mov', '.wmv', '.mp4', '.m4v', '.ogg', '.ogv', '.anx',
    '.mpg', '.avi', '.flv', '.mpeg', '.divx', '.xvid', '.rmvb',
    '.mkv', '.m2v', '.ogm']

def is_video_filename(filename):
    """
    Pass a filename to this method and it will return a boolean
    saying if the filename represents a video file.
    """
    filename = filename.lower()
    for ext in VIDEO_EXTENSIONS:
        if filename.endswith(ext):
            return True
    return False

def is_video_type(type):
    application_video_mime_types = [
        "application/ogg",
        "application/x-annodex",
        "application/x-bittorrent",
        "application/x-shockwave-flash"
    ]
    return (type.startswith('video/') or type.startswith('audio/') or
            type in application_video_mime_types)

def get_first_video_enclosure(entry):
    """Find the first video enclosure in a feedparser entry.  Returns the
    enclosure, or None if no video enclosure is found.
    """
    enclosures = entry.get('media_content') or entry.get('enclosures')
    if not enclosures:
        return None
    best_enclosure = None
    for enclosure in enclosures:
        if is_video_type(enclosure.get('type', '')) or \
                is_video_filename(enclosure.get('url', '')):
            if enclosure.get('isdefault'):
                return enclosure
            elif best_enclosure is None:
                best_enclosure = enclosure
    return best_enclosure

def get_thumbnail_url(entry):
    """Get the URL for a thumbnail from a feedparser entry."""
    # Try the video enclosure
    def _get(d):
        if 'media_thumbnail' in d:
            return d.media_thumbnail[0]['url']
        if 'blip_thumbnail_src' in d and d.blip_thumbnail_src:
            return (u'http://a.images.blip.tv/%s' % (
                d['blip_thumbnail_src'])).encode('utf-8')
        if 'itunes_image' in d:
            return d.itunes_image['href']
        if 'image' in d:
            return d.image['href']
        raise KeyError
    video_enclosure = get_first_video_enclosure(entry)
    if video_enclosure is not None:
        try:
            return _get(video_enclosure)
        except KeyError:
            pass
    # Try to get any enclosure thumbnail
    for key in 'media_content', 'enclosures':
        if key in entry:
            for enclosure in entry[key]:
                try:
                    return _get(enclosure)
                except KeyError:
                    pass
    # Try to get the thumbnail for our entry
    try:
        return _get(entry)
    except KeyError:
        pass

    if entry.get('link', '').find(u'youtube.com') != -1:
        if 'content' in entry:
            content = entry.content[0]['value']
        elif 'summary' in entry:
            content = entry.summary
        else:
            return None
        match = re.search(r'<img alt="" src="([^"]+)" />',
                          content)
        if match:
            return match.group(1)

    return None

def get_tag(tag_text):
    while True:
        try:
            tags = tagging.models.Tag.objects.filter(name=tag_text)
            if not tags.count():
                return tagging.models.Tag.objects.create(name=tag_text)
            elif tags.count() == 1:
                return tags[0]
            else:
                for tag in tags:
                    if tag.name == tag:
                        # MySQL doesn't do case-sensitive equals on strings
                        return tag
        except Exception:
            pass # try again to create the tag

def get_or_create_tags(tag_list):
    tag_set = set()
    for tag_text in tag_list:
        if isinstance(tag_text, basestring):
            tag_text = tag_text[:50] # tags can only by 50 chars
        if settings.FORCE_LOWERCASE_TAGS:
            tag_text = tag_text.lower()
        tag = get_tag(tag_text);
        tag.name = force_unicode(tag.name)
        tag_set.add(tag)
    return tagging.utils.edit_string_for_tags(list(tag_set))


def get_scraped_data(url):
    cache_key = 'vidscraper_data-' + url
    if len(cache_key) >= 250:
        # too long, use the hash
        cache_key = 'vidscraper_data-hash-' + hashlib.sha1(url).hexdigest()
    scraped_data = cache.get(cache_key)

    if not scraped_data:
        # try and scrape the url
        try:
            scraped_data = vidscraper.auto_scrape(url)
        except vidscraper.errors.Error:
            scraped_data = None

        cache.add(cache_key, scraped_data)

    return scraped_data

def send_notice(notice_label, subject, message, fail_silently=True,
                sitelocation=None):
    notice_type = notification.NoticeType.objects.get(label=notice_label)
    recipient_list = notification.NoticeSetting.objects.filter(
        notice_type=notice_type,
        medium="1",
        send=True).exclude(user__email='').filter(
        Q(user__in=sitelocation.admins.all()) |
        Q(user__is_superuser=True)).values_list('user__email', flat=True)
    EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL,
                 bcc=recipient_list).send(fail_silently=fail_silently)

class SortHeaders:
    def __init__(self, request, headers, default_order=None):
        self.request = request
        self.header_defs = headers
        if default_order is None:
            for header, ordering in headers:
                if ordering is not None:
                    default_order = ordering
                    break
        self.default_order = default_order
        if default_order.startswith('-'):
            self.desc = True
            self.ordering = default_order[1:]
        else:
             self.desc = False
             self.ordering = default_order

        # Determine order field and order type for the current request
        sort = request.GET.get('sort', '')
        desc = False
        if sort.startswith('-'):
            desc = True
            sort = sort[1:]
        if sort:
            for header, ordering in headers:
                if ordering and ordering.startswith('-'):
                    ordering = ordering[1:]
                if sort == ordering:
                    self.ordering, self.desc = sort, desc

    def headers(self):
        """
        Generates dicts containing header and sort link details for
        all defined headers.
        """
        for header, ordering in self.header_defs:
            css_class = ''
            if ordering == self.ordering or (
                ordering and ordering.startswith('-') and
                ordering[1:] == self.ordering):
                # current sort
                if self.desc:
                    ordering = self.ordering
                    css_class = 'sortup'
                else:
                    ordering = '-%s' % self.ordering
                    css_class = 'sortdown'
            yield {
                'sort': ordering,
                'link': self._query_string(ordering),
                'label': header,
                'class': css_class
                }

    def __iter__(self):
        return iter(self.headers())

    def _query_string(self, sort):
        """
        Creates a query string from the given dictionary of
        parameters, including any additonal parameters which should
        always be present.
        """
        if sort is None:
            return None
        params = self.request.GET.copy()
        params.pop('sort', None)
        params.pop('page', None)
        if sort != self.default_order:
            params['sort'] = sort
        if not params:
            return self.request.path
        return '?%s' % params.urlencode()

    def order_by(self):
        """
        Creates an ordering criterion based on the current order
        field and order type, for use with the Django ORM's
        ``order_by`` method.
        """
        return '%s%s' % (
            self.desc and '-' or '',
            self.ordering)

class MockQueryset(object):
    """
    Wrap a list of objects in an object which pretends to be a QuerySet.
    """

    def __init__(self, objects, model=None, filters=None):
        self.objects = objects
        self.model = model
        self.filters = filters or {}
        if self.model:
            self.db = model.objects.all().db
        elif hasattr(objects, 'db'):
            self.db = objects.db
        else:
            self.db = 'default'

        self._count = None
        self._iter_index = None
        self._result_cache = []
        self.ordered = True

    def all(self):
        return self

    def _clone(self):
        return self

    def __len__(self):
        if self._count is None:
            if self.model:
                self._count = self.model.objects.filter(
                    pk__in=self.objects).count()
            else:
                self._count = len(self.objects)
        return self._count

    def __iter__(self):
        if not self.model:
            return iter(self.objects)

        it = MockQueryset(self.objects, self.model, self.filters)
        it._count = self._count
        it._result_cache = self._result_cache[:]
        it._iter_index = 0
        return it

    def next(self):
        if self._iter_index is None:
            raise RuntimeError('Cannot use MockQueryset directly as an '
                               'iterator, must call iter() first')
        if self._iter_index == len(self):
            raise StopIteration # don't even bother looking for more results

        if self._iter_index >= len(self._result_cache): # not enough data
            objs = []
            while True:
                next = self.objects[self._iter_index:self._iter_index + 20]
                if not next:
                    break
                values = self.model.objects.in_bulk(next)
                objs = [values[k] for k in next
                        if k in values and \
                            self._is_valid(values[k])]
                if objs:
                    break
            self._result_cache += objs

        if self._iter_index >= len(self._result_cache):
            raise StopIteration

        result = self._result_cache[self._iter_index]
        self._iter_index += 1

        return result

    def _is_valid(self, obj):
        if not self.filters:
            return True
        for filter_key, filter_value in self.filters.items():
            if getattr(obj, filter_key) != filter_value:
                return False
        return True

    def __getitem__(self, k):
        if isinstance(k, slice):
            mq = MockQueryset(self.objects[k], self.model, self.filters)
            return mq
        return self.objects[k]

    def filter(self, **kwargs):
        new_filters = self.filters.copy()
        for k, v in kwargs.items():
            if '__' in k: # special filter
                return self.objects.filter(**kwargs)
            new_filters[k] = v
        return MockQueryset(self.objects, self.model, new_filters)

def get_profile_model():
    app_label, model_name = settings.AUTH_PROFILE_MODULE.split('.')
    Profile = get_model(app_label, model_name)
    if Profile is None:
        raise RuntimeError("could not find a Profile model at %r" %
                           settings.AUTH_PROFILE_MODULE)
    return Profile


SAFE_URL_CHARACTERS = string.ascii_letters + string.punctuation

def quote_unicode_url(url):
    return urllib.quote(url, safe=SAFE_URL_CHARACTERS)
