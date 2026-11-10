from django.urls import path
from . import views, api, profile

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('profile/', profile.profile_edit, name='profile_edit'),
    path('projects/my/', views.my_projects, name='my_projects'),
    path('projects/create/', views.project_create, name='project_create'),
    path('projects/<int:pk>/', views.project_detail, name='project_detail'),
    path('projects/<int:pk>/edit/', views.project_edit, name='project_edit'),
    path('projects/<int:pk>/delete/', views.project_delete, name='project_delete'),
    path('projects/<int:pk>/apply/', views.project_apply, name='project_apply'),
    path('projects/<int:pk>/chat/', views.project_chat, name='project_chat'),
    path('chat/messages/<int:pk>/attachment/', views.chat_attachment_download, name='chat_attachment_download'),
    path('applications/my/', views.my_applications, name='my_applications'),
    path('applications/<int:pk>/<str:action>/', views.application_decide, name='application_decide'),
    path('moderation/', views.moderation_list, name='moderation_list'),
    path('projects/<int:pk>/moderate/<str:action>/', views.project_moderate, name='project_moderate'),
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/<int:pk>/read/', views.notification_mark_read, name='notification_mark_read'),
    path('notifications/read-all/', views.notifications_mark_all_read, name='notifications_mark_all_read'),

    path('api/projects/', api.ProjectListAPI.as_view(), name='api_projects'),
    path('api/projects/<int:pk>/', api.ProjectDetailAPI.as_view(), name='api_project_detail'),
    path('api/projects/<int:pk>/apply/', api.apply_api, name='api_apply'),
    path('api/my-applications/', api.MyApplicationsAPI.as_view(), name='api_my_applications'),
]