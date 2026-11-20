
from rest_framework.routers import DefaultRouter

from .views import StudyGroupViewSet


router = DefaultRouter()

router.register(
    r"",
    StudyGroupViewSet,
    basename="study-group",
)

urlpatterns = router.urls
