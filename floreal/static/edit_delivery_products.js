/* If the "deleted" checkbox is checked, strike the line and disable product edition. */
function reflect_deletion(r) {
  /* TODO: also reflect place renumbering? */
  /* TODO: hide description of deleted products. */
  const P = "#r" + r;
  const deleted = $(P+" .deleted input").is(':checked');
  const inputs  = $(P+" input[type=number],"+
                  P+" input[type=text],"+
                  P+" input[type=file],"+
                  P+" .described input[type=chechbox],"+
                  P+"-description textarea");
  const rows = $(P+","+P+"-description");
  if(deleted) {
    rows.addClass('deleted');
    inputs.attr('disabled', 'disabled');
  } else {
    rows.removeClass('deleted');
    inputs.removeAttr('disabled');
  }
}

/* Enable/disable description editor
 * The editor is only loaded when needed.
 * To remember wehether it is loaded, a "loaded" attribute is added
 * to the bound <textarea> upon loading.
 */
function reflect_description(r) {
    const P = "#r" + r;
    const described = $(P+' .described input').is(':checked');
    const row = $(P+"-description"); 
    const ta = $(P+"-description textarea");
    if( described) {
        const is_loaded = ta.attr("loaded");
        row.show();
        ta.removeAttr("disabled");
        if(! is_loaded) {
            ta.attr("loaded", "1");
            tinymce.init({
              plugins: "link",
              selector: P+'-description textarea',
              content_css: '/static/floreal.css',
              language: 'fr_FR'
            });
        }
    } else {
        row.hide();
        ta.attr("disabled", "disabled");
    }
}

/* The unit is reapeated all around the row. When the input field changes, reflect it. */
function reflect_unit_change(r) {
    const P = "#r" + r;
    let content = $(P+" .unit input").val();
    if(/^\d.*/.test(content)) { content = "×"+content; }
    $(P+" .unit-mirror").text(content);
    $(P+" .if-unit-mirror")[content ? 'show' : 'hide']();
}

/* When an image is uploaded, put its content in the previsualization label img. */
function reflect_image_change(r, event) {
    const P = "#r" + r;
    const img = $(P+" .image-upload img")[0];
    $(P+" input.image-modified").val("1");
    img.src = URL.createObjectURL(event.target.files[0]);
}

/* Only support command description when no producer is selected. */
function reflect_producer_selection() {
  const prod_id = $("#producer").val();
  if(prod_id === "0") {
    $(".when-some-producer").hide();
    $(".when-no-producer").show();
  } else {
    $(".when-no-producer").hide();
    $(".when-some-producer").show();
    const q = $("#edit-producer");
    const url = q.attr("href").split("?")[0] + "?selected=" + prod_id;
    q.attr("href", url);
  }
}


/* change the basic textarea into a timyMCE editor. */
function load_editor(r) {
  tinymce.init({
    plugins: "link",
    selector: "#r" + r + "-description textarea",
    content_css: "/static/floreal.css",
    language: 'fr_FR'
  });
}

/* Exchange the contents of row r0 and r0+1 */
function swap_rows(r0) {
    const r1 = r0+1;
    const P0 = "#r" + r0;
    const P1 = "#r" + r1;
    console.log("Swapping rows "+r0+" and "+r1);

    /* Swap input values, except file uploads and textarea */
    const INPUT_FIELDS = ['id', 'name', 'price', 'unit', 'quantity_per_package',
                        'quantity_limit', 'quantum', 'unit_weight'];
    
    INPUT_FIELDS.map(field => {
        const v0 = $(P0+" ."+field+" input").val();
        const v1 = $(P1+" ."+field+" input").val();
        $(P0+" ."+field+" input").val(v1);
        $(P1+" ."+field+" input").val(v0);
    });

    /* Swap checkbox states. */
    const CHECKBOXES =['described', 'deleted'];
    CHECKBOXES.map(field => {
        const b0 = $(P0+" ."+field+" input").is(":checked");
        const b1 = $(P1+" ."+field+" input").is(":checked");
        $(P0+" ."+field+" input").prop("checked", b1);
        $(P1+" ."+field+" input").prop("checked", b0);
    });

    /* Swap descriptions. Need to also check whether there's 0/1/2 descriptions,
     * to disable/reenable the editors accordingly. */
    let e0 = tinyMCE.get("r" + r0 + "-description-editor");
    let e1 = tinyMCE.get("r" + r1 + "-description-editor");
    /* Load contents to swap if they exist. */
    const c0 = e0 ? e0.getContent() : null;
    const c1 = e1 ? e1.getContent() : null;
    /* Make sure that target editors exist */
    if(e0 && ! e1) { load_editor(r1); e1 = tinyMCE.get("r" + r1 + "-description-editor"); }
    if(e1 && ! e0) { load_editor(r0); e0 = tinyMCE.get("r" + r0 + "-description-editor"); }
    /* Swap contents */
    if(c0 !== null) e1.setContent(c0); else if(e1) e1.setContent("");
    if(c1 !== null) e0.setContent(c1); else if(e0) e0.setContent("");

    /* Swap images. This is tricky because file inputs can't have their content altered
     * for security reasons. Therefore they will be moved and relabelled instead.
     *
     * 
     * Here's the HTML structure we're working on. A hidden "image-modified" field
     * remembers whether the image must be changed in DB (set to true when an upload
     * is initiated by the user).
     *
     *  <td class="image-upload"><div>
     *     <input name="rXXX-image-modified" class="image-modified" type="hidden"/>
     *     <label class="image-display">
     *       <img class="product-image"/>
     *       <input name="rXXX-image-upload" type="file"
     *              onchange="reflect_image_change('rXXX', event)"/></label></div></td>
     */
    const img0 = $(P0+" td.image-upload>div");
    const img1 = $(P1+" td.image-upload>div");
    // Exchange positions in the document
    img0.appendTo(P1+" td.image-upload");
    img1.appendTo(P0+" td.image-upload");
    // Exchange modification markers
    img0.find("input[type=hidden]").attr("name", "r"+r1+"-image-modified");
    img1.find("input[type=hidden]").attr("name", "r"+r0+"-image-modified");
    // Exchange images
    img0.find("input[type=file]")
        .attr("name", "r"+r1+"-image-upload")
        .attr("onchange", "reflect_image_change("+r1+", event)");
    img1.find("input[type=file]")
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

let N_ROWS = 0;

/* Add rows of blank products at the end of the table */
// TODO use an HTML5 template
function add_row() {
  N_ROWS += 1;
  const r = N_ROWS;
  $("#products-table tbody").append(`
    <tr id="r${r}">
        <td class="hidden id">
          <input name="r${r}-id" type="hidden" />
        </td>
        <td class="place">
          <button type="button" class="up">▲</button> ${r} <button class="down" type="button">▼</button>
          <input name="r${r}-place" type="hidden" value="${r}"/>
        </td>
        <td class="name"><input maxlength="64" name="r${r}-name" type="text" /></td>
        <td class="price"><input name="r${r}-price" step="0.01" min="0" type="number" /></td>
        <td>€/</td>
        <td class="unit"><input maxlength="64" name="r${r}-unit" type="text" /></td>
        <!-- Package management currently disabled -- 
        <td class="quantity_per_package"><input name="r${r}-quantity_per_package" type="number" /></td>
        <td class="unit-label">&nbsp;<span class="unit-mirror"></span><span class="if-unit-mirror">/ct</span></td>
        -->
        <td class="quantity_limit"><input name="r${r}-quantity_limit" min="0" type="number"/></td>
          <td class="unit-label">&nbsp;<span class="unit-mirror"></span></td>
        <td class="quantum"><input name="r${r}-quantum" min="0" type="number" step="0.001"/></td>
        <td class="unit-label">&nbsp;<span class="unit-mirror"></span></td>
        <!-- Weight management currently disabled --
        <td class="unit_weight"><input name="r${r}-unit_weight" min="0" step="0.001" type="number"/></td><td>kg</td>
        -->
        <td class="image-upload"><div>
          <input name="r${r}-image-modified" class="image-modified" type="hidden" value="0"/>
          <label class="image-display">
            <img class="product-image" src="/media/none.png"/>
            <input name="r${r}-image-upload" type="file" accept="image/*"
                   onchange="reflect_image_change(${r}, event)"/>
          </label>
        </div></td>

        <td class="deleted">
          <label for="r${r}-deleted" class="button button-primary"></label>
          <input 
            name="r${r}-deleted" 
            id="r${r}-deleted" 
            value="r${r}-deleted" 
            onchange="reflect_deletion(${r})" 
            type="checkbox" 
            style="display: none">
        </td>
        <td class="described">
          <label for="r${r}-described" class="button button-primary">Décrire</label>
          <input
            name="r${r}-described" 
            id="r${r}-described" 
            value="r${r}-described" 
            onchange="reflect_description(${r})" 
            type="checkbox"
            style="display: none">
        </td>
    </tr>
    <tr id="r${r}-description">
      <td></td>
      <td class="pd-description" colspan="15">
        <textarea name="r${r}-description" id="r${r}-description-editor" rows="5"></textarea>
      </td>
    </tr>`);

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
    const P = "#r" + r;
    $.each(record, function(k, v) {
        $(P+' .'+k+" input").val(v);
    });
    reflect_unit_change(r);
    if(record.description) {
        $(P+" .described input")[0].checked=true;
        $(P+"-description textarea").val(record.description);
    }
    reflect_description(r); // hide or enable editor
    if(record.image) {
        $(P+" .product-image").attr("src", record.image);
    }
    // TODO need a way to erase images
}

/* Add rows of blank products at the end of the table */
function add_blank_products() {
  const N_ADDED_ROWS = 3;
  for(let i=0; i<N_ADDED_ROWS; i++) {
    var r = add_row();
    reflect_description(r); // hide description textarea
    // No need to reflect deletion, they aren't deleted by default.
    // No need to reflect image, there isn't any.
  }
}

function submit_if_valid(then_leave) {

    /* Check that delivery has been named */
    if($("#dv-name").val().trim() == "") {
        alert("Avant de pouvoir sauvegarder, il faut donner un nom à la livraison, en haut du formulaire !");
        return;
    }
  
    /* Check that non-deleted products have a unique name and a valid price. */
    for(let i=1; $(`r${i}-id`).length; i++) {
      /* Don't check deleted products */
      if($("[name=r"+i+"-deleted]").is(":checked")) { continue; }
      const name_i = $("input[name=r"+i+"-name]").val().trim();
      if(name_i === "") { continue; }
      /* Check for duplicate non-deleted names. */
      for(let j=1; j<i; j++) {
        if($("[name=r"+j+"-deleted]").is(":checked")) { continue; }
        const name_j = $("[name=r"+j+"-name]").val().trim();
        if(name_i === name_j) {
          alert("Il y a plusieurs produits nommés "+name_i+", il faut en renommer au moins un.");
          return;
        }
      }
      const price = Number($("[name=r"+i+"-price]").val());
      if(! (price > 0)) {
        alert("Le prix de "+name_i+" n'est pas valide.");
        return;
      }
    }

    $("[name=then_leave]").val(then_leave);

    /* All sanity checks passed: submit the form */
    $("#form").submit()
}

/* Will contain dowloaded delivery, helps debug. */
var DELIVERY = null; 

async function load_delivery() {
  const response = await fetch("products.json");
  const dv = await response.json();
  DELIVERY = dv;

  $("#dv-id").val(dv.id);
  $("#dv-state").val(dv.state);
  // TODO I should restrict allowed states when the delivery is producer-edited

  if(dv['freeze-date']) {
    $("#freeze-date").val(dv['freeze-date']);
  }
  if(dv['distribution-date']) {
    $("#distribution-date").val(dv['distribution-date']);
  }

  dv.producers.forEach(p => {
    $("#producer").append(`<option value="${p.id}" ${p.selected?"selected":""}>${p.name}</option>`);
  });
  $("#producer").val(dv.producer);

  /* Upgrade widgets to bootstrap-select. */
  $("select").selectpicker;

  /* Only fill the name for non-newly-created deliveries.
   * For new ones the user has to set it explicitly. */
  const url_params = new URLSearchParams(window.location.search);
  if(! url_params.get('new')) { $("#dv-name").val(dv.name); }

  /* Generate and fill product rows */
  dv.products.forEach(pd => fill_row(add_row(), pd));

  /* Add a couple of empty rows & disable the "move up" button of the first one.
   * "move down" of the last one is handled whenever blank lines are inserted. */
  add_blank_products();
  $("#r1 td.place button.up").attr("disabled", "disabled");

  /* Set the description. In a timeout, in order to wait for tinyMCE to load. */
  
  setTimeout(
    () => {
      tinyMCE.get("dv-description").setContent(dv.description || "");
      reflect_producer_selection();
    },
    0
  );


}

$(document).ready(function() {

    /* Turn plain inputs into Bootstrap inputs. */
    $("select").addClass("form-control");

    /* Turn plain textareas into TinyMCE WYSIWYG editors. */
    tinymce.init({
      plugins: "link",
      selector: 'textarea',
      width: 640,
      content_css: "/static/floreal.css",
      language: 'fr_FR'
    });

    load_delivery();

})
