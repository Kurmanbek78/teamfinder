from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Project, Application, create_notification
from .serializers import ProjectSerializer, ApplicationSerializer
from .views import get_user_course, is_teacher


class ProjectListAPI(generics.ListAPIView):
    queryset = Project.objects.filter(status='open', moderation_status='approved')
    serializer_class = ProjectSerializer
    permission_classes = [permissions.AllowAny]


class ProjectDetailAPI(generics.RetrieveAPIView):
    queryset = Project.objects.filter(moderation_status='approved')
    serializer_class = ProjectSerializer
    permission_classes = [permissions.AllowAny]


class MyApplicationsAPI(generics.ListAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Application.objects.filter(applicant=self.request.user)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def apply_api(request, pk):
    project = get_object_or_404(Project, pk=pk, moderation_status='approved')
    if project.owner == request.user:
        return Response({'detail': 'Нельзя подать заявку на свой проект'},
                        status=status.HTTP_403_FORBIDDEN)
    if is_teacher(request.user):
        return Response({'detail': 'Преподаватели не подают заявки в студенческие проекты'},
                        status=status.HTTP_403_FORBIDDEN)
    if get_user_course(project.owner) != get_user_course(request.user):
        return Response({'detail': 'Подать заявку могут только студенты того же курса'},
                        status=status.HTTP_403_FORBIDDEN)
    if project.status != 'open' or (
        project.max_members is not None and project.accepted_count() >= project.max_members
    ):
        return Response({'detail': 'Набор закрыт'}, status=status.HTTP_400_BAD_REQUEST)
    if Application.objects.filter(project=project, applicant=request.user).exists():
        return Response({'detail': 'Вы уже подавали заявку'}, status=status.HTTP_400_BAD_REQUEST)
    serializer = ApplicationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    application = serializer.save(project=project, applicant=request.user)
    project.sync_recruitment_status()
    create_notification(
        recipient=project.owner,
        message=f'Новая заявка на проект «{project.title}» от {request.user.username}.',
        link=reverse('project_detail', args=[project.pk]),
        event_key=f'app_new:{application.pk}',
    )
    return Response(serializer.data, status=status.HTTP_201_CREATED)
