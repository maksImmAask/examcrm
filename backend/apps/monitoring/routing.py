from django.urls import path

from .consumers import AttemptMonitoringConsumer


websocket_urlpatterns = [
    path(
        "ws/attempts/<uuid:attempt_id>/",
        AttemptMonitoringConsumer.as_asgi(),
        name="attempt-monitoring",
    ),
]
