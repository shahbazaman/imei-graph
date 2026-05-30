frappe.pages["imei-dispute-graph"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "IMEI Dispute Graph",
        single_column: true,
    });

    $(wrapper).find(".page-content").html(`
        <div class="imei-graph-shell">
            <div class="imei-graph-toolbar">
                <select id="start_doctype" class="form-control">
                    <option value="Sales Invoice">Sales Invoice</option>
                    <option value="Purchase Invoice">Purchase Invoice</option>
                    <option value="Delivery Note">Delivery Note</option>
                    <option value="Purchase Receipt">Purchase Receipt</option>
                    <option value="Stock Entry">Stock Entry</option>
                </select>
                <input id="start_name" class="form-control" type="text" placeholder="Disputed transaction name">
                <input id="max_depth" class="form-control" type="number" min="1" max="20" value="8" title="Max depth">
                <button id="build_graph" class="btn btn-primary">Build</button>
                <span id="graph_status"></span>
            </div>
            <div id="imei_network"></div>
        </div>
    `);

    $("<style>").text(`
        .imei-graph-shell { padding: 16px; }
        .imei-graph-toolbar {
            display: grid;
            grid-template-columns: 190px minmax(260px, 1fr) 90px 90px auto;
            gap: 10px;
            align-items: center;
            margin-bottom: 12px;
        }
        #imei_network {
            width: 100%;
            height: 760px;
            border: 1px solid var(--border-color, #d1d8dd);
            border-radius: 6px;
            background: #f8fafc;
        }
        #graph_status { color: #64748b; font-size: 13px; }
        @media (max-width: 760px) {
            .imei-graph-toolbar { grid-template-columns: 1fr; }
            #imei_network { height: 680px; }
        }
    `).appendTo(document.head);

    function load_vis_network(callback) {
        if (window.vis && window.vis.Network) {
            callback();
            return;
        }

        const script = document.createElement("script");
        script.src = "https://unpkg.com/vis-network/standalone/umd/vis-network.min.js";
        script.onload = callback;
        script.onerror = function () {
            frappe.msgprint("Could not load vis-network. Check internet access or bundle the library locally.");
        };
        document.head.appendChild(script);
    }

    function build_graph() {
        const start_doctype = $("#start_doctype").val();
        const start_name = $("#start_name").val().trim();
        const max_depth = cint($("#max_depth").val() || 8);

        if (!start_name) {
            frappe.msgprint("Enter the disputed transaction name.");
            return;
        }

        $("#graph_status").text("Building graph...");
        $("#build_graph").prop("disabled", true);

        frappe.call({
            method: "imei_graph.api.dispute_graph.get_dispute_graph",
            args: { start_doctype, start_name, max_depth },
            callback: function (r) {
                $("#build_graph").prop("disabled", false);
                const data = r.message;

                if (!data || !data.nodes || !data.nodes.length) {
                    $("#graph_status").text("No graph data found.");
                    return;
                }

                $("#graph_status").text(`${data.nodes.length} nodes, ${data.edges.length} links`);

                load_vis_network(function () {
                    const container = document.getElementById("imei_network");
                    const network_data = {
                        nodes: new vis.DataSet(data.nodes),
                        edges: new vis.DataSet(data.edges),
                    };
                    const options = {
                        layout: {
                            hierarchical: {
                                enabled: true,
                                direction: "UD",
                                sortMethod: "directed",
                                levelSeparation: 135,
                                nodeSpacing: 180,
                                treeSpacing: 220,
                            },
                        },
                        physics: false,
                        edges: {
                            arrows: { to: { enabled: true, scaleFactor: 0.75 } },
                            color: { color: "#94a3b8" },
                            smooth: { type: "cubicBezier", forceDirection: "vertical", roundness: 0.45 },
                        },
                        nodes: {
                            borderWidth: 1,
                            font: { size: 12, face: "Inter, Arial" },
                            margin: 10,
                        },
                        interaction: {
                            hover: true,
                            tooltipDelay: 120,
                            zoomView: true,
                            dragView: true,
                        },
                    };
                    new vis.Network(container, network_data, options);
                });
            },
            error: function () {
                $("#build_graph").prop("disabled", false);
                $("#graph_status").text("Server error.");
            },
        });
    }

    $("#build_graph").on("click", build_graph);
    $("#start_name").on("keypress", function (event) {
        if (event.which === 13) build_graph();
    });
};

