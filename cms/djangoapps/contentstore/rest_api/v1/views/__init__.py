"""
Views for v1 contentstore API.

Modifications Copyright (C) 2026 Robbo. See NOTICE at repository root.
"""
from .certificates import CourseCertificatesView
from .course_details import CourseDetailsView
from .course_index import CourseIndexView
from .course_rerun import CourseRerunView
from .course_waffle_flags import CourseWaffleFlagsView
from .course_team import CourseTeamView
from .grading import CourseGradingView
from .group_configurations import CourseGroupConfigurationsView
from .help_urls import HelpUrlsView
from .home import HomePageCoursesView, HomePageLibrariesView, HomePageView
from .robbo_certificate_design import (
    CertificateDesignDetailView,
    CertificateDesignListView,
    CourseCertificateDesignView,
)
from .proctoring import ProctoredExamSettingsView, ProctoringErrorsView
from .settings import CourseSettingsView
from .textbooks import CourseTextbooksView
from .vertical_block import ContainerHandlerView, VerticalContainerView
from .videos import (
    CourseVideosView,
    VideoDownloadView,
    VideoUsageView,
)
