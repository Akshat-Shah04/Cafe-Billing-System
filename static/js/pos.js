/* Take Orders screen. The order is kept as data (not read back out of the DOM), the totals
   shown here are for the cashier only: the server recalculates everything from its own prices. */
(function ($) {
  "use strict";

  const products = JSON.parse(document.getElementById("products-data").textContent);
  const byId = new Map(products.map((p) => [p.id, p]));
  // Lines already on an unpaid order keep their original price, even if the menu changed since.
  const lines = JSON.parse(document.getElementById("lines-data").textContent).map((l) => ({
    product_id: l.product_id,
    name: l.name,
    price: Number(l.price),
    qty: l.qty,
  }));
  const MAX_QTY = 999;
  let busy = false;

  // Money in paise (integers) so 0.1 + 0.2 style float errors never show on screen.
  const toPaise = (v) => Math.round(Number(v) * 100);
  const totalPaise = () => lines.reduce((sum, l) => sum + toPaise(l.price) * l.qty, 0);

  function render() {
    const $tbody = $("#o-list tbody").empty();
    lines.forEach((l, i) => {
      const $tr = $('<tr class="o-item"></tr>').attr("data-index", i);
      $tr.append(
        $("<td></td>").append(
          $('<div class="qty-box"></div>')
            .append('<button type="button" class="btn btn-sm btn-secondary btn-minus" aria-label="Less"><i class="fa fa-minus"></i></button>')
            .append($('<input type="number" class="qty" min="1">').attr("max", MAX_QTY).val(l.qty))
            .append('<button type="button" class="btn btn-sm btn-secondary btn-plus" aria-label="More"><i class="fa fa-plus"></i></button>')
        )
      );
      $tr.append($("<td></td>").text(l.name + " ").append($('<small class="text-muted"></small>').text("(" + money(l.price) + ")")));
      $tr.append($('<td class="text-right"></td>').text(money((toPaise(l.price) * l.qty) / 100)));
      $tr.append('<td><button type="button" class="btn btn-sm btn-danger btn-rem" aria-label="Remove"><i class="fa fa-times"></i></button></td>');
      $tbody.append($tr);
    });
    $(".empty-order").toggle(lines.length === 0);
    $("#total_amount").text(money(totalPaise() / 100));
  }

  function addProduct(id) {
    const p = byId.get(id);
    if (!p) return;
    const existing = lines.find((l) => l.product_id === id);
    if (existing) {
      existing.qty = Math.min(existing.qty + 1, MAX_QTY);
    } else {
      lines.push({ product_id: id, name: p.name, price: Number(p.price), qty: 1 });
    }
    render();
  }

  function setQty(index, qty) {
    qty = parseInt(qty, 10);
    if (!Number.isFinite(qty) || qty < 1) qty = 1;
    lines[index].qty = Math.min(qty, MAX_QTY);
    render();
  }

  // Product and category clicks
  $("#prod-grid").on("click", ".prod-item", function () {
    addProduct(Number($(this).data("id")));
  });
  $("#cat-list").on("click", ".cat-item", function () {
    $(".cat-item").removeClass("active");
    $(this).addClass("active");
    filterProducts();
  });
  $("#prod-search").on("input", filterProducts);
  function filterProducts() {
    const cat = String($(".cat-item.active").data("id"));
    const q = $("#prod-search").val().trim().toLowerCase();
    $(".prod-col").each(function () {
      const okCat = cat === "all" || String($(this).data("category-id")) === cat;
      const okText = !q || String($(this).data("name")).includes(q);
      $(this).toggle(okCat && okText);
    });
  }

  // Quantity controls
  $("#o-list")
    .on("click", ".btn-minus", function () {
      const i = $(this).closest("tr").data("index");
      setQty(i, lines[i].qty - 1);
    })
    .on("click", ".btn-plus", function () {
      const i = $(this).closest("tr").data("index");
      setQty(i, lines[i].qty + 1);
    })
    .on("change", "input.qty", function () {
      setQty($(this).closest("tr").data("index"), $(this).val());
    })
    .on("click", ".btn-rem", function () {
      lines.splice($(this).closest("tr").data("index"), 1);
      render();
    });

  function ready() {
    if (!lines.length) {
      alert_toast("Please add at least 1 product first.", "danger");
      return false;
    }
    const n = parseInt($("#order_number").val(), 10);
    if (!(n >= 1 && n <= 9999)) {
      alert_toast("Please enter an Order No. between 1 and 9999.", "danger");
      $("#order_number").focus();
      return false;
    }
    return true;
  }

  // receiptWin is opened during the click (browsers block pop-ups opened later, after AJAX).
  function submit(tendered, receiptWin) {
    if (busy) return;
    busy = true;
    start_load();
    $.ajax({
      url: POS.saveUrl,
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({
        id: POS.orderId,
        order_number: $("#order_number").val(),
        items: lines.map((l) => ({ product_id: l.product_id, qty: l.qty })),
        tendered: tendered,
      }),
    })
      .done(function (resp) {
        alert_toast("Data successfully saved.", "success");
        $("#pay_modal").modal("hide");
        if (resp.status === "paid" && receiptWin) {
          receiptWin.location.href = resp.receipt_url + "?print=1";
        }
        // Start a fresh order (or go back to the list after billing out an existing one).
        setTimeout(function () {
          if (POS.orderId) location.href = POS.listUrl;
          else location.reload();
        }, 700);
      })
      .fail(function (xhr) {
        busy = false;
        end_load();
        if (receiptWin) receiptWin.close();
        alert_toast(error_message(xhr), "danger");
      });
  }

  // "Pay later": save as an unpaid order
  $("#save_order").on("click", function () {
    if (ready()) submit(null);
  });

  // "Pay": open the calculator
  $("#pay").on("click", function () {
    if (!ready()) return;
    const total = totalPaise() / 100;
    $("#apayable").val(money(total));
    $("#tendered").val("");
    $("#change").val("0.00").removeClass("is-invalid");
    // Quick cash buttons: exact amount and the next round notes
    const $q = $("#quick-cash").empty();
    const options = [total, ...[50, 100, 200, 500, 2000].map((n) => Math.ceil(total / n) * n)];
    [...new Set(options.map((v) => v.toFixed(2)))].slice(0, 5).forEach((v) => {
      $('<button type="button" class="btn btn-outline-secondary btn-sm mr-1 mb-1"></button>')
        .text(Number(v) === total ? "Exact" : money(v))
        .on("click", () => $("#tendered").val(v).trigger("input").focus())
        .appendTo($q);
    });
    $("#pay_modal").modal("show");
  });
  $("#pay_modal").on("shown.bs.modal", () => $("#tendered").trigger("focus"));

  $("#tendered").on("input", function () {
    const clean = $(this).val().replace(/[^0-9.]/g, "");
    if (clean !== $(this).val()) $(this).val(clean);
    const change = toPaise(clean || 0) - totalPaise();
    $("#change").val(money(change / 100)).toggleClass("is-invalid", change < 0);
  });

  $("#pay-form").on("submit", function (e) {
    e.preventDefault();
    const tendered = $("#tendered").val();
    if (tendered === "" || toPaise(tendered) < totalPaise()) {
      alert_toast("Amount tendered is less than the amount payable.", "danger");
      $("#tendered").focus();
      return;
    }
    const win = window.open("", "_blank", "width=420,height=640");
    submit(tendered, win);
  });

  render();
})(jQuery);
