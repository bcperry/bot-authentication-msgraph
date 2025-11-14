# Authentication Bot Utilizing MS Graph

Bot Framework v4 bot authentication using Microsoft Graph sample

This bot has been created using [Bot Framework](https://dev.botframework.com), is shows how to use the bot authentication capabilities of Azure Bot Service. In this sample we are assuming the OAuth 2 provider is Azure Active Directory v2 (AADv2) and are utilizing the Microsoft Graph API to retrieve data about the user. [Check here](https://docs.microsoft.com/en-us/azure/bot-service/bot-builder-authentication?view=azure-bot-service-4.0&tabs=csharp) for information about getting an AADv2
application setup for use in Azure Bot Service. The [scopes](https://developer.microsoft.com/en-us/graph/docs/concepts/permissions_reference) used in this sample are the following:

- `openid`
- `profile`
- `User.Read`

NOTE: Microsoft Teams currently differs slightly in the way auth is integrated with the bot. Refer to sample 5 [here](https://github.com/OfficeDev/Microsoft-Teams-Samples#bots-samples-using-the-v4-sdk).

## To try this sample

- Clone the repository
```bash
git clone https://github.com/Microsoft/botbuilder-samples.git
```
- In a terminal, navigate to `botbuilder-samples\samples\python\24.bot-authentication-msgraph` folder
- Update `config.py` with required configuration settings
  - MicrosoftAppId
  - MicrosoftAppPassword
  - ConnectionName
- Activate your desired virtual environment
- In the terminal, type `pip install -r requirements.txt`
- Run your bot with `python app.py`

## Testing the bot using Bot Framework Emulator

[Microsoft Bot Framework Emulator](https://github.com/microsoft/botframework-emulator) is a desktop application that allows bot developers to test and debug their bots on localhost or running remotely through a tunnel.

- Install the latest Bot Framework Emulator from [here](https://github.com/Microsoft/BotFramework-Emulator/releases)
- In Bot Framework Emulator Settings, enable `Use a sign-in verification code for OAuthCards` to receive the magic code

### Connect to the bot using Bot Framework Emulator

- Launch Bot Framework Emulator
- File -> Open Bot
- Enter a Bot URL of `http://localhost:3978/api/messages`

## Interacting with the bot

This sample uses the bot authentication capabilities of Azure Bot Service, providing features to make it easier to develop a bot that
authenticates users to various identity providers such as Azure AD (Azure Active Directory), GitHub, Uber, and so on. These updates also
take steps towards an improved user experience by eliminating the magic code verification for some clients and channels.
It is important to note that the user's token does not need to be stored in the bot. When the bot needs to use or verify the user has a valid token at any point the OAuth prompt may be sent. If the token is not valid they will be prompted to login.

## Agent Framework + MCP integration

This sample now uses the Agent Framework to satisfy free-form questions by calling an MCP server (for example, a Microsoft Graph MCP agent). The helper in `helpers/agent_service.py` wires up an `AzureOpenAIChatClient`, a `ChatAgent`, and an `MCPStreamableHTTPTool` and persists the agent thread inside the Bot Framework conversation state so each Teams conversation keeps its own history.

Configure the agent layer via environment variables (typically in your `.env` file):

| Variable | Description | Default |
| --- | --- | --- |
| `MCP_TOOL_URL` | The MCP server endpoint (HTTP/SSE). | `http://localhost:8000/mcp` |
| `MCP_TOOL_NAME` | Friendly name that shows up inside the agent for the MCP tool. | `MS Graph` |
| `MCP_APPROVAL_MODE` | Optional approval policy (`always_require` or `never_require`). | _unset_ |
| `TEAMS_AGENT_NAME` | Name assigned to the Agent Framework `ChatAgent`. | `teams_agent` |
| `TEAMS_AGENT_INSTRUCTIONS` | System instructions for the agent. | "You are a helpful Teams assistant…" |
| `TEAMS_AGENT_TEMPERATURE` | Optional float to tweak creativity. | _unset_ |
| `COSMOSDB_ENDPOINT` | Azure Cosmos DB account endpoint. | _required_ |
| `COSMOSDB_KEY` | Primary key for the Cosmos DB account (or emulator). Leave unset to fall back to Entra ID. | _optional_ |
| `COSMOSDB_DATABASE` | Cosmos DB database that stores agent threads. | `bot-data` |
| `COSMOSDB_CONTAINER` | Container name for the persisted threads. | `agent-threads` |
| `COSMOSDB_PARTITION_KEY_PATH` | Partition key path used for the container. | `/conversationKey` |
| `COSMOSDB_CONTAINER_THROUGHPUT` | Optional manual throughput (RUs) when auto-scale is not used. | _unset_ |
| `COSMOSDB_USE_DEFAULT_CREDENTIAL` | Set to `true` to force `DefaultAzureCredential` even when a key is present. | `false` |

When no explicit thread exists for a conversation the agent starts a new one; otherwise the serialized thread is rehydrated so subsequent turns remain in context for that Teams chat. Threads are always persisted to both Bot Framework conversation state and Cosmos DB so history survives bot restarts and multi-instance deployments.

### Using Entra ID (AAD) instead of keys

If your Cosmos account disables local authentication, leave `COSMOSDB_KEY` empty and set `COSMOSDB_USE_DEFAULT_CREDENTIAL=true`. Make sure the hosting environment can obtain an Entra token (Managed Identity, Azure CLI login, Visual Studio Code sign-in, or service principal variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`). Grant that identity the **Cosmos DB Built-in Data Contributor** role (or a custom role with read/write rights) on the Cosmos account so the bot can create the database/container and upsert thread items.

## Microsoft Graph API

This sample demonstrates using Azure Active Directory v2 as the OAuth2 provider and utilizes the Microsoft Graph API.
Microsoft Graph is a Microsoft developer platform that connects multiple services and devices. Initially released in 2015,
the Microsoft Graph builds on Office 365 APIs and allows developers to integrate their services with Microsoft products including Windows, Office 365, and Azure.

## Deploy the bot to Azure

To learn more about deploying a bot to Azure, see [Deploy your bot to Azure](https://aka.ms/azuredeployment) for a complete list of deployment instructions.

## GraphError 404: ResourceNotFound, Resource could not be discovered

This error may confusingly present itself if either of the following are true:

- You're using an email ending in `@microsoft.com`, and/or
- Your OAuth AAD tenant is `microsoft.onmicrosoft.com`.

## Further reading

- [Bot Framework Documentation](https://docs.botframework.com)
- [Bot Basics](https://docs.microsoft.com/azure/bot-service/bot-builder-basics?view=azure-bot-service-4.0)
- [Microsoft Graph API](https://developer.microsoft.com/en-us/graph)
- [MS Graph Docs](https://developer.microsoft.com/en-us/graph/docs/concepts/overview) and [SDK](https://github.com/microsoftgraph/msgraph-sdk-dotnet)
- [Activity processing](https://docs.microsoft.com/en-us/azure/bot-service/bot-builder-concept-activity-processing?view=azure-bot-service-4.0)
- [Azure Bot Service Introduction](https://docs.microsoft.com/azure/bot-service/bot-service-overview-introduction?view=azure-bot-service-4.0)
- [Azure Bot Service Documentation](https://docs.microsoft.com/azure/bot-service/?view=azure-bot-service-4.0)
- [Azure CLI](https://docs.microsoft.com/cli/azure/?view=azure-cli-latest)
- [Azure Portal](https://portal.azure.com)
- [Language Understanding using LUIS](https://docs.microsoft.com/en-us/azure/cognitive-services/luis/)
- [Channels and Bot Connector Service](https://docs.microsoft.com/en-us/azure/bot-service/bot-concepts?view=azure-bot-service-4.0)
