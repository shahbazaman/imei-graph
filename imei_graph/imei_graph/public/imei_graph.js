frappe.pages['imei-graph'].on_page_load = function(wrapper) {

    let page = frappe.ui.make_app_page({
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
                    margin-right:10px;
                "
            >

            <button
                id="search_btn"
                class="btn btn-primary"
            >
                Search
            </button>

        </div>

        <div
            id="network"
            style="
                width:100%;
                height:800px;
                border:1px solid #ddd;
            "
        ></div>

    `);

    $('#search_btn').click(function() {

        let imei = $('#imei_input').val();

        frappe.call({

            method:
            "imei_graph.api.get_imei_graph",

            args: {
                imei: imei
            },

            callback: function(r) {

                if (!r.message.found) {

                    frappe.msgprint(
                        "IMEI NOT FOUND"
                    );

                    return;
                }

                let container =
                    document.getElementById(
                        'network'
                    );

                let data = {

                    nodes:
                    new vis.DataSet(
                        r.message.nodes
                    ),

                    edges:
                    new vis.DataSet(
                        r.message.edges
                    )
                };

                let options = {

                    layout: {

                        hierarchical: {

                            enabled: true,

                            direction: "UD",

                            sortMethod: "directed",

                            levelSeparation: 200,

                            nodeSpacing: 200
                        }
                    },

                    physics: false
                };

                new vis.Network(
                    container,
                    data,
                    options
                );
            }
        });
    });
};