from django import forms

from .models import Delegation


class DelegacionForm(forms.Form):
    nombre = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej.: Delegación Las Compañías',
        }),
    )
    ambito = forms.CharField(
        label='Ámbito territorial',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Describe el territorio o área que cubre esta delegación',
        }),
    )
    estado = forms.ChoiceField(
        choices=[('Activa', 'Activa'), ('Inactiva', 'Inactiva')],
        widget=forms.RadioSelect,
        required=False,
        initial='Activa',
    )

    def __init__(self, *args, excluir_id=None, **kwargs):
        self.excluir_id = excluir_id
        super().__init__(*args, **kwargs)

    def clean_nombre(self):
        nombre = self.cleaned_data['nombre'].strip()
        if len(nombre) < 4:
            raise forms.ValidationError('El nombre debe tener al menos 4 caracteres.')
        qs = Delegation.objects.filter(name__iexact=nombre)
        if self.excluir_id:
            qs = qs.exclude(pk=self.excluir_id)
        if qs.exists():
            raise forms.ValidationError('Ya existe una delegación con ese nombre.')
        return nombre
