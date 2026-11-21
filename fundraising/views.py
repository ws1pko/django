from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.db.models import DecimalField, Max, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse,Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import CampaignParticipant, CampaignUpdate, Category, Donation, Report, ReportDocument, Campaign, Organization, Subscription, User
from .forms import CampaignForm, CampaignUpdateForm, LoginForm, OrganizationApplicationForm, RegisterForm, ReportForm

def moderator_required(view_func):
    return user_passes_test(
        lambda user: user.is_authenticated and (
            user.is_superuser or user.role == User.Role.MODERATOR
        ),
        login_url='login',
    )(view_func)

THEME_STYLES = {
    'animals': 'animals',
    'family': 'family',
    'education': 'education',
}


@login_required(login_url='login')
@moderator_required
def moderation_dashboard(request):
    campaign_count = Campaign.objects.filter(
        status=Campaign.Status.PENDING,
    ).count()
    organization_count = Organization.objects.filter(
        verification_status=Organization.VerificationStatus.PENDING,
    ).count()
    report_count = Report.objects.filter(
        status=Report.Status.PENDING,
    ).count()
    name = request.user.get_full_name() or request.user.username

    return render(request, 'moderation/dashboard.html', {
        'campaign_count': campaign_count,
        'organization_count': organization_count,
        'report_count': report_count,
        'moderator_initial': name[:1].upper(),
        'moderator_name': name,
    })



@login_required(login_url='login')
@moderator_required
def moderation_campaigns(request):
    campaigns = Campaign.objects.filter(
        status=Campaign.Status.PENDING,
    ).select_related('organizer', 'organization', 'category')
    return render(request, 'moderation/campaigns.html', {
        'campaigns': campaigns,
        'moderation_section': 'campaigns',
    })


@login_required(login_url='login')
@moderator_required
def moderation_campaign_action(request, campaign_id):
    if request.method != 'POST':
        return redirect('moderation_campaigns')

    campaign = get_object_or_404(
        Campaign,
        pk=campaign_id,
        status=Campaign.Status.PENDING,
    )
    action = request.POST.get('action')

    if action == 'approve':
        campaign.status = Campaign.Status.ACTIVE
        campaign.published_at = timezone.now()
        campaign.moderation_comment = ''
        campaign.save(update_fields=['status', 'published_at', 'moderation_comment'])
        messages.success(request, f'Сбор «{campaign.title}» одобрен и опубликован.')
    elif action == 'reject':
        comment = request.POST.get('moderation_comment', '').strip()
        if not comment:
            messages.error(request, 'Укажите причину отклонения заявки на сбор.')
            return redirect('moderation_campaigns')
        campaign.status = Campaign.Status.REJECTED
        campaign.moderation_comment = comment
        campaign.save(update_fields=['status', 'moderation_comment'])
        messages.success(request, f'Заявка на сбор «{campaign.title}» отклонена.')
    else:
        messages.error(request, 'Неизвестное действие.')

    return redirect('moderation_campaigns')


@login_required(login_url='login')
@moderator_required
def moderation_organizations(request):
    organizations = Organization.objects.filter(
        verification_status=Organization.VerificationStatus.PENDING,
    ).select_related('created_by')
    return render(request, 'moderation/organizations.html', {
        'organizations': organizations,
        'moderation_section': 'organizations',
    })


@login_required(login_url='login')
@moderator_required
def moderation_organization_action(request, organization_id):
    if request.method != 'POST':
        return redirect('moderation_organizations')

    organization = get_object_or_404(
        Organization,
        pk=organization_id,
        verification_status=Organization.VerificationStatus.PENDING,
    )
    action = request.POST.get('action')
    if action == 'approve':
        organization.verification_status = Organization.VerificationStatus.VERIFIED
        organization.verified_by = request.user
        organization.save(update_fields=['verification_status', 'verified_by'])
        messages.success(request, f'Организация «{organization.name}» подтверждена.')
    elif action == 'reject':
        organization.verification_status = Organization.VerificationStatus.REJECTED
        organization.verified_by = request.user
        organization.save(update_fields=['verification_status', 'verified_by'])
        messages.success(request, f'Заявка организации «{organization.name}» отклонена.')
    else:
        messages.error(request, 'Неизвестное действие.')

    return redirect('moderation_organizations')


@login_required(login_url='login')
@moderator_required
def moderation_reports(request):
    reports = Report.objects.filter(
        status=Report.Status.PENDING,
    ).select_related(
        'campaign', 'campaign__organization', 'author',
    ).prefetch_related('documents')
    return render(request, 'moderation/reports.html', {
        'reports': reports,
        'moderation_section': 'reports',
    })


@login_required(login_url='login')
@moderator_required
def moderation_report_action(request, report_id):
    if request.method != 'POST':
        return redirect('moderation_reports')

    report = get_object_or_404(
        Report,
        pk=report_id,
        status=Report.Status.PENDING,
    )
    action = request.POST.get('action')
    if action == 'approve':
        report.status = Report.Status.APPROVED
        report.moderator = request.user
        report.save(update_fields=['status', 'moderator'])
        messages.success(request, f'Отчёт по сбору «{report.campaign.title}» одобрен.')
    elif action == 'reject':
        report.status = Report.Status.REJECTED
        report.moderator = request.user
        report.save(update_fields=['status', 'moderator'])
        messages.success(request, f'Отчёт по сбору «{report.campaign.title}» отклонён.')
    else:
        messages.error(request, 'Неизвестное действие.')

    return redirect('moderation_reports')

@login_required
def account_view(request, section='profile'):
    organization_form = OrganizationApplicationForm()
    if request.method == 'POST' and section == 'organization':
        organization_form = OrganizationApplicationForm(request.POST)
        if organization_form.is_valid():
            organization = organization_form.save(commit=False)
            organization.created_by = request.user
            organization.save()
            return redirect('account_organization')

    if request.method == 'POST' and section == 'subscriptions' and request.POST.get('unsubscribe'):
        subscription = get_object_or_404(
            request.user.subscription_links,
            pk=request.POST.get('subscription_id'),
        )
        subscription.is_active = False
        subscription.save(update_fields=['is_active'])
        messages.success(request, f'Вы отписались от новостей сбора «{subscription.campaign.title}».')
        return redirect('account_subscriptions')

    donations = (
        request.user.donations
        .select_related('campaign')
        .order_by('-created_at')
    )
    if request.method == 'POST' and section == 'profile':
        full_name = request.POST.get('name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()

        if full_name:
            name_parts = full_name.split(maxsplit=1)
            request.user.first_name = name_parts[0]
            request.user.last_name = name_parts[1] if len(name_parts) > 1 else ''

        if username:
            request.user.username = username

        if email:
            request.user.email = email

        request.user.save()
        return redirect('account_profile')

    subscriptions = (
        request.user.subscription_links
        .filter(is_active=True)
        .select_related('campaign', 'campaign__category')
        .annotate(
            latest_update_at=Max(
                'campaign__updates__created_at',
                filter=Q(
                    campaign__updates__status=CampaignUpdate.Status.PUBLISHED,
                ),
            ),
        )
        .order_by('-created_at')
    )

    user_campaigns = Campaign.objects.filter(organizer=request.user)

    campaign_status_filter = request.GET.get('status', 'all')
    status_filters = {
        'active': Campaign.Status.ACTIVE,
        'pending': Campaign.Status.PENDING,
        'completed': Campaign.Status.COMPLETED,
    }
    if campaign_status_filter not in ('all', *status_filters):
        campaign_status_filter = 'all'

    campaigns = (
        user_campaigns
        .select_related('category')
        .annotate(
            raised_amount=Coalesce(
                Sum(
                    'donations__amount',
                    filter=Q(donations__status=Donation.Status.COMPLETED),
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
        )
        .order_by('-created_at')
    )
    if campaign_status_filter in status_filters:
        campaigns = campaigns.filter(status=status_filters[campaign_status_filter])

    for campaign in campaigns:
        campaign.progress_percent = min(
            100,
            round(campaign.raised_amount / campaign.goal_amount * 100),
        )

    total_donated = donations.filter(status=Donation.Status.COMPLETED,
    ).aggregate(
        total=Coalesce(
            Sum('amount'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
    )['total']

    context = {
        'user': request.user,
        'active_page': section,
        'organization_form': organization_form,
        'my_organizations': Organization.objects.filter(
            created_by=request.user,
        ).order_by('-created_at'),

        'donations': donations,
        'donation_count': donations.count(),
        'total_donated': total_donated,

        'subscriptions': subscriptions,

        'campaigns': campaigns,
        'campaign_status_filter': campaign_status_filter,
        'campaign_count': user_campaigns.count(),
        'active_campaign_count': user_campaigns.filter(
            status=Campaign.Status.ACTIVE,
        ).count(),
        'pending_campaign_count': user_campaigns.filter(
            status=Campaign.Status.PENDING,
        ).count(),
        'completed_campaign_count': user_campaigns.filter(
            status=Campaign.Status.COMPLETED,
        ).count(),
    }

    return render(request, 'account.html', context)


@login_required(login_url='login')
def campaign_create(request):
    form = CampaignForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        campaign = form.save(commit=False)
        campaign.organizer = request.user
        campaign.status = Campaign.Status.PENDING
        campaign.moderation_comment = ''
        campaign.save()
        messages.success(request, 'Сбор отправлен на проверку модератору.')
        return redirect('account_campaigns')
    return render(request, 'campaign_form.html', {
        'form': form,
        'is_edit': False,
        'page_title': 'Создать сбор',
    })


@login_required(login_url='login')
def campaign_edit(request, campaign_id):
    campaign = get_object_or_404(Campaign, pk=campaign_id, organizer=request.user)
    if campaign.status in (Campaign.Status.COMPLETED, Campaign.Status.CLOSED):
        messages.error(request, 'Завершённый или закрытый сбор нельзя редактировать.')
        return redirect('account_campaigns')

    form = CampaignForm(
        request.POST or None,
        request.FILES or None,
        instance=campaign,
        user=request.user,
    )
    if request.method == 'POST' and form.is_valid():
        campaign = form.save(commit=False)
        campaign.status = Campaign.Status.PENDING
        campaign.moderation_comment = ''
        campaign.save()
        messages.success(request, 'Изменения сохранены и отправлены на повторную проверку.')
        return redirect('account_campaigns')
    return render(request, 'campaign_form.html', {
        'form': form,
        'campaign': campaign,
        'is_edit': True,
        'page_title': 'Редактировать сбор',
    })


@login_required(login_url='login')
def campaign_update_create(request, campaign_id):
    campaign = get_object_or_404(
        Campaign,
        pk=campaign_id,
        organizer=request.user,
        status=Campaign.Status.ACTIVE,
    )
    form = CampaignUpdateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        update = form.save(commit=False)
        update.campaign = campaign
        update.author = request.user
        update.status = CampaignUpdate.Status.PUBLISHED
        update.save()
        messages.success(request, 'Новость опубликована и появилась во вкладке «Новости» сбора.')
        return redirect(f"{reverse('campaign_detail', args=[campaign.pk])}#updates")
    return render(request, 'campaign_update_form.html', {
        'campaign': campaign,
        'form': form,
    })


@login_required(login_url='login')
def campaign_report_create(request, campaign_id):
    campaign = get_object_or_404(
        Campaign.objects.select_related('organizer'),
        pk=campaign_id,
        organizer=request.user,
        status__in=(Campaign.Status.ACTIVE, Campaign.Status.COMPLETED, Campaign.Status.CLOSED),
    )
    form = ReportForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            report = form.save(commit=False)
            report.campaign = campaign
            report.author = request.user
            report.status = Report.Status.PENDING
            report.save()
            ReportDocument.objects.create(
                report=report,
                file=form.cleaned_data['document'],
                caption=form.cleaned_data['caption'],
            )
        messages.success(request, 'Отчёт отправлен модератору. После проверки он появится на странице сбора.')
        return redirect('account_campaigns')
    return render(request, 'campaign_report_form.html', {
        'campaign': campaign,
        'form': form,
    })


def how_to_help(request):
    return render(request, 'how_to_help.html')

def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
    return redirect('home')

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request=request, data=request.POST)

        if form.is_valid():
            login(request, form.get_user())
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect('home')
    else:
        form = LoginForm(request=request)

    return render(request, 'auth.html', {
        'form': form,
        'mode': 'login',
        'next': request.POST.get('next') or request.GET.get('next', ''),
    })


def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)

            first_name, last_name = form.cleaned_data['name'].split(maxsplit=1)
            user.first_name = first_name
            user.last_name = last_name
            user.username = form.cleaned_data['email']

            user.save()

            login(request,user)
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'auth.html', {
        'form': form,
        'mode': 'register',
    })


def organizer_detail(request, organizer_id):
    organizer = get_object_or_404(User, pk=organizer_id)

    campaigns = Campaign.objects.filter(
        organizer=organizer,
        organization__isnull=True,
        status__in=(
            Campaign.Status.ACTIVE,
            Campaign.Status.COMPLETED,
        ),
    ).select_related('category').annotate(
        raised_amount=Coalesce(
            Sum(
                'donations__amount',
                filter=Q(donations__status=Donation.Status.COMPLETED),
            ),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
    )

    for campaign in campaigns:
        campaign.progress_percent = min(
            100,
            round(campaign.raised_amount / campaign.goal_amount * 100),
        ) if campaign.goal_amount else 0

    return render(
        request,
        'organizer_detail.html',
        {
            'organizer': organizer,
            'campaigns': campaigns,
        },
    )

def organization_detail(request, organization_id):
    organization = get_object_or_404(
        Organization.objects.filter(
            verification_status=Organization.VerificationStatus.VERIFIED,
        ),
        pk=organization_id,
    )

    organization_campaigns = Campaign.objects.filter(
        organization=organization,
    )

    campaigns = (
        organization_campaigns
        .filter(
            status__in=(
                Campaign.Status.ACTIVE,
                Campaign.Status.COMPLETED,
            ),
        )
        .select_related('category', 'organization', 'organizer')
        .annotate(
            raised_amount=Coalesce(
                Sum(
                    'donations__amount',
                    filter=Q(
                        donations__status=Donation.Status.COMPLETED,
                    ),
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
        )
    )

    today = timezone.localdate()

    for campaign in campaigns:
        campaign.progress_percent = min(
            100,
            round(campaign.raised_amount / campaign.goal_amount * 100),
        ) if campaign.goal_amount else 0

        campaign.days_left = max(
            (campaign.deadline - today).days,
            0,
        )

    completed_donations = Donation.objects.filter(
        campaign__organization=organization,
        status=Donation.Status.COMPLETED,
    )

    total_raised = completed_donations.aggregate(
        total=Coalesce(
            Sum('amount'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
    )['total']

    context = {
        'organization': organization,
        'campaigns': campaigns,
        'completed_campaign_count': organization_campaigns.filter(
            status=Campaign.Status.COMPLETED,
        ).count(),
        'participant_count': completed_donations.count(),
        'total_raised': total_raised,
    }

    return render(request, 'organization_detail.html', context)


def organization_list(request):
    organizations = Organization.objects.filter(
        verification_status=Organization.VerificationStatus.VERIFIED,
    )

    context = {
        "organizations": organizations
    }

    return render(request, "organization_list.html", context=context)
    #return JsonResponse(list(organizations.values()), safe=False)

def campaign_list(request):
    campaigns = (
        Campaign.objects
        .select_related('category', 'organization', 'organizer')
        .annotate(
            raised_amount=Coalesce(
                Sum(
                    'donations__amount',
                    filter=Q(donations__status=Donation.Status.COMPLETED),
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
    )

    status = request.GET.get('status', 'active')
    if status in (Campaign.Status.ACTIVE, Campaign.Status.COMPLETED):
        campaigns = campaigns.filter(status=status)
    else:
        status = 'active'
        campaigns = campaigns.filter(status=Campaign.Status.ACTIVE)

    category_id = request.GET.get('category', '')
    if category_id.isdigit():
        campaigns = campaigns.filter(category_id=int(category_id))

    query = request.GET.get('q', '').strip()
    if query:
        campaigns = campaigns.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
            | Q(organization__name__icontains=query)
        )
    for parameter, lookup in (
        ('goal_min', 'goal_amount__gte'),
        ('goal_max', 'goal_amount__lte'),
    ):
        raw_value = request.GET.get(parameter, '').strip()
        if raw_value:
            try:
                amount = Decimal(raw_value)
                if amount.is_finite() and amount >= 0:
                    campaigns = campaigns.filter(**{lookup: amount})
            except InvalidOperation:
                pass

    sort = request.GET.get('sort', 'actuality')
    if sort == 'newest':
        campaigns = campaigns.order_by('-created_at')
    elif sort == 'deadline':
        campaigns = campaigns.order_by('deadline', '-created_at')
    else:
        sort = 'actuality'
        campaigns = campaigns.order_by('deadline', '-created_at')

    paginator = Paginator(campaigns, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    campaigns = list(page_obj.object_list)

    today = timezone.localdate()
    for campaign in campaigns:
        campaign.progress_percent = min(
            100,
            round(campaign.raised_amount / campaign.goal_amount * 100),
        ) if campaign.goal_amount else 0
        campaign.days_left = max((campaign.deadline - today).days, 0)
    context = {
        'campaigns': campaigns,
        'categories': Category.objects.all(),
        'page_obj': page_obj,
        'result_count': paginator.count,
    }
    return render(request, 'campaign_list.html', context)


def campain_detail_html(request, campaign_id):
    campaign = get_object_or_404(
        Campaign.objects
        .select_related('category', 'organization', 'organizer')
        .annotate(
            raised_amount=Coalesce(
                Sum(
                    'donations__amount',
                    filter=Q(
                        donations__status=Donation.Status.COMPLETED,
                    ),
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        ),
        pk=campaign_id,
    )
    private_statuses = (
        Campaign.Status.DRAFT,
        Campaign.Status.PENDING,
        Campaign.Status.REJECTED,
    )

    if campaign.status in private_statuses:
        user = request.user
        can_view = (
            user.is_authenticated
            and (
                campaign.organizer_id == user.pk
                or user.is_superuser
                or user.role == User.Role.MODERATOR
            )
        )
        if not can_view:
            raise Http404

    campaign.progress_percent = min(
        100,
        round(campaign.raised_amount / campaign.goal_amount * 100),
    ) if campaign.goal_amount else 0

    campaign.progress_percent = min(
        100,
        round(campaign.raised_amount / campaign.goal_amount * 100),
    ) if campaign.goal_amount else 0

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'subscribe':
            if not request.user.is_authenticated:
                messages.info(request, 'Войдите в аккаунт, чтобы подписаться на новости этого сбора.')
                return redirect(f"{reverse('login')}?next={reverse('campaign_detail', args=[campaign.pk])}")
            subscription, created = Subscription.objects.get_or_create(
                user=request.user,
                campaign=campaign,
                defaults={'is_active': True},
            )
            if not created and not subscription.is_active:
                subscription.is_active = True
                subscription.save(update_fields=['is_active'])
            messages.success(request, f'Вы подписались на новости сбора «{campaign.title}».')
            return redirect('campaign_detail', campaign_id=campaign.pk)

        if action == 'unsubscribe':
            if request.user.is_authenticated:
                Subscription.objects.filter(user=request.user, campaign=campaign).update(is_active=False)
                messages.success(request, f'Вы отписались от новостей сбора «{campaign.title}».')
            return redirect('campaign_detail', campaign_id=campaign.pk)

        if action == 'donate':
            if campaign.status != Campaign.Status.ACTIVE:
                messages.error(request, 'Пожертвования доступны только активным сборам.')
                return redirect('campaign_detail', campaign_id=campaign.pk)

            raw_amount = (
                request.POST.get('custom_amount', '').strip()
                or request.POST.get('amount', '').strip()
            )

            try:
                amount = Decimal(raw_amount)

                if (
                    not amount.is_finite()
                    or amount <= 0
                    or amount.as_tuple().exponent < -2
                    or amount >= Decimal('10000000000')
                ):
                    raise InvalidOperation

            except (InvalidOperation, ValueError):
                messages.error(
                    request,
                    'Укажите сумму больше нуля, не более чем с двумя знаками после запятой.',
                )
                return redirect('campaign_detail', campaign_id=campaign.pk)

            Donation.objects.create(
                campaign=campaign,
                donor=request.user if request.user.is_authenticated else None,
                amount=amount,
                status=Donation.Status.COMPLETED,
            )
            if request.user.is_authenticated:
                CampaignParticipant.objects.get_or_create(
                    user=request.user,
                    campaign=campaign,
                    defaults={
                        'participant_role': CampaignParticipant.ParticipantRole.PARTICIPANT,
                    },
                )
            raised_amount = (
                Donation.objects
                .filter(
                    campaign=campaign,
                    status=Donation.Status.COMPLETED,
                )
                .aggregate(total=Sum('amount'))['total']
                or Decimal('0.00')
            )

            if raised_amount >= campaign.goal_amount:
                campaign.status = Campaign.Status.COMPLETED
                campaign.save(update_fields=['status'])

            messages.success(
                request,
                f'Тестовое пожертвование на {amount:,.2f} ₽ записано. Реального списания нет.',
            )
            return redirect('campaign_detail', campaign_id=campaign.pk)

    context = {
        'campaign': campaign,
        'is_subscribed': request.user.is_authenticated and Subscription.objects.filter(
            user=request.user, campaign=campaign, is_active=True,
        ).exists(),
        'raised_amount': campaign.raised_amount,
        'progress_percent': campaign.progress_percent,
        'updates': CampaignUpdate.objects.filter(
            campaign=campaign,
            status=CampaignUpdate.Status.PUBLISHED,
        ),
        'reports': Report.objects.filter(
            campaign=campaign,
            status=Report.Status.APPROVED,
        ).prefetch_related('documents'),
    }
    return render(request, 'campaign_detail.html', context)

def home(request):
    campaigns = list(
        Campaign.objects
        .filter(status=Campaign.Status.ACTIVE)
        .select_related('category', 'organization', 'organizer')
        .annotate(
            raised_amount=Coalesce(
                Sum(
                    'donations__amount',
                    filter=Q(donations__status=Donation.Status.COMPLETED),
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )[:4]
    )

    today = timezone.localdate()

    for campaign in campaigns:
        campaign.visual_theme = THEME_STYLES.get(
            campaign.category.theme,
            'general',
        )
        campaign.progress_percent = min(
            100,
            round(campaign.raised_amount / campaign.goal_amount * 100),
        )
        campaign.days_left = max((campaign.deadline - today).days, 0)

    campaign_count = Campaign.objects.exclude(
        status=Campaign.Status.DRAFT,
    ).count()

    completed_count = Campaign.objects.filter(
        status=Campaign.Status.COMPLETED,
    ).count()

    completed_percent = (
        round(completed_count / campaign_count * 100)
        if campaign_count
        else 0
    )

    total_raised = Donation.objects.filter(
        status=Donation.Status.COMPLETED,
    ).aggregate(
        total=Coalesce(
            Sum('amount'),
            Value(Decimal('0.00')),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
    )['total']

    participant_count = (
        CampaignParticipant.objects
        .filter(
            participant_role=CampaignParticipant.ParticipantRole.PARTICIPANT,
        )
        .values('user_id')
        .distinct()
        .count()
    )

    context = {
        'campaigns': campaigns,
        'active_campaign_count': Campaign.objects.filter(
            status=Campaign.Status.ACTIVE,
        ).count(),
        'participant_count': participant_count,
        'completed_percent': completed_percent,
        'total_raised': total_raised,
    }
    return render(request, 'main.html', context)


