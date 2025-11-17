@description('Azure region for deployment.')
param location string

@description('Base name for Cosmos DB resources')
param resourceBaseName string

@description('Environment name for tagging')
param tags object = {}

@description('Cosmos DB database name')
param databaseName string = 'botdb'

@description('Container names and partition keys')
param containers array = [
  {
    name: 'conversations'
    partitionKey: '/userId'
    defaultTtl: -1
  }
  {
    name: 'botstate'
    partitionKey: '/conversationId'
    defaultTtl: -1
  }
]

// Cosmos DB Account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: toLower('cosmos-${resourceBaseName}')
  location: location
  kind: 'GlobalDocumentDB'
  tags: tags
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
      maxIntervalInSeconds: 5
      maxStalenessPrefix: 100
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    backupPolicy: {
      type: 'Periodic'
      periodicModeProperties: {
        backupIntervalInMinutes: 240
        backupRetentionIntervalInHours: 8
        backupStorageRedundancy: 'Local'
      }
    }
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    isVirtualNetworkFilterEnabled: false
    publicNetworkAccess: 'Enabled'
    disableKeyBasedMetadataWriteAccess: false
    enableFreeTier: false
  }
}

// Cosmos DB SQL Database
resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// Cosmos DB Containers
resource container 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = [for item in containers: {
  parent: database
  name: item.name
  properties: {
    resource: {
      id: item.name
      partitionKey: {
        paths: [
          item.partitionKey
        ]
        kind: 'Hash'
      }
      defaultTtl: item.defaultTtl
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'
          }
        ]
      }
    }
  }
}]

// Outputs
output cosmosAccountName string = cosmosAccount.name
output cosmosAccountId string = cosmosAccount.id
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output cosmosDatabaseName string = database.name
