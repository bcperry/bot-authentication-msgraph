@description('Bot Service name')
param botServiceName string

@description('Bot Service SKU')
param botServiceSku string

@description('Bot Display Name')
param botDisplayName string

@description('Bot App Domain')
param botAppDomain string

@description('bot Azure AD App Client ID')
@minLength(36)
@maxLength(36)
param botAadAppClientId string

@description('bot Azure AD App Tenant ID')
@minLength(36)
@maxLength(36)
param botAadAppTenantId string

@secure()
@description('bot Azure AD App Client Secret')
param botAadAppClientSecret string

@description('OAuth Connection Name')
param oauthConnectionName string = 'graph-connection'

@description('Microsoft Graph Scopes')
param graphScopes string = 'User.Read'

// Register your web service as a bot with the Bot Framework
// NOTE: Bot Service creation may fail in Azure Government cloud
// If deployment fails, create the Bot Service manually in the portal
// or use: az bot create --name bot-service --resource-group rg-bot-service --kind azurebot --app-type SingleTenant --appid <your-app-id> --endpoint https://app-bot-service.azurewebsites.net/api/messages


resource botService 'Microsoft.BotService/botServices@2022-09-15' = {
  name: botServiceName
  location: 'global'
  sku: {
    name: botServiceSku
  }
  kind: 'azurebot'
  properties: {
    displayName: botDisplayName
    endpoint: 'https://${botAppDomain}/api/messages'
    msaAppType: 'SingleTenant'
    msaAppId: botAadAppClientId
    msaAppTenantId: botAadAppTenantId
    tenantId: botAadAppTenantId
  }
}

// Add Microsoft Teams channel
resource teamsChannel 'Microsoft.BotService/botServices/channels@2022-09-15' = {
  parent: botService
  name: 'MsTeamsChannel'
  location: 'global'
  properties: {
    channelName: 'MsTeamsChannel'
    properties: {
      enableCalling: false
      isEnabled: true
    }
  }
}

// Add OAuth connection for Microsoft Graph
resource oauthConnection 'Microsoft.BotService/botServices/connections@2022-09-15' = {
  parent: botService
  name: oauthConnectionName
  location: 'global'
  properties: {
    serviceProviderDisplayName: 'Azure Active Directory v2'
    serviceProviderId: '30dd229c-58e3-4a48-bdfd-91ec48eb906c'
    clientId: botAadAppClientId
    clientSecret: botAadAppClientSecret
    scopes: graphScopes
    parameters: [
      {
        key: 'tenantID'
        value: botAadAppTenantId
      }
    ]
  }
}

output botServiceId string = botService.id
output oauthConnectionName string = oauthConnection.name
