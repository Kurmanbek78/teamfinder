from rest_framework import serializers
from .models import Project, Application


class ProjectSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField()
    required_skills = serializers.StringRelatedField(many=True)

    class Meta:
        model = Project
        fields = ('id', 'title', 'description', 'owner', 'required_skills', 'status', 'created_at')


class ApplicationSerializer(serializers.ModelSerializer):
    project = serializers.StringRelatedField()

    class Meta:
        model = Application
        fields = ('id', 'project', 'message', 'status', 'created_at')
        read_only_fields = ('status',)