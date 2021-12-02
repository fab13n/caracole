$(document).ready(function() {

  // Menu Burger Mobiles
  $('.hamburger').click(function() {
    $(this).toggleClass("is-active");
    $('#navigation ul').toggleClass("active");
    $('#navigation ul li a').click(function() {
      $('#navigation ul').toggleClass("active")
    });
  });


  // Interface connexion accueil

  $('#btn-connexion').click(function() {
    $('#form-connexion').addClass("active");
    $('#btns-default').addClass("clicked");
  });
  $('#btn-quit').click(function() {
    event.preventDefault();
    $('#form-connexion').removeClass("active");
    $('#btns-default').removeClass("clicked");
  });
  $('#btn-connexion').hover(function() {
    event.preventDefault();
    $('#btn-register').toggleClass("button-second");
  });
  $('#btn-register').hover(function() {
    event.preventDefault();
    $('#btn-connexion').toggleClass("button-second");
  });


  // Style navigation Accueil

  if ($('.header-accueil').length) {
    $('#navigation').addClass("accueil");
  } else {}

  // Boutons Quantité

  jQuery('<div class="quantity-nav"><div class="quantity-button quantity-up">+</div><div class="quantity-button quantity-down">-</div></div>').insertAfter('.quantity input');
  jQuery('.quantity').each(function() {
    var spinner = jQuery(this),
      input = spinner.find('input[type="number"]'),
      btnUp = spinner.find('.quantity-up'),
      btnDown = spinner.find('.quantity-down'),
      min = input.attr('min'),
      max = input.attr('max');

    btnUp.click(function() {
      var oldValue = parseFloat(input.val());
      if (oldValue >= max) {
        var newVal = oldValue;
      } else {
        var newVal = oldValue + 1;
      }
      spinner.find("input").val(newVal);
      spinner.find("input").trigger("change");
    });

    btnDown.click(function() {
      var oldValue = parseFloat(input.val());
      if (oldValue <= min) {
        var newVal = oldValue;
      } else {
        var newVal = oldValue - 1;
      }
      spinner.find("input").val(newVal);
      spinner.find("input").trigger("change");
    });

  });


  // Infobulle

  $('.infobulle').click(function() {
    $('.infobulle-content').toggleClass("active");
  });

  // End $(document).ready

});
