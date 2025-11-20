targetScope = 'resourceGroup'

@description('Location for the AI Foundry account and project')
param location string

@description('Tags to stamp on all AI Foundry resources')
param tags object

@description('Name of the AI Foundry (Cognitive Services) account')
param aiFoundryAccountName string

@description('Name of the Foundry project to create')
param aiProjectName string

@description('Name of the model deployment to create')
param openAIModelName string

@description('Requested tokens-per-minute (TPM) capacity for the model deployment')
param openAITPMCapacity int

@description('Set to true to block key-based auth on the Foundry account')
param disableLocalAuth bool = false

resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: aiFoundryAccountName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  properties: {
    allowProjectManagement: true
    customSubDomainName: aiFoundryAccountName
    disableLocalAuth: disableLocalAuth
  }
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  name: aiProjectName
  parent: aiFoundry
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  name: openAIModelName
  parent: aiFoundry
  sku: {
    name: 'GlobalStandard'
    capacity: openAITPMCapacity
  }
  properties: {
    model: {
      name: openAIModelName
      format: 'OpenAI'
    }
  }
}

@secure()
output azureOpenAiApiKey string = disableLocalAuth ? '' : listKeys(aiFoundry.id, '2024-10-01').key1
output azureOpenAiEndpoint string = aiFoundry.properties.endpoint
output azureOpenAiModel string = modelDeployment.name
output aiFoundryAccountName string = aiFoundry.name
output aiFoundryProjectId string = aiProject.id
