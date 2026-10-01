/* =========================================================
   DELIVERY PARTNER PANEL JS
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {

    initDeliveryRequests();
    initActiveDelivery();
    initNotifications();
    initProfileForm();
    initBankForm();
    initSupportForm();
    initWithdrawal();
    initAvailability();
    initConfirmActions();

});


/* =========================================================
   CSRF TOKEN
   ========================================================= */

function getDeliveryCSRFToken() {

    const tokenElement = document.querySelector(
        '[name="csrfmiddlewaretoken"]'
    );

    if (tokenElement) {
        return tokenElement.value;
    }

    const cookies = document.cookie.split(";");

    for (let cookie of cookies) {

        cookie = cookie.trim();

        if (cookie.startsWith("csrftoken=")) {
            return decodeURIComponent(
                cookie.substring("csrftoken=".length)
            );
        }

    }

    return "";
}


/* =========================================================
   DELIVERY REQUESTS
   ========================================================= */

function initDeliveryRequests() {

    const acceptButtons =
        document.querySelectorAll(".delivery-accept");

    const rejectButtons =
        document.querySelectorAll(".delivery-reject");


    acceptButtons.forEach(function (button) {

        button.addEventListener("click", function () {

            const request =
                button.closest(".delivery-request");

            if (!request) return;

            const order =
                request.querySelector("h3");

            const orderId =
                order ? order.textContent : "Order";

            const confirmed = confirm(
                `Accept ${orderId}?`
            );

            if (!confirmed) return;

            request.style.opacity = "0.5";

            setTimeout(function () {

                request.remove();

                showDeliveryMessage(
                    "Delivery request accepted.",
                    "success"
                );

            }, 300);

        });

    });


    rejectButtons.forEach(function (button) {

        button.addEventListener("click", function () {

            const request =
                button.closest(".delivery-request");

            if (!request) return;

            const confirmed = confirm(
                "Are you sure you want to reject this delivery?"
            );

            if (!confirmed) return;

            request.style.opacity = "0.5";

            setTimeout(function () {

                request.remove();

                showDeliveryMessage(
                    "Delivery request rejected.",
                    "info"
                );

            }, 300);

        });

    });

}


/* =========================================================
   ACTIVE DELIVERY
   ========================================================= */

function initActiveDelivery() {

    const completeButton =
        document.getElementById("completeDelivery");

    if (!completeButton) return;


    completeButton.addEventListener("click", function () {

        const confirmed = confirm(
            "Mark this order as delivered?"
        );

        if (!confirmed) return;


        completeButton.disabled = true;

        completeButton.innerHTML =
            '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';


        setTimeout(function () {

            completeButton.innerHTML =
                '<i class="fa-solid fa-check"></i> Delivered';

            completeButton.classList.remove("btn-success");
            completeButton.classList.add("btn-primary");

            showDeliveryMessage(
                "Order marked as delivered.",
                "success"
            );

        }, 800);

    });

}


/* =========================================================
   NOTIFICATIONS
   ========================================================= */

function initNotifications() {

    const markAll =
        document.getElementById(
            "markAllNotifications"
        );

    if (!markAll) return;


    markAll.addEventListener("click", function () {

        const notifications =
            document.querySelectorAll(
                ".delivery-notification.unread"
            );

        notifications.forEach(function (item) {
            item.classList.remove("unread");
        });

        showDeliveryMessage(
            "All notifications marked as read.",
            "success"
        );

    });

}


/* =========================================================
   PROFILE FORM
   ========================================================= */

function initProfileForm() {

    const form =
        document.getElementById(
            "deliveryProfileForm"
        );

    if (!form) return;


    form.addEventListener("submit", function (event) {

        event.preventDefault();

        showDeliveryMessage(
            "Profile updated successfully.",
            "success"
        );

    });

}


/* =========================================================
   BANK FORM
   ========================================================= */

function initBankForm() {

    const form =
        document.getElementById("bankForm");

    if (!form) return;


    form.addEventListener("submit", function (event) {

        event.preventDefault();

        showDeliveryMessage(
            "Bank details saved successfully.",
            "success"
        );

    });

}


/* =========================================================
   SUPPORT FORM
   ========================================================= */

function initSupportForm() {

    const form =
        document.getElementById(
            "deliverySupportForm"
        );

    if (!form) return;


    form.addEventListener("submit", function (event) {

        event.preventDefault();

        showDeliveryMessage(
            "Support ticket submitted successfully.",
            "success"
        );

        form.reset();

    });

}


/* =========================================================
   WITHDRAWAL
   ========================================================= */

function initWithdrawal() {

    const button =
        document.getElementById(
            "requestWithdrawal"
        );

    if (!button) return;


    button.addEventListener("click", function () {

        const amount = prompt(
            "Enter withdrawal amount:"
        );

        if (amount === null) {
            return;
        }

        const numericAmount =
            Number(amount);

        if (
            !numericAmount ||
            numericAmount <= 0
        ) {

            showDeliveryMessage(
                "Please enter a valid amount.",
                "error"
            );

            return;
        }


        showDeliveryMessage(
            `Withdrawal request of ₹${numericAmount} submitted.`,
            "success"
        );

    });

}


/* =========================================================
   AVAILABILITY
   ========================================================= */

function initAvailability() {

    const availability =
        document.getElementById(
            "deliveryAvailability"
        );

    if (!availability) return;


    availability.addEventListener(
        "change",
        function () {

            if (availability.checked) {

                showDeliveryMessage(
                    "You are now online.",
                    "success"
                );

            } else {

                showDeliveryMessage(
                    "You are now offline.",
                    "info"
                );

            }

        }
    );

}


/* =========================================================
   CONFIRM ACTIONS
   ========================================================= */

function initConfirmActions() {

    const elements =
        document.querySelectorAll(
            "[data-confirm]"
        );


    elements.forEach(function (element) {

        element.addEventListener(
            "click",
            function (event) {

                const message =
                    element.dataset.confirm ||
                    "Are you sure?";

                if (!confirm(message)) {
                    event.preventDefault();
                }

            }
        );

    });

}


/* =========================================================
   TOAST MESSAGE
   ========================================================= */

function showDeliveryMessage(
    message,
    type = "success"
) {

    let container =
        document.getElementById(
            "deliveryMessageContainer"
        );


    if (!container) {

        container =
            document.createElement("div");

        container.id =
            "deliveryMessageContainer";

        container.style.position =
            "fixed";

        container.style.top =
            "20px";

        container.style.right =
            "20px";

        container.style.zIndex =
            "99999";

        container.style.display =
            "flex";

        container.style.flexDirection =
            "column";

        container.style.gap =
            "10px";

        document.body.appendChild(container);

    }


    const messageBox =
        document.createElement("div");


    messageBox.textContent =
        message;


    let background =
        "#2563eb";

    if (type === "success") {
        background = "#16a34a";
    }

    if (type === "error") {
        background = "#dc2626";
    }

    if (type === "info") {
        background = "#0891b2";
    }


    messageBox.style.background =
        background;

    messageBox.style.color =
        "#fff";

    messageBox.style.padding =
        "12px 18px";

    messageBox.style.borderRadius =
        "8px";

    messageBox.style.fontSize =
        "14px";

    messageBox.style.fontWeight =
        "600";

    messageBox.style.boxShadow =
        "0 5px 20px rgba(0,0,0,0.15)";

    messageBox.style.opacity =
        "0";

    messageBox.style.transform =
        "translateX(20px)";

    messageBox.style.transition =
        "0.3s ease";


    container.appendChild(messageBox);


    setTimeout(function () {

        messageBox.style.opacity =
            "1";

        messageBox.style.transform =
            "translateX(0)";

    }, 10);


    setTimeout(function () {

        messageBox.style.opacity =
            "0";

        messageBox.style.transform =
            "translateX(20px)";

        setTimeout(function () {
            messageBox.remove();
        }, 300);

    }, 3000);

}


/* =========================================================
   IMAGE PREVIEW
   ========================================================= */

function initDeliveryImagePreview() {

    const input =
        document.getElementById(
            "deliveryImageInput"
        );

    const preview =
        document.getElementById(
            "deliveryImagePreview"
        );

    if (!input || !preview) return;


    input.addEventListener(
        "change",
        function () {

            const file =
                input.files[0];

            if (!file) return;


            const reader =
                new FileReader();


            reader.onload =
                function (event) {

                    preview.src =
                        event.target.result;

                    preview.style.display =
                        "block";

                };


            reader.readAsDataURL(file);

        }
    );

}


/* =========================================================
   AUTO HIDE ALERTS
   ========================================================= */

setTimeout(function () {

    const alerts =
        document.querySelectorAll(
            ".delivery-alert[data-auto-hide]"
        );

    alerts.forEach(function (alert) {

        alert.style.opacity = "0";

        setTimeout(function () {
            alert.remove();
        }, 300);

    });

}, 4000);