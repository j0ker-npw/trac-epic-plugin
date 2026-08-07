/*
 * TracEpicPlugin client side logic.
 *
 * Requires jQuery 3.7.1 (bundled with Trac 1.6).  The plugin exposes its
 * configuration through `window.tracepic` via add_script_data:
 *
 *   tracepic = {
 *     ticket_id : int,
 *     is_epic   : bool,
 *     can_modify: bool,
 *     html      : string,   // server-rendered section fragment
 *     form_token: string,   // CSRF token
 *     base_url  : string    // href to /epic
 *   }
 */
(function ($) {
  "use strict";

  function cfg() {
    return window.tracepic || null;
  }

  // Insert the server-rendered section into the ticket page.
  function injectSection(conf) {
    if (!conf || !conf.html) {
      return null;
    }
    // Avoid double insertion (e.g. on preview refresh).
    $("#epic-links").remove();

    var $section = $(conf.html);
    // Place the section right after the ticket description / properties.
    var $anchor = $("#ticket").length ? $("#ticket") : $("#content");
    $anchor.after($section);
    return $section;
  }

  // Escape a string for safe insertion as HTML text.
  function esc(s) {
    return $("<div/>").text(s == null ? "" : String(s)).html();
  }

  // Build the tickets base URL (e.g. /trac/ticket/123).
  function ticketUrl(conf, id) {
    // base_url ends with '/epic'; strip it and append /ticket/<id>.
    var base = conf.base_url.replace(/\/epic\/?$/, "");
    return base + "/ticket/" + id;
  }

  // Re-render the table body from a list of link objects.
  function renderLinks(conf, $section, links) {
    var $table = $section.find(".epic-links-table");
    var $tbody = $table.find("tbody");
    var $empty = $section.find(".epic-empty");
    $tbody.empty();

    if (!links || links.length === 0) {
      $table.hide();
      $empty.show();
      return;
    }
    $table.show();
    $empty.hide();

    $.each(links, function (i, item) {
      var url = ticketUrl(conf, item.id);
      // Row colour follows Trac's default report/query scheme:
      // odd/even striping plus a prioN class derived from the ticket's
      // priority value.  Closed tickets get a line-through on the id link.
      var rowCls = (i % 2 ? "even" : "odd") +
                   " prio" + (item.priority_value || "");
      var $tr = $("<tr/>").attr("data-link-id", item.id).addClass(rowCls);
      var $idLink = $("<a/>").attr("href", url).text("#" + item.id);
      if (item.status === "closed") {
        $idLink.addClass("closed");
      }
      $tr.append($("<td/>").addClass("epic-col-id").append($idLink));
      $tr.append($("<td/>").addClass("epic-col-summary").append(
        $("<a/>").attr("href", url).text(item.summary)));
      $tr.append($("<td/>").addClass("epic-col-component")
        .text(item.component || ""));
      $tr.append($("<td/>").addClass("epic-col-type").text(item.type || ""));
      $tr.append($("<td/>").addClass("epic-col-status")
        .text(item.status || ""));
      $tr.append($("<td/>").addClass("epic-col-owner")
        .text(item.owner || ""));
      $tr.append($("<td/>").addClass("epic-col-modified")
        .text(item.modified || ""));
      if (conf.can_modify) {
        var $btn = $("<button/>").attr("type", "button")
          .addClass("epic-remove-btn")
          .attr("data-other-id", item.id)
          .attr("title", "Remove this link")
          .text("Remove");
        $tr.append($("<td/>").addClass("epic-col-actions").append($btn));
      }
      $tbody.append($tr);
    });
  }

  // Resolve the (epic_id, ticket_id) pair for an action against `otherId`.
  function pair(conf, otherId) {
    if (conf.is_epic) {
      // Viewed ticket is the epic; the other id is a member ticket.
      return { epic_id: conf.ticket_id, ticket_id: otherId };
    }
    // Viewed ticket is a regular ticket; the other id is an epic.
    return { epic_id: otherId, ticket_id: conf.ticket_id };
  }

  function showMsg($section, text, isError) {
    var $msg = $section.find("#epic-add-msg");
    $msg.text(text || "").toggleClass("epic-error", !!isError);
    if (text) {
      setTimeout(function () { $msg.text("").removeClass("epic-error"); },
        4000);
    }
  }

  function postLink(conf, action, otherId) {
    var p = pair(conf, otherId);
    return $.ajax({
      url: conf.base_url + "/link",
      method: "POST",
      dataType: "json",
      data: {
        action: action,
        epic_id: p.epic_id,
        ticket_id: p.ticket_id,
        view_id: conf.ticket_id,
        __FORM_TOKEN: conf.form_token
      }
    });
  }

  function bindEvents(conf, $section) {
    // Remove link (with confirmation).
    $section.on("click", ".epic-remove-btn", function () {
      var otherId = $(this).data("other-id");
      if (!window.confirm("Remove link to #" + otherId + "?")) {
        return;
      }
      var $btn = $(this).prop("disabled", true);
      postLink(conf, "remove", otherId)
        .done(function (resp) {
          if (resp && resp.ok) {
            renderLinks(conf, $section, resp.links);
          } else {
            showMsg($section, (resp && resp.error) || "Error", true);
            $btn.prop("disabled", false);
          }
        })
        .fail(function (xhr) {
          showMsg($section, errText(xhr), true);
          $btn.prop("disabled", false);
        });
    });

    // Add link button.
    $section.on("click", "#epic-add-btn", function () {
      var otherId = parseInt($section.find("#epic-add-selected").val(), 10);
      if (!otherId) {
        showMsg($section, "Select a ticket first", true);
        return;
      }
      var $btn = $(this).prop("disabled", true);
      postLink(conf, "add", otherId)
        .done(function (resp) {
          if (resp && resp.ok) {
            renderLinks(conf, $section, resp.links);
            $section.find("#epic-add-input").val("");
            $section.find("#epic-add-selected").val("");
            if (!resp.changed) {
              showMsg($section, "Link already existed", false);
            }
          } else {
            showMsg($section, (resp && resp.error) || "Error", true);
          }
          $btn.prop("disabled", true);
        })
        .fail(function (xhr) {
          showMsg($section, errText(xhr), true);
          $btn.prop("disabled", false);
        });
    });

    bindAutocomplete(conf, $section);
  }

  function errText(xhr) {
    try {
      var j = JSON.parse(xhr.responseText);
      if (j && j.error) { return j.error; }
    } catch (e) { /* ignore */ }
    return "Request failed (" + xhr.status + ")";
  }

  // Lightweight autocomplete backed by /epic/search.
  function bindAutocomplete(conf, $section) {
    var $input = $section.find("#epic-add-input");
    var $hidden = $section.find("#epic-add-selected");
    var $addBtn = $section.find("#epic-add-btn");
    var $box = $section.find("#epic-autocomplete");
    var timer = null;

    // When the epic page is viewed we search regular tickets; otherwise
    // we search for epics to attach to.
    var only = conf.is_epic ? "ticket" : "epic";

    function clearSelection() {
      $hidden.val("");
      $addBtn.prop("disabled", true);
    }

    $input.on("input", function () {
      clearSelection();
      var term = $.trim($input.val());
      if (timer) { clearTimeout(timer); }
      if (term.length < 1) { $box.hide().empty(); return; }
      timer = setTimeout(function () { runSearch(term); }, 200);
    });

    function runSearch(term) {
      $.ajax({
        url: conf.base_url + "/search",
        method: "GET",
        dataType: "json",
        data: { q: term, only: only, exclude: conf.ticket_id }
      }).done(function (resp) {
        renderSuggestions(resp && resp.results ? resp.results : []);
      });
    }

    function renderSuggestions(results) {
      $box.empty();
      if (!results.length) { $box.hide(); return; }
      $.each(results, function (i, r) {
        var $item = $("<div/>").addClass("epic-ac-item")
          .attr("data-id", r.id)
          .text(r.label + " [" + r.status + "]");
        $item.on("click", function () {
          $input.val(r.label);
          $hidden.val(r.id);
          $addBtn.prop("disabled", false);
          $box.hide().empty();
        });
        $box.append($item);
      });
      $box.show();
    }

    // Hide the suggestion box when clicking elsewhere.
    $(document).on("click", function (e) {
      if (!$(e.target).closest(".epic-add-form").length) {
        $box.hide();
      }
    });
  }

  $(function () {
    var conf = cfg();
    if (!conf) { return; }
    var $section = injectSection(conf);
    if (!$section) { return; }
    bindEvents(conf, $section);
  });

})(jQuery);
