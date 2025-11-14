# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from botbuilder.core import MessageFactory
from botbuilder.dialogs import WaterfallDialog, WaterfallStepContext, DialogTurnResult
from botbuilder.dialogs.prompts import (
    OAuthPrompt,
    OAuthPromptSettings,
    ConfirmPrompt,
    PromptOptions,
    TextPrompt,
)
from requests.exceptions import HTTPError

from dialogs import LogoutDialog
from simple_graph_client import SimpleGraphClient

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MainDialog(LogoutDialog):
    def __init__(self, connection_name: str):
        super(MainDialog, self).__init__(MainDialog.__name__, connection_name)

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
                    self.begin_command_loop_step,
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
        logger.info("\tExecuting prompt step.")
        return await step_context.begin_dialog(OAuthPrompt.__name__)

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
            await step_context.context.send_activity("You are now logged in.")
            return await step_context.next(None)

        await step_context.context.send_activity(
            "Login was not successful please try again."
        )
        return await step_context.end_dialog()

    async def begin_command_loop_step(
        self, step_context: WaterfallStepContext
    ) -> DialogTurnResult:
        logger.info("\tEntering command loop.")
        return await step_context.begin_dialog("CommandLoopDialog")

    async def command_prompt_step(
        self, step_context: WaterfallStepContext
    ) -> DialogTurnResult:
        logger.info("\tPrompting for command.")

        prompt_text = (
            step_context.options.get("prompt")
            if isinstance(step_context.options, dict)
            else None
        )

        message = (
            prompt_text or "What would you like to do? (try typing 'me' or 'email')"
        )
        return await step_context.prompt(
            TextPrompt.__name__,
            PromptOptions(prompt=MessageFactory.text(message)),
        )

    async def ensure_token_step(
        self, step_context: WaterfallStepContext
    ) -> DialogTurnResult:
        logger.info("\tEnsuring token before processing command.")
        step_context.values["command"] = step_context.result
        return await step_context.begin_dialog(OAuthPrompt.__name__)

    async def process_step(
        self, step_context: WaterfallStepContext
    ) -> DialogTurnResult:
        logger.info("\tExecuting process step.")
        command = (step_context.values.get("command") or "").strip()
        token_response = step_context.result

        if not token_response or not token_response.token:
            await step_context.context.send_activity("We couldn't log you in.")
            return await step_context.replace_dialog("AuthDialog")

        if not command:
            await step_context.context.send_activity(
                "I didn't catch that. Please try 'me' or 'email'."
            )
            return await step_context.replace_dialog(
                "CommandLoopDialog",
                {"prompt": "What would you like to do? (try 'me' or 'email')"},
            )

        parts = command.split(" ")
        command_key = parts[0].lower()

        try:
            client = SimpleGraphClient(token_response.token)

            if command_key == "me":
                me_info = await client.get_me()
                await step_context.context.send_activity(
                    f"You are {me_info['displayName']}"
                )
            elif command_key == "email":
                me_info = await client.get_me()
                await step_context.context.send_activity(
                    f"Your email: {me_info['mail']}"
                )
            elif command_key == "token":
                await step_context.context.send_activity(
                    f"Your token is {token_response.token}"
                )
            else:
                await step_context.context.send_activity(
                    "I do not understand that command. Please try 'me' or 'email'."
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
                return await step_context.replace_dialog("AuthDialog")

            await step_context.context.send_activity(
                "Sorry, I hit an error completing that request. Please try again."
            )

        return await step_context.replace_dialog(
            "CommandLoopDialog",
            {"prompt": "What would you like to do next? (try 'me' or 'email')"},
        )
