/**
 * ULTRA-MODERN E-COMMERCE JAVASCRIPT SUITE
 * Dual-Theme, English/Hindi Translator, AI Chatbot with "Hi" Command Engine, Voice Search,
 * Audio Chime, Leaflet Live Map, Image Zoom & Toast Alerts.
 */

// Add a subtle pointer spotlight to dashboard metric cards.
function initKpiCards() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    document.querySelectorAll('.kpi-card').forEach((card) => {
        card.addEventListener('pointermove', (event) => {
            const bounds = card.getBoundingClientRect();
            const x = ((event.clientX - bounds.left) / bounds.width) * 100;
            const y = ((event.clientY - bounds.top) / bounds.height) * 100;
            card.style.setProperty('--pointer-x', `${x}%`);
            card.style.setProperty('--pointer-y', `${y}%`);
        });

        card.addEventListener('pointerleave', () => {
            card.style.setProperty('--pointer-x', '50%');
            card.style.setProperty('--pointer-y', '50%');
        });
    });
}

// ==========================================
// 1. THEME ENGINE (LIGHT / DARK)
// ==========================================
function initTheme() {
    const savedTheme = localStorage.getItem('ecom_theme') || 
        (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', savedTheme);
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-theme');
    } else {
        document.body.classList.remove('dark-theme');
    }
    updateThemeIcon(savedTheme);
}

function initCustomerFilterMenus() {
    const selects = document.querySelectorAll('.customer-filter-select');
    if (!selects.length) return;

    const closeMenus = () => {
        document.querySelectorAll('.customer-filter-menu.open').forEach((menu) => menu.classList.remove('open'));
    };

    selects.forEach((select) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'customer-filter-menu';
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'customer-filter-menu-button';
        button.setAttribute('aria-expanded', 'false');
        const list = document.createElement('div');
        list.className = 'customer-filter-menu-list';
        list.setAttribute('role', 'listbox');

        Array.from(select.options).forEach((option) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'customer-filter-menu-item';
            item.textContent = option.textContent;
            item.setAttribute('role', 'option');
            item.setAttribute('aria-selected', option.selected ? 'true' : 'false');
            item.addEventListener('click', () => {
                select.value = option.value;
                button.textContent = option.textContent;
                closeMenus();
                select.form.submit();
            });
            list.appendChild(item);
        });

        button.textContent = select.options[select.selectedIndex]?.textContent || '';
        button.addEventListener('click', (event) => {
            event.stopPropagation();
            const isOpen = wrapper.classList.contains('open');
            closeMenus();
            wrapper.classList.toggle('open', !isOpen);
            button.setAttribute('aria-expanded', String(!isOpen));
        });

        wrapper.append(button, list);
        select.classList.add('customer-filter-select-hidden');
        select.style.display = 'none';
        select.parentNode.insertBefore(wrapper, select);
    });

    document.addEventListener('click', closeMenus);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    if (next === 'dark') {
        document.body.classList.add('dark-theme');
    } else {
        document.body.classList.remove('dark-theme');
    }
    localStorage.setItem('ecom_theme', next);
    updateThemeIcon(next);
    showToast(next === 'dark' ? 'Dark Mode Activated 🌙' : 'Light Mode Activated ☀️', 'info');
}

function updateThemeIcon(theme) {
    const icon1 = document.getElementById('themeIcon');
    const icon2 = document.getElementById('publicThemeIcon');
    const cls = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
    if (icon1) icon1.className = cls;
    if (icon2) icon2.className = cls;
}

// ==========================================
// 2. LANGUAGE ENGINE (ENGLISH ⇄ HINDI)
// ==========================================
const TRANSLATIONS = {
    en: {
        'dashboard': 'Dashboard',
        'products': 'Products',
        'categories': 'Categories',
        'search': 'Search',
        'cart': 'My Cart',
        'wishlist': 'Wishlist',
        'orders': 'My Orders',
        'track_order': 'Track Order',
        'returns': 'Returns & Refunds',
        'coupons': 'Coupons',
        'reviews': 'Reviews',
        'notifications': 'Notifications',
        'profile': 'Profile',
        'addresses': 'My Addresses',
        'payments': 'Payments',
        'settings': 'Settings',
        'logout': 'Logout',
        'my_store': 'My Store',
        'inventory': 'Inventory',
        'shipping': 'Shipping',
        'earnings': 'Earnings',
        'offers': 'Offers',
        'customers': 'Customers',
        'reports': 'Reports',
        'online': 'ONLINE',
        'offline': 'OFFLINE',
        'active_delivery': 'Active Delivery',
        'navigation': 'Navigation',
        'delivery_history': 'Delivery History',
        'ratings': 'Ratings',
        'documents': 'Documents',
        'bank_upi': 'Bank / UPI',
        'sellers': 'Sellers',
        'delivery_partners': 'Delivery Partners',
        'commission': 'Commission',
        'support': 'Support',
        'admin_users': 'Admin Users',
        'search_placeholder': 'Search products, brands, deals...',
        'add_to_cart': 'Add to Cart',
        'buy_now': 'Buy Now',
        'free_delivery': 'Free Delivery',
        'write_review': 'Write a Review',
        'apply_coupon': 'Apply Coupon',
        'download_invoice': 'Download Invoice',
        'otp_verify': 'Delivery OTP',
    },
    hi: {
        'dashboard': 'डैशबोर्ड',
        'products': 'प्रोडक्ट्स',
        'categories': 'कैटेगरीज़',
        'search': 'सर्च करें',
        'cart': 'मेरी कार्ट',
        'wishlist': 'विशलिस्ट',
        'orders': 'मेरे आर्डर्स',
        'track_order': 'आर्डर ट्रैक करें',
        'returns': 'रिटर्न व रिफंड',
        'coupons': 'कूपन्स',
        'reviews': 'समीक्षाएं (रिव्यूज)',
        'notifications': 'सूचनाएं (नोटिफिकेशन)',
        'profile': 'प्रोफ़ाइल',
        'addresses': 'मेरे पते',
        'payments': 'भुगतान (पेमेंट्स)',
        'settings': 'सेटिंग्स',
        'logout': 'लॉगआउट',
        'my_store': 'मेरा स्टोर',
        'inventory': 'इन्वेंट्री / स्टॉक',
        'shipping': 'शिपिंग व डिस्पैच',
        'earnings': 'कुल कमाई (Earnings)',
        'offers': 'ऑफर्स व डिस्काउंट',
        'customers': 'ग्राहक (कस्टमर्स)',
        'reports': 'रिपोर्ट्स व आंकड़े',
        'online': 'ऑनलाइन (ड्यूटी चालू)',
        'offline': 'ऑफलाइन',
        'active_delivery': 'सक्रिय डिलीवरी',
        'navigation': 'लाइव नेविगेशन',
        'delivery_history': 'डिलीवरी इतिहास',
        'ratings': 'रेटिंग्स व रिव्यू',
        'documents': 'दस्तावेज़ (डॉक्यूमेंट्स)',
        'bank_upi': 'बैंक खाता / UPI',
        'sellers': 'विक्रेता (सेलर्स)',
        'delivery_partners': 'डिलीवरी पार्टनर्स',
        'commission': 'कमीशन सेटिंग्स',
        'support': 'सहायता / टिकट्स',
        'admin_users': 'एडमिन यूज़र्स',
        'search_placeholder': 'सामान, ब्रांड या ऑफर्स खोजें...',
        'add_to_cart': 'कार्ट में जोड़ें',
        'buy_now': 'तुरंत खरीदें',
        'free_delivery': 'मुफ़्त डिलीवरी',
        'write_review': 'रिव्यू लिखें',
        'apply_coupon': 'कूपन लागू करें',
        'download_invoice': 'इनवॉइस डाउनलोड करें',
        'otp_verify': 'डिलीवरी सत्यापन OTP',
    }
};

function initLanguage() {
    const lang = localStorage.getItem('ecom_lang') || 'en';
    applyLanguage(lang);
}

function toggleLanguage() {
    const current = localStorage.getItem('ecom_lang') || 'en';
    const next = current === 'en' ? 'hi' : 'en';
    localStorage.setItem('ecom_lang', next);
    applyLanguage(next);
    showToast(next === 'hi' ? 'भाषा: हिन्दी सेट की गई 🇮🇳' : 'Language set to English 🇬🇧', 'info');
}

function applyLanguage(lang) {
    const label1 = document.getElementById('langLabel');
    const label2 = document.getElementById('publicLangLabel');
    const text = lang === 'hi' ? 'हिन्दी' : 'English';
    if (label1) label1.textContent = text;
    if (label2) label2.textContent = text;

    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (TRANSLATIONS[lang] && TRANSLATIONS[lang][key]) {
            if (el.tagName === 'INPUT' && el.getAttribute('placeholder')) {
                el.placeholder = TRANSLATIONS[lang][key];
            } else {
                el.textContent = TRANSLATIONS[lang][key];
            }
        }
    });
}

// ==========================================
// 3. AUDIO ALERT CHIME (WEB AUDIO API)
// ==========================================
function playChime(type = 'success') {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        if (type === 'order' || type === 'success') {
            osc.frequency.setValueAtTime(587.33, ctx.currentTime);
            osc.frequency.setValueAtTime(880, ctx.currentTime + 0.1);
            gain.gain.setValueAtTime(0.2, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.35);
        } else if (type === 'alert') {
            osc.frequency.setValueAtTime(440, ctx.currentTime);
            osc.frequency.setValueAtTime(659.25, ctx.currentTime + 0.15);
            gain.gain.setValueAtTime(0.25, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.4);
        }
    } catch (e) {}
}

// ==========================================
// 4. TOAST NOTIFICATION DISPATCHER
// ==========================================
function showToast(message, type = 'success') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast-msg ${type}`;
    const icon = type === 'success' ? 'fa-circle-check' : (type === 'danger' ? 'fa-circle-xmark' : 'fa-bell');
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
    container.appendChild(toast);

    playChime(type === 'success' ? 'success' : 'alert');

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(40px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ==========================================
// 5. VOICE SEARCH (WEB SPEECH API)
// ==========================================
function startVoiceSearch(inputSelector = '#globalSearchInput') {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        showToast('Voice search not supported in this browser. Please use Chrome.', 'warning');
        return;
    }

    const rec = new SpeechRecognition();
    const btn = document.getElementById('voiceSearchBtn');
    const input = document.querySelector(inputSelector);

    rec.lang = localStorage.getItem('ecom_lang') === 'hi' ? 'hi-IN' : 'en-IN';
    rec.continuous = false;
    rec.interimResults = false;

    if (btn) btn.classList.add('recording');
    showToast('Listening... Speak now!', 'info');

    rec.onresult = (e) => {
        const text = e.results[0][0].transcript;
        if (input) {
            input.value = text;
            showToast(`Searching for: "${text}"`, 'success');
            setTimeout(() => {
                const form = input.closest('form');
                if (form) form.submit();
            }, 800);
        }
    };

    rec.onerror = () => {
        if (btn) btn.classList.remove('recording');
        showToast('Could not recognize voice. Please try again.', 'danger');
    };

    rec.onend = () => {
        if (btn) btn.classList.remove('recording');
    };

    rec.start();
}

// ==========================================
// 6. AI CHATBOT WITH "HI" COMMAND ENGINE
// ==========================================
function toggleAiChat() {
    const win = document.getElementById('aiChatWindow');
    if (win) {
        if (win.style.display === 'none' || !win.style.display) {
            win.style.display = 'flex';
            const input = document.getElementById('aiChatInput');
            if (input) input.focus();
        } else {
            win.style.display = 'none';
        }
    }
}

function sendAiPrompt(promptText) {
    const input = document.getElementById('aiChatInput');
    const text = promptText || (input ? input.value.trim() : '');
    if (!text) return;
    if (input) input.value = '';

    const msgContainer = document.getElementById('aiChatMessages');
    if (!msgContainer) return;

    // Append User Bubble
    const userBubble = document.createElement('div');
    userBubble.className = 'chat-bubble user';
    userBubble.textContent = text;
    msgContainer.appendChild(userBubble);
    msgContainer.scrollTop = msgContainer.scrollHeight;

    // Typing bot placeholder
    const botBubble = document.createElement('div');
    botBubble.className = 'chat-bubble bot';
    botBubble.innerHTML = '<i class="fa-solid fa-ellipsis fa-fade"></i> Processing...';
    msgContainer.appendChild(botBubble);
    msgContainer.scrollTop = msgContainer.scrollHeight;

    setTimeout(() => {
        const reply = generateSmartAiResponse(text);
        botBubble.innerHTML = reply;
        msgContainer.scrollTop = msgContainer.scrollHeight;
        playChime('success');
    }, 600);
}

function generateSmartAiResponse(q) {
    const lower = q.toLowerCase();
    const role = document.body.dataset.role || 'public';
    const destinations = {
        public: {
            orders: '/auth/login/', invoice: '/auth/login/', referrals: '/auth/register/',
            returns: '/refund-policy/', offers: '/', payments: '/faq/', support: '/help/',
            products: '/customer/products/', inventory: '/customer/products/', payouts: '/auth/login/',
            reports: '/faq/', addresses: '/auth/login/', profile: '/auth/login/',
            sellerProducts: '/seller-register/', shipping: '/shipping-policy/',
        },
        customer: {
            orders: '/customer/orders/', invoice: '/customer/orders/', referrals: '/customer/rewards/',
            returns: '/customer/returns/', offers: '/customer/coupons/', payments: '/customer/payments/',
            support: '/customer/support/', products: '/customer/products/', inventory: '/customer/products/',
            payouts: '/customer/payments/', reports: '/customer/reports/', addresses: '/customer/addresses/',
            profile: '/customer/profile/', sellerProducts: '/customer/products/', shipping: '/customer/track-order/',
        },
        seller: {
            orders: '/seller/orders/', invoice: '/seller/orders/', referrals: '/seller/settings/',
            returns: '/seller/returns/', offers: '/seller/offers/', payments: '/seller/earnings/',
            support: '/seller/support/', products: '/seller/products/', inventory: '/seller/inventory/',
            payouts: '/seller/withdrawals/', reports: '/seller/reports/', addresses: '/seller/settings/',
            profile: '/seller/settings/', sellerProducts: '/seller/products/add/', shipping: '/seller/shipping/',
        },
        delivery: {
            orders: '/delivery/active-delivery/', invoice: '/delivery/delivery-history/', referrals: '/delivery/profile/',
            returns: '/delivery/support/', offers: '/', payments: '/delivery/earnings/',
            support: '/delivery/support/', products: '/delivery/active-delivery/', inventory: '/delivery/active-delivery/',
            payouts: '/delivery/withdrawals/', reports: '/delivery/reports/', addresses: '/delivery/profile/',
            profile: '/delivery/profile/', sellerProducts: '/delivery/active-delivery/', shipping: '/delivery/navigation/',
        },
        admin: {
            orders: '/admin-panel/orders/', invoice: '/admin-panel/orders/', referrals: '/admin-panel/customers/',
            returns: '/admin-panel/returns/', offers: '/admin-panel/coupons/', payments: '/admin-panel/payments/',
            support: '/admin-panel/tickets/', products: '/admin-panel/products/', inventory: '/admin-panel/products/',
            payouts: '/admin-panel/payouts/', reports: '/admin-panel/analytics/', addresses: '/admin-panel/customers/',
            profile: '/admin-panel/settings/', sellerProducts: '/admin-panel/products/', shipping: '/admin-panel/live-operations/',
        },
    };
    const links = destinations[role] || destinations.public;
    const pageLink = (destination, label) => `<a href="${links[destination]}">${label}</a>`;

    // Greeting workflow: each surface gets commands relevant to its role.
    if (lower === 'hi' || lower === 'hello' || lower === 'namaste' || lower === 'hey') {
        const commands = {
            public: [
                ['🛍️', 'Browse products', 'Show trending products'],
                ['🎟️', 'View offers', 'Show active coupons and promo codes'],
                ['🚚', 'How delivery works', 'Explain delivery tracking and OTP'],
                ['💬', 'Contact support', 'How do I contact ShopVerse support?'],
                ['🔐', 'Account help', 'How do I create an account?'],
                ['💳', 'Payment help', 'What payment methods are supported?'],
                ['📦', 'Order process', 'How do I place an order?'],
                ['↩️', 'Refund policy', 'Explain the refund policy'],
                ['🔒', 'Secure checkout', 'Is checkout secure?'],
                ['📞', 'Help center', 'Show customer help options'],
            ],
            customer: [
                ['📦', 'Track my order', 'Track my live order'],
                ['💳', 'Wallet & payments', 'Show my wallet and payment options'],
                ['🔄', 'Returns', 'How do returns and replacements work?'],
                ['🎟️', 'Coupons', 'Show active coupons and promo codes'],
                ['⭐', 'Product reviews', 'How can I review a delivered product?'],
                ['🤝', 'Refer & Earn', 'How does Refer and Earn work?'],
                ['📍', 'Addresses', 'How do I manage delivery addresses?'],
                ['🔐', 'Account settings', 'How do I update my profile?'],
                ['📄', 'Invoice', 'How do I download my invoice?'],
                ['📞', 'Support', 'How do I create a support ticket?'],
            ],
            seller: [
                ['📦', 'Order queue', 'Show my pending seller orders'],
                ['📉', 'Low stock', 'Show my low stock products'],
                ['💰', 'Net earnings', 'What is my net earnings after 10% commission?'],
                ['🏦', 'Payouts', 'Show my payout request status'],
                ['🔄', 'Returns', 'Show pending return claims'],
                ['📊', 'Sales report', 'Show my sales performance'],
                ['🛒', 'Product listing', 'How do I add a new product?'],
                ['📦', 'Inventory', 'How do I update inventory?'],
                ['🚚', 'Shipping', 'Show my shipping workflow'],
                ['⭐', 'Reviews', 'Show my customer reviews'],
            ],
            delivery: [
                ['🛵', 'Assigned jobs', 'Show my assigned deliveries'],
                ['🗺️', 'Best route', 'Show best route to customer'],
                ['💵', 'Today\'s payout', 'How much did I earn today?'],
                ['🔢', 'OTP & signature', 'How does delivery OTP and signature work?'],
                ['⏭️', 'Skip delivery', 'How can I skip an assigned delivery?'],
                ['⭐', 'My ratings', 'Show my delivery rating'],
                ['📋', 'Delivery history', 'Show my delivery history'],
                ['🏦', 'Bank details', 'How do I update payout bank details?'],
                ['🔔', 'Notifications', 'Show my delivery notifications'],
                ['🛟', 'Rider support', 'How do I contact delivery support?'],
            ],
            admin: [
                ['📈', 'Commission', 'What is today\'s platform commission?'],
                ['🏪', 'Seller approvals', 'Show pending seller verifications'],
                ['💸', 'Payouts', 'Show pending seller payout requests'],
                ['🎧', 'Support tickets', 'Show open support tickets'],
                ['↩️', 'Refunds', 'Show pending refunds'],
                ['📦', 'Order overview', 'Show today\'s order summary'],
                ['👥', 'Customers', 'Show customer management options'],
                ['🛡️', 'Delivery partners', 'Show delivery partner management'],
                ['🎫', 'Coupons', 'Show coupon management options'],
                ['📊', 'Analytics', 'Show platform analytics options'],
            ],
        };
        const menu = commands[role] || commands.public;
        const commandButtons = menu.map(([icon, label, prompt]) =>
            `<button class="ai-command-item" onclick="sendAiPrompt('${prompt.replace(/'/g, "\\'")}')"><span class="ai-command-icon">${icon}</span><span>${label}</span><i class="fa-solid fa-arrow-right"></i></button>`
        ).join('');
        return `
            👋 <strong>Namaste & Welcome!</strong><br><span style="color: var(--text-secondary);">Choose a command for your ${role} workspace:</span>
            <div class="ai-command-menu">${commandButtons}</div>
        `;
    }

    if (lower.includes('invoice') || lower.includes('download bill') || lower.includes('download my bill')) {
        if (role !== 'customer') return `📄 Customer invoices are available from My Orders after signing in. ${pageLink('invoice', role === 'public' ? 'Sign in' : 'Open orders')}.`;
        return `📄 Open ${pageLink('invoice', 'My Orders')}, select the order, then choose its invoice. Use <strong>Print / Download PDF</strong> on the invoice page to save it.`;
    }
    if (lower.includes('refer') || lower.includes('referral')) {
        if (role === 'customer') return `🤝 Open ${pageLink('referrals', 'Rewards')} to copy or share your referral code. A new customer can enter it during registration; the referrer receives ₹200 in wallet credit after successful registration.`;
        return `🤝 Referral codes are for customer accounts. A new customer can enter a friend's code during registration; the referrer receives ₹200 in wallet credit after successful registration. ${pageLink('referrals', role === 'public' ? 'Create an account' : 'Customer registration')}.`;
    }
    if (lower.includes('place an order') || lower.includes('place my order') || lower.includes('checkout')) {
        if (role === 'public') return `🛍️ Browse products, add an item to your cart, then sign in to complete checkout. ${pageLink('products', 'Browse products')}.`;
        if (role === 'customer') return `🛍️ Add products to your cart and continue to checkout to select a delivery address and payment method. ${pageLink('products', 'Browse products')}.`;
        return `🛍️ Orders are placed by customers. Use your panel to manage your work queue: ${pageLink('orders', role === 'seller' ? 'Seller orders' : role === 'delivery' ? 'Delivery requests' : 'Order management')}.`;
    }
    if (lower.includes('commission')) {
        if (role === 'admin') return `💰 Open ${pageLink('payments', 'Payments')} or the commissions section to review recorded commission amounts. This chat does not have live ledger totals.`;
        if (role === 'seller') return `💰 Review your actual earnings and deductions in ${pageLink('payments', 'Seller earnings')}; rates and totals can vary by order.`;
        return '💰 Commission is handled in seller and admin records; it does not change the product price shown at checkout.';
    }
    if (lower.includes('return') || lower.includes('replace') || lower.includes('refund')) {
        if (role === 'public') return `🔄 Return terms depend on the item. Read the ${pageLink('returns', 'refund policy')} before ordering.`;
        return `🔄 Eligibility depends on the item policy and order. Review the product details, then open ${pageLink('returns', role === 'admin' ? 'return claims' : 'Returns')} to view or manage requests.`;
    }
    if (lower.includes('coupon') || lower.includes('promo') || lower.includes('offer')) {
        return `🎟️ ${role === 'public' ? 'See current promotions on the ShopVerse home page.' : role === 'seller' ? 'Manage your store offers here:' : role === 'admin' ? 'Manage platform coupons here:' : 'See offers available to your account here:'} ${pageLink('offers', role === 'seller' ? 'Store offers' : role === 'admin' ? 'Coupons' : role === 'customer' ? 'My coupons' : 'ShopVerse home')}. Check each offer for its own terms and expiry.`;
    }
    if (lower.includes('otp')) {
        if (role === 'delivery') return `🔢 Open ${pageLink('orders', 'Delivery requests')} for assigned job details. Ask the customer for the order OTP only at handoff; never mark delivery complete without the required verification.`;
        return `🔢 I cannot view your order OTP here. Check ${pageLink('orders', role === 'public' ? 'sign in to view orders' : 'your order details')} and share the code only with your assigned delivery partner at handoff.`;
    }
    if (lower.includes('stock') || lower.includes('inventory')) {
        return `📦 ${role === 'seller' ? 'Manage stock in your seller inventory.' : role === 'admin' ? 'Review product availability in the catalogue.' : 'Stock varies by item; check the product page for its current availability.'} ${pageLink('inventory', role === 'seller' ? 'Inventory' : role === 'admin' ? 'Products' : 'Browse products')}.`;
    }
    if (lower.includes('payment') || lower.includes('wallet') || lower.includes('cod')) {
        if (role === 'customer') return `💳 Checkout displays the payment methods available for your order, including UPI, wallet, card, and COD. Review transactions in ${pageLink('payments', 'Payments')}.`;
        if (role === 'seller' || role === 'delivery') return `💳 Review your earnings and payout information in ${pageLink('payments', role === 'seller' ? 'Seller earnings' : 'Delivery earnings')}.`;
        if (role === 'admin') return `💳 Review payment records in ${pageLink('payments', 'Admin payments')}.`;
        return `💳 Available payment options are shown during checkout after you sign in. ${pageLink('payments', 'Sign in')}.`;
    }
    if (lower.includes('delivery') || lower.includes('shipping') || lower.includes('route')) {
        if (role === 'delivery') return `🛵 View assigned jobs and route details in ${pageLink('shipping', 'Delivery navigation')}.`;
        if (role === 'customer') return `🚚 Delivery progress is available from ${pageLink('orders', 'My Orders')} after an order is placed. Delivery timing and serviceability depend on the order and address.`;
        return `🚚 Read the ${pageLink('shipping', 'shipping information')} for delivery details. Exact serviceability is confirmed during checkout.`;
    }
    if (lower.includes('support') || lower.includes('help')) {
        return `💬 Open ${pageLink('support', role === 'admin' ? 'Support tickets' : 'Support')} to get help or manage support requests.`;
    }
    if (lower.includes('address')) {
        if (role === 'customer') return `📍 Select or add a delivery address at checkout, or manage saved addresses in ${pageLink('addresses', 'My Addresses')}.`;
        return `📍 ${role === 'public' ? 'Sign in to manage customer addresses.' : 'Manage your account details from your profile settings.'} ${pageLink('addresses', role === 'public' ? 'Sign in' : 'Profile settings')}.`;
    }
    if (lower.includes('review') || lower.includes('rating')) {
        const label = role === 'delivery' ? 'My ratings' : role === 'seller' ? 'Customer reviews' : role === 'admin' ? 'Reviews' : 'Product reviews';
        return `⭐ Open ${pageLink('reports', label)} to view review and rating information. Customers can review a product after its order is delivered.`;
    }
    if (lower.includes('payout') || lower.includes('withdraw')) {
        return `🏦 Open ${pageLink('payouts', role === 'admin' ? 'Payout requests' : 'Payouts')} to review payout information.`;
    }
    if (lower.includes('report') || lower.includes('analytics') || lower.includes('sales performance')) {
        return `📊 Open ${pageLink('reports', role === 'admin' ? 'Analytics' : 'Reports')} to see the reports available to your role.`;
    }
    if (lower.includes('seller approval') || lower.includes('delivery partner') || lower.includes('customer management')) {
        if (role === 'admin') return `🛠️ Use ${pageLink('orders', 'Admin panel')} to manage platform records and operations.`;
        return '🛠️ That management area is only available to administrators.';
    }
    if (lower.includes('product listing') || lower.includes('add a new product') || lower.includes('create a product')) {
        if (role === 'seller') return `🛍️ Add or edit listings from ${pageLink('sellerProducts', 'Seller products')}.`;
        return `🛍️ Browse available items in the ${pageLink('products', 'product catalogue')}.`;
    }
    if (lower.includes('product') || lower.includes('browse') || lower.includes('shop')) {
        return `🛍️ Browse current items and prices in the ${pageLink('products', 'product catalogue')}.`;
    }
    if (lower.includes('account') || lower.includes('profile') || lower.includes('settings')) {
        return `👤 Open ${pageLink('profile', 'profile settings')} to manage account details.`;
    }

    return `I do not have enough information to answer that accurately. Try asking about ${role === 'public' ? 'products, delivery, payments, returns, or account help' : 'orders, payouts, reports, payments, returns, or support'}.`;
}

// ==========================================
// 7. FLIPKART-STYLE IMAGE ZOOM MAGNIFIER
// ==========================================
function initProductImageZoom() {
    const viewport = document.getElementById('mainImageViewport');
    const mainImg = document.getElementById('mainDisplayImg');
    const lens = document.getElementById('zoomLens');
    const result = document.getElementById('zoomResultWindow');

    if (!viewport || !mainImg || !lens || !result) return;

    viewport.addEventListener('mouseenter', () => {
        lens.style.display = 'block';
        result.style.display = 'block';
        result.style.backgroundImage = `url('${mainImg.src}')`;
        result.style.backgroundSize = `${mainImg.width * 2.5}px ${mainImg.height * 2.5}px`;
    });

    viewport.addEventListener('mouseleave', () => {
        lens.style.display = 'none';
        result.style.display = 'none';
    });

    viewport.addEventListener('mousemove', (e) => {
        const rect = viewport.getBoundingClientRect();
        let x = e.clientX - rect.left - (lens.offsetWidth / 2);
        let y = e.clientY - rect.top - (lens.offsetHeight / 2);

        if (x > viewport.offsetWidth - lens.offsetWidth) x = viewport.offsetWidth - lens.offsetWidth;
        if (x < 0) x = 0;
        if (y > viewport.offsetHeight - lens.offsetHeight) y = viewport.offsetHeight - lens.offsetHeight;
        if (y < 0) y = 0;

        lens.style.left = x + 'px';
        lens.style.top = y + 'px';

        const cx = 2.5;
        const cy = 2.5;
        result.style.backgroundPosition = `-${x * cx}px -${y * cy}px`;
    });
}

function switchMainProductImage(thumbElement, imgUrl) {
    const mainImg = document.getElementById('mainDisplayImg');
    if (mainImg) {
        mainImg.src = imgUrl;
    }
    document.querySelectorAll('.thumbnail-chip').forEach(el => el.classList.remove('active'));
    if (thumbElement) thumbElement.classList.add('active');
}

function initImageViewer() {
    const dialog = document.getElementById('imageViewerDialog');
    const dialogImage = document.getElementById('imageViewerContent');
    const closeButton = document.getElementById('imageViewerClose');
    if (!dialog || !dialogImage || !closeButton) return;

    const openImage = trigger => {
        const image = trigger.matches('img') ? trigger : trigger.querySelector('img');
        const source = trigger.dataset.imageSrc || image?.currentSrc || image?.src;
        if (!source) return;
        dialogImage.src = source;
        dialogImage.alt = trigger.dataset.imageAlt || image?.alt || 'Product image';
        dialog.showModal();
    };

    document.addEventListener('click', event => {
        const trigger = event.target.closest('[data-image-viewer]');
        if (!trigger) return;
        event.preventDefault();
        openImage(trigger);
    });

    document.addEventListener('keydown', event => {
        if (!['Enter', ' '].includes(event.key)) return;
        const trigger = event.target.closest?.('[data-image-viewer][role="button"]');
        if (!trigger) return;
        event.preventDefault();
        trigger.click();
    });

    closeButton.addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', event => {
        if (event.target === dialog) dialog.close();
    });
}

// ==========================================
// 8. WISHLIST HEART ACCENT TOGGLE
// ==========================================
function initWishlistToggle() {
    document.querySelectorAll('.wishlist-btn, .btn-wishlist, .heart-btn, .wishlist-chip').forEach(btn => {
        if (btn.closest('.ajax-wishlist-form')) return;
        btn.addEventListener('click', function(e) {
            this.classList.toggle('active');
            const icon = this.querySelector('i') || (this.tagName === 'I' ? this : null);
            if (icon) {
                if (this.classList.contains('active')) {
                    icon.className = 'fa-solid fa-heart';
                    icon.style.setProperty('color', '#ef4444', 'important');
                    showToast('Added to Wishlist ❤️', 'success');
                } else {
                    icon.className = 'fa-regular fa-heart';
                    icon.style.removeProperty('color');
                    showToast('Removed from Wishlist', 'info');
                }
            }
        });
    });
}

// ==========================================
// 9. LEAFLET LIVE MAP (CARTO VOYAGER TILE FIX)
// ==========================================
let liveMapInstance = null;

function initLiveOrderMap(mapElementId, storeLat = 28.6328, storeLng = 77.2197, custLat = 28.6139, custLng = 77.2090) {
    const mapEl = document.getElementById(mapElementId);
    if (!mapEl || typeof L === 'undefined') return;

    if (liveMapInstance) {
        liveMapInstance.remove();
    }

    liveMapInstance = L.map(mapElementId).setView([(storeLat + custLat) / 2, (storeLng + custLng) / 2], 13);

    // Esri World Street Map Tiles (Zero Watermarks, High Performance, No API Keys Needed)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, Intermap, iPC, NRCAN, Esri Japan, METI, Esri China (Hong Kong), Esri (Thailand), TomTom, 2012',
        maxZoom: 18
    }).addTo(liveMapInstance);

    // Store Marker
    const storeIcon = L.divIcon({
        className: 'map-custom-marker store',
        html: '<div style="background:#4f46e5; color:#fff; width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow:0 3px 10px rgba(0,0,0,0.3);"><i class="fa-solid fa-store"></i></div>',
        iconSize: [34, 34],
        iconAnchor: [17, 17]
    });
    L.marker([storeLat, storeLng], { icon: storeIcon }).addTo(liveMapInstance).bindPopup('<strong>Vendor Store (Pickup Point)</strong>');

    // Customer Marker
    const custIcon = L.divIcon({
        className: 'map-custom-marker cust',
        html: '<div style="background:#10b981; color:#fff; width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow:0 3px 10px rgba(0,0,0,0.3);"><i class="fa-solid fa-house-chimney"></i></div>',
        iconSize: [34, 34],
        iconAnchor: [17, 17]
    });
    L.marker([custLat, custLng], { icon: custIcon }).addTo(liveMapInstance).bindPopup('<strong>Customer Shipping Destination</strong>');
}

// ==========================================
// 10. DOM INITIALIZATION
// ==========================================
function initCustomSelects() {
    document.querySelectorAll('select:not([multiple]):not([data-native-select])').forEach(select => {
        if (select.closest('.custom-select-wrapper')) return;

        const wrapper = document.createElement('div');
        wrapper.className = 'custom-select-wrapper';
        const hasFullWidthStyle = /(^|;)\s*width\s*:\s*100%/i.test(select.getAttribute('style') || '');
        const longestOption = Array.from(select.options).reduce(
            (longest, option) => Math.max(longest, option.textContent.trim().length),
            0
        );
        const compactWidth = Math.min(Math.max(longestOption * 8 + 56, 150), 280);
        wrapper.style.width = hasFullWidthStyle ? '100%' : `${compactWidth}px`;
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);
        select.classList.add('custom-select-native');

        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'custom-select-trigger';
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');
        const triggerLabel = document.createElement('span');
        trigger.appendChild(triggerLabel);

        const menu = document.createElement('div');
        menu.className = 'custom-select-menu';
        menu.setAttribute('role', 'listbox');

        const syncSelection = () => {
            const selected = select.options[select.selectedIndex];
            triggerLabel.textContent = selected ? selected.textContent : '';
            trigger.disabled = select.disabled;
            if (select.disabled) {
                wrapper.classList.remove('open');
                trigger.setAttribute('aria-expanded', 'false');
            }
            menu.querySelectorAll('.custom-select-option').forEach(menuOption => {
                menuOption.classList.toggle('selected', menuOption.dataset.value === select.value);
            });
        };

        const renderOptions = () => {
            menu.replaceChildren();
            Array.from(select.options).filter(option => !option.hidden).forEach(option => {
                const item = document.createElement('div');
                item.className = 'custom-select-option';
                item.textContent = option.textContent;
                item.dataset.value = option.value;
                item.setAttribute('role', 'option');
                item.addEventListener('click', () => {
                    if (select.disabled) return;
                    select.value = option.value;
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                    syncSelection();
                    wrapper.classList.remove('open');
                    trigger.setAttribute('aria-expanded', 'false');
                });
                menu.appendChild(item);
            });
        };

        trigger.addEventListener('click', () => {
            if (select.disabled) return;
            const isOpen = wrapper.classList.toggle('open');
            trigger.setAttribute('aria-expanded', String(isOpen));
        });
        select.addEventListener('change', syncSelection);
        select.addEventListener('optionschange', () => {
            renderOptions();
            syncSelection();
        });
        renderOptions();
        wrapper.appendChild(trigger);
        wrapper.appendChild(menu);
        syncSelection();
    });

    document.addEventListener('click', event => {
        document.querySelectorAll('.custom-select-wrapper.open').forEach(wrapper => {
            if (!wrapper.contains(event.target)) {
                wrapper.classList.remove('open');
                wrapper.querySelector('.custom-select-trigger')?.setAttribute('aria-expanded', 'false');
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initLanguage();
    initWishlistToggle();
    initProductImageZoom();
    initImageViewer();
    initSearchSuggestions();
    initPasswordToggles();
    initUsernameAvailability();
    initCustomSelects();
    initKpiCards();
    initCustomerFilterMenus();

    // Voice search trigger
    const voiceBtn = document.getElementById('voiceSearchBtn');
    if (voiceBtn) {
        voiceBtn.addEventListener('click', () => startVoiceSearch());
    }

    // Enter key on AI chat
    const aiInput = document.getElementById('aiChatInput');
    if (aiInput) {
        aiInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendAiPrompt();
        });
    }
});

function initPasswordToggles() {
    document.querySelectorAll('[data-password-toggle]').forEach(button => {
        button.addEventListener('click', () => {
            const input = document.getElementById(button.dataset.passwordToggle);
            if (!input) return;
            const visible = input.type === 'text';
            input.type = visible ? 'password' : 'text';
            button.setAttribute('aria-label', visible ? 'Show password' : 'Hide password');
            button.setAttribute('title', visible ? 'Show password' : 'Hide password');
            button.innerHTML = `<i class="fa-solid fa-eye${visible ? '' : '-slash'}"></i>`;
        });
    });
}

function initUsernameAvailability() {
    document.querySelectorAll('[data-username-check]').forEach(input => {
        const form = input.form;
        const status = form?.querySelector('[data-username-status]');
        const submitButton = form?.querySelector('[data-username-submit]');
        if (!form || !status || !submitButton) return;

        let timer;
        let checkedUsername = '';
        let isAvailable = false;

        const checkUsername = async () => {
            const username = input.value.trim();
            if (!username) {
                status.textContent = 'Enter a username.';
                status.style.color = '#ef4444';
                return false;
            }

            status.textContent = 'Checking username...';
            status.style.color = '#f59e0b';
            try {
                const response = await fetch(`/username-availability/?username=${encodeURIComponent(username)}`);
                if (!response.ok) throw new Error('Username check failed');
                const result = await response.json();
                isAvailable = result.available;
                checkedUsername = isAvailable ? username : '';
                status.textContent = result.message;
                status.style.color = isAvailable ? '#10b981' : '#ef4444';
                return isAvailable;
            } catch (error) {
                isAvailable = false;
                checkedUsername = '';
                status.textContent = 'Could not verify username. Try again.';
                status.style.color = '#ef4444';
                return false;
            }
        };

        input.addEventListener('input', () => {
            clearTimeout(timer);
            isAvailable = false;
            checkedUsername = '';
            status.textContent = input.value.trim() ? 'Checking username...' : '';
            status.style.color = '#f59e0b';
            if (input.value.trim()) timer = setTimeout(checkUsername, 350);
        });

        input.addEventListener('blur', () => {
            clearTimeout(timer);
            checkUsername();
        });

        form.addEventListener('submit', async event => {
            if (isAvailable && checkedUsername === input.value.trim()) return;
            event.preventDefault();
            clearTimeout(timer);
            if (await checkUsername()) form.requestSubmit(submitButton);
        });
    });
}

function initSearchSuggestions() {
    const input = document.getElementById('globalSearchInput');
    const suggestions = document.getElementById('searchSuggestions');
    if (!input || !suggestions) return;

    const form = input.closest('form');
    const suggestionsUrl = form?.dataset.suggestionsUrl || '/customer/search/';
    const productDetailUrl = form?.dataset.productDetailUrl || '/customer/product/{id}/';
    const adminSearch = form?.dataset.searchMode === 'admin';
    const deliverySearch = form?.dataset.searchMode === 'delivery';
    let timer;
    let requestId = 0;
    let activeController = null;
    input.addEventListener('input', () => {
        clearTimeout(timer);
        activeController?.abort();
        const currentRequestId = ++requestId;
        const query = input.value.trim();
        suggestions.innerHTML = '';
        suggestions.classList.remove('visible');
        if (query.length < 2) {
            return;
        }

        timer = setTimeout(async () => {
            const controller = new AbortController();
            activeController = controller;
            try {
                const url = new URL(suggestionsUrl, window.location.origin);
                url.searchParams.set('suggestions', '1');
                url.searchParams.set('q', query);
                const response = await fetch(url, { signal: controller.signal });
                if (!response.ok) throw new Error('Suggestion request failed');
                const data = await response.json();
                if (currentRequestId !== requestId) return;
                suggestions.innerHTML = data.results.length
                    ? data.results.map(result => adminSearch
                        ? `<a href="${escapeHtml(result.url)}" class="search-suggestion-item" role="option">
                            <span class="search-suggestion-image"><i class="${escapeHtml(result.icon)}"></i></span>
                            <span class="search-suggestion-copy"><strong>${escapeHtml(result.title)}</strong><small>${escapeHtml(result.type)} · ${escapeHtml(result.subtitle)}</small></span>
                        </a>`
                        : deliverySearch
                        ? `<a href="${escapeHtml(productDetailUrl.replace('{id}', encodeURIComponent(result.id)))}" class="search-suggestion-item" role="option">
                            <span class="search-suggestion-image"><i class="fa-solid fa-truck-fast"></i></span>
                            <span class="search-suggestion-copy"><strong>${escapeHtml(result.title)}</strong><small>${escapeHtml(result.subtitle)}</small></span>
                        </a>`
                        : `<a href="${escapeHtml(productDetailUrl.replace('{id}', encodeURIComponent(result.id)))}" class="search-suggestion-item" role="option">
                            <span class="search-suggestion-image">${result.image ? `<img src="${result.image}" alt="">` : '<i class="fa-solid fa-box"></i>'}</span>
                            <span class="search-suggestion-copy"><strong>${escapeHtml(result.title)}</strong><small>${escapeHtml(result.brand)} · ₹${escapeHtml(result.price)}</small></span>
                        </a>`).join('')
                    : `<div class="search-suggestion-empty">${adminSearch ? 'No matching admin records found' : deliverySearch ? 'No assigned orders found' : 'No products found'}</div>`;
                suggestions.classList.add('visible');
            } catch (error) {
                if (error.name === 'AbortError' || currentRequestId !== requestId) return;
                suggestions.innerHTML = '';
                suggestions.classList.remove('visible');
            }
        }, 220);
    });

    document.addEventListener('click', event => {
        if (!event.target.closest('.topbar-search-box, .navbar-search')) {
            suggestions.classList.remove('visible');
        }
    });
}

function escapeHtml(value) {
    const element = document.createElement('div');
    element.textContent = value || '';
    return element.innerHTML;
}
