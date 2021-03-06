from django.urls import path, include
from rest_framework.routers import DefaultRouter

from team import views

router = DefaultRouter()
router.register(r'', views.TeamViewSet, basename='team')

urlpatterns = [
    path('self/', views.SelfView.as_view(), name='team-self'),
    path('create/', views.CreateTeamView.as_view(), name='team-create'),
    path('join/', views.JoinTeamView.as_view(), name='team-join'),
    path('', include(router.urls), name='team'),
]
