from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.db import transaction
from django.utils.text import slugify

from products.models import Product, ProductImage, ProductSpecification
from sellers.models import SellerProductOffer


PRODUCT_DATA = {
    "Electronics": [
        ("NovaSound Bluetooth Speaker", "Portable wireless speaker with rich bass, clear vocals, and all-day battery life."),
        ("PulseFit Smartwatch", "Fitness smartwatch with heart-rate tracking, sleep insights, and message notifications."),
        ("ClearView 24-inch LED Monitor", "Slim Full HD monitor with vivid colors, eye comfort mode, and HDMI connectivity."),
        ("VoltEdge 20000mAh Power Bank", "High-capacity fast-charging power bank with dual USB output and LED battery indicator."),
        ("KeyPro Wireless Keyboard", "Low-profile wireless keyboard with quiet keys and comfortable all-day typing."),
        ("ClickMate Ergonomic Mouse", "Responsive wireless mouse with silent clicks, adjustable sensitivity, and ergonomic grip."),
        ("HomeGuard Indoor Security Camera", "Compact Wi-Fi camera with night vision, motion alerts, and two-way audio."),
        ("StreamBox 4K Media Player", "Smart streaming device with 4K HDR playback, voice search, and dual-band Wi-Fi."),
        ("AirPure Mini Air Purifier", "Quiet desktop air purifier with a replaceable filter for cleaner personal spaces."),
        ("GlowLine USB Desk Lamp", "Adjustable LED desk lamp with three color modes, touch control, and USB power."),
    ],
    "Mobiles & Tablets": [
        ("PixelView 5G Smartphone", "Fast 5G smartphone with a bright display, dual camera system, and dependable battery."),
        ("TabPlus 10-inch Android Tablet", "Large-screen tablet for streaming, study, browsing, and everyday productivity."),
        ("PowerCell 5000mAh Smartphone", "Reliable smartphone with long battery life, crisp cameras, and smooth multitasking."),
        ("NoteMax Stylus Tablet", "Creative tablet with a responsive stylus, vivid display, and expandable storage."),
        ("SnapGo Dual Camera Phone", "Everyday phone with portrait photography, secure face unlock, and fast charging."),
        ("LinkPro 5G Mobile", "Modern 5G handset with a smooth refresh-rate display and dependable performance."),
        ("ReadLite 8-inch Tablet", "Lightweight reading and entertainment tablet with a comfortable eye-care display."),
        ("ChargeHub Mobile Stand", "Adjustable charging stand that keeps your phone visible while it powers up."),
        ("ShieldGlass Screen Protector", "Tempered glass screen protector with precise fit and smooth touch response."),
        ("FlexiGrip Phone Holder", "Rotating phone holder for desks and vehicles with a secure adjustable grip."),
    ],
    "Fashion & Apparel": [
        ("UrbanWeave Cotton Shirt", "Breathable cotton shirt with a clean fit for casual workdays and weekend outings."),
        ("Everyday Chino Trousers", "Stretch chino trousers with a tailored silhouette and comfortable all-day fabric."),
        ("LoomCraft Printed Kurta", "Soft printed kurta with easy movement and versatile styling for daily wear."),
        ("CloudSoft Oversized T-shirt", "Relaxed-fit cotton t-shirt with a soft finish and modern streetwear look."),
        ("Classic Ribbed Cardigan", "Layer-friendly ribbed cardigan with a warm knit and timeless button front."),
        ("ActiveFlex Track Pants", "Flexible track pants with breathable fabric, drawstring waist, and zip pockets."),
        ("Everyday Canvas Backpack", "Durable canvas backpack with organized compartments for work and travel."),
        ("Luna Crossbody Handbag", "Compact crossbody handbag with a secure zip closure and adjustable strap."),
        ("Heritage Leather Belt", "Classic leather belt with a durable buckle for smart and casual outfits."),
        ("SoftStep Cotton Socks Set", "Comfortable cotton socks with stretch support and breathable everyday wear."),
    ],
    "Home & Kitchen": [
        ("ChefMate Nonstick Fry Pan", "Even-heating nonstick fry pan with a comfortable handle for everyday cooking."),
        ("FreshLock Storage Container Set", "Airtight food storage containers that keep pantry and refrigerator items fresh."),
        ("BrewEase Electric Kettle", "Quick-boil electric kettle with auto shut-off, dry-boil protection, and easy pouring."),
        ("BlendPro Mixer Grinder", "Multi-speed mixer grinder with stainless steel jars for kitchen preparation."),
        ("PureSip Water Bottle", "Reusable insulated bottle that keeps drinks cold or warm while traveling."),
        ("SoftNest Cushion Cover Set", "Decorative cushion covers with durable stitching and easy-care fabric."),
        ("WarmGlow Table Lamp", "Ambient table lamp with a warm glow and compact design for bedrooms and desks."),
        ("CleanSweep Microfiber Mop", "Lightweight floor mop with washable microfiber head and easy swivel movement."),
        ("BambooServe Serving Tray", "Strong bamboo serving tray with raised edges for safe dining and hosting."),
        ("HomeEase Curtain Pair", "Room-darkening curtain pair with easy-fit eyelets and a smooth woven finish."),
    ],
    "Beauty & Grooming": [
        ("GlowCare Vitamin C Face Serum", "Lightweight vitamin C serum that supports a brighter, refreshed-looking complexion."),
        ("SilkTouch Hair Dryer", "Compact hair dryer with multiple heat settings and a focused styling nozzle."),
        ("PureBlend Face Wash", "Gentle daily face wash that removes excess oil without leaving skin feeling dry."),
        ("VelvetMatte Lip Color", "Comfortable long-wear lip color with rich pigment and a smooth matte finish."),
        ("FreshMist Body Spray", "Light everyday body mist with a clean fragrance for lasting freshness."),
        ("NourishRoot Hair Oil", "Nourishing hair oil blend designed for a relaxing scalp massage and soft hair."),
        ("ProShape Grooming Trimmer", "Cordless precision trimmer with adjustable settings for beard and body grooming."),
        ("CalmAura Bath Gift Set", "Relaxing bath essentials with a soothing fragrance for an at-home spa routine."),
        ("SoftGlow Makeup Brush Set", "Essential makeup brushes with soft bristles and easy-grip handles."),
        ("SunShield SPF 50 Lotion", "Fast-absorbing sunscreen lotion with broad-spectrum SPF 50 protection."),
    ],
    "Grocery & Essentials": [
        ("GoldenHarvest Basmati Rice", "Aromatic long-grain basmati rice suitable for biryani, pulao, and daily meals."),
        ("DailyPure Cooking Oil", "Light cooking oil for everyday frying, sauteing, and home-style recipes."),
        ("FarmFresh Toor Dal", "Clean, protein-rich toor dal for comforting dals, soups, and traditional meals."),
        ("MorningBlend Ground Coffee", "Freshly ground coffee blend with a balanced aroma for a smooth morning brew."),
        ("GreenLeaf Herbal Tea", "Refreshing herbal tea blend made for a calming break at any time of day."),
        ("CrunchTime Trail Mix", "Balanced snack mix of nuts, seeds, and dried fruit for convenient energy."),
        ("SweetField Organic Jaggery", "Naturally sweet jaggery for traditional recipes, drinks, and mindful pantry choices."),
        ("KitchenFresh Spices Box", "Essential ground spices packed for flavorful everyday Indian cooking."),
        ("DailyBite Oats Pack", "Whole-grain oats for quick breakfasts, smoothies, and healthy snack recipes."),
        ("CleanHome Liquid Detergent", "Effective liquid detergent that lifts daily stains while caring for fabric."),
    ],
    "Sports & Fitness": [
        ("RunTrack Performance Shoes", "Cushioned running shoes with breathable mesh and supportive everyday comfort."),
        ("FlexCore Yoga Mat", "Non-slip exercise mat with comfortable cushioning for yoga and floor workouts."),
        ("IronGrip Resistance Bands", "Progressive resistance band set for strength, mobility, and home workouts."),
        ("HydraSport Steel Bottle", "Leak-resistant insulated sports bottle for hydration during training and travel."),
        ("ProKick Football", "Durable training football with balanced shape for practice and recreational play."),
        ("CourtMaster Badminton Racket", "Lightweight badminton racket with a responsive frame for quick rallies."),
        ("ActiveGuard Knee Support", "Stretch-fit knee support designed to provide comfortable stability during activity."),
        ("FitCore Skipping Rope", "Adjustable speed skipping rope with smooth bearings for cardio training."),
        ("GymMate Training Gloves", "Breathable workout gloves with padded palms and secure wrist closure."),
        ("LiftStrong Dumbbell Pair", "Compact coated dumbbell pair for controlled strength training at home."),
    ],
    "Books & Stationery": [
        ("Focus Planner 2026", "Undated productivity planner with weekly layouts, goals, and habit tracking pages."),
        ("Creative Sketchbook A4", "Thick-paper sketchbook suitable for pencils, charcoal, markers, and creative notes."),
        ("LearnFast Coding Handbook", "Practical beginner handbook covering programming concepts through clear examples."),
        ("World History Illustrated", "Accessible illustrated guide to major events, people, and civilizations."),
        ("Mindful Living Journal", "Guided journal with reflection prompts for planning, gratitude, and daily calm."),
        ("Classic Mystery Collection", "Curated collection of engaging mystery stories for relaxed reading sessions."),
        ("ExamReady Revision Notebook", "Structured revision notebook with subject sections and quick review pages."),
        ("ColorCraft Art Supply Box", "Creative art set with colored pencils, sketch pens, eraser, and sharpener."),
        ("OfficePro Gel Pen Set", "Smooth-writing gel pens with comfortable grip and dependable ink flow."),
        ("StudyDesk Sticky Notes Pack", "Color-coded sticky notes for reminders, bookmarking, and organized study."),
    ],
    "Toys & Baby Care": [
        ("BuildBright Magnetic Tiles", "Colorful magnetic tiles that encourage creative building and spatial thinking."),
        ("LittleLearner Shape Sorter", "Interactive shape sorter that supports early recognition and fine motor skills."),
        ("TinySteps Baby Bib Set", "Soft easy-clean bibs with secure fastening for comfortable mealtimes."),
        ("WonderWheels Pullback Cars", "Bright pullback toy cars designed for imaginative racing and play."),
        ("StoryTime Animal Puzzle", "Chunky-piece animal puzzle that makes early learning fun and hands-on."),
        ("DreamNest Baby Blanket", "Gentle breathable baby blanket with a soft finish for cozy naps."),
        ("SplashFun Bath Toy Set", "Colorful floating bath toys that make bath time playful and engaging."),
        ("MiniChef Pretend Kitchen Set", "Pretend-play kitchen accessories that encourage creativity and role play."),
        ("BrainBoost Number Cards", "Learning cards for practicing numbers, counting, and early math skills."),
        ("CuddleBear Plush Toy", "Soft cuddly plush companion made for imaginative play and bedtime comfort."),
    ],
    "Footwear & Shoes": [
        ("SprintEase Running Shoes", "Lightweight running shoes with cushioned soles and breathable upper for daily miles."),
        ("UrbanWalk Casual Sneakers", "Versatile casual sneakers with supportive footbed and everyday street style."),
        ("Heritage Leather Loafers", "Polished leather loafers with a comfortable fit for office and formal occasions."),
        ("TrailBound Outdoor Shoes", "Durable outdoor shoes with grippy sole for walks, hikes, and weekend travel."),
        ("CloudStep Walking Shoes", "Soft-cushion walking shoes designed for comfortable movement throughout the day."),
        ("FlexiFit Training Shoes", "Stable training shoes with flexible forefoot for gym sessions and active routines."),
        ("Classic Comfort Sandals", "Easy slip-on sandals with supportive footbed and durable everyday construction."),
        ("MiniStride Kids Sneakers", "Comfortable kids sneakers with flexible sole and easy secure fastening."),
        ("VelvetOccasion Heels", "Elegant occasion heels with a balanced heel and cushioned insole."),
        ("RainGuard Waterproof Boots", "Weather-ready waterproof boots with durable sole for rainy commutes."),
    ],
}


class Command(BaseCommand):
    help = "Repair generic products with unique catalog details"

    @transaction.atomic
    def handle(self, *args, **options):
        repaired = 0
        for category_name, entries in PRODUCT_DATA.items():
            entries_by_title = dict(entries)
            products = list(
                Product.objects.filter(category__name=category_name)
                .filter(Q(title__contains=" Product ") | Q(title__in=entries_by_title))
                .order_by("id")
            )
            for index, product in enumerate(products):
                already_repaired = product.title in entries_by_title
                title, description = (
                    (product.title, product.description)
                    if already_repaired else entries[index % len(entries)]
                )
                slug = product.slug if already_repaired else slugify(title)
                image_url = product.main_image_url or f"https://picsum.photos/seed/{slug}-{product.id}/600/600"
                update_fields = [] if already_repaired else ["title", "slug", "description", "main_image_url"]
                if (
                    product.selling_price == product.base_price
                    and product.admin_commission_percentage > 0
                    and not SellerProductOffer.objects.filter(product=product).exists()
                ):
                    old_selling_price = product.selling_price
                    commission = product.base_price * product.admin_commission_percentage / Decimal("100")
                    tax = product.base_price * product.tax_percentage / Decimal("100")
                    product.selling_price = (
                        product.base_price + commission + product.delivery_charge + tax
                    ).quantize(Decimal("0.01"))
                    if product.mrp == (old_selling_price * Decimal("1.3")).quantize(Decimal("0.01")):
                        product.mrp = (product.selling_price * Decimal("1.3")).quantize(Decimal("0.01"))
                    product.discount_percentage = (
                        round((product.mrp - product.selling_price) / product.mrp * Decimal("100"))
                        if product.mrp > product.selling_price else Decimal("0.00")
                    )
                    update_fields.extend(["selling_price", "mrp", "discount_percentage"])
                product.title = title
                product.slug = slug
                product.description = description
                product.main_image_url = image_url
                if update_fields:
                    product.save(update_fields=update_fields)

                ProductImage.objects.get_or_create(
                    product=product,
                    image_url=image_url,
                    defaults={"alt_text": f"{title} product image"},
                )
                specs = [
                    ("Highlights", "Product Type", title),
                    ("Highlights", "Best For", "Everyday use and reliable performance"),
                    ("Care", "Care Instructions", "Use as directed and store in a clean, dry place"),
                ]
                for group_name, name, value in specs:
                    ProductSpecification.objects.update_or_create(
                        product=product,
                        name=name,
                        defaults={"group_name": group_name, "value": value},
                    )
                repaired += 1

        self.stdout.write(self.style.SUCCESS(f"Repaired {repaired} generic products with unique details."))
