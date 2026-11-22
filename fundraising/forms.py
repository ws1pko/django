from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Campaign, CampaignUpdate, Organization, Report, ReportDocument
from django.core.validators import FileExtensionValidator
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
    image = forms.ImageField(
        required=False,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['jpg', 'jpeg', 'png', 'webp'],
            ),
        ],
        widget=forms.ClearableFileInput(
            attrs={'accept': '.jpg,.jpeg,.png,.webp'}
        ),
    )

    class Meta:
        model = Campaign
        fields = (
            'campaign_type',
            'title',
            'category',
            'goal_amount',
            'deadline',
            'description',
            'is_group',
            'organization',
            'image',
        )
        widgets = {
            'campaign_type': forms.Select(),
            'title': forms.TextInput(
                attrs={'placeholder': 'Например, поможем приюту «Лапа»'}
            ),
            'goal_amount': forms.NumberInput(
                attrs={
                    'min': '0.01',
                    'step': '0.01',
                    'placeholder': '120000',
                }
            ),
            'deadline': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={
                'placeholder': 'Расскажите, кому нужна помощь и на что пойдут средства',
                'rows': 5,
            }),
            'is_group': forms.CheckboxInput(),
            'organization': forms.Select(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields['deadline'].widget.attrs['min'] = today.isoformat()
        self.fields['organization'].required = False
        self.fields['organization'].queryset = (
            Organization.objects.filter(
                created_by=user,
                verification_status=Organization.VerificationStatus.VERIFIED,
            )
            if user else Organization.objects.none()
        )
        self.fields['organization'].empty_label = 'Выберите проверенную организацию'
        self.fields['image'].required = False

        if self.instance.pk:
            # An expired campaign must receive a new valid deadline before it
            # can be edited and sent for moderation again.
            self.fields['deadline'].required = self.instance.deadline < today

    def clean_deadline(self):
        deadline = self.cleaned_data.get('deadline')
        if deadline and deadline < timezone.localdate():
            raise ValidationError('Дата окончания сбора не может быть в прошлом.')
        return deadline

    def clean_image(self):
        uploaded = self.cleaned_data.get('image')
        if not uploaded:
            return uploaded

        extension = (
            '.' + uploaded.name.rsplit('.', 1)[-1].lower()
            if '.' in uploaded.name else ''
        )
        expected_formats = {
            '.jpg': 'JPEG',
            '.jpeg': 'JPEG',
            '.png': 'PNG',
            '.webp': 'WEBP',
        }
        actual_format = getattr(
            getattr(uploaded, 'image', None),
            'format',
            None,
        )

        if actual_format != expected_formats.get(extension):
            raise ValidationError(
                'Содержимое файла не соответствует его расширению.'
            )

        return uploaded

    def clean(self):
        cleaned = super().clean()

        if (
            self.instance.pk
            and not self.fields['deadline'].required
            and not cleaned.get('deadline')
        ):
            cleaned['deadline'] = self.instance.deadline

        if cleaned.get('campaign_type') == Campaign.CampaignType.ORGANIZATION:
            if not cleaned.get('organization'):
                self.add_error(
                    'organization',
                    'Выберите свою проверенную организацию.',
                )
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

class ReportForm(forms.ModelForm):
    document = forms.FileField(
        label='Подтверждающий документ',
        help_text='PDF, JPG или PNG, не более 10 МБ.',
    )
    caption = forms.CharField(
        label='Подпись к документу',
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={'placeholder': 'Например, чек за корм'}
        ),
    )

    class Meta:
        model = Report
        fields = ('spent_amount', 'description')
        widgets = {
            'spent_amount': forms.NumberInput(attrs={
                'min': '0',
                'step': '0.01',
                'placeholder': 'Например, 12500',
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Опишите результат сбора и на что потрачены средства',
                'rows': 6,
            }),
        }

    def clean_document(self):
        uploaded = self.cleaned_data['document']
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}

        extension = (
            f".{uploaded.name.rsplit('.', 1)[-1].lower()}"
            if '.' in uploaded.name
            else ''
        )

        if extension not in allowed_extensions:
            raise ValidationError(
                'Неподдерживаемый формат файла. Допускаются PDF, JPG и PNG.'
            )

        if uploaded.size > 10 * 1024 * 1024:
            raise ValidationError(
                'Размер файла не должен превышать 10 МБ.'
            )

        header = uploaded.read(8)
        uploaded.seek(0)

        valid_signature = {
            '.pdf': header.startswith(b'%PDF-'),
            '.jpg': header.startswith(b'\xff\xd8\xff'),
            '.jpeg': header.startswith(b'\xff\xd8\xff'),
            '.png': header.startswith(b'\x89PNG\r\n\x1a\n'),
        }

        if not valid_signature[extension]:
            raise ValidationError(
                'Содержимое файла не соответствует его формату.'
            )

        return uploaded
