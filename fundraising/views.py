from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout

from .models import  CampaignParticipant,CampaignUpdate, Category, Donation, Report , Campaign , Organization , User
from .forms import LoginForm, RegisterForm

THEME_STYLES = {
    'animals': 'animals',
    'family': 'family',
    'education': 'education',
}

def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
    return redirect('home')

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request=request, data=request.POST)

        if form.is_valid():
            login(request, form.get_user())
            return redirect('home')
    else:
        form = LoginForm(request=request)

    return render(request, 'auth.html', {
        'form': form,
        'mode': 'login',
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

            login(
                request,
                user,
                backend='django.contrib.auth.backends.ModelBackend',
            )
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
        status=Campaign.Status.ACTIVE,
    ).select_related('category')

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
        Organization,
        pk=organization_id,
    )

    campaigns = Campaign.objects.filter(
        organization=organization,
        status=Campaign.Status.ACTIVE,
    ).select_related('category', 'organization', 'organizer')

    context = {
        'organization': organization,
        'campaigns': campaigns,
    }

    return render(request, 'organization_detail.html', context)


def organization_list(request):
    organizations = Organization.objects.all()
    
    context = {
        "organizations": organizations
    }
    
    return render(request, "organization_list.html", context=context)
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

    paginator = Paginator(campaigns, 9)
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
                    filter=Q(donations__status=Donation.Status.COMPLETED),
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        ),
        pk=campaign_id,
    )

    campaign.progress_percent = min(
        100,
        round(campaign.raised_amount / campaign.goal_amount * 100),
    ) if campaign.goal_amount else 0

    context = {
        'campaign': campaign,
        'raised_amount': campaign.raised_amount,
        'progress_percent': campaign.progress_percent,
        'updates': CampaignUpdate.objects.filter(
            campaign=campaign,
            status=CampaignUpdate.Status.PUBLISHED,
        ),
        'reports': Report.objects.filter(
            campaign=campaign,
            status=Report.Status.APPROVED,
        ),
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

    