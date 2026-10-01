/* =========================================
   ADMIN PANEL JAVASCRIPT
========================================= */

document.addEventListener("DOMContentLoaded", function () {

    initAdminSearch();
    initConfirmButtons();
    initStatusActions();
    initDeleteActions();
    initAdminForms();
    initAdminSettings();
    initNotifications();
    initAIChat();
    initSelectAll();
    initAutoHideAlerts();

});


/* =========================================
   CSRF TOKEN
========================================= */

function getCSRFToken() {

    const csrfInput = document.querySelector(
        '[name="csrfmiddlewaretoken"]'
    );

    if (csrfInput) {
        return csrfInput.value;
    }

    const cookie = document.cookie
        .split("; ")
        .find(row => row.startsWith("csrftoken="));

    if (cookie) {
        return cookie.split("=")[1];
    }

    return "";
}


/* =========================================
   SEARCH
========================================= */

function initAdminSearch() {

    const searchInputs = document.querySelectorAll(
        "[data-admin-search]"
    );

    searchInputs.forEach(input => {

        input.addEventListener("input", function () {

            const searchValue = this.value
                .toLowerCase()
                .trim();

            const targetSelector =
                this.getAttribute("data-admin-search");

            const target = document.querySelector(targetSelector);

            if (!target) return;

            const rows = target.querySelectorAll(
                "tbody tr"
            );

            rows.forEach(row => {

                const text = row.innerText
                    .toLowerCase();

                row.style.display =
                    text.includes(searchValue)
                        ? ""
                        : "none";

            });

        });

    });
}


/* =========================================
   CONFIRM BUTTONS
========================================= */

function initConfirmButtons() {

    document.querySelectorAll(
        "[data-confirm]"
    ).forEach(button => {

        button.addEventListener("click", function (event) {

            const message =
                this.getAttribute("data-confirm") ||
                "Are you sure?";

            if (!confirm(message)) {
                event.preventDefault();
            }

        });

    });
}


/* =========================================
   STATUS ACTIONS
========================================= */

function initStatusActions() {

    document.querySelectorAll(
        "[data-status-action]"
    ).forEach(button => {

        button.addEventListener("click", function () {

            const action =
                this.getAttribute("data-status-action");

            const id =
                this.getAttribute("data-id");

            if (!id) {
                showAdminMessage(
                    "Record ID not found.",
                    "error"
                );
                return;
            }

            /*
             * Demo mode.
             * Later this will call Django API.
             */

            if (action === "approve") {

                showAdminMessage(
                    "Record approved successfully.",
                    "success"
                );

            }

            if (action === "reject") {

                showAdminMessage(
                    "Record rejected.",
                    "warning"
                );

            }

            if (action === "activate") {

                showAdminMessage(
                    "Record activated.",
                    "success"
                );

            }

            if (action === "deactivate") {

                showAdminMessage(
                    "Record deactivated.",
                    "warning"
                );

            }

        });

    });
}


/* =========================================
   DELETE ACTIONS
========================================= */

function initDeleteActions() {

    document.querySelectorAll(
        "[data-delete]"
    ).forEach(button => {

        button.addEventListener("click", function () {

            const id =
                this.getAttribute("data-delete");

            if (!id) return;

            const confirmed = confirm(
                "Are you sure you want to delete this record?"
            );

            if (!confirmed) return;

            /*
             * Demo mode.
             * Later Django DELETE/API request.
             */

            const row =
                this.closest("tr");

            if (row) {
                row.remove();
            }

            showAdminMessage(
                "Record deleted successfully.",
                "success"
            );

        });

    });
}


/* =========================================
   ADMIN FORMS
========================================= */

function initAdminForms() {

    const forms = document.querySelectorAll(
        ".admin-form"
    );

    forms.forEach(form => {

        form.addEventListener("submit", function (event) {

            /*
             * If form has normal Django action,
             * don't stop submission.
             */

            const demoForm =
                form.hasAttribute("data-demo");

            if (!demoForm) {
                return;
            }

            event.preventDefault();

            showAdminMessage(
                "Changes saved successfully.",
                "success"
            );

        });

    });
}


/* =========================================
   ADMIN SETTINGS
========================================= */

function initAdminSettings() {

    const saveButton =
        document.querySelector("#saveAdminSettings");

    if (!saveButton) return;

    saveButton.addEventListener(
        "click",
        function () {

            showAdminMessage(
                "Admin settings saved successfully.",
                "success"
            );

        }
    );
}


/* =========================================
   NOTIFICATIONS
========================================= */

function initNotifications() {

    const markAll =
        document.querySelector("#markAllNotifications");

    if (!markAll) return;

    markAll.addEventListener(
        "click",
        function () {

            document
                .querySelectorAll(
                    ".admin-notification.unread"
                )
                .forEach(notification => {

                    notification.classList.remove(
                        "unread"
                    );

                });

            showAdminMessage(
                "All notifications marked as read.",
                "success"
            );

        }
    );
}


/* =========================================
   SELECT ALL CHECKBOX
========================================= */

function initSelectAll() {

    const selectAll =
        document.querySelector("#selectAll");

    if (!selectAll) return;

    selectAll.addEventListener(
        "change",
        function () {

            const checkboxes =
                document.querySelectorAll(
                    ".row-checkbox"
                );

            checkboxes.forEach(
                checkbox => {
                    checkbox.checked =
                        selectAll.checked;
                }
            );

        }
    );
}


/* =========================================
   AI CHAT
========================================= */

function initAIChat() {

    const form =
        document.querySelector("#adminAIForm");

    const input =
        document.querySelector("#adminAIInput");

    const messages =
        document.querySelector("#adminAIMessages");

    if (!form || !input || !messages) {
        return;
    }

    form.addEventListener(
        "submit",
        function (event) {

            event.preventDefault();

            const message =
                input.value.trim();

            if (!message) return;

            addAIMessage(
                message,
                "user"
            );

            input.value = "";

            /*
             * Demo AI response.
             * Later connect OpenAI/Django API here.
             */

            setTimeout(function () {

                addAIMessage(
                    "I received your request. AI backend connection will be added next.",
                    "bot"
                );

            }, 600);

        }
    );
}


function addAIMessage(
    message,
    type
) {

    const messages =
        document.querySelector(
            "#adminAIMessages"
        );

    if (!messages) return;

    const div =
        document.createElement("div");

    div.className =
        "admin-ai-message " + type;

    div.textContent =
        message;

    messages.appendChild(div);

    messages.scrollTop =
        messages.scrollHeight;
}


/* =========================================
   ADMIN TOAST MESSAGE
========================================= */

function showAdminMessage(
    message,
    type = "success"
) {

    let container =
        document.querySelector(
            "#adminMessageContainer"
        );

    if (!container) {

        container =
            document.createElement("div");

        container.id =
            "adminMessageContainer";

        container.style.position =
            "fixed";

        container.style.top =
            "20px";

        container.style.right =
            "20px";

        container.style.zIndex =
            "99999";

        container.style.width =
            "320px";

        document.body.appendChild(
            container
        );
    }

    const messageBox =
        document.createElement("div");

    messageBox.className =
        "admin-alert " + type;

    messageBox.style.marginBottom =
        "10px";

    messageBox.style.boxShadow =
        "0 5px 20px rgba(0,0,0,0.12)";

    messageBox.textContent =
        message;

    container.appendChild(
        messageBox
    );

    setTimeout(function () {

        messageBox.style.opacity =
            "0";

        messageBox.style.transition =
            "0.3s";

        setTimeout(function () {

            messageBox.remove();

        }, 300);

    }, 3000);
}


/* =========================================
   AUTO HIDE ALERTS
========================================= */

function initAutoHideAlerts() {

    document.querySelectorAll(
        ".admin-alert[data-auto-hide]"
    ).forEach(alert => {

        setTimeout(function () {

            alert.style.opacity =
                "0";

            alert.style.transition =
                "0.3s";

            setTimeout(function () {
                alert.remove();
            }, 300);

        }, 4000);

    });
}


/* =========================================
   IMAGE PREVIEW
========================================= */

function initAdminImagePreview() {

    const input =
        document.querySelector(
            "#adminImageInput"
        );

    const preview =
        document.querySelector(
            "#adminImagePreview"
        );

    if (!input || !preview) return;

    input.addEventListener(
        "change",
        function () {

            const file =
                this.files[0];

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


/* =========================================
   COPY TEXT
========================================= */

function copyAdminText(text) {

    navigator.clipboard.writeText(text)
        .then(function () {

            showAdminMessage(
                "Copied successfully.",
                "success"
            );

        })
        .catch(function () {

            showAdminMessage(
                "Unable to copy.",
                "error"
            );

        });
}