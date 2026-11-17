from django.urls import path
from . import views
urlpatterns = [
    path('', views.home, name='home'),
    path('campaigns/', views.campaign_list, name='campaign_list'),
    path('campaigns/<int:campaign_id>/',views.campain_detail_html,name='campaign_detail'),
    path('organizations/', views.organization_list , name='organizations_list'),
    path('organizations/<int:organization_id>/',views.organization_detail,name='organization_detail'),
    path('organizers/<int:organizer_id>/',views.organizer_detail,name='organizer_detail',),
    path('login/',views.login_view  , name='login'),
    path('register/', views.register_view, name = 'register'),
    path('logout/', views.logout_view, name='logout'),
]