@description('Cosmos DB account name')
param cosmosAccountName string

@description('Principal ID of the managed identity to grant Cosmos DB access')
param appServicePrincipalId string

// Reference to existing Cosmos DB account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
}

// Cosmos DB Built-in Data Contributor Role Definition ID
// This is the Cosmos DB Data Contributor role (00000000-0000-0000-0000-000000000002)
var cosmosDbDataContributorRoleId = '00000000-0000-0000-0000-000000000002'

// Grant App Service Managed Identity access to Cosmos DB
resource cosmosDbRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  name: guid(cosmosAccount.id, appServicePrincipalId, cosmosDbDataContributorRoleId)
  parent: cosmosAccount
  properties: {
    roleDefinitionId: '/${subscription().id}/resourceGroups/${resourceGroup().name}/providers/Microsoft.DocumentDB/databaseAccounts/${cosmosAccount.name}/sqlRoleDefinitions/${cosmosDbDataContributorRoleId}'
    principalId: appServicePrincipalId
    scope: cosmosAccount.id
  }
}
