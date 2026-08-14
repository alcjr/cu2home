from django import forms
from django.utils.translation import gettext_lazy as _

from apps.properties.constants import PROPERTY_TYPES, DEFAULT_FAVORITE_LIST_NAME
from apps.properties.models import SavedSearch


class SaveSearchForm(forms.ModelForm):
    class Meta:
        model = SavedSearch
        fields = ['name', 'frequency', 'query_params']
        widgets = {
            'query_params': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.name:
            self.fields['name'].initial = DEFAULT_FAVORITE_LIST_NAME


class FavoriteListForm(forms.Form):
    name = forms.CharField(max_length=100, required=True, label=_('List name'))
    # Puedes agregar más campos según tu lógica