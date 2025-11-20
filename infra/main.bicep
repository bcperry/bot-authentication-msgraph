targetScope = 'subscription'

@maxLength(20)
@minLength(4)
@description('Azure Developer environment name.')
param environmentName string

@description('Azure region for deployment.')
@metadata({
  azd: {
    type: 'location'
  }
})
param location string

@description('AKA: Application (client) ID.  Required when create Azure Bot service')
param botAadAppClientId string

@minLength(36)
@maxLength(36)
@description('AKA: Directory (tenant) ID. Tenant that owns the Bot AAD app')
param botAadAppTenantId string

@secure()
@description('AKA: Client Secret. Required when create Azure Bot service')
param botAadAppClientSecret string

@maxLength(42)
param botDisplayName string = 'teams-bot-${environmentName}'

param botServiceSku string = 'F0'

@description('App Service SKU')
param appServicePlanSku string = 'B1'

@description('Use existing OpenAI resources')
param useExistingOpenAIResources bool = false

@description('Openai Tokens per minute limit (only used when creating new OpenAI resources)')
param openAiTokensPerMinute int = 60

@secure()
@description('Azure OpenAI API Key (required only if using existing resources)')
param azureOpenAiApiKey string = ''

@description('Azure OpenAI Endpoint (required only if using existing resources)')
param azureOpenAiEndpoint string = ''

@description('Azure OpenAI Model Deployment Name (required only if using existing resources)')
param azureOpenAiModel string = ''

@allowed(['AzureCloud', 'AzureUSGovernment'])
@description('Cloud Deployment Location')
param cloudLocation string

// Variables
var randomSuffix = uniqueString(subscription().subscriptionId, environmentName)
var resourceGroupName = 'rg-${environmentName}'
var appServicePlanName = 'plan-${environmentName}'
var appServiceName = 'app-${environmentName}-${randomSuffix}'
var botServiceName = '${environmentName}-${randomSuffix}'
var appServiceDomainSuffix = environment().suffixes.storage == 'core.usgovcloudapi.net' ? 'azurewebsites.us' : 'azurewebsites.net'
var botAppDomain = '${appServiceName}.${appServiceDomainSuffix}'
var aiFoundryAccountName = '${environmentName}-foundry-${randomSuffix}'
var aiFoundryProjectName = '${environmentName}-proj'
var azureOpenAiEndpointValue = useExistingOpenAIResources ? azureOpenAiEndpoint : aiFoundry!.outputs.azureOpenAiEndpoint
var azureOpenAiModelValue = useExistingOpenAIResources ? azureOpenAiModel : aiFoundry!.outputs.azureOpenAiModel

// Resource Group
resource resourceGroup 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: {
    'azd-env-name': environmentName
  }
}

// Deploy AI Foundry resources only when new infrastructure is requested
module aiFoundry 'ai_foundry/resources.bicep' = if (!useExistingOpenAIResources) {
  name: 'ai-foundry-deployment'
  scope: resourceGroup
  params: {
    location: location
    aiFoundryAccountName: aiFoundryAccountName
    aiProjectName: aiFoundryProjectName
    tags: {
      'azd-env-name': environmentName
    }
    openAIModelName: !empty(azureOpenAiModel) ? azureOpenAiModel : 'gpt-4o'
    openAITPMCapacity: openAiTokensPerMinute
  }
}

// Deploy Cosmos DB
module cosmosDb 'cosmosdb/resources.bicep' = {
  name: 'cosmosdb-deployment'
  scope: resourceGroup
  params: {
    location: location
    resourceBaseName: environmentName
    tags: {
      'azd-env-name': environmentName
    }
    databaseName: 'botdb'
  }
}

module app_services 'app_services/resources.bicep' = {
  name: 'app-services-deployment'
  scope: resourceGroup
  params: {
    location: location
    appServicePlanName: appServicePlanName
    appServicePlanSku: appServicePlanSku
    appServiceName: appServiceName
    azureOpenAiApiKey: azureOpenAiApiKey
    azureOpenAiEndpoint: azureOpenAiEndpointValue
    azureOpenAiModel: azureOpenAiModelValue
    useExistingOpenAIResources: useExistingOpenAIResources
    aiFoundryAccountName: aiFoundryAccountName
    botAadAppClientId: botAadAppClientId
    botAadAppTenantId: botAadAppTenantId
    botAadAppClientSecret: botAadAppClientSecret
    cloudLocation: cloudLocation
    cosmosEndpoint: cosmosDb.outputs.cosmosEndpoint
    cosmosDatabaseName: cosmosDb.outputs.cosmosDatabaseName
    cosmosAccountName: cosmosDb.outputs.cosmosAccountName
    oauthConnectionName: 'graph-connection'
  }
}

// Deploy resources into the resource group
module resources 'bot_services/resources.bicep' = {
  name: 'resources-deployment'
  scope: resourceGroup
  params: {
    botAadAppClientId: botAadAppClientId
    botAadAppTenantId: botAadAppTenantId
    botAadAppClientSecret: botAadAppClientSecret
    botServiceName: botServiceName
    botServiceSku: botServiceSku
    botDisplayName: botDisplayName
    botAppDomain: botAppDomain
    oauthConnectionName: 'graph-connection'
    graphScopes: 'User.Read'
  }
}

// Grant App Service Managed Identity access to Cosmos DB
module cosmosDbRoleAssignment 'cosmosdb/role_assignment.bicep' = {
  name: 'cosmosdb-role-assignment'
  scope: resourceGroup
  params: {
    cosmosAccountName: cosmosDb.outputs.cosmosAccountName
    appServicePrincipalId: app_services.outputs.appServicePrincipalId
  }
}

// // Outputs
output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = resourceGroupName
output APP_SERVICE_NAME string = appServiceName
output BOT_DOMAIN string = botAppDomain
output BOT_ENDPOINT string = 'https://${botAppDomain}/api/messages'
output MicrosoftAppId string = botAadAppClientId
output MicrosoftAppType string = 'SingleTenant'
output graphUserScopes string = 'User.Read'
output MicrosoftAppTenantId string = botAadAppTenantId
output ConnectionName string = resources.outputs.oauthConnectionName
output COSMOS_ENDPOINT string = cosmosDb.outputs.cosmosEndpoint
output COSMOS_DATABASE_NAME string = cosmosDb.outputs.cosmosDatabaseName
output COSMOS_ACCOUNT_NAME string = cosmosDb.outputs.cosmosAccountName
output AZURE_OPENAI_CHAT_DEPLOYMENT_NAME string = azureOpenAiModelValue
output AZURE_OPENAI_ENDPOINT string = azureOpenAiEndpointValue
@secure()
output AZURE_OPENAI_MODEL string = azureOpenAiModelValue
output AZURE_AI_FOUNDRY_ACCOUNT string = useExistingOpenAIResources ? '' : aiFoundryAccountName
output AZURE_AI_FOUNDRY_PROJECT string = useExistingOpenAIResources ? '' : aiFoundryProjectName
