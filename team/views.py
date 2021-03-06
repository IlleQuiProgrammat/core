from django.http import Http404
from rest_framework import filters
from rest_framework.generics import RetrieveUpdateAPIView, CreateAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN
from rest_framework.views import APIView

from backend.response import FormattedResponse
from backend.permissions import AdminOrReadOnlyVisible
from backend.signals import team_join_attempt, team_join_reject, team_join
from backend.viewsets import AdminListModelViewSet
from config import config
from team.models import Team
from team.permissions import IsTeamOwnerOrReadOnly, HasTeam, TeamsEnabled
from team.serializers import SelfTeamSerializer, TeamSerializer, CreateTeamSerializer, AdminTeamSerializer, \
    ListTeamSerializer


class SelfView(RetrieveUpdateAPIView):
    serializer_class = SelfTeamSerializer
    permission_classes = (IsAuthenticated & IsTeamOwnerOrReadOnly & TeamsEnabled,)
    throttle_scope = 'self'
    pagination_class = None

    def get_object(self):
        if self.request.user.team is None:
            raise Http404()
        return Team.objects.filter(is_visible=True).order_by('id').prefetch_related('solves', 'members', 'hints_used',
                                                                                    'solves__challenge',
                                                                                    'solves__score',
                                                                                    'solves__solved_by')\
            .get(id=self.request.user.team.id)


class TeamViewSet(AdminListModelViewSet):
    permission_classes = (AdminOrReadOnlyVisible & TeamsEnabled,)
    throttle_scope = 'team'
    serializer_class = TeamSerializer
    admin_serializer_class = AdminTeamSerializer
    list_serializer_class = ListTeamSerializer
    list_admin_serializer_class = ListTeamSerializer
    search_fields = ['name']
    filter_backends = [filters.SearchFilter]

    def get_queryset(self):
        if self.action == 'list':
            return Team.objects.order_by('id').prefetch_related('members')
        if self.request.user.is_staff and not self.request.user.should_deny_admin():
            return Team.objects.order_by('id').prefetch_related('solves', 'members', 'hints_used', 'solves__challenge',
                                                                'solves__score', 'solves__solved_by')
        return Team.objects.filter(is_visible=True).order_by('id').prefetch_related('solves', 'members', 'hints_used',
                                                                                    'solves__challenge',
                                                                                    'solves__score',
                                                                                    'solves__solved_by')


class CreateTeamView(CreateAPIView):
    serializer_class = CreateTeamSerializer
    model = Team
    permission_classes = (IsAuthenticated & ~HasTeam & TeamsEnabled,)
    throttle_scope = 'team_create'


class JoinTeamView(APIView):
    permission_classes = (IsAuthenticated & ~HasTeam & TeamsEnabled,)
    throttle_scope = 'team_join'

    def post(self, request):
        if not config.get('enable_team_join'):
            return FormattedResponse(m='join_disabled', status=HTTP_403_FORBIDDEN)
        name = request.data.get('name')
        password = request.data.get('password')
        team_join_attempt.send(sender=self.__class__, user=request.user, name=name)
        if name and password:
            try:
                team = get_object_or_404(Team, name=name, password=password)
            except Http404:
                team_join_reject.send(sender=self.__class__, user=request.user, name=name)
                raise Http404
            team_size = config.get('team_size')
            if team_size > 0 and team.members.count() >= config.get('team_size'):
                return FormattedResponse(m='team_full', status=HTTP_403_FORBIDDEN)
            request.user.team = team
            request.user.save()
            team_join.send(sender=self.__class__, user=request.user, team=team)
            return FormattedResponse()
        return FormattedResponse(m='joined_team', status=HTTP_400_BAD_REQUEST)
