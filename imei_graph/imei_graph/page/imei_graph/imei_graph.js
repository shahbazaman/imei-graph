frappe.pages['imei-graph'].on_page_load = function(wrapper) {

    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'IMEI Graph',
        single_column: true
    });

    $(wrapper).html(`

        <div style="padding:20px;">

            <input
                type="text"
                id="imei_input"
                placeholder="Enter IMEI"
                style="
                    width:300px;
                    padding:10px;
                    font-size:16px;
                "
            >

            <button
                id="search_btn"
                class="btn btn-primary"
            >
                Search
            </button>

            <div
                id="network"
                style="
                    width:100%;
                    height:800px;
                    border:1px solid #ccc;
                    margin-top:20px;
                "
            ></div>

        </div>

    `);

    // LOAD VIS NETWORK

    const script = document.createElement("script");

    script.src =
        "https://unpkg.com/vis-network/standalone/umd/vis-network.min.js";

    document.head.appendChild(script);

    // SEARCH

    $('#search_btn').click(function() {

        let imei = $('#imei_input').val();

        frappe.call({

            method:
                "imei_graph.api.roadmap.get_imei_graph",

            args: {
                imei: imei
            },

            callback: function(r) {

                let data = r.message;

                if (!data || data.length === 0) {

                    frappe.msgprint("IMEI NOT FOUND");
                    return;
                }

                let nodes = [];
                let edges = [];

                let voucher_added = {};
                let invoice_added = {};

                data.forEach((row, index) => {

                    let voucher_id =
                        "voucher_" + row.voucher;

                    let invoice_id =
                        "invoice_" + row.invoice;

                    let device_id =
                        "device_" + index;

                    // VOUCHER

                    if (!voucher_added[voucher_id]) {

                        nodes.push({

                            id: voucher_id,

                            label:
                                "Voucher\n" +
                                row.voucher,

                            shape: "box",

                            color: "#16a34a",

                            font: {
                                color: "white"
                            }

                        });

                        voucher_added[voucher_id] = true;
                    }

                    // INVOICE

                    if (!invoice_added[invoice_id]) {

                        nodes.push({

                            id: invoice_id,

                            label:
                                "Invoice\n" +
                                row.invoice,

                            shape: "ellipse",

                            color: "#f59e0b"

                        });

                        edges.push({

                            from: voucher_id,
                            to: invoice_id

                        });

                        invoice_added[invoice_id] = true;
                    }

                    // DEVICE

                    nodes.push({

                        id: device_id,

                        label:
                            "STEP " +
                            row.step +
                            "\n\n" +
                            row.device,

                        shape:
                            row.matched
                                ? "star"
                                : "dot",

                        size:
                            row.matched
                                ? 35
                                : 20,

                        color:
                            row.matched
                                ? "#ff0000"
                                : "#334155",

                        font: {
                            color: "white"
                        }

                    });

                    edges.push({

                        from: invoice_id,
                        to: device_id

                    });

                });

                const container =
                    document.getElementById('network');

                const graphData = {

                    nodes: new vis.DataSet(nodes),
                    edges: new vis.DataSet(edges)

                };

                const options = {

                    layout: {

                        hierarchical: {

                            enabled: true,
                            direction: "UD"

                        }

                    },

                    physics: false

                };

                new vis.Network(
                    container,
                    graphData,
                    options
                );

            }

        });

    });

};