# Azure Cosmos DB Infrastructure

This module deploys an Azure Cosmos DB account configured for bot conversation storage.

## Features

- **Serverless Cosmos DB**: Cost-effective serverless configuration for variable workloads
- **Session Consistency**: Balanced consistency for bot conversations
- **Two Default Containers**:
  - `conversations`: Stores conversation history (partitioned by `/userId`)
  - `botstate`: Stores bot state data (partitioned by `/conversationId`)
- **Automatic Backups**: Periodic backups every 4 hours with 8-hour retention

## Deployed Resources

- Azure Cosmos DB Account (Serverless)
- SQL Database: `botdb`
- Containers with optimized partition keys

## Configuration

### Default Containers

The module creates two containers by default:

1. **conversations**
   - Partition Key: `/userId`
   - Use Case: Store chat history per user
   - TTL: Disabled (data retained indefinitely)

2. **botstate**
   - Partition Key: `/conversationId`
   - Use Case: Store conversation state
   - TTL: Disabled

### Customization

To add or modify containers, update the `containers` parameter in `main.bicep`:

```bicep
containers: [
  {
    name: 'mycontainer'
    partitionKey: '/myPartitionKey'
    defaultTtl: 86400  // 1 day in seconds, or -1 for no expiry
  }
]
```

## Accessing Cosmos DB from Python

The App Service receives these environment variables:

- `COSMOS_ENDPOINT`: The Cosmos DB endpoint URL
- `COSMOS_DATABASE_NAME`: The database name
- `COSMOS_ACCOUNT_NAME`: The account name

### Authentication

Use Azure Managed Identity (recommended) or connection keys:

```python
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
import os

# Using Managed Identity (recommended)
credential = DefaultAzureCredential()
client = CosmosClient(
    url=os.environ['COSMOS_ENDPOINT'],
    credential=credential
)

# Or using connection string from Key Vault
# See grant-cosmos-access.ps1 for setting up RBAC permissions
```

## Best Practices

1. **Partition Key Selection**: Choose keys with high cardinality (many unique values)
2. **Data Modeling**: Embed related data accessed together to minimize cross-partition queries
3. **Monitoring**: Use Azure Monitor to track RU consumption
4. **Security**: Use Managed Identity instead of connection keys when possible

## Cost Optimization

- **Serverless Mode**: Only pay for Request Units (RUs) consumed
- **No minimum charge**: Ideal for development and variable workloads
- **TTL Configuration**: Set Time-To-Live to automatically delete old data

## Next Steps

1. Run the deployment: `azd provision`
2. Configure RBAC access using the included `grant-cosmos-access.ps1` script
3. Update your Python code to connect to Cosmos DB
4. Monitor usage in Azure Portal

## References

- [Cosmos DB Best Practices](https://learn.microsoft.com/azure/cosmos-db/nosql/best-practice-dotnet)
- [Partition Key Strategies](https://learn.microsoft.com/azure/cosmos-db/partitioning-overview)
- [Serverless Mode](https://learn.microsoft.com/azure/cosmos-db/serverless)
