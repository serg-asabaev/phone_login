from django import forms
import re

class PhoneForm(forms.Form):
    """Форма для ввода номера телефона"""
    phone = forms.CharField(
        max_length=18,
        label='Номер телефона',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+79991234567',
            'autofocus': True,
        })
    )

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if not re.match(r'^\+?[0-9]{10,15}$', phone):
            raise forms.ValidationError('Неверный формат номера телефона')
        return phone


class SMSCodeForm(forms.Form):
    """Форма для ввода SMS-кода"""
    code = forms.CharField(
        max_length=4,
        min_length=4,
        label='Код из SMS',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '123456',
            'autofocus': True,
            'inputmode': 'numeric',
            'pattern': '[0-9]{4}',
        })
    )


class InviteCodeForm(forms.Form):
    """Форма для ввода инвайт-кода"""
    invite_code = forms.CharField(
        max_length=6,
        min_length=6,
        label='Инвайт-код',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ABC123',
            'autofocus': True,
            'style': 'text-transform: uppercase;',
        })
    )

    def clean_invite_code(self):
        return self.cleaned_data['invite_code'].upper().strip()