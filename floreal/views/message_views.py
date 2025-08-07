from django.shortcuts import render, redirect
from django.template.context_processors import csrf
from django.db.models import Q

from .. import models as m
from .getters import must_be_prod_or_staff


def editor(
    request,
    target=None,
    title="Éditer",
    template="editor.html",
    content=None,
    is_rich=True,
    **kwargs,
):
    ctx = dict(
        title=title,
        target=target or request.path,
        content=content or "",
        next=request.GET.get("next"),
        is_rich=is_rich,
        **kwargs,
    )
    ctx.update(csrf(request))
    return render(request, template, ctx)


def set_message(request, destination=None, id=None):
    if id is not None:
        msg = m.AdminMessage.objects.get(pk=id)
        must_be_prod_or_staff(request, msg.network_id)
    else:
        msg = None

    if request.method == "POST":
        P = request.POST
        d = P["destination"].split("-")
        if d[0] == "everyone":
            network_id = None
        elif d[0] == "nw":
            network_id = int(d[1])
        else:
            assert False

        must_be_prod_or_staff(request, network_id)

        text = P["editor"]
        if text.startswith("<p>"):
            text = text[3:]
            if text.endswith("</p>"):
                text = text[:-4]
        if msg is not None:
            msg.message = text
            msg.title = P["message_title"]
            msg.network_id = network_id
            msg.save()
            m.JournalEntry.log(
                request.user,
                "Modified message msg-%i to %s",
                msg.id,
                f"nw-{network_id}" if network_id else "everyone",
            )
        else:
            msg = m.AdminMessage.objects.create(
                message=text, network_id=network_id, title=P["message_title"]
            )
            m.JournalEntry.log(
                request.user,
                "Posted message msg-%i to %s",
                msg.id,
                f"nw-{network_id}" if network_id else "everyone",
            )
        target = request.GET.get("next", "index")
        return redirect(target)
    else:
        u = request.user
        if u.is_staff:
            options = [("Tout le monde", "everyone")] + [
                ("Réseau %s" % nw.name, f"nw-{nw.id}") for nw in m.Network.objects.all()
            ]
        else:
            options = [
                ("Réseau %s" % nw.name, f"nw-{nw.id}")
                for nw in m.Network.objects.filter(
                    Q(networkmembership__is_staff=True)
                    | Q(networkmembership__is_producer=True),
                    networkmembership__user_id=u.id,
                    networkmembership__valid_until=None,
                )
            ]

        if msg is None:
            selected_option = destination or options[0][0]
        elif msg.network_id is None:
            selected_option = "everyone"
        else:
            selected_option = f"nw-{msg.network_id}"

        return editor(
            request,
            title="Message administrateur",
            template="set_message.html",
            target=f"/edit-message/{id}" if msg is not None else "/set-message",
            options=options,
            message_title=msg.title if msg else m.AdminMessage.title.field.default,
            title_maxlength=m.AdminMessage.title.field.max_length,
            maxlength=m.AdminMessage.message.field.max_length,
            content=msg.message if msg is not None else "",
            selected_option=selected_option,
            is_rich=False,
        )


def unset_message(request, id):
    msg = m.AdminMessage.objects.get(id=int(id))
    must_be_prod_or_staff(request, msg.network)
    m.JournalEntry.log(
        request.user,
        "Deleted message %i to %s",
        msg.id,
        f"nw-{msg.network_id}" if msg.network_id else "everyone",
    )
    msg.delete()
    target = request.GET.get("next", "index")
    return redirect(target)
