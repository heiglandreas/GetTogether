from django.db import models
from django.contrib.sites.models import Site
from django.contrib.auth.models import User, Group
from django.utils.translation import ugettext_lazy as _
from django.shortcuts import reverse

from rest_framework import serializers

from .locale import *
from .profiles import *
from .search import *

import re
import pytz
import datetime
import unicodedata

SLUG_OK = '-_~'


class Place(models.Model):
    name = models.CharField(help_text=_('Name of the Place'), max_length=150)
    city = models.ForeignKey(City, verbose_name=_('City'), on_delete=models.CASCADE)
    address = models.CharField(help_text=_('Address with Street and Number'), max_length=150, null=True, blank=True)
    longitude = models.FloatField(help_text=_('Longitude in Degrees East'), null=True, blank=True)
    latitude = models.FloatField(help_text=_('Latitude in Degrees North'), null=True, blank=True)
    tz = models.CharField(max_length=32, verbose_name=_('Timezone'), default='UTC', choices=[(tz, tz) for tz in pytz.all_timezones], blank=False, null=False)
    place_url = models.URLField(help_text=_('URL for the Place Homepage'), verbose_name=_('URL of the Place'), max_length=200, blank=True, null=True)
    cover_img = models.URLField(_("Place photo"), null=True, blank=True)

    def __str__(self):
        return u'%s, %s' % (self.name, self.city.name)

class PlaceSerializer(serializers.ModelSerializer):
    city = serializers.CharField(read_only=True)
    class Meta:
        model = Place
        fields = (
            'id',
            'name',
            'city',
            'address',
            'longitude',
            'latitude',
            'tz',
            'place_url',
            'cover_img'
        )


class Event(models.Model):
    name = models.CharField(max_length=150, verbose_name=_('Event Name'))
    team = models.ForeignKey(Team, on_delete=models.CASCADE)

    start_time = models.DateTimeField(help_text=_('Local date and time that the event starts'), verbose_name=_('Local Start Time'), db_index=True)
    end_time = models.DateTimeField(help_text=_('Local date and time that the event ends'), verbose_name=_('Local End Time'), db_index=True)
    summary = models.TextField(help_text=_('Summary of the Event'), blank=True, null=True)

    place = models.ForeignKey(Place, blank=True, null=True, on_delete=models.CASCADE)

    web_url = models.URLField(verbose_name=_('Website'), help_text=_('URL for the event'), max_length=200, blank=True, null=True)
    announce_url = models.URLField(verbose_name=_('Announcement'), help_text=_('URL for the announcement'), max_length=200, blank=True, null=True)

    created_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    created_time = models.DateTimeField(help_text=_('the date and time when the event was created'), default=datetime.datetime.now, db_index=True)

    tags = models.CharField(verbose_name=_("Keyword Tags"), blank=True, null=True, max_length=128)
    #image
    #replies

    attendees = models.ManyToManyField(UserProfile, through='Attendee', related_name="attending", blank=True)

    def get_absolute_url(self):
        return reverse('show-event', kwargs={'event_id': self.id, 'event_slug': self.slug})

    def get_full_url(self):
        site = Site.objects.get(id=1)
        return "https://%s%s" % (site.domain, self.get_absolute_url())

    @property
    def slug(self):
        return slugify(self.name)

    def __str__(self):
        return u'%s by %s at %s' % (self.name, self.team.name, self.start_time)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # Call the "real" save() method.
        update_event_searchable(self)

def update_event_searchable(event):
    site = Site.objects.get(id=1)
    event_url = "https://%s%s" % (site.domain, event.get_absolute_url())
    origin_url = "https://%s%s" % (site.domain, reverse('searchables'))
    try:
        searchable = Searchable.objects.get(event_url=event_url)
    except:
        searchable = Searchable(event_url)
        searchable.origin_node = origin_url
        searchable.federation_node = origin_url
        searchable.federation_time = datetime.datetime.now()

    if event.team.category:
        searchable.img_url = event.team.category.img_url
    else:
        searchable.img_url = "https://%s%s" % (site.domain, '/static/img/team_placeholder.png')
    searchable.event_title = event.name
    searchable.group_name = event.team.name
    searchable.start_time = event.start_time
    searchable.end_time = event.end_time
    searchable.cost = 0
    searchable.tags = event.tags
    if (event.place is not None):
        searchable.location_name = str(event.place.city)
        searchable.venue_name = event.place.name
        searchable.longitude = event.place.longitude or None
        searchable.latitude = event.place.latitude or None
    else:
        searchable.location_name = event.team.location_name

    if event.team.city is not None and (searchable.longitude is None or searchable.latitude is None):
        searchable.longitude = event.team.city.longitude
        searchable.latitude = event.team.city.latitude

    searchable.save()

def slugify(s, ok=SLUG_OK, lower=True, spaces=False):
    # L and N signify letter/number.
    # http://www.unicode.org/reports/tr44/tr44-4.html#GC_Values_Table
    rv = []
    for c in unicodedata.normalize('NFKC', s):
        cat = unicodedata.category(c)[0]
        if cat in 'LN' or c in ok:
            rv.append(c)
        if cat == 'Z':  # space
            rv.append(' ')
    new = ''.join(rv).strip()
    if not spaces:
        new = re.sub('[-\s]+', '-', new)
    return new.lower() if lower else new

class Attendee(models.Model):
    NORMAL=0
    CREW=1
    HOST=2
    ROLES = [
        (NORMAL, _("Normal")),
        (CREW, _("Crew")),
        (HOST, _("Host"))
    ]
    NO=-1
    MAYBE=0
    YES=1
    STATUSES = [
        (NO, _("No")),
        (MAYBE, _("Maybe")),
        (YES, _("Yes")),
    ]
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    role = models.SmallIntegerField(_("Role"), choices=ROLES, default=NORMAL, db_index=True)
    status = models.SmallIntegerField(_("Attending?"), choices=STATUSES, default=YES, db_index=True)
    joined_date = models.DateTimeField(default=datetime.datetime.now)

    @property
    def role_name(self):
        return Attendee.ROLES[self.role][1]

    @property
    def status_name(self):
        return Attendee.STATUSES[self.status+1][1]

    def __str__(self):
        return "%s at %s" % (self.user, self.event)
    
