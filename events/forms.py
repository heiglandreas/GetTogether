from django.utils.safestring import mark_safe
from django import forms
from django.forms.widgets import TextInput, Media
from django.utils.translation import ugettext_lazy as _

from django.contrib.auth.models import User
from .models.profiles import Team, UserProfile
from .models.events import Event, Place

from datetime import time
from time import strptime, strftime

class LookupMedia(Media):
    def render(self):
        return mark_safe('''<script type="text/javascript"><script>
$(document).ready(function(){
    $("#{{ widget.name }}_search").keyup(function() {
	var searchText = this.value;
	$.getJSON("{{ widget.source }}?q="+searchText, function(data) {
	    var selectField = $("#{{ widget.name }}_select");
	    selectField.empty();
	    $.each(data, function(){
		selectField.append('<option value="'+ this.{{ widget.key }} +'">'+ this.{{ widget.label }} + '</option>')
	    });
	});
    });
});
</script>''')

class Lookup(TextInput):
    input_type = 'text'
    template_name = 'forms/widgets/lookup.html'
    add_id_index = False
    checked_attribute = {'selected': True}
    option_inherits_attrs = False

    def __init__(self, source='#', key="id", label="name", attrs=None):
        super().__init__(attrs)
        self.source = source
        self.key = key
        self.label = label

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['source'] = self.source
        context['widget']['key'] = self.key
        context['widget']['label'] = self.label
        return context

    def format_value(self, value):
        if value is not None:
            return mark_safe('<option value="%s">%s</option>' % (value, _('No change')))
        else:
            return mark_safe('<option value="">--------</option>')

class DateWidget(forms.DateInput):
    """A more-friendly date widget with a p% if widget.value != None %} value="{{ widget.value|stringformat:'s' }}"{% endif %op-up calendar.
    """
    template_name = 'forms/widgets/date.html'
    def __init__(self, attrs=None):
        self.date_class = 'datepicker'
        if not attrs:
            attrs = {}
        if 'date_class' in attrs:
            self.date_class = attrs.pop('date_class')
        if 'class' not in attrs:
            attrs['class'] = 'date'

        super(DateWidget, self).__init__(attrs=attrs)


class TimeWidget(forms.MultiWidget):
    """A more-friendly time widget.
    """
    def __init__(self, attrs=None):
        self.time_class = 'timepicker'
        if not attrs:
            attrs = {}
        if 'time_class' in attrs:
            self.time_class = attrs.pop('time_class')
        if 'class' not in attrs:
            attrs['class'] = 'time'

        widgets = (
            forms.Select(attrs=attrs, choices=[(i + 1, "%02d" % (i + 1)) for i in range(0, 12)]),
            forms.Select(attrs=attrs, choices=[(i, "%02d" % i) for i in range(00, 60, 15)]),
            forms.Select(attrs=attrs, choices=[('AM', _('AM')), ('PM', _('PM'))])
        )

        super(TimeWidget, self).__init__(widgets, attrs)

    def decompress(self, value):
        if isinstance(value, str):
            try:
                value = strptime(value, '%I:%M %p')
            except:
                value = strptime(value, '%H:%M:%S')
            hour = int(value.tm_hour)
            minute = int(value.tm_min)
            if hour < 12:
                meridian = 'AM'
            else:
                meridian = 'PM'
                hour -= 12
            return (hour, minute, meridian)
        elif isinstance(value, time):
            hour = int(value.strftime("%I"))
            minute = int(value.strftime("%M"))
            meridian = value.strftime("%p")
            return (hour, minute, meridian)
        return (None, None, None)

    def value_from_datadict(self, data, files, name):
        value = super(TimeWidget, self).value_from_datadict(data, files, name)
        t = strptime("%02d:%02d %s" % (int(value[0]), int(value[1]), value[2]), "%I:%M %p")
        return strftime("%H:%M:%S", t)

    def format_output(self, rendered_widgets):
        return '<span class="%s">%s%s%s</span>' % (
            self.time_class,
            rendered_widgets[0], rendered_widgets[1], rendered_widgets[2]
        )

class DateTimeWidget(forms.SplitDateTimeWidget):
    """
    A more-friendly date/time widget.
    """
    def __init__(self, attrs=None, date_format=None, time_format=None):
        super(DateTimeWidget, self).__init__(attrs, date_format, time_format)
        self.widgets = (
            DateWidget(attrs=attrs),
            TimeWidget(attrs=attrs),
        )

    def decompress(self, value):
        if value:
            d = strftime("%Y-%m-%d", value.timetuple())
            t = strftime("%I:%M %p", value.timetuple())
            return (d, t)
        else:
            return (None, None)

    def format_output(self, rendered_widgets):
        return '%s %s' % (rendered_widgets[0], rendered_widgets[1])

    def value_from_datadict(self, data, files, name):
        values = super(DateTimeWidget, self).value_from_datadict(data, files, name)
        return ' '.join(values)

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'description', 'category', 'city', 'web_url', 'tz']
        widgets = {
            'city': Lookup(source='/api/cities/', label='name'),
        }
        raw_id_fields = ('city')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['city'].required = True

class NewTeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'description', 'category', 'city', 'web_url', 'tz']
        widgets = {
            'city': Lookup(source='/api/cities/', label='name'),
        }
        raw_id_fields = ('city')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['city'].required = True

class DeleteTeamForm(forms.Form):
    confirm = forms.BooleanField(label="Yes, delete team", required=True)

class TeamEventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['name', 'start_time', 'end_time', 'summary', 'place', 'web_url', 'announce_url', 'tags']
        widgets = {
            'place': Lookup(source='/api/places/', label='name'),
            'start_time': DateTimeWidget,
            'end_time': DateTimeWidget
        }

class NewTeamEventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['name', 'start_time', 'end_time', 'summary']
        widgets = {
            'start_time': DateTimeWidget,
            'end_time': DateTimeWidget
        }

class DeleteEventForm(forms.Form):
    confirm = forms.BooleanField(label="Yes, delete event", required=True)

class NewPlaceForm(forms.ModelForm):
    class Meta:
        model = Place
        fields = ['name', 'address', 'city', 'longitude', 'latitude', 'place_url', 'tz']
        widgets = {
            'city': Lookup(source='/api/cities/', label='name'),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['city'].required = True

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email']

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['realname', 'avatar', 'send_notifications']
        labels = {
            'send_notifications': _('Send me notification emails'),
        }

class SendNotificationsForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['send_notifications']
        labels = {
            'send_notifications': _('Send me notification emails'),
        }
        
class SearchForm(forms.Form):
    city = forms.IntegerField(required=False, widget=Lookup(source='/api/cities/', label='name'))
    distance = forms.IntegerField(label=_("Distance(km)"), required=True)
    class Meta:
        widgets ={
            'city': Lookup(source='/api/cities/', label='name'),
        }
