$(function() {
    // Identifier for messages related to editing the hierarchy.
    var EDIT_HIERARCHY_MESSAGE = "edit-hierarchy-message";

    // The first row is a dummy that exists so that the user can drag
    // other regions to the top level.
    var ALL_ROWS = $(".treetable tbody tr.region");
    var REGION_ROWS = ALL_ROWS.not(":first-child");

    /* Per Django documentation, to get CSRF cookie for AJAX post. */
    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie != '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = jQuery.trim(cookies[i]);
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) == (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    /* Add user message to the top of the page. */
    var addUserMessage = function(id, type, message) {
        clearUserMessage(id);  // Remove previous messages that used this ID.
        close = $("<a>").attr("href", "#")
        close.addClass("close").attr("data-dismiss", "alert")
        close.html("×");
        msgDiv = $("<div>").attr("id", id);
        msgDiv.addClass("alert alert-" + type);
        msgDiv.html(message)
        msgDiv.prepend(close);
        $("#user-messages").append(msgDiv);
    }

    /* Remove user message from the top of the page. */
    var clearUserMessage = function(id) {
        $("#" + id).remove();
    }

    /* Allow user to edit region hierarchy. */
    $("#edit-hierarchy").click(function () {
        clearUserMessage(EDIT_HIERARCHY_MESSAGE);

        /* Display only the "Save Hierarchy" button. */
        $("#region-actions .btn.hierarchy").addClass("hidden");
        $("#save-hierarchy").removeClass("hidden");

        /* Show user help message. */
        $("#edit-hierarchy-help").removeClass("hidden");

        /* Show boundary selectors. */
        REGION_ROWS.find('.value-boundary .value').addClass('hidden');
        REGION_ROWS.find('.value-boundary .boundary-select').removeClass('hidden');

        /* Enable drag-and-drop. */
        $(".list_groups_region").addClass("edit-mode");
        REGION_ROWS.draggable("enable");
        ALL_ROWS.droppable("enable");
    })

    /* Save edited region hierarchy to server. */
    $("#save-hierarchy").click(function() {
        /* Disable drag-and-drop. */
        REGION_ROWS.draggable("disable");
        ALL_ROWS.droppable("disable");

        /* Display only the "Saving Hierarchy..." button. */
        $("#region-actions .btn.hierarchy").addClass("hidden");
        $("#saving-hierarchy").removeClass("hidden");

        updateHierarchyOnServer();
    });

    /* Display success message & allow user to edit again. */
    var saveHierarchySuccess = function(message) {
        addUserMessage(EDIT_HIERARCHY_MESSAGE, "success", message);

        /* Hide user help message. */
        $("#edit-hierarchy-help").addClass("hidden");

        /* Hide boundary selectors. */
        REGION_ROWS.find('.value-boundary .boundary-select').addClass('hidden');
        REGION_ROWS.find('.value-boundary .value').removeClass('hidden');

        /* Display only the "Edit Hierarchy" button. */
        $(".list_groups_region").removeClass("edit-mode");
        $("#region-actions .btn.hierarchy").addClass("hidden");
        $("#edit-hierarchy").removeClass("hidden");
    }

    /* Display error message & maintain "editing" state. */
    var saveHierarchyFailure = function(message) {
        addUserMessage(EDIT_HIERARCHY_MESSAGE, "error", message);

        /* Display only the "Save Hierarchy" button. */
        $("#region-actions .btn.hierarchy").addClass("hidden");
        $("#save-hierarchy").removeClass("hidden");
    }

    /* Send the updated region hierarchy to the server. */
    var updateHierarchyOnServer = function() {
        var regionParents = {};  // region id -> (parent id, boundary id)
        $(".list_groups_region tbody").find("tr:not(:first-child)").each(function(i) {
            var regionId = $(this).data("ttId");
            var parentId = $(this).data("ttParentId") || null;
            var boundaryId = $(this).find(".boundary-select").val() || null;
            regionParents[regionId] = [parentId, boundaryId];
        });

        $.ajax({
            data: {
                csrfmiddlewaretoken: getCookie('csrftoken'),
                data: JSON.stringify(regionParents)
            },
            dataType: "json",
            type: "POST",
            url: $(".list_groups_region").data("updateHierarchyUrl")
        }).done(function(data, status, xhr) {
            if (data['success']) {
                saveHierarchySuccess(data['message']);
            } else {
                message = "<strong>An error occurred while saving the " +
                          "hierarchy:</strong> " + data["message"];
                saveHierarchyFailure(message);
            }
        }).fail(function() {
            var message = "An error has occurred and your changes were not " +
                          "saved. Please try again later.";
            saveHierarchyFailure(message);
        });
    };

    /* Allow dragging table rows that represent regions. */
    REGION_ROWS.draggable({
        containment: "document",
        cursor: "move",
        delay: 200,  // Avoid triggering drag when expanding/collapsing.
        helper: function() {
            var cell = $(this).find("td:first-child");
            var indenterPadding = parseInt(cell.find(".indenter").css("padding-left"));
            var el = cell.find(".value").clone()
            // Pad to be approximately in line with original cell.
            el.css("padding-left", 34 + indenterPadding + "px");
            return el;
        },
        opacity: 0.75,
        refreshPositions: true,  // Necessary when nodes expand while dragging.
        revert: "invalid",
        revertDuration: 300,
        scroll: true,
        start: function(e, ui) {
            $(this).addClass("selected");
        },
        stop: function(e, ui) {
            $(this).removeClass("selected");
        }
    });
    REGION_ROWS.draggable("disable");  // Enable by clicking #edit-hierarchy.

    /* Allow dropping regions onto any table row. */
    ALL_ROWS.droppable({
        accept: REGION_ROWS,
        drop: function(e, ui) {
            var table = $(this).closest(".treetable");
            var toMoveNode = table.treetable("node", ui.draggable.data("ttId"));
            var newParentNode = table.treetable("node", $(this).data("ttId"));
            table.treetable("expandNode", newParentNode.id);
            table.treetable("move", toMoveNode.id, newParentNode.id);
            table.treetable("sortBranch", newParentNode);
        },
        hoverClass: "hovered",
        over: function(e, ui) {
            var toMove = ui.draggable;
            var candidateParent = $(this);
            if (toMove != candidateParent && !candidateParent.is(".expanded")) {
                var table = $(this).closest(".treetable");
                table.treetable("expandNode", candidateParent.data("ttId"));
            }
        }
    });
    ALL_ROWS.droppable("disable");  // Enable by clicking #edit-hierarchy.

    /* Initialize the hierarchical tree table in the expanded state. */
    $(".treetable").treetable({
        expandable: true,
        expanderTemplate: '<a href="#"><span class="glyphicon"></span></a>',
        initialState: "expanded",
        onInitialized: function() {
            var table = $(this.table);
            table.find("tr").removeClass("hidden");
            table.find("tr.loading-text").remove();
        }
    });

    $('td.value-boundary select').change(function() {
        var self = $(this);
        var label = self.find(':selected').text();
        self.closest('.value-boundary').find('.value').text(label);
    });
});
