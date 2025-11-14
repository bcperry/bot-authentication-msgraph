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
        text = turn_context.activity.text.strip().lower()

        logger.info(
            "Received message: '%s' from user: %s",
            text,
            turn_context.activity.from_property.name
            if turn_context.activity.from_property
            else "Unknown",
        )

        await DialogHelper.run_dialog(
            self.dialog,
            turn_context,
            self.conversation_state.create_property("DialogState"),
        )
