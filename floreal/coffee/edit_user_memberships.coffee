users = null # to be filled with XHR
subgroups = null # to be filled with XHR
sorted_users = null # to be filled with XHR

# Generate a line of header, radio boxes and checkboxes allowing to change a user's memberships.
# This is performed dynamically, because user settings are retrieved after page loading through an XHR.
make_user_line: (id) ->
    u = users[id];
    subgroup_cells = [];
    for sg in subgroups
        cell = """<td class="radio-subgroup"><input type="radio" id="u#{id}-sg#{sg.id}" name="u#{id}-sg" value="#{sg.id}" onclick="update_user_group(#{id}, #{sg.id});"/></td>"""
        subgroup_cells.push(cell)
    return """
        <tr id="u#{id}" class="user-starts-with-#{u.initial} user-of-subgroup-#{u.subgroup} user">
            <th class="email">{email}</th>
            <th class="name">{first_name} {last_name}</th>
            <td><input type="checkbox" name="u{id}-network-admin" onclick="mark_user_modified({id});"/></td>
            <td><input type="checkbox" name="u{id}-subgroup-admin" onclick="mark_user_modified({id});"/></td>";
            #{subgroup_cells.join("\n")}
            <td><input type="radio" id="u#{id}-sg-1" name="u#{id}-sg" value="-1" onclick="update_user_group(#{id}, -1);"/></td>
            <td><input type="radio" id="u#{id}-sg-2" name="u#{id}-sg" value="-2" onclick="update_user_group(#{id}, -2);"/></td>
        </tr>"""

# Generate the page parts which need the XHR-provided data: lists of subgroups and of users. */
fill_page: ->
    # Table headers
    rows = []
    for sg in subgroups
        rows.push("<th class='rotate'><div><span>#{sg.name}</span></div></th>")
    rows.push("<th class='rotate'><div><span>Membre d'autres réseaux</span></div></th>")
    rows.push("<th class='rotate'><div><span>Non-membre</span></div></th>")
    $("#header-row").append(rows.join('\n'));

    # subgroup show/hide links
    rows = []
    for sg in subgroups
        rows.push("<a href='#' onclick='hide_all_but_subgroup(#{sg.id})'>#{sg.name}</a>");
    rows.push("<a href='#' onclick='hide_all_but_subgroup(-1);'>Membre d'autres réseaux</a>");
    rows.push("<a href='#' onclick='hide_all_but_subgroup(-2);'>Non-membres</a>");
    $("#hide-subgroups").append(rows.join('\n'));

    # Table rows
    rows = []
    for uid in sorted_users
        rows.push(make_user_line(users[uid]))
    $('#users-table').append(rows.join('\n'))

# Toggle the radio buttons and checkboxes which must be initially set
init_form_inputs: ->
    for uid in sorted_users
      user = users[uid]
      $("#u#{uid}-sg#{user.subgroup}").prop("checked", true)
      if user.is_subgroup_admin then $("[name=u#{uid}-subgroup-admin]").prop("checked", true)
      if user.is_network_admin  then $("[name=u#{uid}-network-admin]").prop("checked", true)
      if user.subgroup < 0
        invalid_choice = if user.subgroup == -1 then -2 else -1
        $("#u#{uid}-sg"+invalid_choice).attr("disabled", "disabled")

hide_all_but_letter:      (x) -> $("tr.user").hide(); $("tr.user-starts-with-"+x).show()
hide_all_but_subgroup: (sgid) -> $("tr.user").hide(); $("tr.user-of-subgroup-"+sgid).show();
show_all:                     -> $("tr.user").show()

update_user_group: (uid, sgid) ->
    row = $("tr#u"+uid)
    classes = row.prop('class').split(/\s+/)
    for c in classes
      if c.startsWith('user-of-subgroup-') then row.removeClass(c)
    row.addClass('user-of-subgroup-'+sgid);
    # Disable admin checkboxes iff non-member
    $("#u#{uid} input[type=checkbox]").prop("disabled", sgid==-1)
    mark_user_modified(uid)

mark_user_modified: (uid) ->
    $("tr#u"+uid).addClass('modified')
    $("#submit").prop('disabled', false)

disable_unmodified_inputs: ->
    # Disabled fields won't be sent in the POST request, thus dramatically reducing it.
    $("tr:not(.modified) input").prop('disabled', true);
    modified=[];
    $("tr.modified").each (i, input) -> modified.push(input.id)
    $("#modified-users").attr("value", modified.join(','))


main: (json_url) -> $(document).ready -> $.getJSON json_url, (data) ->
    users = data.users
    sorted_users = data.sorted_users
    subgroups = data.subgroups
    fill_page()
    init_form_inputs()
