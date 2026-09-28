from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q


class LoginForm(forms.Form):
    """Authenticates against Django auth User and links to StaffProfile."""

    username = forms.CharField(
        label='Usuario',
        widget=forms.TextInput(attrs={'class': 'form-control', 'autofocus': True, 'placeholder': 'Nombre de usuario'})
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña'})
    )

    def clean(self):
        cleaned = super().clean()
        usuario = cleaned.get('username')
        password = cleaned.get('password')
        if usuario and password:
            usuario = usuario.strip()
            user = authenticate(username=usuario, password=password)
            if not user:
                # Also check if username field is an email address
                user_obj = get_user_model().objects.filter(email__iexact=usuario).first()
                if user_obj and user_obj.check_password(password):
                    user = user_obj
            if not user or not user.is_active:
                raise forms.ValidationError('Usuario o contraseña incorrectos.')
            self.user = user
            profile = getattr(user, 'staff_profile', None)
            display_name = profile.display_name if profile else (user.get_full_name() or user.username)
            role = (
                profile.legacy_role
                if profile and profile.legacy_role
                else ('administrador' if user.is_superuser else 'funcionario')
            )
            self.persona = {
                'nombre': display_name,
                'rol': role,
                'usuario': user.username,
            }
        return cleaned

    def get_user(self):
        return getattr(self, 'user', None)

    def get_persona(self):
        return getattr(self, 'persona', None)


class RegistroForm(forms.Form):
    """Creates a new User and associated StaffProfile in the relational DB."""

    first_name = forms.CharField(
        label='Nombre', max_length=150, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre'})
    )
    last_name = forms.CharField(
        label='Apellido', max_length=150, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido'})
    )
    username = forms.CharField(
        label='Nombre de usuario', max_length=150, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de usuario'})
    )
    email = forms.EmailField(
        label='Correo electrónico', required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'nombre@laserena.cl'})
    )
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña'})
    )
    password2 = forms.CharField(
        label='Repite la contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Repite la contraseña'})
    )

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Ya existe una cuenta con ese nombre de usuario.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta registrada con ese correo.')
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        if p1 and len(p1) < 8:
            raise forms.ValidationError('La contraseña debe tener al menos 8 caracteres.')
        return cleaned

    def save(self):
        from .models import StaffProfile

        User = get_user_model()
        first_name = self.cleaned_data['first_name'].strip()
        last_name = self.cleaned_data['last_name'].strip()
        username = self.cleaned_data['username'].strip()
        email = self.cleaned_data['email'].strip().lower()
        password = self.cleaned_data['password1']

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        display_name = f"{first_name} {last_name}".strip()
        StaffProfile.objects.create(
            user=user,
            display_name=display_name,
            legacy_role='funcionario',
        )
        self.user = user
        return {
            'nombre': display_name,
            'rol': 'funcionario',
            'usuario': user.username,
        }


class BuscarUsuarioForm(forms.Form):
    """Password recovery step 1: identify account by username or email."""

    identificador = forms.CharField(
        label='Usuario o correo electrónico',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tu usuario o correo', 'autofocus': True})
    )

    def buscar_usuario(self):
        ident = self.cleaned_data.get('identificador', '').strip()
        user = get_user_model().objects.filter(
            Q(username__iexact=ident) | Q(email__iexact=ident)
        ).first()
        if user:
            profile = getattr(user, 'staff_profile', None)
            display_name = profile.display_name if profile else (user.get_full_name() or user.username)
            return {
                'usuario': user.username,
                'nombre': display_name,
                'correo': user.email,
            }
        return None


class NuevaPasswordForm(forms.Form):
    """Password recovery step 2: define and validate new password."""

    password1 = forms.CharField(
        label='Nueva contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nueva contraseña'})
    )
    password2 = forms.CharField(
        label='Repite la nueva contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Repite la nueva contraseña'})
    )

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        if p1 and len(p1) < 8:
            raise forms.ValidationError('La contraseña debe tener al menos 8 caracteres.')
        return cleaned
