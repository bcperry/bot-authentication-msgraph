# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
from botbuilder.core import ConversationState, UserState, TurnContext
from botbuilder.core.teams import TeamsActivityHandler
from botbuilder.dialogs import Dialog
import logging
from helpers.dialog_helper import DialogHelper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,  # Force reconfiguration even if logging is already configured
)

# Also set the root logger level and configure uvicorn loggers
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class DialogBot(TeamsActivityHandler):
    def __init__(
        self,
        conversation_state: ConversationState,
        user_state: UserState,
        dialog: Dialog,
    ):
        if conversation_state is None:
            raise Exception(
                "[DialogBot]: Missing parameter. conversation_state is required"
            )
        if user_state is None:
            raise Exception("[DialogBot]: Missing parameter. user_state is required")
        if dialog is None:
            raise Exception("[DialogBot]: Missing parameter. dialog is required")

        self.conversation_state = conversation_state
        self.user_state = user_state
        self.dialog = dialog

    async def on_turn(self, turn_context: TurnContext):
        await super().on_turn(turn_context)

        # Save any state changes that might have occurred during the turn.
        await self.conversation_state.save_changes(turn_context, False)
        await self.user_state.save_changes(turn_context, False)

    async def on_message_activity(self, turn_context: TurnContext):
        logger.info(f"Message activity received: {turn_context.activity.from_property}")
        # TurnContext.remove_recipient_mention(turn_context.activity)

        # Handle adaptive card submission
        if turn_context.activity.value:
            value = turn_context.activity.value
            if (
                isinstance(value, dict)
                and value.get("action") == "submit_draft_request"
            ):
                document_type = value.get("documentType", "")
                draft_content = value.get("draftContent", "")

                # Create a text command from the adaptive card input
                # Keep the document type case-sensitive for matching
                turn_context.activity.text = (
                    f"process_draft_request|{document_type}|{draft_content}"
                )
                logger.info(
                    f"Adaptive card submission - Type: {document_type}, Content length: {len(draft_content)}"
                )

        # Only lowercase for logging, not for processing
        if turn_context.activity.text:
            text = turn_context.activity.text.strip()
            logger.info(
                "Received message: '%s' from user: %s",
                text[:100] + "..."
                if len(text) > 100
                else text,  # Truncate long messages in log
                turn_context.activity.from_property.name
                if turn_context.activity.from_property
                else "Unknown",
            )
        else:
            logger.warning("No text in activity")

        await DialogHelper.run_dialog(
            self.dialog,
            turn_context,
            self.conversation_state.create_property("DialogState"),
        )
