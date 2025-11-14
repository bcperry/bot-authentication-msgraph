# Add a protected tool to test authentication

import os
import logging
from typing import Callable
from functools import wraps
from msgraph.generated.models.o_data_errors.o_data_error import ODataError

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_tools_with_token(token: str) -> list[Callable]:
    """
    Create a list of tool functions with the access token bound to them.

    This allows the agent to call these tools without needing to know about the token.
    Each tool function has the token "baked in" via a wrapper that preserves the
    original function signature (minus the token parameter).

    Args:
        token: The user's access token from OAuth

    Returns:
        A list of callable tool functions ready to be used by the agent
    """

    def wrap_tool_with_token(func: Callable, token: str) -> Callable:
        """
        Wrap a tool function to inject the token parameter while hiding it from the schema.

        This wrapper:
        1. Preserves the original function's name and docstring
        2. Removes the 'token' parameter from the visible signature
        3. Injects the token when the function is called
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Inject the token into kwargs
            kwargs["token"] = token
            return func(*args, **kwargs)

        # Remove the 'token' parameter from the wrapper's signature
        # This ensures the model doesn't see it in the tool schema
        import inspect

        sig = inspect.signature(func)
        params = [p for name, p in sig.parameters.items() if name != "token"]
        wrapper.__signature__ = sig.replace(parameters=params)

        return wrapper

    return [
        wrap_tool_with_token(greet_user, token),
        wrap_tool_with_token(list_email_messages, token),
        wrap_tool_with_token(get_email_message, token),
    ]


def get_user_info(token) -> dict:
    """Returns information about the authenticated Azure user based on the MCP server connection access token."""

    # The AzureProvider stores user data in token claims
    return {
        "azure_id": token.claims.get("sub"),
        "email": token.claims.get("email"),
        "name": token.claims.get("name"),
        "job_title": token.claims.get("job_title"),
        "office_location": token.claims.get("office_location"),
    }


async def greet_user(token: str = None) -> dict:
    """
    Greet a user by retrieving their information from Microsoft Graph.

    This tool retrieves the authenticated user's profile information and returns
    a greeting with their display name and email.

    Args:
        token: The user's OAuth access token

    Returns:
        dict: A dictionary containing:
            - greeting (str): The greeting message
            - display_name (str): User's display name
            - email (str): User's email address (mail or userPrincipalName)
            - success (bool): Whether the operation was successful
            - error (str, optional): Error message if something went wrong

    """
    try:
        from simple_graph_client import SimpleGraphClient

        logger.info(f"Calling greet_user tool with token {token[:5]}")

        # Create Graph client with the token
        client = SimpleGraphClient(token)

        # Get user information - await the async call
        user = await client.get_me()

        if user:
            display_name = user.get("displayName") or "User"
            # For Work/school accounts, email is in mail property
            # Personal accounts, email is in userPrincipalName
            email = (
                user.get("mail") or user.get("userPrincipalName") or "No email found"
            )

            greeting = f"Hello, {display_name}!"

            return {
                "greeting": greeting,
                "display_name": display_name,
                "email": email,
                "success": True,
            }
        else:
            return {
                "greeting": "Hello!",
                "error": "Unable to retrieve user information",
                "success": False,
            }

    except ODataError as odata_error:
        error_msg = "Unknown error"
        if odata_error.error:
            error_msg = f"{odata_error.error.code}: {odata_error.error.message}"

        return {"greeting": "Hello!", "error": error_msg, "success": False}
    except Exception as e:
        logger.exception("Error in greet_user", exc_info=e)
        return {"greeting": "Hello!", "error": str(e), "success": False}


def list_email_messages(token: str = None) -> dict:
    """
    List email messages from the authenticated user's mailbox.

    Use this tool to identify relevant messages based on subject, sender, or preview text.
    This tool returns lightweight message metadata (id, subject, sender, preview) which
    helps you discover and filter messages. Once you identify the message(s) you need,
    use the get_email_message tool with the message ID to retrieve the full email content
    including the complete body, all recipients, and attachment details.

    Retrieves a collection of messages from the user's mail folders. Returns message
    metadata including sender, recipients, subject, preview text, and other properties.
    Messages are returned in reverse chronological order by default.

    Workflow:
        1. Use this tool to browse and identify relevant messages
        2. Note the 'id' field of messages you want to read
        3. Use get_email_message(message_id) to retrieve full content

    Args:
        token: The user's OAuth access token (for future live Graph API calls)

    Returns:
        dict: A dictionary containing:
            - @odata.context (str): OData context URL for the response
            - value (list): Array of message objects, each containing:
                - id (str): Unique message identifier
                - subject (str): Email subject line
                - from (dict): Sender information with emailAddress object
                - bodyPreview (str): First 255 characters of the message body
            - message_count (int): Total number of messages returned
            - success (bool): Whether the operation was successful
            - error (str, optional): Error message if the request failed

    Permissions required: Mail.Read or Mail.ReadWrite
    """
    try:
        # Get the path to the sample data file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_file = os.path.join(
            os.path.dirname(current_dir), "data", "sample_emails.json"
        )

        # Read the JSON file
        import json

        with open(data_file, "r", encoding="utf-8") as f:
            email_data = json.load(f)

        # Extract only the fields we want to return
        filtered_messages = []
        for message in email_data.get("value", []):
            filtered_messages.append(
                {
                    "id": message.get("id"),
                    "subject": message.get("subject"),
                    "from": message.get("from"),
                    "isRead": message.get("isRead"),
                    "bodyPreview": message.get("bodyPreview"),
                }
            )

        return {
            "value": filtered_messages,
            "message_count": len(filtered_messages),
            "success": True,
        }

    except FileNotFoundError:
        return {
            "error": f"Sample email data file not found at {data_file}",
            "success": False,
            "value": [],
        }
    except json.JSONDecodeError as e:
        return {
            "error": f"Failed to parse email data: {str(e)}",
            "success": False,
            "value": [],
        }
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}", "success": False, "value": []}


def get_email_message(message_id: str, token: str = None) -> dict:
    """
    Retrieve a specific email message by ID from the authenticated user's mailbox.

    Gets the full details of a single message including the complete body content,
    all recipients, attachments information, and metadata.

    Args:
        message_id (str): The unique identifier of the message to retrieve
        token (str): The user's OAuth access token (for future live Graph API calls)

    Returns:
        dict: A dictionary containing:
            - id (str): Unique message identifier
            - subject (str): Email subject line
            - from (dict): Sender information with emailAddress object
            - sender (dict): Actual sender information
            - toRecipients (list): Array of recipient emailAddress objects
            - ccRecipients (list): Array of CC recipient emailAddress objects
            - bccRecipients (list): Array of BCC recipient emailAddress objects
            - receivedDateTime (str): ISO 8601 datetime when message was received
            - sentDateTime (str): ISO 8601 datetime when message was sent
            - createdDateTime (str): ISO 8601 datetime when message was created
            - lastModifiedDateTime (str): ISO 8601 datetime of last modification
            - isRead (bool): Whether the message has been read
            - isDraft (bool): Whether the message is a draft
            - importance (str): Message importance (normal, high, low)
            - bodyPreview (str): First 255 characters of the message body
            - body (dict): Full message body with contentType and content
            - hasAttachments (bool): Whether the message has file attachments
            - webLink (str): URL to open the message in Outlook on the web
            - inferenceClassification (str): Classification (focused or other)
            - flag (dict): Follow-up flag status and dates
            - conversationId (str): Conversation identifier
            - parentFolderId (str): Parent folder identifier
            - success (bool): Whether the operation was successful
            - error (str, optional): Error message if the request failed

    Permissions required: Mail.Read or Mail.ReadWrite
    """
    try:
        # Remove trailing "=" if present in the message_id
        clean_message_id = message_id.rstrip("=")

        # Get the path to the specific message JSON file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(os.path.dirname(current_dir), "data")
        message_file = os.path.join(data_dir, f"{clean_message_id}.json")

        # Read the JSON file for this specific message
        import json

        with open(message_file, "r", encoding="utf-8") as f:
            message = json.load(f)

        return {**message, "success": True}

    except FileNotFoundError:
        return {"error": f"Message with ID '{message_id}' not found", "success": False}
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse message data: {str(e)}", "success": False}
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}", "success": False}
