# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from typing import Optional

from botbuilder.core import MessageFactory, StatePropertyAccessor
from botbuilder.schema import CardAction
from botbuilder.dialogs import WaterfallDialog, WaterfallStepContext, DialogTurnResult
from botbuilder.schema._connector_client_enums import ActionTypes

from botbuilder.dialogs.prompts import (
    OAuthPrompt,
    OAuthPromptSettings,
    ConfirmPrompt,
    PromptOptions,
    TextPrompt,
)
from requests.exceptions import HTTPError

from dialogs import LogoutDialog
from helpers.agent_service import AgentService
from helpers.thread_store import AgentThreadStore
from helpers.tools import create_tools_with_token
from helpers.card_helper import create_simple_card
from simple_graph_client import SimpleGraphClient

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MainDialog(LogoutDialog):
    def __init__(
        self,
        connection_name: str,
        agent_service: AgentService,
        agent_thread_accessor: StatePropertyAccessor,
        thread_store: AgentThreadStore,
    ):
        super(MainDialog, self).__init__(MainDialog.__name__, connection_name)
        self._agent_service = agent_service
        self._agent_thread_accessor = agent_thread_accessor
        self._thread_store = thread_store

        self.add_dialog(
            OAuthPrompt(
                OAuthPrompt.__name__,
                OAuthPromptSettings(
                    connection_name=connection_name,
                    text="Please Sign In",
                    title="Sign In",
                    timeout=300000,
                ),
            )
        )

        self.add_dialog(TextPrompt(TextPrompt.__name__))
        self.add_dialog(ConfirmPrompt(ConfirmPrompt.__name__))

        self.add_dialog(
            WaterfallDialog(
                "AuthDialog",
                [
                    self.prompt_step,
                    self.login_step,
                    self.process_input_step,
                ],
            )
        )

        self.add_dialog(
            WaterfallDialog(
                "CommandLoopDialog",
                [
                    self.command_prompt_step,
                    self.ensure_token_step,
                    self.process_step,
                ],
            )
        )

        self.initial_dialog_id = "AuthDialog"

    async def prompt_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        logger.info("\tExecuting prompt_step - Beginning OAuth prompt.")
        logger.info(f"\tChannel: {step_context.context.activity.channel_id}")
        logger.info(f"\tConnection name configured: {self.connection_name}")

        if not self.connection_name:
            logger.error(
                "\tERROR: ConnectionName is not configured! OAuth will not work."
            )
            await step_context.context.send_activity(
                "Bot configuration error: OAuth connection name is not set. "
                "Please set the ConnectionName environment variable."
            )
            return await step_context.end_dialog()

        # Store the original user command before showing OAuth prompt
        user_message = (
            step_context.context.activity.text.strip()
            if step_context.context.activity.text
            else ""
        )
        step_context.values["pending_command"] = user_message
        logger.info(f"\tStored pending command: '{user_message}'")

        result = await step_context.begin_dialog(OAuthPrompt.__name__)
        logger.info(
            f"\tOAuth prompt result status: {result.status if result else 'None'}"
        )

        # Log if any activities were queued to be sent
        if hasattr(step_context.context, "_buffered_reply_activities"):
            logger.info(
                f"\tBuffered activities count: {len(step_context.context._buffered_reply_activities)}"
            )

        return result

    async def login_step(self, step_context: WaterfallStepContext) -> DialogTurnResult:
        # Get the token from the previous step. Note that we could also have gotten the
        # token directly from the prompt itself. There is an example of this in the next method.
        token_preview = (
            step_context.result.token[:5]
            if step_context.result and getattr(step_context.result, "token", None)
            else ""
        )
        logger.info(f"\tExecuting login step with token: {token_preview}.")
        if step_context.result:
            # Store the token for the next step
            step_context.values["token_response"] = step_context.result
            return await step_context.next(step_context.result)

        await step_context.context.send_activity(
            "Login was not successful please try again."
        )
        return await step_context.end_dialog()

    async def process_input_step(
        self, step_context: WaterfallStepContext
    ) -> DialogTurnResult:
        """Process user input after successful login."""
        logger.info("\tProcessing input after login.")

        # Get the original command that was stored before OAuth prompt
        command = step_context.values.get("pending_command", "").strip()
        token_response = step_context.result

        logger.info(f"\tRetrieved pending command: '{command}'")

        if not command:
            # No command was stored, just logged in - end dialog and wait for next input
            logger.info("\tNo pending command, ending dialog")
            return await step_context.end_dialog()

        # Process the command with the token
        await self._process_command(step_context, command, token_response)
        return await step_context.end_dialog()

    async def begin_command_loop_step(
        self, step_context: WaterfallStepContext
    ) -> DialogTurnResult:
        logger.info("\tEntering command loop.")
        # End the dialog here instead of starting command loop
        # The bot will wait for user input naturally
        return await step_context.end_dialog()

    async def command_prompt_step(
        self, step_context: WaterfallStepContext
    ) -> DialogTurnResult:
        logger.info("\tExecuting command_prompt_step.")

        prompt_text = (
            step_context.options.get("prompt")
            if isinstance(step_context.options, dict)
            else None
        )

        # Only show prompt if explicitly provided in options, otherwise use invisible character
        message = prompt_text if prompt_text else "\u200b"  # Zero-width space
        logger.info(
            f"\tPrompting with message: {message if prompt_text else '(no visible prompt)'}"
        )
        result = await step_context.prompt(
            TextPrompt.__name__,
            PromptOptions(prompt=MessageFactory.text(message)),
        )
        logger.info(
            f"\tCommand prompt result status: {result.status if result else 'None'}"
        )
        return result

    async def ensure_token_step(
        self, step_context: WaterfallStepContext
    ) -> DialogTurnResult:
        logger.info("\tEnsuring token before processing command.")
        step_context.values["command"] = step_context.result
        return await step_context.begin_dialog(OAuthPrompt.__name__)

    async def process_step(
        self, step_context: WaterfallStepContext
    ) -> DialogTurnResult:
        logger.info("\tExecuting process_step.")
        command = (step_context.values.get("command") or "").strip()
        token_response = step_context.result

        logger.info(f"\tCommand received: '{command}'")
        logger.info(f"\tToken response present: {token_response is not None}")

        if not token_response or not token_response.token:
            logger.warning("\tNo valid token - redirecting to AuthDialog")
            await step_context.context.send_activity("We couldn't log you in.")
            return await step_context.replace_dialog("AuthDialog")

        if not command:
            logger.warning("\tEmpty command received")
            await step_context.context.send_activity(
                "I didn't catch that. Ask me anything about Microsoft 365."
            )
            return await step_context.end_dialog()

        await self._process_command(step_context, command, token_response)
        return await step_context.end_dialog()

    async def _process_command(
        self,
        step_context: WaterfallStepContext,
        command: str,
        token_response,
    ) -> None:
        """Process a user command with the given token."""
        logger.info(f"\tProcessing command: '{command}'")

        parts = command.split(" ")
        command_key = parts[0].lower()

        try:
            client = SimpleGraphClient(token_response.token)

            if command_key == "me":
                me_info = await client.get_me()
                card = create_simple_card(
                    "User Info", f"You are {me_info['displayName']}"
                )
                await step_context.context.send_activity(card)
            elif command_key == "email":
                me_info = await client.get_me()
                card = create_simple_card("Email", f"Your email: {me_info['mail']}")
                await step_context.context.send_activity(card)
            elif command_key == "token":
                card = create_simple_card(
                    "Token", f"Your token is {token_response.token}"
                )
                await step_context.context.send_activity(card)
            elif command_key == "card" or command_key == "get_card":
                card = create_simple_card(
                    "Available Actions",
                    "Please select from the following actions, or type your own message to interact with the agent.",
                    buttons=[
                        CardAction(
                            type=ActionTypes.message_back,
                            title="Analyze Email",
                            text="start_analyze_email",
                        ),
                    ],
                )
                await step_context.context.send_activity(card)
            elif command_key == "analyze_email" or command_key == "start_analyze_email":
                await step_context.context.send_activity("Analyzing your email...")
                await self._run_agent_response(
                    step_context,
                    "Analyze my email and provide a summary. Be sure to reference specific emails where relevant, identify high priority items, \
                    and suggest any actions I should take.",
                    token_response.token,
                )
            else:
                await self._run_agent_response(
                    step_context, command, token_response.token
                )

        except HTTPError as error:
            status = error.response.status_code if error.response else None
            logger.warning(
                "Graph request failed with status %s: %s",
                status,
                error,
            )
            if status in (401, 403):
                await step_context.context.send_activity(
                    "Your session has expired. Please sign in again."
                )
            else:
                await step_context.context.send_activity(
                    "Sorry, I hit an error completing that request. Please try again."
                )

    async def _run_agent_response(
        self,
        step_context: WaterfallStepContext,
        prompt: str,
        token: str,
    ) -> None:
        """
        Run the agent with the given prompt and user token.

        Args:
            step_context: The current dialog step context
            prompt: The user's message/question
            token: The user's OAuth access token for Graph API calls
        """
        conversation_key = self._conversation_key(step_context)
        thread_state = await self._agent_thread_accessor.get(
            step_context.context, lambda: None
        )
        if not thread_state:
            thread_state = await self._thread_store.load(conversation_key)
            if thread_state:
                logger.debug(
                    "Recovered thread state for %s from persistent store.",
                    conversation_key,
                )
                # Re-hydrate conversation state so future turns use in-memory copy
                await self._agent_thread_accessor.set(
                    step_context.context, thread_state
                )
        if thread_state:
            message_count = len(
                thread_state.get("chat_message_store_state", {}).get("messages", [])
            )
            logger.info(
                "Loaded thread state for %s containing %s messages.",
                conversation_key,
                message_count,
            )
        else:
            logger.info(
                "No existing thread state found for %s; starting fresh.",
                conversation_key,
            )
        user_id: Optional[str] = (
            step_context.context.activity.from_property.id
            if step_context.context.activity.from_property
            else None
        )

        try:
            # Create tools with the user's token bound to them
            tools_with_token = create_tools_with_token(token)

            response, serialized_thread = await self._agent_service.run(
                prompt, thread_state=thread_state, user=user_id, tools=tools_with_token
            )
            await self._agent_thread_accessor.set(
                step_context.context, serialized_thread
            )
            await self._thread_store.save(conversation_key, serialized_thread)
            message_count = len(
                serialized_thread.get("chat_message_store_state", {}).get(
                    "messages", []
                )
            )
            logger.info(
                "Persisted thread state for %s with %s messages.",
                conversation_key,
                message_count,
            )

            reply_text = response.text or "I'm here whenever you're ready."
            await step_context.context.send_activity(reply_text)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Agent invocation failed", exc_info=exc)
            await step_context.context.send_activity(
                "Sorry, I couldn't reach our assistant just now. Please try again in a moment."
            )

    def _conversation_key(self, step_context: WaterfallStepContext) -> str:
        activity = step_context.context.activity
        channel_id = activity.channel_id or "unknown"
        conversation_id = (
            activity.conversation.id if activity.conversation else "no-conv"
        )
        return f"{channel_id}:{conversation_id}"
