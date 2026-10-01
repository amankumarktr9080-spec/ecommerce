from django import forms
from products.models import Product

from .models import FAQItem, MarketplaceSettings


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleImageInput

    def clean(self, data, initial=None):
        if not data:
            return []
        uploads = data if isinstance(data, (list, tuple)) else [data]
        return [super(MultipleImageField, self).clean(upload, initial) for upload in uploads]


class HomepageHeroSlidesForm(forms.Form):
    hero_images = MultipleImageField(required=False)

    def clean_hero_images(self):
        images = self.cleaned_data['hero_images']
        if len(images) > 10:
            raise forms.ValidationError('Upload no more than 10 hero images at a time.')
        return images


class MarketplaceSettingsForm(forms.ModelForm):
    class Meta:
        model = MarketplaceSettings
        fields = (
            'platform_commission',
            'tax_rate',
            'base_delivery_fee',
            'max_return_window',
            'hero_badge', 'hero_title', 'hero_subtitle',
            'facebook_url', 'instagram_url', 'youtube_url', 'twitter_url',
            'privacy_policy', 'terms_conditions', 'refund_policy',
            'shipping_policy', 'cancellation_policy',
        )


class FAQItemForm(forms.ModelForm):
    class Meta:
        model = FAQItem
        fields = ('question', 'answer', 'ordering', 'is_active')


class MarketplaceContentForm(forms.ModelForm):
    class Meta:
        model = MarketplaceSettings
        fields = (
            'hero_badge', 'hero_title', 'hero_subtitle',
            'facebook_url', 'instagram_url', 'youtube_url', 'twitter_url',
            'privacy_policy', 'terms_conditions', 'refund_policy',
            'shipping_policy', 'cancellation_policy',
        )


class FeaturedProductsForm(forms.ModelForm):
    class Meta:
        model = MarketplaceSettings
        fields = ('featured_product_codes',)
        widgets = {
            'featured_product_codes': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
        }

    def clean_featured_product_codes(self):
        raw_codes = self.cleaned_data['featured_product_codes']
        codes = [code.strip() for code in raw_codes.replace(',', '\n').splitlines() if code.strip()]
        if codes == ['0']:
            return ''
        if len(codes) > 20:
            raise forms.ValidationError('Enter no more than 20 item codes.')
        if len(set(codes)) != len(codes):
            raise forms.ValidationError('Each item code can only be entered once.')

        active_codes = set(Product.objects.filter(is_active=True, item_code__in=codes).values_list('item_code', flat=True))
        missing_codes = [code for code in codes if code not in active_codes]
        if missing_codes:
            raise forms.ValidationError('Active products not found for item code(s): %(codes)s', params={'codes': ', '.join(missing_codes)})
        return '\n'.join(codes)
