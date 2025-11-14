# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
import traceback
from datetime import datetime
from fastapi import FastAPI, Request, Response
import os
import uvicorn
import logging


from botbuilder.core import (
    ConversationState,
    MemoryStorage,
    TurnContext,
    UserState,
)
from botbuilder.integration.aiohttp import (
    CloudAdapter,
    ConfigurationBotFrameworkAuthentication,
)
from botbuilder.schema import Activity, ActivityTypes

from bots import AuthBot

# Create the loop and Flask app
from config import DefaultConfig
from dialogs import MainDialog


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

# Configure uvicorn and fastapi loggers to show INFO level
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("fastapi").setLevel(logging.INFO)

CONFIG = DefaultConfig()

# Create adapter.
# See https://aka.ms/about-bot-adapter to learn more about how bots work.
ADAPTER = CloudAdapter(ConfigurationBotFrameworkAuthentication(CONFIG))


# Catch-all for errors.
async def on_error(context: TurnContext, error: Exception):
    # This check writes out errors to console log .vs. app insights.
    # NOTE: In production environment, you should consider logging this to Azure
    #       application insights.
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()

    # Send a message to the user
    await context.send_activity("The bot encountered an error or bug.")
    await context.send_activity(
        "To continue to run this bot, please fix the bot source code."
    )

    # Send a trace activity if we're talking to the Bot Framework Emulator
    if context.activity.channel_id == "emulator":
        # Create a trace activity that contains the error object
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.utcnow(),
            type=ActivityTypes.trace,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        )
        # Send a trace activity, which will be displayed in Bot Framework Emulator
        await context.send_activity(trace_activity)


ADAPTER.on_turn_error = on_error

# Create MemoryStorage and state
MEMORY = MemoryStorage()
USER_STATE = UserState(MEMORY)
CONVERSATION_STATE = ConversationState(MEMORY)

# Create dialog
DIALOG = MainDialog(CONFIG.CONNECTION_NAME)

# Create Bot
BOT = AuthBot(CONVERSATION_STATE, USER_STATE, DIALOG)


app = FastAPI(title="Azure Bot Service")


@app.post("/api/messages")
# Listen for incoming requests on /api/messages.
async def messages(req: Request) -> Response:
    return await ADAPTER.process(req, BOT)


if __name__ == "__main__":
    try:
        host = "0.0.0.0" if os.environ.get("WEBSITE_SITE_NAME") else "localhost"
        uvicorn.run(app, host=host, port=CONFIG.PORT)
    except Exception as error:
        raise error
