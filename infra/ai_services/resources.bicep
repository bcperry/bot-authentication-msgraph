targetScope = 'resourceGroup'

// Parameters
@minLength(1)
@description('Primary location for all resources')
param location string

@description('Resource token for unique naming')
param resourceToken string

@description('Resource prefix for naming')
param resourcePrefix string

@description('Tags for all resources')
param tags object

@description('Name of the OpenAI model to deploy')
param openAIModelName string

@description('API version for OpenAI service')
param openAIAPIVersion string 

@description('Azure OpenAI TPM Capacity')
param openAITPMCapacity int = 10


// Azure OpenAI Service
resource cognitiveServices 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: '${resourcePrefix}-openai-${resourceToken}'
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: '${resourcePrefix}-openai-${resourceToken}'
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

// OpenAI Model Deployment
resource openAIModelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: cognitiveServices
  name: openAIModelName
  properties: {
    model: {
      format: 'OpenAI'
      name: openAIModelName
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    currentCapacity: openAITPMCapacity

  }
  sku: {
    name: 'Standard'
    capacity: openAITPMCapacity
  }
}

// Outputs
output azureOpenAiApiKey string = listKeys(cognitiveServices.id, openAIAPIVersion).key1
output azureOpenAiEndpoint string = cognitiveServices.properties.endpoint
output azureOpenAiModel string = openAIModelDeployment.name
