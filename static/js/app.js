/* Shared page helpers, with the same names the original PHP pages used
   (start_load, end_load, alert_toast, uni_modal, _conf), plus CSRF handling. */
(function ($) {
  "use strict";

  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[1]) : null;
  }
  window.csrfToken = function () {
    return getCookie("csrftoken");
  };

  // Every non-GET AJAX request carries the CSRF token.
  $.ajaxSetup({
    beforeSend: function (xhr, settings) {
      if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type)) {
        xhr.setRequestHeader("X-CSRFToken", window.csrfToken());
      }
    },
  });

  window.start_load = function () {
    if (!$("#preloader2").length) $("body").prepend('<div id="preloader2"></div>');
  };
  window.end_load = function () {
    $("#preloader2").fadeOut("fast", function () {
      $(this).remove();
    });
  };

  window.alert_toast = function (msg, bg) {
    const $t = $("#alert_toast");
    $t.removeClass("bg-success bg-danger bg-info bg-warning").addClass("bg-" + (bg || "success"));
    $t.find(".toast-body").text(msg);
    $t.toast({ delay: 3000 }).toast("show");
  };

  // Turns an error response into one readable message.
  window.error_message = function (xhr) {
    const r = xhr && xhr.responseJSON;
    if (r && r.error) return r.error;
    if (r && r.errors) {
      const first = Object.keys(r.errors)[0];
      return (first === "__all__" ? "" : first.replace(/_/g, " ") + ": ") + r.errors[first];
    }
    if (xhr && xhr.status === 403) return "You do not have permission to do this.";
    return "Something went wrong. Please try again.";
  };

  // Shows field errors next to their inputs inside a form.
  window.show_form_errors = function ($form, xhr) {
    $form.find(".is-invalid").removeClass("is-invalid");
    $form.find(".invalid-feedback.js").remove();
    const r = xhr && xhr.responseJSON;
    if (!r || !r.errors) {
      alert_toast(error_message(xhr), "danger");
      return;
    }
    let shown = false;
    $.each(r.errors, function (field, msg) {
      const $input = $form.find('[name="' + field + '"]');
      if ($input.length) {
        $input.addClass("is-invalid");
        $('<div class="invalid-feedback js"></div>').text(msg).insertAfter($input.last());
        shown = true;
      }
    });
    if (!shown || r.errors.__all__) alert_toast(error_message(xhr), "danger");
  };

  window.uni_modal = function (title, url, size) {
    start_load();
    $.get(url)
      .done(function (resp) {
        $("#uni_modal .modal-title").text(title);
        $("#uni_modal .modal-body").html(resp);
        $("#uni_modal .modal-dialog").attr("class", "modal-dialog modal-dialog-centered " + (size || "modal-md"));
        $("#uni_modal").modal({ show: true, backdrop: "static", keyboard: false, focus: true });
      })
      .fail(function (xhr) {
        alert_toast(error_message(xhr), "danger");
      })
      .always(end_load);
  };

  window._conf = function (msg, onConfirm) {
    $("#confirm_modal .modal-body").text(msg);
    $("#confirm_modal #confirm")
      .off("click")
      .on("click", function () {
        $("#confirm_modal").modal("hide");
        onConfirm();
      });
    $("#confirm_modal").modal("show");
  };

  // POST a form or object, reload on success, show errors on failure.
  window.post_and_reload = function (url, data, successMsg, $form) {
    start_load();
    $.post(url, data)
      .done(function () {
        alert_toast(successMsg || "Data successfully saved.", "success");
        setTimeout(function () {
          location.reload();
        }, 800);
      })
      .fail(function (xhr) {
        end_load();
        if ($form) show_form_errors($form, xhr);
        else alert_toast(error_message(xhr), "danger");
      });
  };

  window.money = function (v) {
    return Number(v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  $(function () {
    $("#manage_my_account").on("click", function () {
      uni_modal("Manage Account", $(this).data("url"));
    });
    $(".sidebar-toggle").on("click", function () {
      $("body").toggleClass("sidebar-open");
    });
    $("#uni_modal").on("click", "#submit", function () {
      $("#uni_modal form").trigger("submit");
    });
  });
})(jQuery);
