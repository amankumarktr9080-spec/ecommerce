/* =========================================
   CUSTOMER PANEL
   customer.js
========================================= */

document.addEventListener("DOMContentLoaded", function () {

    console.log("Customer Panel JS Loaded");

    initQuantityControls();
    initAddToCart();
    initWishlist();
    initSearch();
    initProductFilters();
    initNotifications();
    initAddressSelection();
    initPaymentMethod();
    initConfirmActions();

});


/* =========================================
   CSRF TOKEN
========================================= */

function getCSRFToken() {

    const cookieValue = document.cookie
        .split("; ")
        .find(row => row.startsWith("csrftoken="));

    if (!cookieValue) {
        return "";
    }

    return decodeURIComponent(cookieValue.split("=")[1]);
}


/* =========================================
   QUANTITY CONTROL
========================================= */

function initQuantityControls() {

    document.querySelectorAll(".quantity-control").forEach(control => {

        const minusBtn = control.querySelector(".quantity-minus");
        const plusBtn = control.querySelector(".quantity-plus");
        const quantity = control.querySelector(".quantity-value");

        if (!quantity) return;

        if (minusBtn) {

            minusBtn.addEventListener("click", function () {

                let value = parseInt(quantity.textContent) || 1;

                if (value > 1) {
                    value--;
                    quantity.textContent = value;

                    updateCartItem(control, value);
                }

            });

        }

        if (plusBtn) {

            plusBtn.addEventListener("click", function () {

                let value = parseInt(quantity.textContent) || 1;

                value++;

                quantity.textContent = value;

                updateCartItem(control, value);

            });

        }

    });

}


/* =========================================
   UPDATE CART ITEM
========================================= */

function updateCartItem(control, quantity) {

    const productId = control.dataset.productId;

    console.log(
        "Product:",
        productId,
        "Quantity:",
        quantity
    );

    /*
       Backend connect later:

       fetch("/api/cart/update/", {
           method: "POST",
           headers: {
               "Content-Type": "application/json",
               "X-CSRFToken": getCSRFToken()
           },
           body: JSON.stringify({
               product_id: productId,
               quantity: quantity
           })
       });
    */
}


/* =========================================
   ADD TO CART
========================================= */

function initAddToCart() {

    document.querySelectorAll(".add-to-cart").forEach(button => {

        button.addEventListener("click", function () {

            const productId = this.dataset.productId;

            if (!productId) {
                showCustomerMessage(
                    "Product added to cart",
                    "success"
                );
                return;
            }

            addToCart(productId);

        });

    });

}


function addToCart(productId) {

    console.log("Adding product:", productId);

    /*
       Backend API later:

       fetch("/api/cart/add/", {
           method: "POST",
           headers: {
               "Content-Type": "application/json",
               "X-CSRFToken": getCSRFToken()
           },
           body: JSON.stringify({
               product_id: productId,
               quantity: 1
           })
       });
    */

    showCustomerMessage(
        "Product added to cart",
        "success"
    );

}


/* =========================================
   WISHLIST
========================================= */

function initWishlist() {

    document.querySelectorAll(".wishlist-btn").forEach(button => {
        if (button.closest('.ajax-wishlist-form')) return;

        button.addEventListener("click", function () {

            const productId = this.dataset.productId;

            this.classList.toggle("active");

            const icon = this.querySelector("i");

            if (icon) {

                if (this.classList.contains("active")) {

                    icon.classList.remove("fa-regular");
                    icon.classList.add("fa-solid");

                    showCustomerMessage(
                        "Added to wishlist",
                        "success"
                    );

                } else {

                    icon.classList.remove("fa-solid");
                    icon.classList.add("fa-regular");

                    showCustomerMessage(
                        "Removed from wishlist",
                        "success"
                    );

                }

            }

            console.log("Wishlist product:", productId);

        });

    });

}


/* =========================================
   SEARCH
========================================= */

function initSearch() {

    const searchInput =
        document.querySelector("#searchInput");

    const searchForm =
        document.querySelector("#searchForm");

    if (!searchInput) return;

    if (searchForm) {

        searchForm.addEventListener("submit", function (event) {

            event.preventDefault();

            const query =
                searchInput.value.trim();

            if (!query) {
                showCustomerMessage(
                    "Please enter a search term",
                    "warning"
                );
                return;
            }

            const url =
                `/customer/search/?q=${encodeURIComponent(query)}`;

            window.location.href = url;

        });

    }

}


/* =========================================
   PRODUCT FILTER
========================================= */

function initProductFilters() {

    const filterForm =
        document.querySelector("#productFilterForm");

    if (!filterForm) return;

    filterForm.addEventListener("change", function () {

        const formData =
            new FormData(filterForm);

        const params =
            new URLSearchParams(formData);

        const currentPath =
            window.location.pathname;

        window.location.href =
            `${currentPath}?${params.toString()}`;

    });

}


/* =========================================
   NOTIFICATIONS
========================================= */

function initNotifications() {

    const markAll =
        document.querySelector("#markAllNotifications");

    if (!markAll) return;

    markAll.addEventListener("click", function () {

        document
            .querySelectorAll(".notification-item.unread")
            .forEach(item => {

                item.classList.remove("unread");

            });

        showCustomerMessage(
            "All notifications marked as read",
            "success"
        );

    });

}


/* =========================================
   ADDRESS SELECTION
========================================= */

function initAddressSelection() {

    document
        .querySelectorAll(".address-card")
        .forEach(card => {

            card.addEventListener("click", function () {

                document
                    .querySelectorAll(".address-card")
                    .forEach(item => {
                        item.classList.remove("selected");
                    });

                this.classList.add("selected");

                const radio =
                    this.querySelector(
                        'input[type="radio"]'
                    );

                if (radio) {
                    radio.checked = true;
                }

            });

        });

}


/* =========================================
   PAYMENT METHOD
========================================= */

function initPaymentMethod() {

    document
        .querySelectorAll(
            'input[name="payment_method"]'
        )
        .forEach(input => {

            input.addEventListener("change", function () {

                document
                    .querySelectorAll(".payment-method")
                    .forEach(item => {
                        item.classList.remove("selected");
                    });

                const parent =
                    this.closest(".payment-method");

                if (parent) {
                    parent.classList.add("selected");
                }

            });

        });

}


/* =========================================
   CONFIRM ACTIONS
========================================= */

function initConfirmActions() {

    document
        .querySelectorAll("[data-confirm]")
        .forEach(button => {

            button.addEventListener("click", function (event) {

                const message =
                    this.dataset.confirm ||
                    "Are you sure?";

                if (!confirm(message)) {
                    event.preventDefault();
                }

            });

        });

}


/* =========================================
   REMOVE CART ITEM
========================================= */

function removeCartItem(productId, element) {

    if (!confirm("Remove this product from cart?")) {
        return;
    }

    console.log(
        "Removing product:",
        productId
    );

    if (element) {
        const item =
            element.closest(".cart-item");

        if (item) {
            item.remove();
        }
    }

    updateCartTotal();

    showCustomerMessage(
        "Product removed from cart",
        "success"
    );

}


/* =========================================
   CART TOTAL
========================================= */

function updateCartTotal() {

    let subtotal = 0;

    document
        .querySelectorAll(".cart-item")
        .forEach(item => {

            const price =
                parseFloat(
                    item.dataset.price || 0
                );

            const quantityElement =
                item.querySelector(
                    ".quantity-value"
                );

            const quantity =
                parseInt(
                    quantityElement?.textContent || 1
                );

            subtotal += price * quantity;

        });

    const subtotalElement =
        document.querySelector("#cartSubtotal");

    if (subtotalElement) {
        subtotalElement.textContent =
            `₹${subtotal.toFixed(2)}`;
    }

}


/* =========================================
   COUPON COPY
========================================= */

function copyCustomerCoupon(code) {

    navigator.clipboard
        .writeText(code)
        .then(() => {

            showCustomerMessage(
                `Coupon ${code} copied`,
                "success"
            );

        })
        .catch(() => {

            showCustomerMessage(
                "Unable to copy coupon",
                "danger"
            );

        });

}


/* =========================================
   CUSTOMER MESSAGE
========================================= */

function showCustomerMessage(message, type = "info") {

    let container =
        document.querySelector(
            "#customerMessageContainer"
        );

    if (!container) {

        container =
            document.createElement("div");

        container.id =
            "customerMessageContainer";

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

        document.body.appendChild(container);

    }

    const alert =
        document.createElement("div");

    alert.className =
        `customer-alert alert-${type}`;

    alert.style.marginBottom =
        "10px";

    alert.innerHTML = `
        <span>${message}</span>
    `;

    container.appendChild(alert);

    setTimeout(() => {

        alert.style.opacity = "0";
        alert.style.transition = "0.3s";

        setTimeout(() => {
            alert.remove();
        }, 300);

    }, 2500);

}


/* =========================================
   PRODUCT IMAGE ERROR
========================================= */

document.addEventListener(
    "error",
    function (event) {

        if (
            event.target.tagName === "IMG" &&
            event.target.classList.contains("product-image")
        ) {

            event.target.src =
                "/static/images/product-placeholder.jpg";

        }

    },
    true
);


/* =========================================
   AUTO DISMISS MESSAGES
========================================= */

setTimeout(() => {

    document
        .querySelectorAll(
            ".customer-alert[data-auto-hide]"
        )
        .forEach(alert => {

            alert.style.opacity = "0";

            setTimeout(() => {
                alert.remove();
            }, 300);

        });

}, 3000);


/* =========================================
   DARK MODE SUPPORT
========================================= */

function enableCustomerDarkMode() {

    document.body.classList.add(
        "customer-dark-mode"
    );

}


function disableCustomerDarkMode() {

    document.body.classList.remove(
        "customer-dark-mode"
    );

}