# Grant Cosmos DB Data Plane RBAC to Managed Identity
# This script assigns the "Cosmos DB Built-in Data Contributor" role to a principal
# so it can read/write data in the Cosmos DB account without using account keys.

param(
    [string]$ResourceGroup = "rg-commercial",
    [string]$AccountName = "bot-demo",
    [string]$PrincipalId = "85848966-c836-49bc-b39c-495fbe1730ff",
    [string]$Scope = "/"
)

Write-Host "Granting Cosmos DB data plane access..." -ForegroundColor Cyan
Write-Host "  Account: $AccountName" -ForegroundColor Gray
Write-Host "  Resource Group: $ResourceGroup" -ForegroundColor Gray
Write-Host "  Principal ID: $PrincipalId" -ForegroundColor Gray
Write-Host "  Scope: $Scope" -ForegroundColor Gray
Write-Host ""

# Step 1: Get the built-in Data Contributor role definition ID
Write-Host "[1/3] Fetching role definition for 'Cosmos DB Built-in Data Contributor'..." -ForegroundColor Yellow
$roleDefId = az cosmosdb sql role definition list `
    --account-name $AccountName `
    --resource-group $ResourceGroup `
    --query "[?roleName=='Cosmos DB Built-in Data Contributor'].id" `
    --output tsv

if (-not $roleDefId) {
    Write-Error "Failed to find 'Cosmos DB Built-in Data Contributor' role definition."
    exit 1
}

Write-Host "  Role Definition ID: $roleDefId" -ForegroundColor Green
Write-Host ""

# Step 2: Create the role assignment
Write-Host "[2/3] Creating role assignment..." -ForegroundColor Yellow
$assignment = az cosmosdb sql role assignment create `
    --account-name $AccountName `
    --resource-group $ResourceGroup `
    --role-definition-id $roleDefId `
    --scope $Scope `
    --principal-id $PrincipalId `
    --output json 2>&1

if ($LASTEXITCODE -ne 0) {
    # Check if it already exists
    if ($assignment -match "already exists") {
        Write-Host "  ✓ Role assignment already exists" -ForegroundColor Green
    } else {
        Write-Error "Failed to create role assignment: $assignment"
        exit 1
    }
} else {
    Write-Host "  ✓ Role assignment created successfully" -ForegroundColor Green
}
Write-Host ""

# Step 3: Verify the assignment
Write-Host "[3/3] Verifying role assignment..." -ForegroundColor Yellow
$verify = az cosmosdb sql role assignment list `
    --account-name $AccountName `
    --resource-group $ResourceGroup `
    --query "[?principalId=='$PrincipalId'].{id: id, roleDefinitionId: roleDefinitionId}" `
    --output json | ConvertFrom-Json

if ($verify) {
    Write-Host "  ✓ Verified: Principal has $($verify.Count) role assignment(s)" -ForegroundColor Green
    $verify | ForEach-Object {
        Write-Host "    - Assignment ID: $($_.id.Split('/')[-1])" -ForegroundColor Gray
    }
} else {
    Write-Warning "Could not verify role assignment. Check manually with 'az cosmosdb sql role assignment list'."
}

Write-Host ""
Write-Host "✓ Done! Wait 1-2 minutes for RBAC propagation, then restart your application." -ForegroundColor Cyan
Write-Host "  The identity can now authenticate to Cosmos DB using DefaultAzureCredential." -ForegroundColor Gray
