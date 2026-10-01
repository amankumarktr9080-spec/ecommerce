/* =========================================
   SELLER PANEL
   seller.js
========================================= */

document.addEventListener("DOMContentLoaded", function () {

    console.log("Seller Panel JS Loaded");

    initSellerSearch();
    initConfirmButtons();
    initProductForm();
    initSellerForms();
    initNotifications();
    initOfferActions();
    initInventoryActions();
    initOrderActions();
    initWithdrawal();
    initSupportForm();

});


/* =========================================
   CSRF TOKEN
========================================= */

function getCSRFToken() {

    const cookie = document.cookie
        .split("; ")
        .find(row => row.startsWith("csrftoken="));

    if (!cookie) {
        return "";
    }

    return decodeURIComponent(
        cookie.split("=")[1]
    );
}


/* =========================================
   SEARCH
========================================= */

function initSellerSearch() {

    const searchInput =
        document.querySelector("#productSearch");

    const table =
        document.querySelector("#productsTable");

    if (!searchInput || !table) {
        return;
    }

    searchInput.addEventListener("input", function () {

        const searchText =
            this.value.toLowerCase().trim();

        const rows =
            table.querySelectorAll("tbody tr");

        rows.forEach(row => {

            const text =
                row.textContent.toLowerCase();

            if (text.includes(searchText)) {
                row.style.display = "";
            } else {
                row.style.display = "none";
            }

        });

    });

}


/* =========================================
   CONFIRM BUTTONS
========================================= */

function initConfirmButtons() {

    document
        .querySelectorAll("[data-confirm]")
        .forEach(button => {

            button.addEventListener(
                "click",
                function (event) {

                    const message =
                        this.dataset.confirm ||
                        "Are you sure?";

                    if (!confirm(message)) {
                        event.preventDefault();
                    }

                }
            );

        });

}


/* =========================================
   PRODUCT FORM
========================================= */

function initProductForm() {

    const forms =
        document.querySelectorAll(
            ".seller-form"
        );

    forms.forEach(form => {

        const productName =
            form.querySelector(
                'input[name="name"]'
            );

        const price =
            form.querySelector(
                'input[name="price"]'
            );

        const stock =
            form.querySelector(
                'input[name="stock"]'
            );

        if (!productName) {
            return;
        }

        form.addEventListener(
            "submit",
            function (event) {

                event.preventDefault();

                if (
                    productName.value.trim() === ""
                ) {

                    showSellerMessage(
                        "Please enter product name",
                        "danger"
                    );

                    productName.focus();

                    return;
                }

                if (
                    price &&
                    Number(price.value) < 0
                ) {

                    showSellerMessage(
                        "Price cannot be negative",
                        "danger"
                    );

                    return;
                }

                if (
                    stock &&
                    Number(stock.value) < 0
                ) {

                    showSellerMessage(
                        "Stock cannot be negative",
                        "danger"
                    );

                    return;
                }

                /*
                    Django backend API will be
                    connected here later.
                */

                showSellerMessage(
                    "Product saved successfully",
                    "success"
                );

            }
        );

    });

}


/* =========================================
   GENERAL SELLER FORMS
========================================= */

function initSellerForms() {

    document
        .querySelectorAll(
            ".seller-form:not(#productForm)"
        )
        .forEach(form => {

            /*
             * Only handle forms which are
             * currently demo forms.
             *
             * Real Django POST/API logic
             * will be connected later.
             */

            form.addEventListener(
                "submit",
                function (event) {

                    if (
                        form.querySelector(
                            'input[type="file"]'
                        )
                    ) {
                        return;
                    }

                    event.preventDefault();

                    showSellerMessage(
                        "Changes saved successfully",
                        "success"
                    );

                }
            );

        });

}


/* =========================================
   NOTIFICATIONS
========================================= */

function initNotifications() {

    const button =
        document.querySelector(
            "#markAllNotifications"
        );

    if (!button) {
        return;
    }

    button.addEventListener(
        "click",
        function () {

            document
                .querySelectorAll(
                    ".seller-notification.unread"
                )
                .forEach(notification => {

                    notification.classList.remove(
                        "unread"
                    );

                });

            showSellerMessage(
                "All notifications marked as read",
                "success"
            );

        }
    );

}


/* =========================================
   OFFER ACTIONS
========================================= */

function initOfferActions() {

    document
        .querySelectorAll(
            ".offer-delete"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                function () {

                    if (
                        confirm(
                            "Delete this offer?"
                        )
                    ) {

                        const row =
                            this.closest("tr");

                        if (row) {
                            row.remove();
                        }

                        showSellerMessage(
                            "Offer deleted",
                            "success"
                        );

                    }

                }
            );

        });

}


/* =========================================
   INVENTORY
========================================= */

function initInventoryActions() {

    document
        .querySelectorAll(
            ".inventory-update"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                function () {

                    const row =
                        this.closest("tr");

                    if (!row) {
                        return;
                    }

                    const stockInput =
                        row.querySelector(
                            ".stock-input"
                        );

                    if (!stockInput) {
                        return;
                    }

                    const stock =
                        Number(stockInput.value);

                    if (stock < 0) {

                        showSellerMessage(
                            "Stock cannot be negative",
                            "danger"
                        );

                        return;
                    }

                    showSellerMessage(
                        "Inventory updated",
                        "success"
                    );

                }
            );

        });

}


/* =========================================
   ORDER ACTIONS
========================================= */

function initOrderActions() {

    document
        .querySelectorAll(
            ".order-confirm"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                function () {

                    if (
                        confirm(
                            "Confirm this order?"
                        )
                    ) {

                        showSellerMessage(
                            "Order confirmed",
                            "success"
                        );

                    }

                }
            );

        });


    document
        .querySelectorAll(
            ".order-cancel"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                function () {

                    if (
                        confirm(
                            "Cancel this order?"
                        )
                    ) {

                        showSellerMessage(
                            "Order cancelled",
                            "success"
                        );

                    }

                }
            );

        });

}


/* =========================================
   WITHDRAWAL
========================================= */

function initWithdrawal() {

    const button =
        document.querySelector(
            "#requestWithdrawal"
        );

    if (!button) {
        return;
    }

    button.addEventListener(
        "click",
        function () {

            const amount =
                prompt(
                    "Enter withdrawal amount:"
                );

            if (amount === null) {
                return;
            }

            const value =
                Number(amount);

            if (
                !value ||
                value <= 0
            ) {

                showSellerMessage(
                    "Enter a valid amount",
                    "danger"
                );

                return;
            }

            showSellerMessage(
                "Withdrawal request submitted",
                "success"
            );

        }
    );

}


/* =========================================
   SUPPORT
========================================= */

function initSupportForm() {

    const form =
        document.querySelector(
            "#supportForm"
        );

    if (!form) {
        return;
    }

    form.addEventListener(
        "submit",
        function (event) {

            event.preventDefault();

            showSellerMessage(
                "Support ticket created successfully",
                "success"
            );

            form.reset();

        }
    );

}


/* =========================================
   SELLER MESSAGE
========================================= */

function showSellerMessage(
    message,
    type = "info"
) {

    let container =
        document.querySelector(
            "#sellerMessageContainer"
        );

    if (!container) {

        container =
            document.createElement("div");

        container.id =
            "sellerMessageContainer";

        container.style.position =
            "fixed";

        container.style.top =
            "20px";

        container.style.right =
            "20px";

        container.style.zIndex =
            "99999";

        container.style.maxWidth =
            "350px";

        document.body.appendChild(
            container
        );

    }

    const messageBox =
        document.createElement("div");

    messageBox.className =
        "seller-alert";

    messageBox.style.padding =
        "14px 17px";

    messageBox.style.marginBottom =
        "10px";

    messageBox.style.borderRadius =
        "8px";

    messageBox.style.background =
        type === "success"
            ? "#dcfce7"
            : type === "danger"
            ? "#fee2e2"
            : "#dbeafe";

    messageBox.style.color =
        type === "success"
            ? "#166534"
            : type === "danger"
            ? "#991b1b"
            : "#1e40af";

    messageBox.textContent =
        message;

    container.appendChild(
        messageBox
    );

    setTimeout(
        function () {

            messageBox.style.opacity =
                "0";

            messageBox.style.transition =
                "0.3s";

            setTimeout(
                function () {

                    messageBox.remove();

                },
                300
            );

        },
        2500
    );

}


/* =========================================
   IMAGE PREVIEW
========================================= */

function initImagePreview() {

    const input =
        document.querySelector(
            'input[type="file"][accept*="image"]'
        );

    const preview =
        document.querySelector(
            "#imagePreview"
        );

    if (!input || !preview) {
        return;
    }

    input.addEventListener(
        "change",
        function () {

            preview.innerHTML = "";

            Array.from(
                this.files
            ).forEach(file => {

                const reader =
                    new FileReader();

                reader.onload =
                    function (event) {

                        const image =
                            document.createElement(
                                "img"
                            );

                        image.src =
                            event.target.result;

                        image.style.width =
                            "100px";

                        image.style.height =
                            "100px";

                        image.style.objectFit =
                            "cover";

                        image.style.borderRadius =
                            "8px";

                        image.style.margin =
                            "5px";

                        preview.appendChild(
                            image
                        );

                    };

                reader.readAsDataURL(file);

            });

        }
    );

}


/* =========================================
   STORE EDIT
========================================= */

function enableStoreEdit() {

    const form =
        document.querySelector(
            "#storeForm"
        );

    if (!form) {
        return;
    }

    form.addEventListener(
        "submit",
        function (event) {

            event.preventDefault();

            showSellerMessage(
                "Store information updated",
                "success"
            );

        }
    );

}


/* =========================================
   AUTO HIDE ALERTS
========================================= */

setTimeout(
    function () {

        document
            .querySelectorAll(
                ".seller-alert[data-auto-hide]"
            )
            .forEach(alert => {

                alert.remove();

            });

    },
    4000
);