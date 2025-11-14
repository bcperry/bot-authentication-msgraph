targetScope = 'subscription'

@maxLength(20)
@minLength(4)
@description('Used to generate names for all resources in this file')
param resourceBaseName string

@description('Required when create Azure Bot service')
param botAadAppClientId string

@secure()
@description('Required when create Azure Bot service')
param botAadAppClientSecret string

@minLength(36)
@maxLength(36)
@description('Tenant that owns the Bot AAD app')
param botAadAppTenantId string

@maxLength(42)
param botDisplayName string

@description('Azure Developer environment name.')
param environmentName string

@description('Azure region for deployment.')
@metadata({
  azd: {
    type: 'location'
  }
})
param location string

param botServiceSku string = 'F0'

@description('App Service SKU')
param appServicePlanSku string = 'B1'

@description('Use existing OpenAI resources')
param useExistingOpenAIResources bool = false

@description('Openai Tokens per minute limit (only used when creating new OpenAI resources)')
param openAiTokensPerMinute int = 10

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
var botServiceName = '${resourceBaseName}-${randomSuffix}'
var appServiceDomainSuffix = environment().suffixes.storage == 'core.usgovcloudapi.net' ? 'azurewebsites.us' : 'azurewebsites.net'
var botAppDomain = '${appServiceName}.${appServiceDomainSuffix}'

// Resource Group
resource resourceGroup 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: resourceGroupName
  location: location
  tags: {
    'azd-env-name': environmentName
  }
}

// Deploy new AI services only if NOT using existing resources
module aiServices 'ai_services/resources.bicep' = if (!useExistingOpenAIResources) {
  name: 'ai-services-deployment'
  scope: resourceGroup
  params: {
    location: location
    resourceToken: toLower(uniqueString(resourceGroup.id))
    resourcePrefix: resourceBaseName
    tags: {
      'azd-env-name': environmentName
    }
    openAIModelName: !empty(azureOpenAiModel) ? azureOpenAiModel : 'gpt-4o'
    openAIAPIVersion: '2024-10-01'
    openAITPMCapacity: openAiTokensPerMinute
  }
}

module app_services 'app_services/resources.bicep' = {
  name: 'app-services-deployment'
  scope: resourceGroup
  params: {
    location: location
    resourceBaseName: resourceBaseName
    appServicePlanName: appServicePlanName
    appServicePlanSku: appServicePlanSku
    appServiceName: appServiceName
    azureOpenAiApiKey: aiServices.outputs.azureOpenAiApiKey != '' ? aiServices.outputs.azureOpenAiApiKey : azureOpenAiApiKey
    azureOpenAiEndpoint: aiServices.outputs.azureOpenAiEndpoint != '' ? aiServices.outputs.azureOpenAiEndpoint : azureOpenAiEndpoint
    azureOpenAiModel: aiServices.outputs.azureOpenAiModel != '' ? aiServices.outputs.azureOpenAiModel :  azureOpenAiModel
    botAadAppClientId: botAadAppClientId
    botAadAppTenantId: botAadAppTenantId
    botAadAppClientSecret: botAadAppClientSecret
    cloudLocation: cloudLocation

  }
}

// Deploy resources into the resource group
module resources 'bot_services/resources.bicep' = {
  name: 'resources-deployment'
  scope: resourceGroup
  params: {
    botAadAppClientId: botAadAppClientId
    botAadAppTenantId: botAadAppTenantId
    botServiceName: botServiceName
    botServiceSku: botServiceSku
    botDisplayName: botDisplayName
    botAppDomain: botAppDomain
  }
}

// Outputs
output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = resourceGroupName
output APP_SERVICE_NAME string = appServiceName
output BOT_DOMAIN string = botAppDomain
output BOT_ENDPOINT string = 'https://${botAppDomain}/api/messages'
output MicrosoftAppId string = botAadAppClientId
output MicrosoftAppType string = 'SingleTenant'
output graphUserScopes string = 'User.Read'
output MicrosoftAppTenantId string = botAadAppTenantId
output MicrosoftAppPassword string = botAadAppClientSecret
