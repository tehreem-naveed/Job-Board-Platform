import django_filters

from .models import EmploymentType, ExperienceLevel, Job, JobStatus


class JobFilter(django_filters.FilterSet):
    """
    Explicit, whitelisted filters. Values are validated against the model's
    controlled choices, so a client can never inject arbitrary field lookups.
    """

    location = django_filters.CharFilter(field_name="location", lookup_expr="icontains")
    employment_type = django_filters.ChoiceFilter(choices=EmploymentType.choices)
    experience_level = django_filters.ChoiceFilter(choices=ExperienceLevel.choices)
    status = django_filters.ChoiceFilter(choices=JobStatus.choices)
    salary_min = django_filters.NumberFilter(field_name="salary_min", lookup_expr="gte")
    salary_max = django_filters.NumberFilter(field_name="salary_max", lookup_expr="lte")

    class Meta:
        model = Job
        fields = ["location", "employment_type", "experience_level", "status", "salary_min", "salary_max"]
