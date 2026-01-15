param(
  [Parameter(Mandatory)] [string] $TenantId,
  [Parameter(Mandatory)] [string] $ClientId,
  [Parameter(Mandatory)] [string] $ClientSecret,
  [Parameter(Mandatory)] [string] $PolicyName,
  [Parameter(Mandatory)] [string] $OutFile
)

$ErrorActionPreference = "Stop"

Install-Module Microsoft.Graph -Scope CurrentUser -Force -AllowClobber | Out-Null
Import-Module Microsoft.Graph.Authentication
Import-Module Microsoft.Graph.DeviceManagement

# App-only auth
$sec = ConvertTo-SecureString $ClientSecret -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential($ClientId, $sec)
Connect-MgGraph -TenantId $TenantId -ClientSecretCredential $cred -NoWelcome

Select-MgProfile beta

# Settings catalog policies live here:
# GET /deviceManagement/configurationPolicies
$policies = Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/beta/deviceManagement/configurationPolicies?`$filter=name eq '$PolicyName'"

if (-not $policies.value -or $policies.value.Count -eq 0) {
  throw "Policy not found: $PolicyName"
}

$policyId = $policies.value[0].id

# Expand settings so you capture all config values
$policy = Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/beta/deviceManagement/configurationPolicies/$policyId?`$expand=settings"

$policy | ConvertTo-Json -Depth 50 | Out-File -FilePath $OutFile -Encoding utf8
Write-Host "Exported policy to: $OutFile"

pwsh ./scripts/Export-SettingsCatalogPolicy.ps1 `
  -TenantId $TENANT_ID `
  -ClientId $CLIENT_ID `
  -ClientSecret $CLIENT_SECRET `
  -PolicyName "Edge - Tampermonkey Managed Config (20260114-104629)" `
  -OutFile "./policies/edge-tampermonkey-managed-config.json"

param(
  [Parameter(Mandatory)] [string] $TenantId,
  [Parameter(Mandatory)] [string] $ClientId,
  [Parameter(Mandatory)] [string] $ClientSecret,
  [Parameter(Mandatory)] [string] $PolicyJsonPath
)

$ErrorActionPreference = "Stop"

Install-Module Microsoft.Graph -Scope CurrentUser -Force -AllowClobber | Out-Null
Import-Module Microsoft.Graph.Authentication

$sec = ConvertTo-SecureString $ClientSecret -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential($ClientId, $sec)
Connect-MgGraph -TenantId $TenantId -ClientSecretCredential $cred -NoWelcome
Select-MgProfile beta

$desired = Get-Content $PolicyJsonPath -Raw | ConvertFrom-Json
$desiredName = $desired.name

# Remove server-managed fields if present
$desired.PSObject.Properties.Remove("id") | Out-Null
$desired.PSObject.Properties.Remove("createdDateTime") | Out-Null
$desired.PSObject.Properties.Remove("lastModifiedDateTime") | Out-Null
$desired.PSObject.Properties.Remove("version") | Out-Null

# Check if exists
$existing = Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/beta/deviceManagement/configurationPolicies?`$filter=name eq '$desiredName'"

if (-not $existing.value -or $existing.value.Count -eq 0) {
  Write-Host "Policy not found. Creating: $desiredName"

  $body = $desired | ConvertTo-Json -Depth 50
  $created = Invoke-MgGraphRequest -Method POST `
    -Uri "https://graph.microsoft.com/beta/deviceManagement/configurationPolicies" `
    -Body $body `
    -ContentType "application/json"

  Write-Host "Created policy id: $($created.id)"
}
else {
  $policyId = $existing.value[0].id
  Write-Host "Policy exists ($policyId). Updating: $desiredName"

  # PATCH base policy
  $base = $desired | Select-Object name,description,platforms,technologies,roleScopeTagIds
  $baseBody = $base | ConvertTo-Json -Depth 20
  Invoke-MgGraphRequest -Method PATCH `
    -Uri "https://graph.microsoft.com/beta/deviceManagement/configurationPolicies/$policyId" `
    -Body $baseBody `
    -ContentType "application/json" | Out-Null

  # Replace settings (simple & reliable approach)
  # 1) Get existing settings
  $current = Invoke-MgGraphRequest -Method GET `
    -Uri "https://graph.microsoft.com/beta/deviceManagement/configurationPolicies/$policyId?`$expand=settings"

  # 2) Delete each existing setting instance
  foreach ($s in ($current.settings | ForEach-Object { $_ })) {
    if ($s.id) {
      Invoke-MgGraphRequest -Method DELETE `
        -Uri "https://graph.microsoft.com/beta/deviceManagement/configurationPolicies/$policyId/settings/$($s.id)" | Out-Null
    }
  }

  # 3) Add desired settings back
  foreach ($s in ($desired.settings | ForEach-Object { $_ })) {
    $s.PSObject.Properties.Remove("id") | Out-Null
    $sBody = $s | ConvertTo-Json -Depth 50
    Invoke-MgGraphRequest -Method POST `
      -Uri "https://graph.microsoft.com/beta/deviceManagement/configurationPolicies/$policyId/settings" `
      -Body $sBody `
      -ContentType "application/json" | Out-Null
  }

  Write-Host "Updated policy + settings."
}

Disconnect-MgGraph | Out-Null
