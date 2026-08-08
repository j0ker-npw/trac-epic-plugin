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
 *     html      : string,   // server-rendered section shell
 *     form_token: string,   // CSRF token
 *     base_url  : string,   // href to /epic
 *     links     : [ {...} ],// linked-ticket summaries (unsorted)
 *     sort      : { field, order },  // default sort from trac.ini
 *     page_size : int       // rows per page before paginating
 *   }
 *
 * epic.js owns the table rendering: it sorts `links` client side, paginates
 * them into pages of `page_size`, renders the current page, draws Trac-style
 * page buttons and updates the sortable column headers.  Clicking a header
 * sorts by that column (a second click toggles the direction), exactly like
 * Trac's report / query tables.
 */
(function ($) {
  "use strict";

  var SORTABLE = ["id", "summary", "component", "type", "status", "owner",
                  "modified", "priority"];

  function cfg() {
    return window.tracepic || null;
  }

  // Insert the server-rendered shell into the ticket page.
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

  // Build the tickets base URL (e.g. /trac/ticket/123).
  function ticketUrl(conf, id) {
    // base_url ends with '/epic'; strip it and append /ticket/<id>.
    var base = conf.base_url.replace(/\/epic\/?$/, "");
    return base + "/ticket/" + id;
  }

  // Numeric priority sort key (blocker = 1 .. trivial = 6).  Missing values
  // sort as the least severe.
  function prioKey(item) {
    var v = parseInt(item.priority_value, 10);
    return isNaN(v) ? 1e9 : v;
  }

  // Comparator matching the documented semantics.  For every column except
  // priority, 'asc'/'desc' are the usual ascending/descending orders.  For
  // priority, 'desc' lists the most severe tickets first (blocker at top),
  // i.e. ascending numeric priority value.  Ties break by ascending id so
  // the order is always deterministic.
  function cmpLinks(a, b, field, order) {
    var r, av, bv;
    if (field === "id") {
      r = (parseInt(a.id, 10) || 0) - (parseInt(b.id, 10) || 0);
    } else if (field === "modified") {
      r = (parseInt(a.changetime, 10) || 0) -
          (parseInt(b.changetime, 10) || 0);
    } else if (field === "priority") {
      r = prioKey(a) - prioKey(b);
    } else {
      av = (a[field] == null ? "" : String(a[field])).toLowerCase();
      bv = (b[field] == null ? "" : String(b[field])).toLowerCase();
      r = av < bv ? -1 : (av > bv ? 1 : 0);
    }
    if (r === 0) {
      r = (parseInt(a.id, 10) || 0) - (parseInt(b.id, 10) || 0);
    }
    if (field === "priority") {
      // desc => most severe (smallest value) first => ascending numeric.
      return order === "desc" ? r : -r;
    }
    return order === "desc" ? -r : r;
  }

  function sortedLinks(links, field, order) {
    var copy = (links || []).slice();
    copy.sort(function (a, b) { return cmpLinks(a, b, field, order); });
    return copy;
  }

  // Sensible initial direction the first time a column is selected.
  function naturalOrder(field) {
    return (field === "priority" || field === "modified" || field === "id")
      ? "desc" : "asc";
  }

  // --- rendering ----------------------------------------------------------

  function renderHeader($section, field, order) {
    $section.find("th.epic-sortable").each(function () {
      var $th = $(this);
      $th.removeClass("asc desc");
      if ($th.data("field") === field) {
        $th.addClass(order);
      }
    });
  }

  function renderRows(conf, $section, pageLinks) {
    var $tbody = $section.find(".epic-links-table tbody");
    $tbody.empty();
    $.each(pageLinks, function (i, item) {
      var url = ticketUrl(conf, item.id);
      // Row colour follows Trac's default report/query scheme: odd/even
      // striping plus a prioN class from the ticket's priority value.
      var rowCls = (i % 2 ? "even" : "odd") +
                   " prio" + (item.priority_value || "");
      var $tr = $("<tr/>").attr("data-link-id", item.id).addClass(rowCls);

      var $idLink = $("<a/>").attr("href", url).text("#" + item.id);
      if (item.status === "closed") {
        $idLink.addClass("closed");
      }
      $tr.append($("<td/>").addClass("epic-col-id").append($idLink));
      $tr.append($("<td/>").addClass("epic-col-summary").append(
        $("<a/>").attr("href", url).text(item.summary || "")));
      $tr.append($("<td/>").addClass("epic-col-component")
        .text(item.component || ""));
      $tr.append($("<td/>").addClass("epic-col-type").text(item.type || ""));
      $tr.append($("<td/>").addClass("epic-col-status")
        .text(item.status || ""));
      $tr.append($("<td/>").addClass("epic-col-owner")
        .text(item.owner || ""));
      // Relative "... ago" text with the absolute date/time as a hover
      // tooltip, matching Trac's pretty_dateinfo output.
      $tr.append($("<td/>").addClass("epic-col-modified").append(
        $("<span/>").attr("title", item.modified_title || "")
          .text(item.modified || "")));
      // Compact priority badge: a coloured dot whose colour mirrors the row
      // priority, with the priority name revealed on hover.  Keeps the
      // Summary column wide instead of spending space on a text column.
      var $prio = $("<td/>").addClass("epic-col-priority");
      if (item.priority_value) {
        $prio.append($("<span/>")
          .addClass("epic-prio-badge prio" + item.priority_value)
          .attr("title", item.priority || ""));
      }
      $tr.append($prio);

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

  function renderPager(conf, $section, state, total, numPages) {
    var $pager = $section.find(".epic-paging");
    $pager.empty();
    if (numPages <= 1) {
      $pager.hide();
      return;
    }

    var start = (state.page - 1) * state.pageSize + 1;
    var end = Math.min(state.page * state.pageSize, total);
    $pager.append($("<span/>").addClass("epic-paging-info")
      .text("Showing " + start + "\u2013" + end + " of " + total));

    var $nav = $("<span/>").addClass("epic-paging-nav");

    function pageBtn(label, page, disabled, current) {
      if (current) {
        return $("<span/>").addClass("epic-page-current").text(label);
      }
      var $a = $("<a/>").attr("href", "#").addClass("epic-page-btn")
        .attr("data-page", page).text(label);
      if (disabled) {
        $a.addClass("disabled").attr("aria-disabled", "true");
      }
      return $a;
    }

    $nav.append(pageBtn("\u00AB Prev", state.page - 1, state.page <= 1,
                        false));
    for (var p = 1; p <= numPages; p++) {
      $nav.append(pageBtn(String(p), p, false, p === state.page));
    }
    $nav.append(pageBtn("Next \u00BB", state.page + 1,
                        state.page >= numPages, false));

    $pager.append($nav).show();
  }

  // Full render: sort, paginate, draw header/body/pager/empty state.
  function render(conf, $section, state) {
    var $table = $section.find(".epic-links-table");
    var $empty = $section.find(".epic-empty");
    var $pager = $section.find(".epic-paging");
    var links = state.links || [];
    var total = links.length;

    if (total === 0) {
      $table.hide();
      $pager.hide();
      $empty.show();
      return;
    }
    $empty.hide();
    $table.show();

    var numPages = Math.max(1, Math.ceil(total / state.pageSize));
    if (state.page > numPages) { state.page = numPages; }
    if (state.page < 1) { state.page = 1; }

    var sorted = sortedLinks(links, state.field, state.order);
    var from = (state.page - 1) * state.pageSize;
    var pageLinks = sorted.slice(from, from + state.pageSize);

    renderHeader($section, state.field, state.order);
    renderRows(conf, $section, pageLinks);
    renderPager(conf, $section, state, total, numPages);
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

  function bindEvents(conf, $section, state) {
    // Sort by clicking a column header (toggle direction on repeat click).
    $section.on("click", "th.epic-sortable a.epic-sort", function (e) {
      e.preventDefault();
      var field = $(this).data("field");
      if (SORTABLE.indexOf(field) === -1) { return; }
      if (state.field === field) {
        state.order = (state.order === "asc") ? "desc" : "asc";
      } else {
        state.field = field;
        state.order = naturalOrder(field);
      }
      state.page = 1;
      render(conf, $section, state);
    });

    // Pagination buttons.
    $section.on("click", ".epic-page-btn", function (e) {
      e.preventDefault();
      var $btn = $(this);
      if ($btn.hasClass("disabled")) { return; }
      var page = parseInt($btn.data("page"), 10);
      if (!page || page === state.page) { return; }
      state.page = page;
      render(conf, $section, state);
    });

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
            state.links = resp.links || [];
            render(conf, $section, state);
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
            state.links = resp.links || [];
            render(conf, $section, state);
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

  // Build the initial sort/pagination state from the plugin config.
  function initialState(conf) {
    var sort = conf.sort || {};
    var field = SORTABLE.indexOf(sort.field) !== -1 ? sort.field : "priority";
    var order = (sort.order === "asc" || sort.order === "desc")
      ? sort.order : "desc";
    var size = parseInt(conf.page_size, 10);
    if (isNaN(size) || size < 1) { size = 10; }
    return {
      links: conf.links || [],
      field: field,
      order: order,
      page: 1,
      pageSize: size
    };
  }

  // Expose pure helpers for unit testing under Node (no effect in the
  // browser, where `module` is undefined).
  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      cmpLinks: cmpLinks,
      sortedLinks: sortedLinks,
      prioKey: prioKey,
      naturalOrder: naturalOrder,
      initialState: initialState
    };
  }

  $(function () {
    var conf = cfg();
    if (!conf) { return; }
    var $section = injectSection(conf);
    if (!$section) { return; }
    var state = initialState(conf);
    bindEvents(conf, $section, state);
    render(conf, $section, state);
  });

})(typeof jQuery !== "undefined" ? jQuery : function () { return undefined; });
