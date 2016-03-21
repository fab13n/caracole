products = null  # id -> {quantum, weight, unit}; fed through XHR

# update per-line totals as well as delivery total
update_weight_prices_and_errors: ->
    total_price = 0
    total_weight = 0
    for pd_id, pd of products
        ordered    = parseFloat($("#pd#{pd_id}-ordered_quantity").attr("value"))
        unit_price = parseFloat($("#pd#{pd_id}-unit_price").text().replace(',','.'))
        price      = ordered * unit_price
        $("#pd#{pd_id}-ordered_price").text(price.toFixed(2))
        total_price += price
        total_weight += ordered * pd.weight
        check_quantum(pd_id)
    $("#total_price").text(total_price.toFixed(2));
    $("#total_weight").text(total_weight.toFixed(0));
    # Prevent submission if there's at least one quantum error
    $("input[type=submit]").prop('disabled', $(".quantum-error").length > 0);


# Set an ordered quantity to zero
reset_order: (pd_id) ->
    $("#pd#{pd_id}-ordered_quantity").attr("value", "0")
    update_weight_prices_and_errors()

# TODO isn't is enforced by input[step]?
# If there is an ordering quantum, and the order isn't a multiple thereof, display a warning and
# disable submission. Otherwise, remove any existing quantum error message.
check_quantum: (pd_id) ->
    pd = products[pd_id]
    msgid = "pd#{pd_id}-quantum-error"
    if pd.quantum
        ordered = Number($("#pd{pd_id}-ordered_quantity").val());
        reminder = Math.abs(ordered % pd.quantum)
        EPSILON = 1e-9  # for floating point rounding errors
        if quantum-EPSILON <= reminder <= EPSILON
            $("#"+msgid).remove()
            return true
        else if $("#"+msgid).length == 0  # A message is needed and there is none
            $("#row-"+id).after(
                """<tr id='#{msgid}' class='quantum-error'><td colspan=7>
                    Ce produit doit être commandé par multiples de #{pd.quantum} #{pd.unit}
                </td></tr>""")
            return false  # error
        else # message needed, but already there
          return false  # error
    else
        return true  # no quantum => no error

main: (json_url) -> $(document).ready -> $.getJSON json_url, (data) ->
    products = data.products
    for pd_id, qty of data.purchases
        $("#pd{pd_id}-ordered_quantity").attr("value", qty)
    $(":input").bind('keyup mouseup', update_weight_prices_and_errors)
    update_weight_prices_and_errors()
