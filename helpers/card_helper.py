# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from typing import List, Optional
from botbuilder.schema import HeroCard, CardAction, ActionTypes, Attachment
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
        CardAction(
            type=ActionTypes.message_back,
            title="Draft Document",
            text="start_draft_document",
        ),
        CardAction(
            type=ActionTypes.message_back,
            title="Curate Updates",
            text="start_curate_updates",
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


def create_draft_input_card():
    """
    Create an Adaptive Card to collect draft document requirements.

    Returns:
        Activity with the adaptive card attachment
    """
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "Draft Military Document",
                "weight": "Bolder",
                "size": "Large",
            },
            {
                "type": "TextBlock",
                "text": "Select document type and provide details:",
                "wrap": True,
                "spacing": "Medium",
            },
            {
                "type": "Input.ChoiceSet",
                "id": "documentType",
                "label": "Document Type",
                "choices": [
                    {"title": "FRAGO (Fragmentary Order)", "value": "FRAGO"},
                    {"title": "EXORD (Execute Order)", "value": "EXORD"},
                    {"title": "Decision Memo", "value": "Decision Memo"},
                    {"title": "Talking Points", "value": "Talking Points"},
                ],
                "placeholder": "Select document type",
                "value": "FRAGO",
            },
            {
                "type": "Input.Text",
                "id": "draftContent",
                "label": "Requirements and Context",
                "placeholder": "Provide details, context, and requirements for the document...",
                "isMultiline": True,
                "maxLength": 2000,
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Generate Draft",
                "data": {"action": "submit_draft_request"},
            }
        ],
    }

    attachment = Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card,
    )

    return MessageFactory.attachment(attachment)
