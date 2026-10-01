function initAjaxWishlist() {
    document.querySelectorAll('.ajax-wishlist-form').forEach(function (form) {
        const button = form.querySelector('.wishlist-btn');
        const icon = button && button.querySelector('i');
        if (!button || !icon) return;

        form.addEventListener('submit', async function (event) {
            event.preventDefault();
            if (button.disabled) return;
            button.disabled = true;

            try {
                const response = await fetch(form.getAttribute('action'), {
                    method: 'POST',
                    body: new FormData(form),
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    credentials: 'same-origin',
                });
                const result = await response.json();
                if (!response.ok || !result.success) {
                    throw new Error(result.error || 'Could not update your wishlist.');
                }

                button.classList.toggle('active', result.added);
                button.classList.toggle('in-wishlist', result.added);
                icon.className = result.added ? 'fa-solid fa-heart' : 'fa-regular fa-heart';
                icon.style.setProperty('color', result.added ? '#ef4444' : '', 'important');
                button.title = result.added ? 'Remove from Wishlist' : 'Add to Wishlist';
                button.setAttribute('aria-label', button.title);
            } catch (error) {
                if (typeof showToast === 'function') showToast(error.message || 'Could not update your wishlist.', 'error');
            } finally {
                button.disabled = false;
            }
        });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAjaxWishlist, { once: true });
} else {
    initAjaxWishlist();
}