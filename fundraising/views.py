from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import  CampaignParticipant,CampaignUpdate, Category, Donation, Report , Campaign


THEME_STYLES = {
    'animals': 'animals',
    'family': 'family',
    'education': 'education',
}

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

    