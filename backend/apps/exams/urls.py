
from rest_framework.routers import DefaultRouter

from .views import ExamViewSet, ExamPublicationViewSet


router = DefaultRouter()

router.register(
    "exams",
    ExamViewSet,
    basename="exam",
)

router.register(
    "exam-publications",
    ExamPublicationViewSet,
    basename="exam-publication",
)

urlpatterns = router.urls
