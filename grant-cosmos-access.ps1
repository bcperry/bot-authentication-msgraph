# Grant Cosmos DB Data Plane RBAC to Managed Identity
# This script assigns the "Cosmos DB Built-in Data Contributor" role to a principal
# so it can read/write data in the Cosmos DB account without using account keys.

param(
    [string]$ResourceGroup,
    [string]$AccountName,
    [string]$PrincipalId = "85848966-c836-49bc-b39c-495fbe1730ff",
    [string]$Scope = "/"
)

# Load environment variables from .azure/auth-bot/.env
$envFile = Join-Path $PSScriptRoot ".azure" "auth-bot" ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*)\s*=\s*"?([^"]*)"?\s*$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            Set-Variable -Name $key -Value $value -Scope Script
        }
    }
    Write-Host "Loaded environment from: $envFile" -ForegroundColor Gray
} else {
    Write-Error "Environment file not found: $envFile"
    exit 1
}

# Use environment variables if parameters not provided
if (-not $ResourceGroup) {
    $ResourceGroup = $AZURE_RESOURCE_GROUP
}
if (-not $AccountName) {
    $AccountName = $COSMOS_ACCOUNT_NAME
}

Write-Host "Granting Cosmos DB data plane access..." -ForegroundColor Cyan
Write-Host "  Account: $AccountName" -ForegroundColor Gray
Write-Host "  Resource Group: $ResourceGroup" -ForegroundColor Gray
Write-Host "  Principal ID: $PrincipalId" -ForegroundColor Gray
Write-Host "  Scope: $Scope" -ForegroundColor Gray
Write-Host ""

# Step 1: Get or create the custom role definition
Write-Host "[1/4] Checking for custom role 'Cosmos DB Data and Schema Manager'..." -ForegroundColor Yellow
$roleDefId = az cosmosdb sql role definition list `
    --account-name $AccountName `
    --resource-group $ResourceGroup `
    --query "[?roleName=='Cosmos DB Data and Schema Manager'].id" `
    --output tsv

if (-not $roleDefId) {
    Write-Host "  Custom role not found. Creating from cosmosdb-role.json..." -ForegroundColor Yellow
    
    # Create the custom role definition
    $roleDef = az cosmosdb sql role definition create `
        --account-name $AccountName `
        --resource-group $ResourceGroup `
        --body @cosmosdb-role.json `
        --output json | ConvertFrom-Json
    
    $roleDefId = $roleDef.id
    
    if (-not $roleDefId) {
        Write-Error "Failed to create custom role definition."
        exit 1
    }
    
    Write-Host "  ✓ Custom role created: $roleDefId" -ForegroundColor Green
} else {
    Write-Host "  ✓ Custom role found" -ForegroundColor Green
}

Write-Host "  Role Definition ID: $roleDefId" -ForegroundColor Green
Write-Host ""

# Step 2: Create the role assignment
Write-Host "[2/4] Creating role assignment..." -ForegroundColor Yellow
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
Write-Host "[3/4] Verifying role assignment..." -ForegroundColor Yellow
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

# Step 4: List all current permissions for verification
Write-Host "[4/4] Listing all role assignments for this principal..." -ForegroundColor Yellow
$allAssignments = az cosmosdb sql role assignment list `
    --account-name $AccountName `
    --resource-group $ResourceGroup `
    --query "[?principalId=='$PrincipalId']" `
    --output json | ConvertFrom-Json

if ($allAssignments) {
    Write-Host "  ✓ Principal has $($allAssignments.Count) role assignment(s):" -ForegroundColor Green
    $allAssignments | ForEach-Object {
        $roleName = (az cosmosdb sql role definition show --account-name $AccountName --resource-group $ResourceGroup --id $_.roleDefinitionId --query "roleName" --output tsv)
        Write-Host "    - Role: $roleName" -ForegroundColor Gray
        Write-Host "      Scope: $($_.scope)" -ForegroundColor Gray
    }
} else {
    Write-Warning "No role assignments found. This is unexpected."
}

Write-Host ""
Write-Host "✓ Done! Wait 1-2 minutes for RBAC propagation, then restart your application." -ForegroundColor Cyan
Write-Host "  The identity can now authenticate to Cosmos DB using DefaultAzureCredential." -ForegroundColor Gray
