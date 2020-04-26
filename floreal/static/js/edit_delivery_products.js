/* If the "deleted" checkbox is checked, strike the line and disable product edition. */
function reflect_deletion(r) {
  /* TODO: also reflect place renumbering? */
  /* TODO: hide description of deleted products. */
  var P = "#r" + r;
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

/* Enable/disable description editor
 * The summernote editor is only loaded when needed.
 * To remember wehether it is loaded, a "loaded" attribute is added
 * to the bound <textarea> upon loading.
 */
function reflect_description(r) {
    var P = "#r" + r;
    var described = $(P+' .described input').is(':checked');
    var row = $(P+"-description"); 
    var ta = $(P+"-description textarea");
    if( described) {
        var is_loaded = ta.attr("loaded");
        row.show();
        ta.removeAttr("disabled");
        if(! is_loaded) {
            ta.attr("loaded", "1");
            ta.summernote();
        }
    } else {
        row.hide();
        ta.attr("disabled", "disabled");
    }
}

/* The unit is reapeated all around the row. When the input field changes, reflect it. */
function reflect_unit_change(r) {
    var P = "#r" + r;
    var content = $(P+" .unit input").val();
    if(RegExp("^\\d.*").test(content)) { content = "×"+content; }
    $(P+" .unit-mirror").text(content);
    $(P+" .if-unit-mirror")[content ? 'show' : 'hide']();
}

/* When an image is uploaded, put its content in the previsualization label img */
function reflect_image_change(r, event) {
    var P = "#r" + r;
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
    ld0 = ta0.attr("loaded");
    ld1 = ta1.attr("loaded");
    if(ld1) { ta0.attr("loaded", "1"); } else { ta0.removeAttr("loaded"); }
    if(ld0) { ta1.attr("loaded", "1"); } else { ta1.removeAttr("loaded"); }
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
        .attr("onchange", "reflect_image_change("+r1+", event)");
    e1.find("input[type=file]")
        .attr("name", "r"+r0+"-image-upload")
        .attr("onchange", "reflect_image_change("+r0+", event)");

    reflect_deletion(r0);
    reflect_description(r0);
    reflect_unit_change(r0);
    reflect_deletion(r1);
    reflect_description(r1);
    reflect_unit_change(r1);
    /* No reflect_image_change: it only happens when a file is uploaded.
     * Here the image is in the input's label, they're all swapped together. */
}

/* Add rows of blank products at the end of the table */
function add_row() {
  var r = Number($("#n_rows").val()) + 1;
  $("#n_rows").val(r);
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
                   onchange="reflect_image_change(%, event)"/>\n\
          </label>\n\
        </div></td>\n\
        <td class="deleted">\n\
          <input name="r%-deleted" value="r%-deleted" onchange="reflect_deletion(%)" type="checkbox">\n\
        </td>\n\
        <td class="described">\n\
          <input name="r%-described" value="r%-described" onchange="reflect_description(%)" type="checkbox">\n\
        </td>\n\
    </tr>\n\
    <tr id="r%-description">\n\
      <td></td>\n\
      <td class="description" colspan="15">\n\
        <textarea name="r%-description" rows="5"></textarea>\n\
      </td>\n\
    </tr>'.replace(/%/g, r));

  // disable last "down" button, re-enable before-last "down" button, which was previously last
  $("#r"+(r-1)+" td.place button.down").removeAttr("disabled");
  $("#r"+r+" td.place button.down").attr("disabled", "disabled");

  // wire place-swapping buttons
  $("#r"+r+" td.place button.up").click(function() { swap_rows(r-1); })
  $("#r"+r+" td.place button.down").click(function() { swap_rows(r); })

  // wire unit change reflections upon keystrokes
  $("#r"+r+" .unit input").keyup(function() { reflect_unit_change(r); });
  reflect_unit_change(r);

  return r;
}

/* Fill a product row with the content of JSON record */
function fill_row(r, record) {
    var P = "#r" + r;
    $.each(record, function(k, v) {
        $(P+' .'+k+" input").val(v);
    });
    reflect_unit_change(r);
    if(record.description) {
        $(P+" .described input")[0].checked=true;
        $(P+"-description textarea").val(record.description);
    }
    reflect_description(r); // hide or enable summernote
    if(record.image) {
        $(P+" .product-image").attr("src", record.image);
    }
    // TODO need a way to erase images
}

/* Add rows of blank products at the end of the table */
function add_blank_products() {
  var N_ADDED_ROWS = 3;
  for(var i=0; i<N_ADDED_ROWS; i++) {
    var r = add_row();
    reflect_description(r); // hide description textarea
    // No need to reflect deletion, they aren't deleted by default.
    // No need to reflect image, there isn't any.
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
            fill_row(add_row(), dv.products[i]);
        }

        /* Add a couple of empty rows & disable the "move up" button of the first one.
         * "move down" of the last one is handled whenever blank lines are inserted. */
        add_blank_products();
        $("#r1 td.place button.up").attr("disabled", "disabled");
      });
})
