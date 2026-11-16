from django.urls import path
from . import views
urlpatterns = [
    path('', views.home, name='home'),
    path('campaigns/', views.campaign_list, name='campaign_list'),
    path('campaigns/<int:campaign_id>/',views.campain_detail_html,name='campaign_detail'),
]