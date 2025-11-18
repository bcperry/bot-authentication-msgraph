# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from typing import List, Optional
from botbuilder.schema import HeroCard, CardAction, ActionTypes
from botbuilder.core import MessageFactory, CardFactory
from datetime import datetime


def create_simple_card(
    title: str, text: str, buttons: Optional[List[CardAction]] = None
):
    """
    Create a simple hero card.

    Args:
        title: Card title
        text: Card text content
        buttons: Optional list of card action buttons

    Returns:
        Activity with the card attachment
    """
    card = HeroCard(title=title, text=text, buttons=buttons or [])
    return MessageFactory.attachment(CardFactory.hero_card(card))


def create_greeting_card(user_name: str):
    """
    Create a greeting card with action buttons.

    Args:
        user_name: The user's display name

    Returns:
        Activity with the greeting card
    """
    buttons = [
        CardAction(
            type=ActionTypes.message_back,
            title="Analyze Email",
            text="start_analyze_email",
        ),
    ]

    # Determine greeting based on current time
    current_hour = datetime.now().hour
    if current_hour < 12:
        greeting = f"Good morning, {user_name}"
    elif current_hour < 18:
        greeting = f"Good afternoon, {user_name}"
    else:
        greeting = f"Good evening, {user_name}"

    card = HeroCard(
        title=greeting,
        text="Use the Buttons to perform Actions or type your own message to interact with the agent. I will use the tools at my disposal to assist you.",
        buttons=buttons,
    )

    return MessageFactory.attachment(CardFactory.hero_card(card))
