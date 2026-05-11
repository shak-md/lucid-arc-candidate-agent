import base64
import logging
import httpx
from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from botbuilder.schema import Activity, ActivityTypes, Attachment
from bot.agent_client import agent_client
from bot.session_store import get_session_id, set_session_id, clear_session
from bot.cards import (
    pool_selection_card,
    confirmation_card,
    validation_error_card,
    success_card,
)
from bot.config import settings

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024


def _recruiter_id(turn_context: TurnContext) -> str:
    """Use the Teams user AAD object ID as a stable recruiter identifier."""
    aad_id = (
        turn_context.activity.from_property.aad_object_id
        or turn_context.activity.from_property.id
    )
    return aad_id


def _conversation_id(turn_context: TurnContext) -> str:
    return turn_context.activity.conversation.id


def _adaptive_card_attachment(card: dict) -> Attachment:
    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card,
    )


class CandidatePoolBot(ActivityHandler):

    async def on_message_activity(self, turn_context: TurnContext):
        activity = turn_context.activity
        conversation_id = _conversation_id(turn_context)
        recruiter_id = _recruiter_id(turn_context)

        # Handle Adaptive Card submit actions
        if activity.value:
            await self._handle_card_action(turn_context, activity.value, conversation_id, recruiter_id)
            return

        # Handle file attachments
        if activity.attachments:
            for attachment in activity.attachments:
                if self._is_file_attachment(attachment):
                    await self._handle_file_upload(turn_context, attachment, conversation_id, recruiter_id)
                    return

        # Handle plain text
        text = (activity.text or "").strip().lower()

        if text in ("hi", "hello", "start", "help", ""):
            await self._send_welcome(turn_context)
            return

        # Forward any other text to the agent as a message
        session_id = get_session_id(conversation_id)
        if not session_id:
            await self._send_welcome(turn_context)
            return

        await self._forward_message(turn_context, session_id, recruiter_id, activity.text.strip())

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await self._send_welcome(turn_context)

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    async def _send_welcome(self, turn_context: TurnContext):
        await turn_context.send_activity(
            MessageFactory.text(
                "Hi! I can add candidates from your LinkedIn Recruiter export directly into a "
                "Workday candidate pool.\n\nJust upload your export file (xlsx) to get started."
            )
        )

    def _is_file_attachment(self, attachment: Attachment) -> bool:
        spreadsheet_types = {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        }
        return (
            attachment.content_type in spreadsheet_types
            or (attachment.name or "").lower().endswith(".xlsx")
        )

    async def _handle_file_upload(
        self,
        turn_context: TurnContext,
        attachment: Attachment,
        conversation_id: str,
        recruiter_id: str,
    ):
        await turn_context.send_activity(
            Activity(type=ActivityTypes.typing)
        )

        # Download the file from Teams content URL
        try:
            content_url = attachment.content_url or (
                attachment.content.get("downloadUrl") if isinstance(attachment.content, dict) else None
            )
            if not content_url:
                await turn_context.send_activity(
                    MessageFactory.text("I could not access the file. Please try uploading again.")
                )
                return

            async with httpx.AsyncClient(timeout=30) as client:
                file_response = await client.get(content_url)
                file_response.raise_for_status()
                file_bytes = file_response.content

        except Exception as e:
            logger.error(f"File download error: {e}")
            await turn_context.send_activity(
                MessageFactory.text("I had trouble downloading your file. Please try again.")
            )
            return

        if len(file_bytes) > MAX_FILE_BYTES:
            await turn_context.send_activity(
                MessageFactory.text(
                    f"Your file is too large (max {settings.MAX_FILE_SIZE_MB}MB). "
                    f"Please reduce the file size and try again."
                )
            )
            return

        file_b64 = base64.b64encode(file_bytes).decode()
        filename = attachment.name or "export.xlsx"

        # Start or reuse session
        session_id = get_session_id(conversation_id)
        if not session_id:
            session_data = await agent_client.start_session(recruiter_id)
            session_id = session_data["session_id"]
            set_session_id(conversation_id, session_id)

        # Upload to agent core
        try:
            result = await agent_client.upload_file(session_id, recruiter_id, file_b64, filename)
        except Exception as e:
            logger.error(f"Agent upload error: {e}")
            await turn_context.send_activity(
                MessageFactory.text("Something went wrong processing your file. Please try again.")
            )
            return

        await self._handle_agent_response(turn_context, result, filename)

    async def _handle_card_action(
        self,
        turn_context: TurnContext,
        value: dict,
        conversation_id: str,
        recruiter_id: str,
    ):
        action = value.get("action")
        session_id = get_session_id(conversation_id)

        if action == "restart":
            clear_session(conversation_id)
            await self._send_welcome(turn_context)
            return

        if not session_id:
            await self._send_welcome(turn_context)
            return

        if action == "pool_selected":
            pool_id = value.get("selected_pool_id", "")
            message = pool_id
        elif action == "confirm":
            message = "confirm"
        elif action == "cancel":
            message = "cancel"
        else:
            return

        await self._forward_message(turn_context, session_id, recruiter_id, message)

    async def _forward_message(
        self,
        turn_context: TurnContext,
        session_id: str,
        recruiter_id: str,
        message: str,
    ):
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))
        try:
            result = await agent_client.send_message(session_id, recruiter_id, message)
        except Exception as e:
            logger.error(f"Agent message error: {e}")
            await turn_context.send_activity(
                MessageFactory.text("Something went wrong. Please try again.")
            )
            return

        await self._handle_agent_response(turn_context, result)

    async def _handle_agent_response(
        self,
        turn_context: TurnContext,
        result: dict,
        filename: str = "your file",
    ):
        state = result.get("state", "")
        parse_result = result.get("parse_result")
        available_pools = result.get("available_pools")

        # Validation errors - show error card
        if parse_result and parse_result.get("invalid_count", 0) > 0:
            card = validation_error_card(parse_result["invalid_records"])
            await turn_context.send_activity(
                MessageFactory.attachment(_adaptive_card_attachment(card))
            )
            return

        # Pool selection - show dropdown card
        if state == "awaiting_pool_selection" and available_pools:
            card = pool_selection_card(
                pools=available_pools,
                candidate_count=parse_result["valid_count"] if parse_result else 0,
                filename=filename,
            )
            await turn_context.send_activity(
                MessageFactory.attachment(_adaptive_card_attachment(card))
            )
            return

        # Confirmation - show confirm/cancel card
        if state == "awaiting_confirmation":
            selected_pool = result.get("selected_pool") or {}
            parse_r = result.get("parse_result") or {}
            card = confirmation_card(
                pool_name=selected_pool.get("pool_name", "selected pool"),
                candidate_count=parse_r.get("valid_count", 0),
            )
            await turn_context.send_activity(
                MessageFactory.attachment(_adaptive_card_attachment(card))
            )
            return

        # Complete - show success card
        if state == "complete":
            parse_r = result.get("parse_result") or {}
            selected_pool = result.get("selected_pool") or {}
            succeeded = parse_r.get("valid_count", 0)
            failed = 0
            # Parse any failure count from the message text as fallback
            message_text = result.get("message", "")
            if "could not be added" in message_text:
                try:
                    failed = int(message_text.split("**")[1].split(" ")[0])
                    succeeded = succeeded - failed
                except Exception:
                    pass
            card = success_card(
                pool_name=selected_pool.get("pool_name", "the selected pool"),
                succeeded=succeeded,
                failed=failed,
            )
            await turn_context.send_activity(
                MessageFactory.attachment(_adaptive_card_attachment(card))
            )
            return

        # Fallback - plain text
        message = result.get("message", "")
        if message:
            await turn_context.send_activity(MessageFactory.text(message))
