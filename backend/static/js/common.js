/* =========================================================
   E-COMMERCE - COMMON JS
   ========================================================= */


/* =========================
   PAGE LOADER
   ========================= */

document.addEventListener("DOMContentLoaded", function () {

    const loader = document.getElementById("pageLoader");

    if (loader) {

        setTimeout(function () {

            loader.classList.add("hidden");

        }, 400);

    }

});


/* =========================
   MOBILE MENU
   ========================= */

document.addEventListener("DOMContentLoaded", function () {

    const menuButton =
        document.getElementById("mobileMenuBtn");

    const menu =
        document.querySelector(".navbar-menu");


    if (menuButton && menu) {

        menuButton.addEventListener("click", function () {

            menu.classList.toggle("active");


            const icon =
                menuButton.querySelector("i");


            if (menu.classList.contains("active")) {

                icon.classList.remove("fa-bars");

                icon.classList.add("fa-xmark");

            } else {

                icon.classList.remove("fa-xmark");

                icon.classList.add("fa-bars");

            }

        });


        /* Close menu after clicking link */

        const menuLinks =
            menu.querySelectorAll("a");


        menuLinks.forEach(function (link) {

            link.addEventListener("click", function () {

                menu.classList.remove("active");

                const icon =
                    menuButton.querySelector("i");


                icon.classList.remove("fa-xmark");

                icon.classList.add("fa-bars");

            });

        });

    }

});


/* =========================
   AUTO CLOSE MESSAGES
   ========================= */

document.addEventListener("DOMContentLoaded", function () {

    const messages =
        document.querySelectorAll(".alert");


    messages.forEach(function (message) {

        setTimeout(function () {

            message.style.opacity = "0";

            message.style.transform =
                "translateX(20px)";

            setTimeout(function () {

                message.remove();

            }, 300);

        }, 5000);

    });

});


/* =========================
   CART COUNT
   ========================= */

function updateCartCount(count) {

    const cartCount =
        document.querySelector(".cart-count");


    if (!cartCount) {
        return;
    }


    count = Number(count) || 0;


    cartCount.textContent = count;


    if (count > 0) {

        cartCount.style.display = "flex";

    } else {

        cartCount.style.display = "none";

    }

}


/* =========================
   GET CART COUNT
   ========================= */

function getCartCount() {

    const cart =
        JSON.parse(
            localStorage.getItem("cart") || "[]"
        );


    updateCartCount(cart.length);

}


/* =========================
   LOCAL CART
   ========================= */

function addToLocalCart(product) {

    let cart =
        JSON.parse(
            localStorage.getItem("cart") || "[]"
        );


    const existingProduct =
        cart.find(
            item => item.id === product.id
        );


    if (existingProduct) {

        existingProduct.quantity =
            (existingProduct.quantity || 1) + 1;

    } else {

        cart.push({

            ...product,

            quantity: 1

        });

    }


    localStorage.setItem(
        "cart",
        JSON.stringify(cart)
    );


    updateCartCount(cart.length);

}


/* =========================
   REMOVE FROM LOCAL CART
   ========================= */

function removeFromLocalCart(productId) {

    let cart =
        JSON.parse(
            localStorage.getItem("cart") || "[]"
        );


    cart =
        cart.filter(
            item => item.id !== productId
        );


    localStorage.setItem(
        "cart",
        JSON.stringify(cart)
    );


    updateCartCount(cart.length);

}


/* =========================
   GET LOCAL CART
   ========================= */

function getLocalCart() {

    return JSON.parse(
        localStorage.getItem("cart") || "[]"
    );

}


/* =========================
   CLEAR CART
   ========================= */

function clearLocalCart() {

    localStorage.removeItem("cart");

    updateCartCount(0);

}


/* =========================
   SEARCH
   ========================= */

document.addEventListener("DOMContentLoaded", function () {

    const searchInput =
        document.querySelector(
            '.navbar-search input[name="q"]'
        );


    if (!searchInput) {
        return;
    }


    searchInput.addEventListener(
        "keydown",
        function (event) {

            if (event.key === "Enter") {

                const query =
                    searchInput.value.trim();


                if (!query) {

                    event.preventDefault();

                    return;

                }

            }

        }
    );

});


/* =========================
   PASSWORD TOGGLE
   ========================= */

function togglePassword(inputId) {

    const input =
        document.getElementById(inputId);


    if (!input) {
        return;
    }


    const button =
        input.parentElement.querySelector(
            ".password-toggle"
        );


    const icon =
        button
            ? button.querySelector("i")
            : null;


    if (input.type === "password") {

        input.type = "text";


        if (icon) {

            icon.classList.remove(
                "fa-eye"
            );

            icon.classList.add(
                "fa-eye-slash"
            );

        }

    } else {

        input.type = "password";


        if (icon) {

            icon.classList.remove(
                "fa-eye-slash"
            );

            icon.classList.add(
                "fa-eye"
            );

        }

    }

}


/* =========================
   CONFIRM PASSWORD
   ========================= */

function checkPasswords(
    passwordId,
    confirmPasswordId
) {

    const password =
        document.getElementById(passwordId);

    const confirmPassword =
        document.getElementById(
            confirmPasswordId
        );


    if (!password || !confirmPassword) {

        return false;

    }


    if (
        password.value !==
        confirmPassword.value
    ) {

        confirmPassword.setCustomValidity(
            "Passwords do not match."
        );

        return false;

    }


    confirmPassword.setCustomValidity("");

    return true;

}


/* =========================
   CONFIRM PASSWORD LIVE CHECK
   ========================= */

document.addEventListener("DOMContentLoaded", function () {

    const password =
        document.getElementById(
            "registerPassword"
        );

    const confirmPassword =
        document.getElementById(
            "confirmPassword"
        );


    if (password && confirmPassword) {

        confirmPassword.addEventListener(
            "input",
            function () {

                checkPasswords(
                    "registerPassword",
                    "confirmPassword"
                );

            }
        );

    }

});


/* =========================
   EMAIL VALIDATION
   ========================= */

function isValidEmail(email) {

    const pattern =
        /^[^\s@]+@[^\s@]+\.[^\s@]+$/;


    return pattern.test(
        String(email).toLowerCase()
    );

}


/* =========================
   PHONE VALIDATION
   ========================= */

function isValidPhone(phone) {

    const cleaned =
        String(phone)
            .replace(/\s/g, "")
            .replace(/-/g, "");


    return /^[+]?[0-9]{10,15}$/.test(
        cleaned
    );

}


/* =========================
   FORMAT CURRENCY
   ========================= */

function formatCurrency(amount) {

    amount = Number(amount) || 0;


    return new Intl.NumberFormat(
        "en-IN",
        {
            style: "currency",
            currency: "INR",
            maximumFractionDigits: 2
        }
    ).format(amount);

}


/* =========================
   SHOW NOTIFICATION
   ========================= */

function showNotification(
    message,
    type = "info"
) {

    const container =
        document.querySelector(
            ".messages-container"
        );


    if (!container) {
        return;
    }


    const alert =
        document.createElement("div");


    alert.className =
        `alert alert-${type}`;


    alert.innerHTML = `

        <span>${message}</span>

        <button
            type="button"
            class="close-message"
            onclick="this.parentElement.remove()">

            <i class="fa-solid fa-xmark"></i>

        </button>

    `;


    container.appendChild(alert);


    setTimeout(function () {

        alert.remove();

    }, 5000);

}


/* =========================
   INITIALIZE
   ========================= */

document.addEventListener(
    "DOMContentLoaded",
    function () {

        getCartCount();

    }
);