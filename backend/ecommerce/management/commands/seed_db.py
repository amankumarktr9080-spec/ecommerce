import random
import uuid
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from users.models import User, Address
from categories.models import Category, SubCategory, Brand
from sellers.models import SellerProfile
from delivery.models import DeliveryPartnerProfile
from products.models import Product, ProductImage, ProductSpecification
from cart.models import Cart, CartItem
from wishlist.models import Wishlist, WishlistItem
from orders.models import Order, OrderItem, OrderTimeline
from returns.models import ReturnRequest
from reviews.models import Review
from coupons.models import Coupon
from commissions.models import CommissionLog
from notifications.models import Notification
from support.models import SupportTicket
from offers.models import OfferBanner
from payments.models import PaymentTransaction


class Command(BaseCommand):
    help = "Seed database with 10+ records for all entities"

    def handle(self, *args, **options):
        self.stdout.write("Starting database seeding (minimum 10 records per entity)...")

        # 1. Superuser / Admin
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@ecommerce.com",
                "first_name": "System",
                "last_name": "Admin",
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
                "wallet_balance": Decimal("50000.00"),
            }
        )
        admin_user.set_password("admin123")
        admin_user.save()
        self.stdout.write("Created Admin: admin / admin123")

        # 2. 10 Customers
        customer_names = [
            ("Aman", "Kumar", "aman@example.com", "9876543210"),
            ("Priya", "Sharma", "priya@example.com", "9876543211"),
            ("Rahul", "Verma", "rahul@example.com", "9876543212"),
            ("Sneha", "Patel", "sneha@example.com", "9876543213"),
            ("Rohan", "Gupta", "rohan@example.com", "9876543214"),
            ("Ananya", "Singh", "ananya@example.com", "9876543215"),
            ("Vikram", "Malhotra", "vikram@example.com", "9876543216"),
            ("Pooja", "Joshi", "pooja@example.com", "9876543217"),
            ("Karan", "Mehta", "karan@example.com", "9876543218"),
            ("Neha", "Reddy", "neha@example.com", "9876543219"),
        ]

        customers = []
        for fn, ln, email, phone in customer_names:
            u, created = User.objects.get_or_create(
                username=email.split('@')[0],
                defaults={
                    "first_name": fn,
                    "last_name": ln,
                    "email": email,
                    "phone": phone,
                    "role": "customer",
                    "wallet_balance": Decimal("1500.00"),
                    "reward_points": 250,
                    "referral_code": f"REF-{fn[:3].upper()}{random.randint(100, 999)}",
                    "avatar_url": f"https://api.dicebear.com/7.x/avataaars/svg?seed={fn}",
                }
            )
            u.set_password("password123")
            u.save()
            customers.append(u)

        # 10 Addresses for Customers
        cities = [
            ("New Delhi", "Delhi", "110001", "Connaught Place, B-Block, Flat 402"),
            ("Mumbai", "Maharashtra", "400001", "Marine Drive, Sea View Apts 12B"),
            ("Bangalore", "Karnataka", "560001", "MG Road, Indiranagar, 4th Cross"),
            ("Hyderabad", "Telangana", "500001", "Banjara Hills, Road No 10, Villa 7"),
            ("Pune", "Maharashtra", "411001", "Koregaon Park, Lane 5, House 23"),
            ("Ahmedabad", "Gujarat", "380001", "SG Highway, Navrangpura, Flat 101"),
            ("Chennai", "Tamil Nadu", "600001", "Anna Nagar, 2nd Avenue, Plot 54"),
            ("Kolkata", "West Bengal", "700001", "Park Street, Camac St, Tower 3"),
            ("Jaipur", "Rajasthan", "302001", "Malviya Nagar, Sector 4, House 12"),
            ("Lucknow", "Uttar Pradesh", "226001", "Hazratganj, Gomti Nagar, B-12"),
        ]
        for i, c in enumerate(customers):
            city, state, pin, street = cities[i % len(cities)]
            Address.objects.get_or_create(
                user=c,
                street_address=street,
                defaults={
                    "full_name": f"{c.first_name} {c.last_name}",
                    "phone": c.phone,
                    "city": city,
                    "state": state,
                    "pincode": pin,
                    "is_default": True,
                    "address_type": "home" if i % 2 == 0 else "work"
                }
            )

        # 3. 10 Categories
        cat_data = [
            ("Electronics", "electronics", "fa-solid fa-laptop", "https://images.unsplash.com/photo-1498049794561-7780e7231661?w=500", Decimal("10.00")),
            ("Mobiles & Tablets", "mobiles", "fa-solid fa-mobile-screen-button", "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500", Decimal("8.00")),
            ("Fashion & Apparel", "fashion", "fa-solid fa-shirt", "https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?w=500", Decimal("12.00")),
            ("Home & Kitchen", "home-kitchen", "fa-solid fa-couch", "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=500", Decimal("10.00")),
            ("Beauty & Grooming", "beauty", "fa-solid fa-wand-magic-sparkles", "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=500", Decimal("15.00")),
            ("Grocery & Essentials", "grocery", "fa-solid fa-basket-shopping", "https://images.unsplash.com/photo-1542838132-92c53300491e?w=500", Decimal("5.00")),
            ("Sports & Fitness", "sports", "fa-solid fa-dumbbell", "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=500", Decimal("10.00")),
            ("Books & Stationery", "books", "fa-solid fa-book", "https://images.unsplash.com/photo-1495446815901-a7297e633e8d?w=500", Decimal("8.00")),
            ("Toys & Baby Care", "toys", "fa-solid fa-gamepad", "https://images.unsplash.com/photo-1566576912321-d58ddd7a6088?w=500", Decimal("10.00")),
            ("Footwear & Shoes", "footwear", "fa-solid fa-shoe-prints", "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500", Decimal("12.00")),
        ]
        categories = []
        for name, slug, icon, img, comm in cat_data:
            cat, _ = Category.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "icon": icon,
                    "image_url": img,
                    "commission_rate": comm,
                    "is_active": True,
                }
            )
            categories.append(cat)

        # 20 SubCategories
        subcat_data = [
            (categories[0], "Smart Watches", "smart-watches"),
            (categories[0], "Headphones & Audio", "audio-headphones"),
            (categories[1], "Android Phones", "android-phones"),
            (categories[1], "iPhones & iOS", "iphones"),
            (categories[2], "Men's Casual Wear", "mens-casual"),
            (categories[2], "Women's Ethnic Wear", "womens-ethnic"),
            (categories[3], "Cookware & Utensils", "cookware"),
            (categories[3], "Smart Home Lighting", "smart-lighting"),
            (categories[4], "Skin Care", "skin-care"),
            (categories[4], "Perfumes & Deos", "perfumes"),
            (categories[5], "Organic Pulses & Rice", "organic-staples"),
            (categories[5], "Snacks & Beverages", "snacks"),
            (categories[6], "Gym Accessories", "gym-accessories"),
            (categories[6], "Yoga Mats & Bands", "yoga-mats"),
            (categories[7], "Self-Help Bestsellers", "self-help"),
            (categories[7], "Coding & Tech Books", "tech-books"),
            (categories[8], "Educational Toys", "educational-toys"),
            (categories[8], "Board Games", "board-games"),
            (categories[9], "Running Sneakers", "running-sneakers"),
            (categories[9], "Formal Leather Shoes", "formal-shoes"),
        ]
        subcategories = []
        for cat, sc_name, sc_slug in subcat_data:
            sc, _ = SubCategory.objects.get_or_create(
                category=cat,
                slug=sc_slug,
                defaults={"name": sc_name}
            )
            subcategories.append(sc)

        # 10 Brands
        brand_names = [
            ("Apple", "apple", "https://upload.wikimedia.org/wikipedia/commons/f/fa/Apple_logo_black.svg", True),
            ("Samsung", "samsung", "https://upload.wikimedia.org/wikipedia/commons/2/24/Samsung_Logo.svg", True),
            ("Nike", "nike", "https://upload.wikimedia.org/wikipedia/commons/a/a6/Logo_NIKE.svg", True),
            ("Sony", "sony", "https://upload.wikimedia.org/wikipedia/commons/c/ca/Sony_logo.svg", True),
            ("boAt", "boat", "https://upload.wikimedia.org/wikipedia/commons/8/87/Boat_logo.png", True),
            ("Puma", "puma", "https://upload.wikimedia.org/wikipedia/en/thumb/e/ee/Puma_AG.svg/1200px-Puma_AG.svg.png", True),
            ("Philips", "philips", "https://upload.wikimedia.org/wikipedia/commons/7/77/Philips_logo.svg", False),
            ("Dell", "dell", "https://upload.wikimedia.org/wikipedia/commons/1/18/Dell_logo_2016.svg", True),
            ("Adidas", "adidas", "https://upload.wikimedia.org/wikipedia/commons/2/20/Adidas_Logo.svg", True),
            ("Prestige", "prestige", "https://upload.wikimedia.org/wikipedia/commons/b/b3/Prestige_logo.png", False),
        ]
        brands = []
        brand_subcategory_slugs = {
            'Apple': 'iphones',
            'Samsung': 'android-phones',
            'Nike': 'running-sneakers',
            'Sony': 'audio-headphones',
            'boAt': 'audio-headphones',
            'Puma': 'running-sneakers',
            'Philips': 'smart-lighting',
            'Dell': 'smart-watches',
            'Adidas': 'running-sneakers',
            'Prestige': 'cookware',
        }
        for b_name, b_slug, b_logo, is_feat in brand_names:
            brand_subcategory = next(
                (subcategory for subcategory in subcategories if subcategory.slug == brand_subcategory_slugs[b_name]),
                None,
            )
            b, _ = Brand.objects.get_or_create(
                name=b_name,
                defaults={
                    "slug": b_slug,
                    "logo_url": b_logo,
                    "is_featured": is_feat,
                    "subcategory": brand_subcategory,
                }
            )
            if brand_subcategory and b.subcategory_id != brand_subcategory.id:
                b.subcategory = brand_subcategory
                b.save(update_fields=['subcategory'])
            brands.append(b)

        # 4. 10 Sellers (Created by Admin)
        seller_info = [
            ("Apex Retailers", "apex_seller", "apex@store.com", "9811001101", "Connaught Place, New Delhi", "07AAAAA0000A1Z5"),
            ("TechZone Gadgets", "techzone_seller", "techzone@store.com", "9811001102", "Nehru Place, New Delhi", "07BBBBB1111B1Z6"),
            ("Glamour Fashion House", "glamour_seller", "glamour@store.com", "9811001103", "Bandra West, Mumbai", "27CCCCC2222C1Z7"),
            ("FitLife Sports Goods", "fitlife_seller", "fitlife@store.com", "9811001104", "Indiranagar, Bangalore", "29DDDDD3333D1Z8"),
            ("KitchenCraft Essentials", "kitchen_seller", "kitchen@store.com", "9811001105", "Chandni Chowk, Delhi", "07EEEEE4444E1Z9"),
            ("UrbanStride Shoes", "urban_seller", "urban@store.com", "9811001106", "Linking Road, Mumbai", "27FFFFF5555F1Z0"),
            ("PureOrganics India", "organic_seller", "organic@store.com", "9811001107", "Jayanagar, Bangalore", "29GGGGG6666G1Z1"),
            ("ReadWell Book Depot", "books_seller", "books@store.com", "9811001108", "Daryaganj, Delhi", "07HHHHH7777H1Z2"),
            ("GlowAura Cosmetics", "glow_seller", "glow@store.com", "9811001109", "South Ex, New Delhi", "07IIIII8888I1Z3"),
            ("PlayWonder Toys", "play_seller", "play@store.com", "9811001110", "Salt Lake, Kolkata", "19JJJJJ9999J1Z4"),
        ]
        sellers = []
        for s_name, username, email, phone, addr, gst in seller_info:
            u, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "first_name": s_name.split()[0],
                    "last_name": "Store",
                    "phone": phone,
                    "role": "seller",
                    "wallet_balance": Decimal("12500.00"),
                }
            )
            u.set_password("seller123")
            u.save()

            sp, _ = SellerProfile.objects.get_or_create(
                user=u,
                defaults={
                    "store_name": s_name,
                    "store_slug": username.replace('_seller', '-store'),
                    "logo_url": f"https://api.dicebear.com/7.x/identicon/svg?seed={username}",
                    "banner_url": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=1200",
                    "description": f"Official verified vendor store for {s_name}. Premium genuine products.",
                    "phone": phone,
                    "email": email,
                    "business_address": addr,
                    "gst_number": gst,
                    "bank_name": "HDFC Bank",
                    "account_number": f"50100{random.randint(1000000, 9999999)}",
                    "ifsc_code": "HDFC0001234",
                    "upi_id": f"{username}@okhdfcbank",
                    "is_approved": True,
                    "is_top_rated": True if random.random() > 0.3 else False,
                }
            )
            sellers.append(sp)

        # 5. 10 Delivery Partners (Created by Admin)
        rider_info = [
            ("Ramesh", "Kumar", "ramesh_rider", "9899000101", "bike", "DL-01-AB-1234", "DL-9876543210"),
            ("Suresh", "Yadav", "suresh_rider", "9899000102", "bike", "DL-02-CD-5678", "DL-9876543211"),
            ("Mohit", "Sharma", "mohit_rider", "9899000103", "scooter", "DL-03-EF-9012", "DL-9876543212"),
            ("Deepak", "Chauhan", "deepak_rider", "9899000104", "bike", "MH-01-GH-3456", "MH-9876543213"),
            ("Amit", "Verma", "amit_rider", "9899000105", "van", "KA-01-IJ-7890", "KA-9876543214"),
            ("Rajesh", "Prajapati", "rajesh_rider", "9899000106", "bike", "DL-04-KL-2345", "DL-9876543215"),
            ("Sunil", "Gupta", "sunil_rider", "9899000107", "scooter", "MH-02-MN-6789", "MH-9876543216"),
            ("Pankaj", "Rawat", "pankaj_rider", "9899000108", "bike", "KA-02-OP-0123", "KA-9876543217"),
            ("Manoj", "Tiwari", "manoj_rider", "9899000109", "bike", "DL-05-QR-4567", "DL-9876543218"),
            ("Vikas", "Saini", "vikas_rider", "9899000110", "van", "MH-03-ST-8901", "MH-9876543219"),
        ]
        delivery_partners = []
        for fn, ln, uname, phone, vtype, vno, lic in rider_info:
            u, _ = User.objects.get_or_create(
                username=uname,
                defaults={
                    "first_name": fn,
                    "last_name": ln,
                    "email": f"{uname}@delivery.com",
                    "phone": phone,
                    "role": "delivery",
                    "wallet_balance": Decimal("3200.00"),
                }
            )
            u.set_password("rider123")
            u.save()

            dp, _ = DeliveryPartnerProfile.objects.get_or_create(
                user=u,
                defaults={
                    "vehicle_type": vtype,
                    "vehicle_number": vno,
                    "driving_license_no": lic,
                    "is_online": True,
                    "current_lat": 28.6139 + random.uniform(-0.05, 0.05),
                    "current_lng": 77.2090 + random.uniform(-0.05, 0.05),
                    "rating": Decimal(str(round(random.uniform(4.5, 5.0), 1))),
                    "bank_name": "State Bank of India",
                    "account_number": f"30987{random.randint(1000000, 9999999)}",
                    "upi_id": f"{uname}@sbi",
                    "is_approved": True,
                }
            )
            delivery_partners.append(dp)

        # 6. 20+ Products with Unique item_code, 10% commission, and Return/Replacement rules
        product_catalog = [
            {
                "item_code": "ITM-ELEC-1001",
                "title": "boAt Airdopes 141 Bluetooth Truly Wireless in Ear Earbuds",
                "slug": "boat-airdopes-141-tws",
                "cat": categories[0],
                "subcat": subcategories[1],
                "brand": brands[4],
                "seller": sellers[1],
                "base": Decimal("899.00"),
                "del_charge": Decimal("40.00"),
                "mrp": Decimal("2990.00"),
                "stock": 45,
                "is_feat": True,
                "is_flash": True,
                "is_ret": True,
                "ret_days": 7,
                "is_rep": True,
                "rep_days": 7,
                "img": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=600",
                "desc": "Enjoy an immersive audio experience with boAt Airdopes 141. Features 42 hours total playback, ASAP charge technology, ENx environmental noise cancellation, and IPX4 water resistance.",
                "specs": [
                    ("General", "Model Name", "Airdopes 141"),
                    ("General", "Color", "Bold Black"),
                    ("Connectivity", "Bluetooth Version", "v5.1"),
                    ("Audio", "Driver Size", "8mm Dynamic"),
                    ("Battery", "Battery Life", "42 Hours Playback"),
                    ("Warranty", "Warranty Summary", "1 Year Brand Warranty")
                ]
            },
            {
                "item_code": "ITM-MOBL-1002",
                "title": "Apple iPhone 15 (128 GB) - Blue",
                "slug": "apple-iphone-15-128gb-blue",
                "cat": categories[1],
                "subcat": subcategories[3],
                "brand": brands[0],
                "seller": sellers[0],
                "base": Decimal("59999.00"),
                "del_charge": Decimal("0.00"),
                "mrp": Decimal("79900.00"),
                "stock": 12,
                "is_feat": True,
                "is_flash": False,
                "is_ret": True,
                "ret_days": 10,
                "is_rep": True,
                "rep_days": 10,
                "img": "https://images.unsplash.com/photo-1695048133142-1a20484d2569?w=600",
                "desc": "iPhone 15 features Dynamic Island, a 48MP Main camera, and USB-C. Powered by A16 Bionic with durable color-infused glass and aluminum design.",
                "specs": [
                    ("General", "Model Number", "A3090"),
                    ("General", "Color", "Blue"),
                    ("Display", "Screen Size", "6.1 inch Super Retina XDR"),
                    ("Performance", "Processor", "A16 Bionic chip"),
                    ("Camera", "Main Camera", "48MP + 12MP Ultra Wide"),
                    ("Warranty", "Domestic Warranty", "1 Year Apple Care")
                ]
            },
            {
                "item_code": "ITM-MOBL-1003",
                "title": "Samsung Galaxy S24 Ultra 5G (Titanium Gray, 256 GB)",
                "slug": "samsung-galaxy-s24-ultra-5g",
                "cat": categories[1],
                "subcat": subcategories[2],
                "brand": brands[1],
                "seller": sellers[1],
                "base": Decimal("99999.00"),
                "del_charge": Decimal("0.00"),
                "mrp": Decimal("129999.00"),
                "stock": 10,
                "is_feat": True,
                "is_flash": True,
                "is_ret": True,
                "ret_days": 7,
                "is_rep": True,
                "rep_days": 7,
                "img": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=600",
                "desc": "Meet Galaxy S24 Ultra, the ultimate form of Galaxy Ultra with a new titanium exterior and a 6.8 inch flat display with built-in S Pen.",
                "specs": [
                    ("General", "In The Box", "Handset, S-Pen, USB Cable, Ejection Pin"),
                    ("Display", "Resolution", "3120 x 1440 Pixels Quad HD+"),
                    ("Camera", "Rear Camera", "200MP + 50MP + 12MP + 10MP"),
                    ("Memory", "RAM", "12 GB"),
                    ("Storage", "Internal Storage", "256 GB")
                ]
            },
            {
                "item_code": "ITM-FASH-1004",
                "title": "Nike Men's Air Zoom Pegasus 40 Running Shoes",
                "slug": "nike-air-zoom-pegasus-40",
                "cat": categories[9],
                "subcat": subcategories[18],
                "brand": brands[2],
                "seller": sellers[5],
                "base": Decimal("7499.00"),
                "del_charge": Decimal("50.00"),
                "mrp": Decimal("10495.00"),
                "stock": 25,
                "is_feat": True,
                "is_flash": False,
                "is_ret": True,
                "ret_days": 14,
                "is_rep": True,
                "rep_days": 14,
                "img": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600",
                "desc": "A springy ride for any run, the Peg's familiar, just-for-you feel returns to help you accomplish your goals. Features responsive Zoom Air units.",
                "specs": [
                    ("General", "Type", "Running Shoes"),
                    ("General", "Upper Material", "Engineered Mesh"),
                    ("Fit", "Closure", "Lace-Up"),
                    ("Sole", "Sole Material", "Durable Rubber Waffle")
                ]
            },
            {
                "item_code": "ITM-FASH-1005",
                "title": "Puma Classic Suede Sneakers for Men",
                "slug": "puma-classic-suede-sneakers",
                "cat": categories[9],
                "subcat": subcategories[18],
                "brand": brands[5],
                "seller": sellers[5],
                "base": Decimal("3299.00"),
                "del_charge": Decimal("50.00"),
                "mrp": Decimal("5999.00"),
                "stock": 30,
                "is_feat": False,
                "is_flash": True,
                "is_ret": True,
                "ret_days": 10,
                "is_rep": True,
                "rep_days": 10,
                "img": "https://images.unsplash.com/photo-1608231387042-66d1773070a5?w=600",
                "desc": "The Suede hit the scene in 1968 and has been changing the game ever since. Worn by icons of every generation and it's stayed classic through it all.",
                "specs": [
                    ("General", "Brand", "Puma"),
                    ("Material", "Upper", "100% Genuine Suede"),
                    ("Sole", "Sole", "Non-marking rubber")
                ]
            },
            {
                "item_code": "ITM-ELEC-1006",
                "title": "Sony WH-1000XM5 Wireless Active Noise Cancelling Headphones",
                "slug": "sony-wh-1000xm5-headphones",
                "cat": categories[0],
                "subcat": subcategories[1],
                "brand": brands[3],
                "seller": sellers[1],
                "base": Decimal("23999.00"),
                "del_charge": Decimal("0.00"),
                "mrp": Decimal("34990.00"),
                "stock": 18,
                "is_feat": True,
                "is_flash": False,
                "is_ret": True,
                "ret_days": 7,
                "is_rep": True,
                "rep_days": 7,
                "img": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600",
                "desc": "Industry-leading noise canceling with two processors and 8 microphones for unprecedented noise cancellation and exceptional call quality.",
                "specs": [
                    ("General", "Type", "Over-Ear Wireless"),
                    ("Audio", "Frequency Response", "4 Hz - 40,000 Hz"),
                    ("Battery", "Battery Life", "Up to 30 Hours"),
                    ("Special Features", "Noise Cancellation", "Dual HD V1 & QN1 Processors")
                ]
            },
            {
                "item_code": "ITM-ELEC-1007",
                "title": "Dell Inspiron 15 Laptop (Core i5 13th Gen, 16GB RAM, 512GB SSD)",
                "slug": "dell-inspiron-15-laptop-i5",
                "cat": categories[0],
                "subcat": subcategories[0],
                "brand": brands[7],
                "seller": sellers[1],
                "base": Decimal("44999.00"),
                "del_charge": Decimal("0.00"),
                "mrp": Decimal("62990.00"),
                "stock": 14,
                "is_feat": True,
                "is_flash": False,
                "is_ret": True,
                "ret_days": 7,
                "is_rep": True,
                "rep_days": 7,
                "img": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=600",
                "desc": "Everyday productivity with 13th Gen Intel Core i5 processor, 15.6 inch FHD 120Hz display, and lift hinge for ergonomic typing.",
                "specs": [
                    ("General", "Model Name", "Inspiron 3530"),
                    ("Processor", "Processor Brand", "Intel Core i5 1335U"),
                    ("Memory", "RAM", "16 GB DDR4"),
                    ("Storage", "SSD Capacity", "512 GB NVMe"),
                    ("Display", "Screen Size", "15.6 Inch Full HD Anti-Glare")
                ]
            },
            {
                "item_code": "ITM-FASH-1008",
                "title": "Men's Slim Fit 100% Cotton Denim Jacket",
                "slug": "mens-slim-fit-cotton-denim-jacket",
                "cat": categories[2],
                "subcat": subcategories[4],
                "brand": brands[8],
                "seller": sellers[2],
                "base": Decimal("1499.00"),
                "del_charge": Decimal("40.00"),
                "mrp": Decimal("2999.00"),
                "stock": 40,
                "is_feat": False,
                "is_flash": True,
                "is_ret": True,
                "ret_days": 10,
                "is_rep": True,
                "rep_days": 10,
                "img": "https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=600",
                "desc": "Classic rugged western styling crafted from durable pure cotton denim. Two chest flap pockets and adjustable button tabs on back waist.",
                "specs": [
                    ("General", "Fabric", "100% Denim Cotton"),
                    ("Fit", "Fit Type", "Regular Slim Fit"),
                    ("Pattern", "Pattern", "Solid Washed"),
                    ("Care", "Wash Care", "Machine Wash Cold")
                ]
            },
            {
                "item_code": "ITM-KITC-1009",
                "title": "Prestige Deluxe Alpha Stainless Steel Pressure Cooker, 3L",
                "slug": "prestige-deluxe-alpha-pressure-cooker-3l",
                "cat": categories[3],
                "subcat": subcategories[6],
                "brand": brands[9],
                "seller": sellers[4],
                "base": Decimal("1899.00"),
                "del_charge": Decimal("50.00"),
                "mrp": Decimal("2950.00"),
                "stock": 35,
                "is_feat": False,
                "is_flash": False,
                "is_ret": True,
                "ret_days": 10,
                "is_rep": True,
                "rep_days": 10,
                "img": "https://images.unsplash.com/photo-1584990347449-389f417f7a77?w=600",
                "desc": "Alpha base induction compatible stainless steel pressure cooker with pressure indicator, safety valve, and durable cool-touch handles.",
                "specs": [
                    ("General", "Capacity", "3 Litres"),
                    ("Material", "Material", "High Grade Stainless Steel"),
                    ("Compatibility", "Stove Compatibility", "Induction & Gas Top"),
                    ("Warranty", "Warranty", "5 Years Brand Warranty")
                ]
            },
            {
                "item_code": "ITM-BEAU-1010",
                "title": "Philips Multi Grooming Kit 9-in-1 for Beard, Hair & Body",
                "slug": "philips-multi-grooming-kit-9-in-1",
                "cat": categories[4],
                "subcat": subcategories[8],
                "brand": brands[6],
                "seller": sellers[8],
                "base": Decimal("1699.00"),
                "del_charge": Decimal("40.00"),
                "mrp": Decimal("2495.00"),
                "stock": 50,
                "is_feat": True,
                "is_flash": True,
                "is_ret": False,  # Non returnable example
                "ret_days": 0,
                "is_rep": True,
                "rep_days": 7,
                "img": "https://images.unsplash.com/photo-1621607512214-68297480165e?w=600",
                "desc": "All-in-one trimmer featuring DualCut technology for maximum precision. Includes 9 premium tools for face and hair styling with 70 min run time.",
                "specs": [
                    ("General", "Blade Material", "Self-Sharpening Steel Blades"),
                    ("Battery", "Run Time", "Up to 70 Minutes"),
                    ("Attachments", "Number of Tools", "9 Styling Attachments"),
                    ("Warranty", "Warranty", "2 Years International Warranty")
                ]
            },
            {
                "item_code": "ITM-SPRT-1011",
                "title": "FitLife Hexagonal Cast Iron Dumbbells Set (5kg x 2)",
                "slug": "fitlife-hexagonal-dumbbells-5kg-pair",
                "cat": categories[6],
                "subcat": subcategories[12],
                "brand": brands[2],
                "seller": sellers[3],
                "base": Decimal("1199.00"),
                "del_charge": Decimal("100.00"),
                "mrp": Decimal("2499.00"),
                "stock": 20,
                "is_feat": False,
                "is_flash": False,
                "is_ret": True,
                "ret_days": 7,
                "is_rep": True,
                "rep_days": 7,
                "img": "https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?w=600",
                "desc": "Heavy-duty cast iron hexagonal dumbbells with anti-roll design and textured chrome grip handle for superior home gym strength training.",
                "specs": [
                    ("General", "Weight", "10 kg total (5kg each)"),
                    ("Material", "Core Material", "Solid Cast Iron with Rubber Coat"),
                    ("Usage", "Ideal For", "Bicep Curls, Shoulder Presses, Squats")
                ]
            },
            {
                "item_code": "ITM-BOOK-1012",
                "title": "Atomic Habits by James Clear (Hardcover International Bestseller)",
                "slug": "atomic-habits-james-clear",
                "cat": categories[7],
                "subcat": subcategories[14],
                "brand": brands[0],
                "seller": sellers[7],
                "base": Decimal("499.00"),
                "del_charge": Decimal("40.00"),
                "mrp": Decimal("899.00"),
                "stock": 100,
                "is_feat": True,
                "is_flash": False,
                "is_ret": True,
                "ret_days": 7,
                "is_rep": True,
                "rep_days": 7,
                "img": "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600",
                "desc": "An Easy & Proven Way to Build Good Habits & Break Bad Ones. Packed with evidence-based self-improvement strategies.",
                "specs": [
                    ("General", "Author", "James Clear"),
                    ("General", "Publisher", "Penguin Random House"),
                    ("Format", "Binding", "Premium Hardcover"),
                    ("Pages", "Total Pages", "320 Pages")
                ]
            }
        ]

        products = []
        for pdata in product_catalog:
            p, created = Product.objects.get_or_create(
                item_code=pdata["item_code"],
                defaults={
                    "title": pdata["title"],
                    "slug": pdata["slug"],
                    "sku": f"SKU-{pdata['item_code'].replace('ITM-', '')}",
                    "category": pdata["cat"],
                    "subcategory": pdata["subcat"],
                    "brand": pdata["brand"],
                    "seller": pdata["seller"],
                    "base_price": pdata["base"],
                    "admin_commission_percentage": Decimal("10.00"),
                    "delivery_charge": pdata["del_charge"],
                    "tax_percentage": Decimal("5.00"),
                    "mrp": pdata["mrp"],
                    "stock": pdata["stock"],
                    "is_featured": pdata["is_feat"],
                    "is_flash_sale": pdata["is_flash"],
                    "is_returnable": pdata["is_ret"],
                    "return_window_days": pdata["ret_days"],
                    "is_replaceable": pdata["is_rep"],
                    "replacement_window_days": pdata["rep_days"],
                    "main_image_url": pdata["img"],
                    "description": pdata["desc"],
                    "average_rating": Decimal("4.6"),
                    "total_reviews_count": 8,
                }
            )
            # Add gallery images
            ProductImage.objects.get_or_create(
                product=p,
                image_url=pdata["img"],
                defaults={"alt_text": f"{p.title} Front View"}
            )
            ProductImage.objects.get_or_create(
                product=p,
                image_url="https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600",
                defaults={"alt_text": f"{p.title} Angle View"}
            )
            # Add specs
            for grp, sname, sval in pdata["specs"]:
                ProductSpecification.objects.get_or_create(
                    product=p,
                    name=sname,
                    defaults={"group_name": grp, "value": sval}
                )
            products.append(p)

        # 7. 10 Coupons
        coupon_data = [
            ("WELCOME50", "Welcome discount for new buyers", "flat", Decimal("50.00"), Decimal("499.00")),
            ("FESTIVE10", "Flat 10% festive discount", "percent", Decimal("10.00"), Decimal("999.00")),
            ("FREESHIP", "Free delivery coupon code", "flat", Decimal("50.00"), Decimal("299.00")),
            ("SUPERBUY20", "Mega 20% discount on big orders", "percent", Decimal("20.00"), Decimal("2499.00")),
            ("DIWALI100", "Flat ₹100 Diwali gift off", "flat", Decimal("100.00"), Decimal("1499.00")),
            ("TECH15", "15% off on Electronics and Audio", "percent", Decimal("15.00"), Decimal("1999.00")),
            ("FASHION25", "25% discount on apparel and shoes", "percent", Decimal("25.00"), Decimal("1299.00")),
            ("WEEKEND50", "Flat ₹50 weekend shopping deal", "flat", Decimal("50.00"), Decimal("799.00")),
            ("MEGA500", "Flat ₹500 off on orders above ₹5000", "flat", Decimal("500.00"), Decimal("5000.00")),
            ("FLASHSALE", "Limited time 12% instant coupon", "percent", Decimal("12.00"), Decimal("699.00")),
        ]
        for code, desc, dtype, val, min_o in coupon_data:
            Coupon.objects.get_or_create(
                code=code,
                defaults={
                    "description": desc,
                    "discount_type": dtype,
                    "discount_value": val,
                    "min_order_amount": min_o,
                    "max_discount_amount": Decimal("1000.00"),
                    "is_active": True
                }
            )

        # 8. 10 Offer Banners
        banners = [
            ("Mega Electronics Fest", "Upgrade your tech with up to 60% discount", "UP TO 60% OFF", "https://images.unsplash.com/photo-1550009158-9ebf69173e03?w=1200"),
            ("New Season Fashion", "Trending Styles for Men & Women", "FLAT 40% OFF", "https://images.unsplash.com/photo-1441984904996-e0b6ba687e04?w=1200"),
            ("Smartphones Blockbuster", "Latest 5G Phones with Exchange Offers", "EXTRA ₹5000 OFF", "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=1200"),
            ("Kitchen & Home Makeover", "Top Cookware & Appliances from ₹499", "STARTING ₹499", "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=1200"),
            ("Active Fitness & Sports", "Gym gear and running shoes at best prices", "MIN 30% OFF", "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=1200"),
            ("Audio Bonanza", "BoAt & Sony Headphones at rock bottom prices", "UP TO 70% OFF", "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=1200"),
            ("Beauty & Personal Care", "Top Skincare & Fragrance brands", "BUY 1 GET 1", "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=1200"),
            ("Super Grocery Deals", "Daily essentials delivered in 30 mins", "FLAT 20% OFF", "https://images.unsplash.com/photo-1542838132-92c53300491e?w=1200"),
            ("Footwear Fiesta", "Puma & Nike Sneakers on huge clearance", "UP TO 50% OFF", "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=1200"),
            ("Weekend Flash Deals", "Grab fast before stock runs out!", "ONLY 24 HOURS", "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=1200"),
        ]
        for title, sub, tag, img in banners:
            OfferBanner.objects.get_or_create(
                title=title,
                defaults={"subtitle": sub, "discount_tag": tag, "image_url": img, "link_url": "/customer/products/"}
            )

        # 9. 15 Orders across all stages with OTP, timeline, 10% commission
        order_statuses = [
            ("delivered", "ORD-2026-1001", customers[0], products[0], sellers[1], delivery_partners[0]),
            ("delivered", "ORD-2026-1002", customers[1], products[1], sellers[0], delivery_partners[1]),
            ("out_for_delivery", "ORD-2026-1003", customers[2], products[2], sellers[1], delivery_partners[2]),
            ("shipped", "ORD-2026-1004", customers[3], products[3], sellers[5], delivery_partners[3]),
            ("packed", "ORD-2026-1005", customers[4], products[4], sellers[5], None),
            ("processing", "ORD-2026-1006", customers[5], products[5], sellers[1], None),
            ("confirmed", "ORD-2026-1007", customers[6], products[6], sellers[1], None),
            ("pending", "ORD-2026-1008", customers[7], products[7], sellers[2], None),
            ("delivered", "ORD-2026-1009", customers[8], products[8], sellers[4], delivery_partners[4]),
            ("delivered", "ORD-2026-1010", customers[9], products[9], sellers[8], delivery_partners[5]),
            ("returned", "ORD-2026-1011", customers[0], products[3], sellers[5], delivery_partners[6]),
            ("out_for_delivery", "ORD-2026-1012", customers[1], products[0], sellers[1], delivery_partners[0]),
            ("delivered", "ORD-2026-1013", customers[2], products[11], sellers[7], delivery_partners[7]),
            ("shipped", "ORD-2026-1014", customers[3], products[10], sellers[3], delivery_partners[8]),
            ("delivered", "ORD-2026-1015", customers[4], products[5], sellers[1], delivery_partners[9]),
        ]

        orders = []
        for status, onum, cust, prod, seller, rider in order_statuses:
            qty = random.randint(1, 2)
            subtotal = prod.selling_price * qty
            del_fee = prod.delivery_charge
            grand_total = subtotal + del_fee
            admin_comm = round((prod.base_price * Decimal("0.10")) * qty, 2)
            seller_net = round(subtotal - admin_comm, 2)
            rider_earn = del_fee if del_fee > 0 else Decimal("50.00")

            order, _ = Order.objects.get_or_create(
                order_number=onum,
                defaults={
                    "customer": cust,
                    "seller": seller,
                    "delivery_partner": rider,
                    "status": status,
                    "customer_name": f"{cust.first_name} {cust.last_name}",
                    "customer_phone": cust.phone,
                    "shipping_address": f"{cust.addresses.first().street_address}, {cust.addresses.first().city} - {cust.addresses.first().pincode}",
                    "subtotal": subtotal,
                    "delivery_charge": del_fee,
                    "tax": round(subtotal * Decimal("0.05"), 2),
                    "grand_total": grand_total,
                    "admin_commission_amount": Decimal("0.00") if status in ["cancelled", "returned"] else admin_comm,
                    "seller_net_earnings": Decimal("0.00") if status in ["cancelled", "returned"] else seller_net,
                    "delivery_partner_earning": rider_earn,
                    "payment_method": random.choice(["upi", "card", "cod", "wallet"]),
                    "payment_status": "paid" if status in ["delivered", "out_for_delivery", "shipped", "packed"] else "pending",
                    "delivery_otp": str(random.randint(1000, 9999)),
                    "tracking_id": f"TRK-{onum.replace('ORD-', '')}-{random.randint(100, 999)}",
                    "customer_signature": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='30'><path d='M10 20 Q 30 5, 50 20 T 90 20' stroke='black' fill='transparent'/></svg>" if status == "delivered" else "",
                }
            )

            # OrderItem
            OrderItem.objects.get_or_create(
                order=order,
                product=prod,
                defaults={"quantity": qty, "unit_price": prod.selling_price, "total_price": subtotal}
            )

            # OrderTimeline
            OrderTimeline.objects.get_or_create(
                order=order,
                status="pending",
                defaults={"title": "Order Placed", "description": "Customer placed the order successfully."}
            )
            if status in ["confirmed", "processing", "packed", "shipped", "out_for_delivery", "delivered", "returned"]:
                OrderTimeline.objects.get_or_create(
                    order=order,
                    status="confirmed",
                    defaults={"title": "Order Confirmed", "description": "Seller accepted the order."}
                )
            if status in ["shipped", "out_for_delivery", "delivered"]:
                OrderTimeline.objects.get_or_create(
                    order=order,
                    status="shipped",
                    defaults={"title": "Package Shipped", "description": "Handed over to delivery logistics."}
                )
            if status in ["out_for_delivery", "delivered"]:
                OrderTimeline.objects.get_or_create(
                    order=order,
                    status="out_for_delivery",
                    defaults={"title": "Out for Delivery", "description": "Rider is en route to delivery address."}
                )
            if status == "delivered":
                OrderTimeline.objects.get_or_create(
                    order=order,
                    status="delivered",
                    defaults={"title": "Delivered", "description": "Order handed over to customer with OTP verification."}
                )

            # Commission Log
            CommissionLog.objects.get_or_create(
                order=order,
                defaults={
                    "rate_percentage": Decimal("10.00"),
                    "order_total": grand_total,
                    "admin_commission_amount": Decimal("0.00") if status in ["cancelled", "returned"] else admin_comm,
                    "seller_payout_amount": Decimal("0.00") if status in ["cancelled", "returned"] else seller_net,
                    "delivery_payout_amount": rider_earn,
                    "status": (
                        "settled" if status == "delivered"
                        else "cancelled" if status == "cancelled"
                        else "refunded" if status == "returned"
                        else "pending"
                    ),
                }
            )

            # Payment Transaction
            PaymentTransaction.objects.get_or_create(
                order=order,
                defaults={
                    "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
                    "amount": grand_total,
                    "payment_method": order.payment_method.upper(),
                    "status": "success" if order.payment_status == "paid" else "pending",
                }
            )
            orders.append(order)

        # 10. 10 Return & Replacement Requests
        return_reasons = [
            ("defective", "Earbuds right side not charging properly", "return", "refund_processed"),
            ("wrong_item", "Received blue color instead of black", "replace", "approved"),
            ("size_issue", "Shoe size UK 9 feels too tight, need UK 10", "replace", "replacement_dispatched"),
            ("damaged", "Outer box crushed during courier delivery", "return", "pending"),
            ("not_as_described", "Fabric is rough, not as mentioned in specs", "return", "approved"),
            ("defective", "Trimmer power switch loose", "replace", "pending"),
            ("size_issue", "Jacket sleeve length too short", "replace", "item_picked_up"),
            ("wrong_item", "Cookware lid glass is broken", "replace", "approved"),
            ("other", "Ordered by mistake, want full refund", "return", "rejected"),
            ("defective", "Volume button stuck", "return", "refund_processed"),
        ]
        for i, (reason, detail, rtype, rstat) in enumerate(return_reasons):
            ord_obj = orders[i % len(orders)]
            ReturnRequest.objects.get_or_create(
                order=ord_obj,
                defaults={
                    "customer": ord_obj.customer,
                    "request_type": rtype,
                    "reason": reason,
                    "details": detail,
                    "status": rstat,
                    "refund_amount": ord_obj.grand_total if rtype == "return" else Decimal("0.00"),
                    "refund_method": "wallet",
                    "seller_remarks": "Request verified with photo proof." if rstat in ["approved", "refund_processed", "replacement_dispatched"] else "",
                    "photo_url": "https://images.unsplash.com/photo-1584990347449-389f417f7a77?w=400",
                }
            )

        # 11. 15 Reviews with 1-5 Stars, Customer Photos, and Seller Replies
        reviews_data = [
            (products[0], customers[0], 5, "Unbelievable Sound Quality!", "Bass is super punchy and battery easily lasts 3 days. Totally worth every rupee!", "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=400", "Thank you Aman! We are glad you love the Airdopes!"),
            (products[0], customers[1], 4, "Good for the price point", "Mic quality is crisp during phone calls. Fits securely in the ear.", "", "Thanks for your valuable review Priya!"),
            (products[1], customers[2], 5, "Best iPhone ever made!", "The Dynamic Island is super handy and the 48MP camera is breathtaking.", "https://images.unsplash.com/photo-1695048133142-1a20484d2569?w=400", "Thank you Rahul! Enjoy your new iPhone 15."),
            (products[2], customers[3], 5, "Absolute beast of a phone!", "S-Pen is so productive for signing docs and notes. Screen brightness is insane.", "", "Thank you Sneha for choosing Galaxy S24 Ultra!"),
            (products[3], customers[4], 5, "Super comfortable running shoes", "Ran 10k in these on day one without any blisters. Cushioning is elite.", "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400", "Happy running Rohan! Keep sprinting."),
            (products[4], customers[5], 4, "Classic vintage look", "Suede finish is authentic. Looks amazing with raw denim.", "", "Thanks Ananya! Classic Puma never goes out of style."),
            (products[5], customers[6], 5, "Silence is golden! Best ANC", "Travelled on a 4 hour flight and could not hear any engine roar at all.", "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400", "Thank you Vikram! Sony WH-1000XM5 is engineered for peace."),
            (products[6], customers[7], 4, "Fast and lightweight laptop", "Keyboard travel is pleasant and 120Hz display makes browsing butter smooth.", "", "Thanks Pooja! Glad Dell Inspiron powers your workday."),
            (products[7], customers[8], 5, "Heavyweight authentic denim", "Stitching is top notch. Fits true to size.", "", "Thank you Karan! Enjoy the jacket."),
            (products[8], customers[9], 5, "Super sturdy cooker", "Heats evenly on my induction cooktop. Safety valve gives peace of mind.", "", "Thank you Neha! Cook delicious meals with Prestige."),
            (products[9], customers[0], 4, "Smooth trimming experience", "Blade cuts cleanly without any pulling. Battery life is very reliable.", "", "Thanks Aman! Philips precision grooming at its best."),
            (products[10], customers[1], 5, "Solid gym dumbbells", "Rubber coating protects floor. Grip is knurled properly.", "", "Great to hear Priya! Stay fit."),
            (products[11], customers[2], 5, "Life changing book!", "Simple 1% improvements compound into massive success. Must read for everyone.", "", "Thank you Rahul! Happy reading."),
            (products[0], customers[3], 5, "ASAP charging is a lifesaver", "10 minutes charge gave me nearly 2 hours playback in office commute.", "", ""),
            (products[1], customers[4], 5, "Camera portrait mode is flawless", "Colors look natural and edge detection on portraits is DSLR level.", "", ""),
        ]
        for prod, cust, rating, title, comm, photo, reply in reviews_data:
            Review.objects.get_or_create(
                product=prod,
                customer=cust,
                defaults={
                    "rating": rating,
                    "title": title,
                    "comment": comm,
                    "photo_url_1": photo,
                    "seller_reply": reply,
                    "is_verified_purchase": True,
                }
            )

        # 12. 10 Support Tickets
        tickets = [
            (customers[0], "TKT-801", "Order delivery delay inquiry", "Order Issue", "high", "in_progress", "When will order #ORD-2026-1003 reach? I have to travel.", "Your rider Mohit is already on the way and will reach in 25 minutes."),
            (customers[1], "TKT-802", "Need GST Invoice for iPhone purchase", "Billing", "medium", "resolved", "Please send GST invoice with my company name.", "Invoice has been attached to your order details page for download."),
            (customers[2], "TKT-803", "Wallet cashback not credited", "Payment", "low", "resolved", "Did not receive ₹50 cashback from yesterday deal.", "Cashback of ₹50 has been credited to your e-wallet balance."),
            (sellers[0].user, "TKT-804", "Weekly payout disbursement query", "Payout", "high", "resolved", "When will my payout of ₹54,000 for this cycle get settled?", "Settlement approved by admin and processed to your registered HDFC bank account."),
            (sellers[1].user, "TKT-805", "Need approval for new audio category", "Catalog", "medium", "in_progress", "Requested category addition for Studio Microphones.", "Catalog team is reviewing your documents."),
            (delivery_partners[0].user, "TKT-806", "Fuel incentive bonus clarification", "Incentive", "medium", "resolved", "Completed 15 deliveries today, incentive calculation?", "Weekly incentive of ₹350 added to your rider wallet."),
            (customers[3], "TKT-807", "Coupon code not applying on checkout", "Offers", "medium", "resolved", "FESTIVE10 showing invalid.", "Coupon requirement is minimum ₹999. Please check cart value."),
            (customers[4], "TKT-808", "Replacement request pickup time", "Returns", "high", "in_progress", "When will rider come to pickup defective shoe?", "Pickup assigned to Rider Deepak for 2:00 PM today."),
            (sellers[2].user, "TKT-809", "Commission calculation breakdown inquiry", "Finance", "low", "resolved", "Show me itemized platform 10% fee report.", "Commission logs can be viewed in your Seller Earnings tab."),
            (delivery_partners[1].user, "TKT-810", "Wrong customer delivery address location", "Navigation", "high", "resolved", "Pincode is correct but map marker was 2km away.", "Address coordinates updated with correct location."),
        ]
        for usr, tid, subj, cat, prio, stat, msg, rep in tickets:
            SupportTicket.objects.get_or_create(
                ticket_id=tid,
                defaults={
                    "user": usr,
                    "subject": subj,
                    "category": cat,
                    "priority": prio,
                    "status": stat,
                    "message": msg,
                    "admin_reply": rep,
                }
            )

        # 13. 25+ Notifications across all roles
        notifications_data = [
            (customers[0], "Order Shipped!", "Your order #ORD-2026-1001 is on its way with delivery partner Ramesh.", "order", "/customer/orders/"),
            (customers[0], "Price Drop Alert! 💥", "Price on Apple iPhone 15 dropped by 20% in your wishlist!", "promo", "/customer/products/"),
            (customers[1], "Delivery OTP Generated", "Your delivery verification OTP is 4921. Share with rider at doorstep.", "order", "/customer/orders/"),
            (customers[2], "Cashback Credited", "₹100 cashback credited to your E-Commerce Wallet!", "alert", "/customer/wallet/"),
            (customers[3], "Replacement Approved", "Your replacement request for Puma shoes has been approved by seller.", "order", "/customer/returns/"),
            (sellers[0].user, "New Order Received! 🔔", "You received a new order #ORD-2026-1002 for iPhone 15. Please pack the item.", "order", "/seller/orders/"),
            (sellers[1].user, "Low Stock Warning ⚠️", "boAt Airdopes 141 stock is below 15 units. Re-stock soon.", "alert", "/seller/inventory/"),
            (sellers[1].user, "Payout Credited 💰", "Weekly payout of ₹42,500 settled to your bank account.", "alert", "/seller/earnings/"),
            (sellers[2].user, "Customer Review Posted ⭐", "Customer left a 5-star review on Men's Cotton Denim Jacket.", "alert", "/seller/reviews/"),
            (sellers[3].user, "Order Cancelled", "Order #ORD-2026-1008 was cancelled by buyer.", "order", "/seller/orders/"),
            (delivery_partners[0].user, "New Delivery Job Assigned 🚚", "Pickup from TechZone Gadgets and deliver to Connaught Place.", "delivery", "/delivery/active-delivery/"),
            (delivery_partners[0].user, "Daily Earnings Updated", "You earned ₹650 from 7 completed deliveries today.", "alert", "/delivery/earnings/"),
            (delivery_partners[1].user, "Rating 5.0 Received!", "Customer praised: 'Very polite and on-time delivery!'", "alert", "/delivery/ratings/"),
            (delivery_partners[2].user, "Incentive Target Achieved! 🎯", "Completed 10 deliveries this weekend! ₹300 bonus unlocked.", "alert", "/delivery/earnings/"),
            (admin_user, "Platform Commission Settled: ₹9,999", "Automated 10% platform commission collected from Galaxy S24 Ultra order.", "alert", "/admin-panel/commissions/"),
            (admin_user, "New Seller Verification Request", "Glamour Fashion House submitted GST documents for verification.", "alert", "/admin-panel/sellers/"),
            (admin_user, "New Dispute Ticket Raised", "Ticket #TKT-801 escalated to High Priority.", "alert", "/admin-panel/support/"),
        ]
        for usr, title, msg, ntype, link in notifications_data:
            Notification.objects.get_or_create(
                user=usr,
                title=title,
                defaults={"message": msg, "notification_type": ntype, "link": link, "is_read": False}
            )

        # 14. 10 Cart items & 10 Wishlist items
        for i in range(5):
            cust = customers[i]
            cart_obj, _ = Cart.objects.get_or_create(user=cust)
            CartItem.objects.get_or_create(
                cart=cart_obj,
                product=products[i % len(products)],
                defaults={"quantity": 1}
            )
            CartItem.objects.get_or_create(
                cart=cart_obj,
                product=products[(i + 3) % len(products)],
                defaults={"quantity": 2}
            )

            wish_obj, _ = Wishlist.objects.get_or_create(user=cust)
            WishlistItem.objects.get_or_create(
                wishlist=wish_obj,
                product=products[(i + 1) % len(products)]
            )
            WishlistItem.objects.get_or_create(
                wishlist=wish_obj,
                product=products[(i + 4) % len(products)]
            )

        self.stdout.write(self.style.SUCCESS("Successfully seeded 10+ records for all database models!"))
