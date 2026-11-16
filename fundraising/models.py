from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MaxLengthValidator,
    MinLengthValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.db.models import Q


MAX_REPORT_FILE_SIZE = 10 * 1024 * 1024  # 10 МБ


def validate_report_document_size(uploaded_file):
    if uploaded_file.size > MAX_REPORT_FILE_SIZE:
        raise ValidationError('Размер файла не должен превышать 10 МБ.')


class User(AbstractUser):
    class Role(models.TextChoices):
        DONOR = 'donor', 'Жертвователь'
        ORGANIZER = 'organizer', 'Организатор'
        MODERATOR = 'moderator', 'Модератор'

    # username, password, is_active и date_joined унаследованы от AbstractUser.
    # Django хранит хеш пароля в поле password.
    email = models.EmailField('электронная почта', unique=True)
    role = models.CharField(
        'роль',
        max_length=20,
        choices=Role.choices,
        default=Role.DONOR,
    )

    class Meta:
        verbose_name = 'пользователь'
        verbose_name_plural = 'пользователи'
        ordering = ['username']

    def __str__(self):
        return self.username


class Category(models.Model):
    class Theme(models.TextChoices):
        ANIMALS = 'animals', 'Помощь животным'
        FAMILY = 'family', 'Помощь людям и семьям'
        EDUCATION = 'education', 'Образование'
        GENERAL = 'general', 'Другая помощь'

    name = models.CharField('название', max_length=100, unique=True)
    description = models.CharField(
        'описание',
        max_length=500,
        blank=True,
    )
    theme = models.CharField(
        'тема оформления',
        max_length=20,
        choices=Theme.choices,
        default=Theme.GENERAL,
    )
    image = models.FileField(
        'изображение категории',
        upload_to='categories/',
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'svg'],
            ),
        ],
    )

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'категории'
        ordering = ['name']

    def __str__(self):
        return self.name


class Organization(models.Model):
    class VerificationStatus(models.TextChoices):
        PENDING = 'pending', 'На проверке'
        VERIFIED = 'verified', 'Проверена'
        REJECTED = 'rejected', 'Отклонена'

    name = models.CharField('название', max_length=200)
    description = models.TextField(
        'описание',
        validators=[MaxLengthValidator(5000)],
    )
    registration_number = models.CharField(
        'регистрационный номер',
        max_length=12,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^(?:\d{10}|\d{12})$',
                message='Укажите регистрационный номер из 10 или 12 цифр.',
            ),
        ],
    )
    verification_status = models.CharField(
        'статус проверки',
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_organizations',
        verbose_name='создал',
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='verified_organizations',
        verbose_name='проверил',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(
        'дата создания',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'организация'
        verbose_name_plural = 'организации'
        ordering = ['name']

    def __str__(self):
        return self.name


class Campaign(models.Model):
    class CampaignType(models.TextChoices):
        PERSONAL = 'personal', 'Личный сбор'
        ORGANIZATION = 'organization', 'Сбор организации или проекта'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Черновик'
        PENDING = 'pending', 'На модерации'
        ACTIVE = 'active', 'Активный'
        REJECTED = 'rejected', 'Отклонён'
        COMPLETED = 'completed', 'Завершён'
        CLOSED = 'closed', 'Закрыт'

    title = models.CharField('название', max_length=150)
    description = models.TextField(
        'описание',
        validators=[
            MinLengthValidator(1),
            MaxLengthValidator(10000),
        ],
    )
    goal_amount = models.DecimalField(
        'целевая сумма',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    campaign_type = models.CharField(
        'тип сбора',
        max_length=20,
        choices=CampaignType.choices,
    )
    is_group = models.BooleanField(
        'групповой сбор',
        default=False,
    )
    status = models.CharField(
        'статус',
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    deadline = models.DateField('срок окончания')
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='organized_campaigns',
        verbose_name='организатор',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='campaigns',
        verbose_name='категория',
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='campaigns',
        verbose_name='организация',
        null=True,
        blank=True,
    )
    moderation_comment = models.TextField(
        'комментарий модератора',
        blank=True,
        validators=[MaxLengthValidator(2000)],
    )
    created_at = models.DateTimeField(
        'дата создания',
        auto_now_add=True,
    )
    published_at = models.DateTimeField(
        'дата публикации',
        null=True,
        blank=True,
    )

    subscribers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='Subscription',
        related_name='subscribed_campaigns',
        verbose_name='подписчики',
        blank=True,
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='CampaignParticipant',
        related_name='participating_campaigns',
        verbose_name='участники',
        blank=True,
    )

    class Meta:
        verbose_name = 'сбор'
        verbose_name_plural = 'сборы'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=Q(goal_amount__gt=0),
                name='campaign_goal_positive',
            ),
        ]

    def __str__(self):
        return self.title


class Donation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает'
        COMPLETED = 'completed', 'Учтено'
        CANCELLED = 'cancelled', 'Отменено'

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.PROTECT,
        related_name='donations',
        verbose_name='сбор',
    )
    donor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='donations',
        verbose_name='жертвователь',
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        'сумма',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    status = models.CharField(
        'статус',
        max_length=12,
        choices=Status.choices,
        default=Status.COMPLETED,
    )
    created_at = models.DateTimeField(
        'дата пожертвования',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'пожертвование'
        verbose_name_plural = 'пожертвования'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name='donation_amount_positive',
            ),
        ]

    def __str__(self):
        return f'{self.amount} — {self.campaign.title}'


class CampaignUpdate(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Черновик'
        PUBLISHED = 'published', 'Опубликовано'

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='updates',
        verbose_name='сбор',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='campaign_updates',
        verbose_name='автор',
    )
    title = models.CharField('заголовок', max_length=150)
    text = models.TextField(
        'текст',
        validators=[
            MinLengthValidator(1),
            MaxLengthValidator(5000),
        ],
    )
    status = models.CharField(
        'статус',
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(
        'дата создания',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'обновление сбора'
        verbose_name_plural = 'обновления сборов'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Report(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'На проверке'
        APPROVED = 'approved', 'Одобрен'
        REJECTED = 'rejected', 'Отклонён'

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name='сбор',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_reports',
        verbose_name='автор отчёта',
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='moderated_reports',
        verbose_name='модератор',
        null=True,
        blank=True,
    )
    description = models.TextField(
        'описание результата',
        validators=[
            MinLengthValidator(1),
            MaxLengthValidator(5000),
        ],
    )
    spent_amount = models.DecimalField(
        'израсходованная сумма',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
    )
    status = models.CharField(
        'статус',
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(
        'дата создания',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'отчёт'
        verbose_name_plural = 'отчёты'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=Q(spent_amount__gte=0),
                name='report_spent_nonnegative',
            ),
        ]

    def __str__(self):
        return f'Отчёт: {self.campaign.title}'


class ReportDocument(models.Model):
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='отчёт',
    )
    file = models.FileField(
        'файл',
        upload_to='report_documents/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'png', 'jpg', 'jpeg'],
            ),
            validate_report_document_size,
        ],
    )
    uploaded_at = models.DateTimeField(
        'дата загрузки',
        auto_now_add=True,
    )
    caption = models.CharField(
        'подпись',
        max_length=200,
        blank=True,
    )

    class Meta:
        verbose_name = 'документ отчёта'
        verbose_name_plural = 'документы отчётов'
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.caption or self.file.name


class Subscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription_links',
        verbose_name='пользователь',
    )
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='subscription_links',
        verbose_name='сбор',
    )
    is_active = models.BooleanField(
        'активна',
        default=True,
    )
    created_at = models.DateTimeField(
        'дата подписки',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'подписка на обновления'
        verbose_name_plural = 'подписки на обновления'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'campaign'],
                name='unique_user_campaign_subscription',
            ),
        ]

    def __str__(self):
        return f'{self.user} — {self.campaign}'


class CampaignParticipant(models.Model):
    class ParticipantRole(models.TextChoices):
        ORGANIZER = 'organizer', 'Организатор'
        PARTICIPANT = 'participant', 'Участник'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='campaign_participation_links',
        verbose_name='пользователь',
    )
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='participant_links',
        verbose_name='сбор',
    )
    participant_role = models.CharField(
        'роль участника',
        max_length=12,
        choices=ParticipantRole.choices,
        default=ParticipantRole.PARTICIPANT,
    )
    joined_at = models.DateTimeField(
        'дата присоединения',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'участник сбора'
        verbose_name_plural = 'участники сборов'
        ordering = ['joined_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'campaign'],
                name='unique_user_campaign_participant',
            ),
        ]

    def __str__(self):
        return f'{self.user} — {self.campaign}'
