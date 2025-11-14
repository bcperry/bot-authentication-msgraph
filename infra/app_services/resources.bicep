@description('Location for all resources')
param location string

@description('Base name for resources')
param resourceBaseName string

@description('App Service Plan name')
param appServicePlanName string

@description('App Service Plan SKU')
param appServicePlanSku string

@description('App Service name')
param appServiceName string


@description('Bot Azure AD App Client ID')
@minLength(36)
@maxLength(36)
param botAadAppClientId string

@secure()
@description('Bot Azure AD App Client Secret')
param botAadAppClientSecret string

@description('Bot Azure AD App Tenant ID')
@minLength(36)
@maxLength(36)
param botAadAppTenantId string

@secure()
@description('Azure OpenAI API Key')
param azureOpenAiApiKey string

@description('Azure OpenAI Endpoint')
param azureOpenAiEndpoint string

@description('Azure OpenAI Model Deployment Name')
param azureOpenAiModel string

var normalizedPlanSku = toUpper(appServicePlanSku)
var standardPlanSkus = [
  'S1'
  'S2'
  'S3'
]
var premiumV2PlanSkus = [
  'P1V2'
  'P2V2'
  'P3V2'
]

@allowed(['AzureCloud', 'AzureUSGovernment'])
@description('Cloud Deployment Location')
param cloudLocation string

// App Service Plan
resource appServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: appServicePlanSku
    tier: contains(standardPlanSkus, normalizedPlanSku) ? 'Standard' : contains(premiumV2PlanSkus, normalizedPlanSku) ? 'PremiumV2' : 'Basic'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

// App Service
resource appService 'Microsoft.Web/sites@2022-03-01' = {
  name: appServiceName
  location: location
  kind: 'app,linux'
  tags: {
    'azd-service-name': 'api'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appCommandLine: 'python -m uvicorn app:app --host 0.0.0.0 --port 8000'
      appSettings: [
        {
          name: 'MicrosoftAppId'
          value: botAadAppClientId
        }
        {
          name: 'MicrosoftAppPassword'
          value: botAadAppClientSecret
        }
        {
          name: 'MicrosoftAppType'
          value: 'SingleTenant'
        }
        {name: 'graphUserScopes'
          value: 'User.Read'
        }
        {
          name: 'MicrosoftAppTenantId'
          value: botAadAppTenantId
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {name: 'CLOUD_LOCATION'
          value: cloudLocation
        }
        {
          name: 'WEBSITE_HTTPLOGGING_RETENTION_DAYS'
          value: '7'
        }
        {
          name: 'WEBSITE_ENABLE_CONTAINER_LOGGING'
          value: '1'
        }
        {
          name: 'CHANNEL_SERVICE'
          value: 'https://botframework.azure.us'
        }
        {
          name: 'OAUTH_URL'
          value: 'https://tokengcch.botframework.azure.us/'
        }
        {
          name: 'TO_CHANNEL_FROM_BOT_LOGIN_URL'
          value: 'https://login.microsoftonline.us/MicrosoftServices.onmicrosoft.us'
        }
        {
          name: 'TO_CHANNEL_FROM_BOT_OAUTH_SCOPE'
          value: 'https://api.botframework.us'
        }
        {
          name: 'TO_BOT_FROM_CHANNEL_TOKEN_ISSUER'
          value: 'https://api.botframework.us'
        }
        {
          name: 'TO_BOT_FROM_CHANNEL_OPENID_METADATA_URL'
          value: 'https://login.botframework.azure.us/v1/.well-known/openidconfiguration'
        }
        {
          name: 'TO_BOT_FROM_EMULATOR_OPENID_METADATA_URL'
          value: 'https://login.microsoftonline.us/cab8a31a-1906-4287-a0d8-4eef66b95f6e/v2.0/.well-known/openid-configuration'
        }
        {
          name: 'VALIDATE_AUTHORITY'
          value: 'true'
        }
        {
          name: 'AZURE_OPENAI_API_KEY'
          value: azureOpenAiApiKey
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: azureOpenAiEndpoint
        }
        {
          name: 'AZURE_OPENAI_MODEL'
          value: azureOpenAiModel
        }
      ]
    }
  }
}

resource appServiceLogs 'Microsoft.Web/sites/config@2022-03-01' = {
  name: 'logs'
  parent: appService
  properties: {
    applicationLogs: {
      fileSystem: {
        level: 'Information'
      }
    }
    httpLogs: {
      fileSystem: {
        enabled: true
        retentionInDays: 7
        retentionInMb: 100
      }
    }
  }
}

// Outputs
output appServicePlanId string = appServicePlan.id
output appServiceId string = appService.id
output appServiceName string = appService.name
output appServiceHostName string = appService.properties.defaultHostName
