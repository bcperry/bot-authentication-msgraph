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
from helpers.card_helper import create_simple_card, create_draft_input_card
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
        logger.info(
            f"\tProcessing command: '{command[:200]}'"
        )  # Truncate long commands in log

        # Check if this is a pipe-delimited command (from adaptive card)
        if "|" in command:
            parts = command.split("|")
            command_key = parts[0].lower().strip()
        else:
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
                    ],
                )
                await step_context.context.send_activity(card)
            elif command_key == "analyze_email" or command_key == "start_analyze_email":
                await step_context.context.send_activity("Analyzing your email...")
                await self._run_agent_response(
                    step_context,
                    """Analyze my emails and provide a concise, actionable summary.

REQUIREMENTS:
- Report the total number of emails reviewed
- Focus only on emails directly related to my work and responsibilities
- Ignore newsletters, promotions, and automated notifications (count them but don't summarize)
- Identify high-priority items requiring action
- Provide specific, actionable next steps

OUTPUT FORMAT:
- No preamble or filler text
- Use clean markdown formatting
- Reference specific emails with: sender name, date, and subject line
- Make suggestions concrete and actionable

GOOD EXAMPLE:
**Reviewed 150 emails**

### Key Actions:
1. **Budget Briefing Follow-up** - John Doe (March 3rd)
   *Subject: Q2 Financial Review Meeting*
   
   → Schedule follow-up meeting to discuss Q2 budget projections
   
   → Need Date: [Insert Date Here]

2. **Cybersecurity Meeting** - Jane Smith (March 5th)
   *Subject: Urgent: Threat Assessment Review Required*
   
   → Meet with cybersecurity team this week to address identified threats
   
   → Need Date: [Insert Date Here]

3. **Congressional Inquiry Response** - Rep. Johnson (March 7th)
   *Subject: Information Request RE: Department Operations*
   
   → Draft comprehensive response addressing operational oversight questions
   
   → Need Date: [Insert Date Here]   

BAD EXAMPLE (too vague):
"Prioritize tasks related to high-level meetings. Engage with cybersecurity experts. Prepare response to inquiry."
""",
                    token_response.token,
                )
            elif command_key == "start_draft_document" or command_key == "draft":
                # Show the adaptive card to collect draft requirements
                draft_card = create_draft_input_card()
                await step_context.context.send_activity(draft_card)
            elif (
                command_key == "start_curate_updates"
                or command_key == "curate_updates"
                or command_key == "curate"
            ):
                await step_context.context.send_activity(
                    "Curating personalized updates from your emails..."
                )
                await self._run_agent_response(
                    step_context,
                    """Review my emails and curate personalized updates on the following topics:

REQUIRED TOPICS TO COVER:
1. **Sustainment KPIs** - Key performance indicators related to logistics, supply chain, readiness metrics
2. **JFLCC Posture** - Joint Force Land Component Commander operational status, force positioning, readiness
3. **DIB Developments** - Defense Industrial Base updates, acquisitions, industry partnerships, manufacturing

REQUIREMENTS:
- Report the total number of emails reviewed
- Extract and summarize ONLY information relevant to the three topics above
- Organize findings by topic with clear headers
- Include specific details: numbers, percentages, dates, and key decision points
- Reference source emails with sender name, date, and subject
- Highlight urgent items or emerging trends
- If no relevant information found for a topic, state "No updates found"

OUTPUT FORMAT:
- Use clean markdown formatting
- Start with email count and date range
- Organize by the three topics
- Make each update specific and actionable
- No preamble or filler text

EXAMPLE OUTPUT:
**Reviewed 150 emails (March 1-15, 2024)**

## Sustainment KPIs

### Readiness Metrics
- **Class III (Fuel) Status**: 87% of operational requirements met (up 3% from last week)
  *Source: LTC Johnson, March 12 - Weekly Sustainment Report*
  → Trend positive, continue monitoring

- **Maintenance Backlog**: 23 vehicles in depot-level maintenance (down from 31)
  *Source: MAJ Davis, March 14 - Maintenance Update*
  → 8 vehicles returned to service this week

### Supply Chain
- **Critical Parts Shortages**: Hydraulic components delayed 2-3 weeks
  *Source: Logistics Command, March 10 - Supply Chain Alert*
  ⚠️ **ACTION REQUIRED**: Coordinate alternative sourcing by March 20

## JFLCC Posture

### Force Positioning
- **3rd Brigade Deployment**: On schedule for April 1 deployment to AO Phoenix
  *Source: BG Williams, March 13 - OPORD Brief*
  → 94% personnel in theater, 89% equipment positioned

### Operational Readiness
- **C-Rating Improvement**: Battalion increased from C3 to C2 status
  *Source: COL Martinez, March 11 - Readiness Assessment*
  → Training completion and equipment availability met thresholds

## DIB Developments

### Acquisitions
- **New Comms System Contract**: $45M awarded to TechDef Solutions
  *Source: Defense News Digest, March 9*
  → Delivery timeline: 18 months, initial fielding Q4 2025

### Industry Partnerships
- **Advanced Manufacturing Initiative**: Partnership with 3 commercial manufacturers
  *Source: Under Secretary memo, March 8 - Industrial Base Modernization*
  → Focus on additive manufacturing for rapid prototyping
  → Pilot program launches May 2024

### Supply Chain Resilience
- **Critical Minerals Sourcing**: New domestic supplier identified for rare earth elements
  *Source: Defense Logistics Agency, March 15*
  ⚠️ **WATCHLIST**: Monitoring for price stability and delivery reliability
""",
                    token_response.token,
                )
            elif command_key == "process_draft_request":
                # Process the draft request from adaptive card submission
                parts = command.split("|")
                if len(parts) >= 3:
                    document_type = parts[1].strip()
                    draft_content = parts[2].strip()

                    if not draft_content:
                        await step_context.context.send_activity(
                            "Please provide the requirements and context for the document."
                        )
                    else:
                        await step_context.context.send_activity(
                            f"Drafting your {document_type}..."
                        )

                        # Create a detailed prompt for the agent based on document type
                        if document_type == "FRAGO":
                            prompt = f"""You must draft a properly formatted FRAGO (Fragmentary Order) document based on these user requirements:

{draft_content}

CRITICAL INSTRUCTIONS:
1. If the user mentions emails, USE YOUR EMAIL SEARCH TOOLS to retrieve the actual email content first
2. Extract operational details from emails to populate the FRAGO sections
3. OUTPUT ONLY A PROPERLY FORMATTED FRAGO - Do NOT summarize emails or provide commentary
4. Fill ALL sections below with specific information - NO placeholders or "[TBD]" text allowed
5. If specific details aren't available, make reasonable military assumptions or state "No change from original OPORD"

YOUR OUTPUT MUST FOLLOW THIS EXACT FORMAT:

====================
FRAGMENTARY ORDER [Insert Number]
====================
(CLASSIFICATION)

**REFERENCES:** 
- Reference: OPORD [Number], dated [Date]
- Maps: [Chart series, sheet numbers, edition]
- Other: [Additional documents]

**TIME ZONE USED THROUGHOUT THE ORDER:** [ZULU/Local/Other]

**TASK ORGANIZATION:**
[List specific changes to subordinate units OR state "No changes to task organization from OPORD [Number]"]

---

**1. SITUATION:**

**a. Enemy Forces:**
[Describe current enemy disposition, strength, capabilities, and most likely course of action OR state "No significant changes to enemy situation"]

**b. Friendly Forces:**
[Describe adjacent unit operations, higher headquarters' intent updates, or supporting unit changes OR state "No changes to friendly forces"]

**c. Terrain and Weather:**
[Note environmental factors affecting operations OR state "No significant changes"]

---

**2. MISSION:**

[Insert complete mission statement using WHO, WHAT, WHEN, WHERE, WHY format]
Example: "Task Force Bravo conducts relief in place with 3rd Brigade NLT 151200NOV25 at OBJ HAWK in order to enable division consolidation operations."

---

**3. EXECUTION:**

**a. Concept of Operations:**
[3-5 sentences describing the overall approach, phasing, main effort, and supporting efforts with specific details]

**b. Tasks to Subordinate Units:**

**1st Battalion:**
- [Specific task with timeline and purpose]

**2nd Battalion:**
- [Specific task with timeline and purpose]

**Support Company:**
- [Specific task with timeline and purpose]

[Add additional units as needed]

**c. Coordinating Instructions:**

**1. Timeline:**
   - H-Hour: [DDTTTTZMONYY format, e.g., 151400ZNOV25]
   - LD/SP Time: [If applicable]
   - TOT: [If applicable]

**2. Movement:**
   - Routes: [Primary and alternate]
   - Formation: [Specify]
   - Order of March: [Specify]

**3. Fire Support:**
   - Priority of Fires: [Unit/phase]
   - Restrictive Fire Lines: [Grid coordinates]
   - Priority Targets: [List with coordinates]

**4. Control Measures:**
   - Phase Lines: [PL NAME - 8-digit grid]
   - Checkpoints: [CP## - 8-digit grid]
   - Boundaries: [Description with grids]

**5. Communications:**
   - Radio Windows: [Times and frequencies]
   - Reports: [Types, times, and recipients]

**6. Rules of Engagement:**
   - [Specific ROE guidance or state "No change to ROE"]

---

**4. SUSTAINMENT:**

**a. Supply:**
   - **Ammunition:** [Resupply point location, time, and procedures]
   - **Fuel:** [FARP/refuel point location and schedule]
   - **Water:** [Distribution point and quantities]

**b. Transportation:**
   - [Vehicle allocations, convoy details, or state "No change"]

**c. Maintenance:**
   - Collection Point: [Location - 8-digit grid]
   - Recovery: [Procedures and contact]

**d. Medical:**
   - **CASEVAC:** 9-Line frequency [####.#]
   - **Aid Station:** [Location - 8-digit grid]

---

**5. COMMAND AND SIGNAL:**

**a. Command:**
   - **Commander's Location:** [Specific location or grid]
   - **Succession of Command:** [List 1st through 3rd]
   - **Command Posts:** [TAC/MAIN/REAR locations]

**b. Signal:**

**PACE Communications:**
   - **Primary:** [System] - Freq [####.#] / Net [Name] / Call Sign [Alpha-6]
   - **Alternate:** [System] - Freq [####.#] / Net [Name] / Call Sign [Alpha-6A]
   - **Contingency:** [System/method]
   - **Emergency:** [System/method]

**Reports Required:**
   - [Report type, frequency, and recipient]
   - [Additional reports as needed]

---

**ACKNOWLEDGE:** All subordinate commanders acknowledge receipt via [method] NLT [time].

(CLASSIFICATION)

====================

REMEMBER: Output ONLY the formatted FRAGO above. Do NOT provide email summaries, commentary, or explanations outside the FRAGO format."""
                        elif document_type == "EXORD":
                            prompt = f"""Draft an EXORD (Execute Order) based on the following requirements and context:

{draft_content}

INSTRUCTIONS:
- Follow standard military EXORD format
- Include situation, mission, execution, sustainment, and command and signal sections
- Specify execution time and deployment timeline
- Include force protection measures
- Provide clear rules of engagement (ROE) guidance
- Use appropriate classification markings
- Ensure all instructions are actionable and time-sensitive

OUTPUT FORMAT:
- Use clean markdown formatting
- Include proper military headers and sections
- Specify all critical timelines and coordination measures"""
                        elif document_type == "Decision Memo":
                            prompt = f"""Draft a Decision Memo based on the following requirements and context:

{draft_content}

INSTRUCTIONS:
- Start with executive summary/purpose
- Provide background and context
- Present the issue/decision required clearly
- Outline options/alternatives with pros and cons
- Include risk assessment
- Provide clear recommendation
- Conclude with implementation plan if decision is approved
- Use professional tone suitable for senior leadership

OUTPUT FORMAT:
- Use clean markdown formatting
- Include clear section headers (Purpose, Background, Issue, Options, Recommendation, etc.)
- Keep concise and focused on decision-making"""
                        elif document_type == "Talking Points":
                            prompt = f"""Draft Talking Points based on the following requirements and context:

{draft_content}

INSTRUCTIONS:
- Create clear, concise bullet points for oral presentation
- Start with key message/bottom line up front
- Organize by topic or priority
- Include supporting facts, statistics, or examples
- Anticipate questions and include potential responses
- Use conversational but professional language
- Keep each point to 1-2 sentences maximum

OUTPUT FORMAT:
- Use clean markdown formatting with bullet points
- Bold key phrases or topics
- Include section headers if multiple topics
- Ensure easy readability for quick reference"""
                        else:
                            prompt = f"""Draft a {document_type} based on the following requirements and context:

{draft_content}

INSTRUCTIONS:
- Follow standard military format and structure for {document_type}
- Include all required sections and fields
- Use appropriate military terminology and classification markings (if applicable)
- Ensure clarity, precision, and actionable language
- Format the output professionally with proper headers and sections

OUTPUT FORMAT:
- Use clean markdown formatting
- Include clear section headers
- Make all instructions and requirements explicit
- Ensure the document is ready for review and refinement"""

                        await self._run_agent_response(
                            step_context, prompt, token_response.token
                        )
                else:
                    await step_context.context.send_activity(
                        "Invalid draft request format. Please use the Draft Document button."
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
