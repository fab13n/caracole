// TODO Store in a rogue attribute of the checkbox?
var LOADED_DESCRIPTIONS = {};  // row prefix -> true

/* If the "deleted" checkbox is checked, strike the line and disable product edition. */
function reflect_deletion(r_prefix) {
  /* TODO: also reflect place renumbering. */
  /* TODO: hide description of deleted products. */
  var P = "#" + r_prefix;
  var deleted = $(P+" .deleted input").is(':checked');
  var inputs  = $(P+" input[type=number],"+
                  P+" input[type=text],"+
                  P+" input[type=file],"+
                  P+" .described input[type=chechbox],"+
                  P+"-description textarea");
  var rows = $(P+","+P+"-description");
  if(deleted) {
    rows.addClass('deleted');
    inputs.attr('disabled', 'disabled');
  } else {
    rows.removeClass('deleted');
    inputs.removeAttr('disabled');
  }
}

/* Enable/disable description editor */
function reflect_description(r_prefix) {
    var P = "#" + r_prefix;
    var described = $(P+' .described input').is(':checked');
    if( described) {
        $(P+"-description").show();
        $(P+"-description textarea").removeAttr("disabled");
        if(! LOADED_DESCRIPTIONS[r_prefix]) {
            LOADED_DESCRIPTIONS[r_prefix] = true;
            $(P+"-description textarea").summernote();
        }
    } else {
        $(P+"-description").hide();
        $(P+"-description textarea").attr("disabled", "disabled");
    }
}

function reflect_unit_change(r_prefix) {
    var P = "#" + r_prefix;
    var content = $(P+" .unit input").val();
    if(RegExp("^\\d.*").test(content)) { content = "×"+content; }
    $(P+" .unit-mirror").text(content);
    $(P+" .if-unit-mirror")[content ? 'show' : 'hide']();
}

function reflect_image_change(r_prefix, event) {
    var P = "#" + r_prefix;
    var image = $(P+" .image-upload img")[0];
    $(P+" input.image-modified").val("1");
    image.src = URL.createObjectURL(event.target.files[0]);
}

/* Exchange the contents of row r0 and r0+1 */
function swap_rows(r0) {
    var r1 = r0+1;
    var P0 = "#r" + r0;
    var P1 = "#r" + r1;
    console.log("Swapping rows "+r0+" and "+r1);

    // TODO Use $.each rather than for loops?

    /* Swap input values, except file uploads and textarea */
    var input_fields = ['id', 'name', 'price', 'unit', 'quantity_per_package',
                        'quantity_limit', 'quantum', 'unit_weight'];
    for(var i=0; i<input_fields.length; i++) {
        var field = input_fields[i];
        var v0 = $(P0+" ."+field+" input").val();
        var v1 = $(P1+" ."+field+" input").val();
        $(P0+" ."+field+" input").val(v1);
        $(P1+" ."+field+" input").val(v0);
    }

    /* Swap checkbox states. */
    var checkboxes =['described', 'deleted'];
    for(i=0; i<checkboxes.length; i++) {
        var field = checkboxes[i];
        var b0 = $(P0+" ."+field+" input").is(":checked");
        var b1 = $(P1+" ."+field+" input").is(":checked");
        $(P0+" ."+field+" input").prop("checked", b1);
        $(P1+" ."+field+" input").prop("checked", b0);
    }

    /* Swap descriptions. Need to also check whether there's 0/1/2 descriptions,
     * to disable/reenable the summernote editors accordingly. */
    var ta0 = $(P0+"-description textarea");
    var ta1 = $(P1+"-description textarea");
    // TODO may be simpler if LOADED_DESCRIPTION flag was in the record?
    ld0 = LOADED_DESCRIPTIONS["r"+r0];
    ld1 = LOADED_DESCRIPTIONS["r"+r1];
    LOADED_DESCRIPTIONS["r"+r0] = ld1;
    LOADED_DESCRIPTIONS["r"+r1] = ld0;
    if(ld0) { ta0.summernote('destroy'); }
    if(ld1) { ta1.summernote('destroy'); }
    var v0 = ta0.val();
    var v1 = ta1.val();
    ta0.val(v1);
    ta1.val(v0);
    if(ld1) { ta0.summernote(); }
    if(ld0) { ta1.summernote(); }

    /* Swap images. This is tricky because file inputs can't have their content altered
     * for security reasons. Therefore they will be moved and relabelled instead.
     *
     *  <td class="image-upload"><div>
     *     <input name="rXXX-image-modified" class="image-modified" type="hidden"/>
     *     <label class="image-display">
     *       <img class="product-image"/>
     *       <input name="rXXX-image-upload" type="file"
     *              onchange="reflect_image_change('rXXX', event)"/></label></div></td>
     */
    var e0 = $(P0+" td.image-upload>div");
    var e1 = $(P1+" td.image-upload>div");
    // Exchange positions
    e0.appendTo(P1+" td.image-upload");
    e1.appendTo(P0+" td.image-upload");
    // Exchange input names
    e0.find("input[type=hidden]").attr("name", "r"+r1+"-image-modified");
    e1.find("input[type=hidden]").attr("name", "r"+r0+"-image-modified");
    e0.find("input[type=file]")
        .attr("name", "r"+r1+"-image-upload")
        .attr("onchange", "reflect_image_change('r"+r1+"', event)");
    e1.find("input[type=file]")
        .attr("name", "r"+r0+"-image-upload")
        .attr("onchange", "reflect_image_change('r"+r0+"', event)");

    reflect_deletion("r"+r0);
    reflect_description("r"+r0);
    reflect_unit_change("r"+r0);
    reflect_deletion("r"+r1);
    reflect_description("r"+r1);
    reflect_unit_change("r"+r1);
    /* No reflect_image_change: it only happens when a faile is uploaded. */
}

/* Add rows of blank products at the end of the table */
function add_row() {
  var r_num = Number($("#n_rows").val()) + 1;
  $("#n_rows").val(r_num);
  $("#products-table tbody").append('\n\
    <tr id="r%">\n\
        <td class="hidden id">\n\
          <input name="r%-id" type="hidden" />\n\
        </td>\n\
        <td class="place">\n\
          <button type="button" class="up">▲</button> % <button class="down" type="button">▼</button>\n\
          <input name="r%-place" type="hidden" value="%"/>\n\
        </td>\n\
        <td class="name"><input maxlength="64" name="r%-name" type="text" /></td>\n\
        <td class="price"><input name="r%-price" step="0.01" min="0" type="number" /></td>\n\
        <td>€/</td>\n\
        <td class="unit"><input maxlength="64" name="r%-unit" type="text" /></td>\n\
        <td class="quantity_per_package"><input name="r%-quantity_per_package" type="number" /></td>\n\
        <td class="unit-label">&nbsp;<span class="unit-mirror"></span><span class="if-unit-mirror">/ct</span></td>\n\
        <td class="quantity_limit"><input name="r%-quantity_limit" min="0" type="number"/></td>\n\
          <td class="unit-label">&nbsp;<span class="unit-mirror"></span></td>\n\
        <td class="quantum"><input name="r%-quantum" min="0" type="number" step="0.001"/></td>\n\
        <td class="unit-label">&nbsp;<span class="unit-mirror"></span></td>\n\
        <td class="unit_weight"><input name="r%-unit_weight" min="0" step="0.001" type="number"/></td><td>kg</td>\n\
        <td class="image-upload"><div>\n\
          <input name="r%-image-modified" class="image-modified" type="hidden" value="0"/>\n\
          <label class="image-display">\n\
            <img class="product-image" src="/media/none.png"/>\n\
            <input name="r%-image-upload" type="file" accept="image/*"\n\
                   onchange="reflect_image_change(\'r%\', event)"/>\n\
          </label>\n\
        </div></td>\n\
        <td class="deleted">\n\
          <input name="r%-deleted" value="r%-deleted" onchange="reflect_deletion(\'r%\')" type="checkbox">\n\
        </td>\n\
        <td class="described">\n\
          <input name="r%-described" value="r%-described" onchange="reflect_description(\'r%\')" type="checkbox">\n\
        </td>\n\
    </tr>\n\
    <tr id="r%-description">\n\
      <td></td>\n\
      <td class="description" colspan="15">\n\
        <textarea name="r%-description" rows="5"></textarea>\n\
      </td>\n\
    </tr>'.replace(/%/g, r_num));

  // disable last "down" button, re-enable before-last "down" button, which was previously last
  $("#r"+r_num+" td.place button.down").attr("disabled", "disabled");
  $("#r"+(r_num-1)+" td.place button.down").removeAttr("disabled");

  // wire buttons
  $("#r"+r_num+" td.place button.up").click(function() { swap_rows(r_num-1); })
  $("#r"+r_num+" td.place button.down").click(function() { swap_rows(r_num); })

  // wire unit change reflections upon keystrokes
  $("#r"+r_num+" .unit input").keyup(function() { reflect_unit_change("r"+r_num); });
  reflect_unit_change("r"+r_num);

  return "r"+r_num;
}

/* Fill a product row with the content of JSON record */
function fill_row(r_prefix, record) {
    var P = "#" + r_prefix;
    $.each(record, function(k, v) {
        $(P+' .'+k+" input").attr('value', v);
    });
    reflect_unit_change(r_prefix);
    if(record.description) {
        $(P+" .described input")[0].checked=true;
        $(P+"-description textarea").val(record.description);
    }
    reflect_description(r_prefix); // hide or enable summernote
    if(record.image) {
        $(P+" .product-image").attr("src", record.image);
    }
    // TODO need a way to erase images
}

/* Add rows of blank products at the end of the table */
function add_blank_products() {
  var N_ADDED_ROWS = 3;
  for(var i=0; i<N_ADDED_ROWS; i++) {
    var r_prefix = add_row();
    reflect_description(r_prefix); // hide description textarea
    // No need to reflect deletion, they aren't deleted by default
  }
}

function submit_if_valid() {
    if($("#dv-name").val().trim() == "") {
        alert("Avant de pouvoir sauvegarder, il faut donner un nom à la livraison, en haut du formulaire !");
        return;
    }
    // TODO more validity tests!
    /* All sanity checks passed: submit the form */
    $("#form").submit()
}

$(document).ready(function() {

    $.getJSON("products.json", function(dv) {
        $("#dv-id").val(dv.id);
        $("#dv-state").val(dv.state);
        $("#dv-description").val(dv.description).summernote();
        /* Only fill the name for non-newly-created deliveries.
         * For new ones the user has to set it explicitly. */
        var url_params = new URLSearchParams(window.location.search);
        if(! url_params.get('new')) { $("#dv-name").val(dv.name); }

        /* Generate and fill product rows */
        for(var i = 0; i < dv.products.length; i++) {
            var record = dv.products[i];
            var r_prefix = add_row();
            fill_row(r_prefix, record);
        }
        /* Add a couple of empty rows & disable the "move up" button of the first one.
         * "move down" of the last one is handled whenever blank lines are inserted. */
        add_blank_products();
        $("#r1 td.place button.up").attr("disabled", "disabled");

      });


})
