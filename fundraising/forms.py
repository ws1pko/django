from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from .models import Campaign, CampaignUpdate, Organization

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


class OrganizationApplicationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ('name', 'registration_number', 'description')
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Например, фонд «Добрые сердца»',
                'autocomplete': 'organization',
            }),
            'registration_number': forms.TextInput(attrs={
                'placeholder': '10 или 12 цифр',
                'inputmode': 'numeric',
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Расскажите, кому помогает организация и чем занимается',
                'rows': 5,
            }),
        }


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ('campaign_type', 'title', 'category', 'goal_amount', 'deadline',
                  'description', 'is_group', 'organization', 'image')
        widgets = {
            'campaign_type': forms.Select(),
            'title': forms.TextInput(attrs={'placeholder': 'Например, поможем приюту «Лапа»'}),
            'goal_amount': forms.NumberInput(attrs={'min': '1', 'step': '1', 'placeholder': '120000'}),
            'deadline': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={
                'placeholder': 'Расскажите, кому нужна помощь и на что пойдут средства',
                'rows': 5,
            }),
            'is_group': forms.CheckboxInput(),
            'organization': forms.Select(),
            'image': forms.ClearableFileInput(attrs={'accept': '.jpg,.jpeg,.png,.webp'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['organization'].required = False
        self.fields['organization'].queryset = Organization.objects.filter(
            created_by=user,
            verification_status=Organization.VerificationStatus.VERIFIED,
        ) if user else Organization.objects.none()
        self.fields['organization'].empty_label = 'Выберите проверенную организацию'
        self.fields['image'].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('campaign_type') == Campaign.CampaignType.ORGANIZATION:
            if not cleaned.get('organization'):
                self.add_error('organization', 'Выберите свою проверенную организацию.')
        else:
            cleaned['organization'] = None
        return cleaned


class CampaignUpdateForm(forms.ModelForm):
    class Meta:
        model = CampaignUpdate
        fields = ('title', 'text')
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Например, закупили первую партию корма'}),
            'text': forms.Textarea(attrs={
                'placeholder': 'Расскажите подписчикам, что нового произошло',
                'rows': 6,
            }),
        }
