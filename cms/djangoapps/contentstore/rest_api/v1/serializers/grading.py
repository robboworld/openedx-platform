"""
API Serializers for course grading

Modifications Copyright (C) 2026 Robbo. See NOTICE at repository root.
"""

from rest_framework import serializers


class GradersSerializer(serializers.Serializer):
    """ Serializer for graders """
    type = serializers.CharField()
    min_count = serializers.IntegerField()
    drop_count = serializers.IntegerField()
    short_label = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    weight = serializers.IntegerField()
    id = serializers.IntegerField()


class GracePeriodSerializer(serializers.Serializer):
    """ Serializer for course grace period """
    hours = serializers.IntegerField()
    minutes = serializers.IntegerField()


class CourseGradingModelSerializer(serializers.Serializer):
    """ Serializer for course grading model data """
    graders = GradersSerializer(many=True)
    grade_cutoffs = serializers.DictField(child=serializers.FloatField())
    grace_period = GracePeriodSerializer(required=False, allow_null=True)
    minimum_grade_credit = serializers.FloatField()


class GroupAssignmentCountSerializer(serializers.Serializer):
    """ Robbo: subsections of an assignment type that give points to the learners of one group """
    partition = serializers.CharField()
    group = serializers.CharField(allow_null=True)
    count = serializers.IntegerField()


class GroupAssignmentCountsSerializer(serializers.Serializer):
    """ Robbo: subsections of an assignment type that give points to someone, and to each group """
    everyone = serializers.IntegerField()
    groups = GroupAssignmentCountSerializer(many=True)


class CourseGradingSerializer(serializers.Serializer):
    """ Serializer for course grading context data """
    mfe_proctored_exam_settings_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    course_assignment_lists = serializers.DictField(
        child=serializers.ListSerializer(
            child=serializers.CharField()
        )
    )
    # Robbo: graded subsections without anything that gives points, by assignment type
    unscored_assignment_lists = serializers.DictField(
        child=serializers.ListSerializer(
            child=serializers.CharField()
        )
    )
    # Robbo: by assignment type, the subsections that give points to each group of a group configuration
    # (group None: learners in none of its groups); only configurations that change a count
    group_assignment_counts = serializers.DictField(
        child=GroupAssignmentCountsSerializer()
    )
    course_details = CourseGradingModelSerializer()
    show_credit_eligibility = serializers.BooleanField()
    is_credit_course = serializers.BooleanField()
    default_grade_designations = serializers.ListSerializer(
        child=serializers.CharField()
    )
