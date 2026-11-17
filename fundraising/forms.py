from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError

User = get_user_model()


class LoginForm(AuthenticationForm):
      username = forms.EmailField(
         label='Электронная почта',
         max_length=150,
         widget=forms.EmailInput(attrs={
            'placeholder': 'name@example.ru',
            'autocomplete': 'email',
         }),
      ) 

      def clean(self):
         email = self.cleaned_data.get('username')
         password = self.cleaned_data.get('password')

         if email and password:
            user = User.objects.filter(email__iexact=email).first()
            if user:
                self.cleaned_data['username'] = user.username

         return super().clean()
      def __init__(self, *args, **kwargs):
         super().__init__(*args, **kwargs)

         self.fields['password'].label = 'Пароль'
         self.fields['password'].help_text = 'Не менее 8 символов'
         self.fields['password'].widget.attrs['placeholder'] = 'Не менее 8 символов'
   
class RegisterForm(UserCreationForm):
    name = forms.CharField(
        label='Имя',
        max_length=150,
        widget=forms.TextInput(attrs={
            'placeholder': 'Например, Анна Иванова',
            'autocomplete': 'name',
        }),
    )

    email = forms.EmailField(
        label='Электронная почта',
        max_length=150,
        widget=forms.EmailInput(attrs={
            'placeholder': 'name@example.ru',
            'autocomplete': 'email',
        }),
    )

    class Meta:
        model = User
        fields = ('name', 'email', 'password1', 'password2')

    def clean_name(self):
        name = ' '.join(self.cleaned_data['name'].split())
        if len(name.split()) < 2:
            raise ValidationError('Введите имя и фамилию через пробел.')
        return name
    def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)

      self.fields['password1'].label = 'Пароль'
      self.fields['password1'].help_text = 'Не менее 8 символов'
      self.fields['password1'].widget.attrs['placeholder'] = 'Не менее 8 символов'

      self.fields['password2'].label = 'Повторите пароль'
      self.fields['password2'].widget.attrs['placeholder'] = 'Пароль ещё раз'