"""

    var N_BLANKS = 0;

    var DELIVERY = {{delivery.id}};

    var PRODUCTS = [{% for pd in products %}
      { 'id': "{{pd.id|escapejs}}",
        'name': "{{pd.name|escapejs}}",
        'price': "{{pd.price|escapejs}}",
        'unit': "{{pd.unit|escapejs}}",
        'quantity_limit': "{{pd.quantity_limit|escapejs}}",
        'quantity_per_package': "{{pd.quantity_per_package|escapejs}}",
        'quantum': "{{pd.quantum|default_if_none:""|escapejs}}",
        'unit_weight': "{{pd.unit_weight|escapejs}}",
        'deleted': false,
        'delivery': {{pd.delivery.id}} },
    {% endfor %}];
"""

# If the "deleted" checkbox is checked, strike the line and disable product edition.
reflect_deletion: (prefix) ->
    deleted = $("##{prefix}-deleted").is(':checked');
    inputs = $("##{prefix}-row input[type=number], ##{prefix}-row input[type=text]")
    if deleted
        $("##{prefix}-row").addClass('deleted')
        inputs.attr('disabled', 'disabled')
    else
        $("#{prefix}-row").removeClass('deleted')
        inputs.removeAttr('disabled')

# Keep unit names in sync between the input field and the text spans where it occurs.
# TODO rename `sync_unit_name`
attach_closure: (prefix) ->
    f: ->
        content = $("##{prefix}-unit").attr('value');
        $(".#{prefix}-unit-mirror").text(content)
        if content then $(".#{prefix}-if-unit-mirror").show()
        else $(".#{prefix}-if-unit-mirror").hide()
    $("##{prefix}-unit").keyup(f);
    f()

# Add rows of blank products at the end of the table
add_row: (prefix) ->
    $("#products-table").append """
        <tr id="%-row">
            <td class="name"><input id="%-id" name="%-id" type="hidden" /><input id="%-name" maxlength="64" name="%-name" type="text" /></td>
            <td class="price"><input id="%-price" name="%-price" step="0.1" min="0" type="number" /></td>
            <td>€/</td>\n\
            <td class="unit"><input id="%-unit" maxlength="64" name="%-unit" type="text" /></td>
            <td class="qpp"><input id="%-quantity_per_package" name="%-quantity_per_package" type="number" /></td>
            <td class="unit-label">&nbsp;<span class="%-unit-mirror"></span><span class="%-if-unit-mirror">/ct</span></td>
            <td class="quota"><input id="%-quantity_limit" name="%-quantity_limit" min="0" type="number"/></td>
            <td class="unit-label">&nbsp;<span class="%-unit-mirror"></span></td>
            <td class="quantum"><input id="%-quantum" name="%-quantum" min="0" type="number" step="0.001"/></td>
            <td class="unit-label">&nbsp;<span class="%-unit-mirror"></span></td>
            <td class="weight"><input id="%-unit_weight" name="%-unit_weight" min="0" step="0.1" type="number"/></td><td>kg</td>
            <td class="deleted">
              <input id="%-deleted" name="%-deleted" onchange="reflect_deletion(\'%\')" type="checkbox" value="off">
            </td>
        </tr>
    """.replace(/%/g, prefix)

# Fill a product row with data from a JSON record
fill_row: (prefix, record) ->
    $.each record, (k, v) -> $("##{prefix}-k").attr('value', v)
    if record['delivery'] != DELIVERY
        $("##{prefix}-deleted")[0].checked = true
        reflect_deletion(prefix)


# Add rows of blank products at the end of the table
add_blank_products: ->
    N_ADDED_ROWS = 3
    for i in [0...N_ADDED_ROWS]
        prefix = "blank"+i
        add_row(prefix)
        attach_closure(prefix)
    N_BLANKS += N_ADDED_ROWS;
    $("#n_blanks").attr("value", N_BLANKS)


main: (json_url) -> $(document).ready -> $.getJSON json_url, (data) ->
    product_id_list = []
    for pd in data.products
        prefix = "pd"+pd.id
        add_row(prefix)
        fill_row(prefix, pd)
        attach_closure(prefix)
        product_id_list.push(record.id)
    $("#product_ids").attr("value", product_id_list.join(","))
