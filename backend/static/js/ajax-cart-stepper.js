function updateCartCountBadge(count) {
    const badge = document.querySelector('[data-cart-count-badge]');
    if (!badge) return;
    const cartCount = Math.max(0, Number(count) || 0);
    badge.dataset.cartCount = String(cartCount);
    badge.textContent = cartCount > 99 ? '99+' : String(cartCount);
    badge.setAttribute('aria-label', cartCount + ' items in cart');
    badge.hidden = cartCount === 0;
}

function initAjaxCartSteppers() {
    document.querySelectorAll('.ajax-cart-form').forEach(function (form) {
        const addButton = form.querySelector('[data-cart-add]');
        const stepper = form.querySelector('[data-cart-stepper]');
        const quantityLabel = form.querySelector('[data-cart-quantity]');
        const actionInput = form.querySelector('[data-cart-action]');
        const incrementButton = form.querySelector('[data-cart-increment]');
        const decrementButton = form.querySelector('[data-cart-decrement]');
        const productId = form.querySelector('[name="product_id"]').value;
        const quantityStorageKey = 'shopverse-cart-quantity-' + productId;
        const stockLimit = Number(form.dataset.stock || 0);
        let quantity = Number(form.dataset.quantity || 0);
        let isUpdating = false;

        function setQuantity(value) {
            quantity = Math.max(0, Math.min(stockLimit, Number(value) || 0));
            form.dataset.quantity = String(quantity);
            renderQuantity();
        }

        function broadcastQuantity() {
            const value = String(quantity);
            try {
                localStorage.setItem(quantityStorageKey, value);
            } catch (error) {
                // The current page still updates even when storage is unavailable.
            }
            window.dispatchEvent(new CustomEvent('shopverse:cart-quantity-change', {
                detail: { productId: productId, quantity: quantity },
            }));
        }

        function readStoredQuantity() {
            try {
                const storedQuantity = localStorage.getItem(quantityStorageKey);
                if (storedQuantity !== null) setQuantity(storedQuantity);
            } catch (error) {
                return;
            }
        }

        function renderQuantity() {
            quantityLabel.textContent = quantity;
            addButton.style.display = quantity > 0 ? 'none' : 'flex';
            stepper.style.display = quantity > 0 ? 'flex' : 'none';
            addButton.disabled = isUpdating || stockLimit < 1;
            incrementButton.disabled = isUpdating || quantity >= stockLimit;
            decrementButton.disabled = isUpdating;
        }

        async function updateCart(action, nextQuantity) {
            if (isUpdating) return;
            isUpdating = true;
            renderQuantity();
            actionInput.value = action;
            const data = new FormData(form);
            if (nextQuantity !== undefined) data.set('quantity', String(nextQuantity));

            try {
                const response = await fetch(form.getAttribute('action'), {
                    method: 'POST',
                    body: data,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    credentials: 'same-origin',
                });
                const result = await response.json();
                if (response.ok) {
                    setQuantity(result.quantity);
                    if (result.cart_count !== undefined) updateCartCountBadge(result.cart_count);
                    broadcastQuantity();
                } else {
                    if (result.quantity !== undefined) setQuantity(result.quantity);
                    if (typeof showToast === 'function') showToast(result.error || 'Could not update your cart.', 'error');
                }
            } catch (error) {
                if (typeof showToast === 'function') showToast('Could not update your cart. Please try again.', 'error');
            } finally {
                isUpdating = false;
                renderQuantity();
            }
        }

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            updateCart('add');
        });
        incrementButton.addEventListener('click', function () {
            if (quantity < stockLimit) updateCart('update_qty', quantity + 1);
        });
        decrementButton.addEventListener('click', function () {
            if (quantity > 0) updateCart('update_qty', quantity - 1);
        });
        window.addEventListener('storage', function (event) {
            if (event.key === quantityStorageKey && event.newValue !== null) {
                setQuantity(event.newValue);
            }
        });
        window.addEventListener('shopverse:cart-quantity-change', function (event) {
            if (event.detail.productId === productId) setQuantity(event.detail.quantity);
        });
        window.addEventListener('pageshow', readStoredQuantity);
        renderQuantity();
        broadcastQuantity();
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAjaxCartSteppers, { once: true });
} else {
    initAjaxCartSteppers();
}