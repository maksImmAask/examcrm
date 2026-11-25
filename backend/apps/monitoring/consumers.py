from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.attempts.models import Attempt


class AttemptMonitoringConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        access = await self.get_attempt_access(
            self.scope["url_route"]["kwargs"]["attempt_id"],
            user.id,
            user.role,
        )

        if not access:
            await self.close(code=4403)
            return

        self.attempt_id = access["attempt_id"]
        self.exam_id = access["exam_id"]
        self.role = access["role"]

        self.attempt_group = f"attempt_{self.attempt_id}"
        self.exam_group = f"exam_{self.exam_id}"

        if self.role == "student":
            await self.channel_layer.group_add(
                self.attempt_group,
                self.channel_name,
            )
        else:
            await self.channel_layer.group_add(
                self.exam_group,
                self.channel_name,
            )

        await self.accept()

        await self.send_json({
            "type": "connection.ready",
            "attempt_id": self.attempt_id,
            "exam_id": self.exam_id,
            "role": self.role,
            "event_version": access["event_version"],
        })

    async def disconnect(self, close_code):
        if hasattr(self, "attempt_group"):
            await self.channel_layer.group_discard(
                self.attempt_group,
                self.channel_name,
            )

        if hasattr(self, "exam_group"):
            await self.channel_layer.group_discard(
                self.exam_group,
                self.channel_name,
            )

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})
            return

        await self.send_json({
            "type": "error",
            "code": "unsupported_event",
        })

    async def monitoring_event(self, event):
        await self.send_json(event["payload"])

    @database_sync_to_async
    def get_attempt_access(self, attempt_id, user_id, role):
        try:
            attempt = (
                Attempt.objects
                .select_related(
                    "assignment",
                    "assignment__student",
                    "assignment__publication",
                    "assignment__publication__exam",
                )
                .get(pk=attempt_id)
            )
        except (Attempt.DoesNotExist, ValueError, TypeError):
            return None

        exam = attempt.assignment.publication.exam

        if role == "student":
            if attempt.assignment.student_id != user_id:
                return None

        elif role == "teacher":
            if exam.owner_id != user_id:
                return None

        elif role != "admin":
            return None

        return {
            "attempt_id": str(attempt.id),
            "exam_id": str(exam.id),
            "role": role,
            "event_version": attempt.event_version,
        }
