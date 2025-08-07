import re
from functools import lru_cache
import pytz
from django.utils import html
from django.conf import settings
from django.shortcuts import render

from .. import models as m
from .getters import must_be_staff


JOURNAL_LINKS = {
    "nw": ("/admin/reseaux.html#nw-%d", m.Network, None, ()),
    "u": ("/admin/users.html?selected=%d", m.User, "%(first_name)s %(last_name)s (%(email)s)", ("first_name", "last_name", "email")),
    "dv": ("/admin/dv-%d/edit", m.Delivery, None, ()),
}


def journal(request):
    must_be_staff(request)
    journal_link_re = re.compile(r"\b([a-z][a-z]?)-([0-9]+)")

    @lru_cache
    def add_link_to_actions(m):
        txt, code, n = m.group(0, 1, 2)
        if code not in JOURNAL_LINKS:
            return txt
        href_template, cls, tooltip_template, value_names = JOURNAL_LINKS.get(code)
        href = href_template % int(n)
        if tooltip_template is None:
            return f"<a href='{href}'>{html.escape(txt)}</a>"
        else:
            values = cls.objects.filter(pk=int(n)).values(*value_names).first()
            title = tooltip_template % values
            return f"<a href='{href}' data-toggle='tooltip' title='{html.escape(title)}'>{html.escape(txt)}</a>"

    days = []
    current_day = None
    n = int(request.GET.get("n", 1024))
    tz = pytz.timezone(settings.TIME_ZONE)
    for entry in m.JournalEntry.objects.all().select_related("user").order_by("-date")[:n]:
        date = entry.date.astimezone(tz)
        today = date.strftime("%x")
        action = journal_link_re.sub(add_link_to_actions, html.escape(entry.action))
        record = {
            "user": entry.user,
            "hour": date.strftime("%X"),
            "action": action,
        }
        if not current_day or current_day["day"] != today:
            current_day = {"day": today, "entries": [record]}
            days.append(current_day)
        else:
            current_day["entries"].append(record)
    return render(request, "journal.html", {"user": request.user, "days": days})
