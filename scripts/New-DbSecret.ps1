$ErrorActionPreference = 'Stop'
$passwordSecure = Read-Host 'Enter a database password' -AsSecureString
$password = [System.Net.NetworkCredential]::new('', $passwordSecure).Password
if ([string]::IsNullOrWhiteSpace($password)) { throw 'Password cannot be empty.' }
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($password))
$content = @"
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
  namespace: usermgmt-02230130
type: Opaque
data:
  POSTGRES_DB: dXNlcm1nbXQ=
  POSTGRES_USER: dXNlcm1nbXQ=
  POSTGRES_PASSWORD: $encoded
  DB_NAME: dXNlcm1nbXQ=
  DB_USER: dXNlcm1nbXQ=
  DB_PASSWORD: $encoded
"@
$path = Join-Path $PSScriptRoot '..\k8s\02-db-secret.yaml'
Set-Content -Path $path -Value $content -Encoding ascii
Write-Host "Wrote Secret manifest to $((Resolve-Path $path).Path). It is git-ignored."
