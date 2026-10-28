<#
  KnowledgeHub-Setup.ps1  -  deploy and validate the Windows side of The Knowledge Hub

  RUN ON : the domain controller (10.0.10.2), PowerShell as Administrator
  USAGE  : .\KnowledgeHub-Setup.ps1 -Action Deploy     builds the OUs and the staff GPO
           .\KnowledgeHub-Setup.ps1 -Action Test       checks everything, prints PASS/FAIL
           .\KnowledgeHub-Setup.ps1 -Action All        Deploy, then Test

  The staff GPO: maps drive Z:, forces Windows updates, blocks RegEdit.
  It only applies to the group staff-only (so admins are excluded).
  Safe to run more than once: things that already exist are skipped.
#>
param(
    [ValidateSet("Deploy", "Test", "All")][string]$Action = "All",
    [string]$GpoName    = "Staff Workstation Policy",   # [CONFIRM] same name as in your GPMC
    [string]$StaffGroup = "staff-only",
    [string]$SharePath  = "\\10.0.10.3\it-documents",
    [string]$WebServer  = "10.0.40.2",
    [string]$LinuxHost  = "monitor-server"              # [CONFIRM] name of the Linux server in AD
)

Import-Module ActiveDirectory
Import-Module GroupPolicy
$domain = Get-ADDomain
$dn     = $domain.DistinguishedName
$dns    = $domain.DNSRoot
$OUs    = "Management", "IT", "Operations", "Public Terminals"

function Deploy {
    # 1. OU structure (mirrors the organisation chart)
    foreach ($ou in $OUs) {
        if (Get-ADOrganizationalUnit -Filter "Name -eq '$ou'" -SearchBase $dn -SearchScope OneLevel) {
            Write-Host "[SKIP] OU $ou exists"
        } else {
            New-ADOrganizationalUnit -Name $ou -Path $dn
            Write-Host "[ OK ] OU $ou created" -ForegroundColor Green
        }
    }

    # 2. GPO
    $gpo = Get-GPO -Name $GpoName -ErrorAction SilentlyContinue
    if (-not $gpo) { $gpo = New-GPO -Name $GpoName; Write-Host "[ OK ] GPO created" -ForegroundColor Green }
    else           { Write-Host "[SKIP] GPO exists, updating it" }
    $guid = "{$($gpo.Id.ToString().ToUpper())}"

    # 3. Drive map Z: (written as a Group Policy Preferences file)
    $dir = "\\$dns\SYSVOL\$dns\Policies\$guid\User\Preferences\Drives"
    if (-not (Test-Path "$dir\Drives.xml")) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        $xml = '<?xml version="1.0" encoding="utf-8"?><Drives clsid="{8FDDCC1A-0C3C-43cd-A6B4-71A6DF20DA8C}"><Drive clsid="{935D1B74-9CB8-4e3c-9914-7DD559B7A417}" name="Z:" status="Z:" image="2" changed="2026-01-01 00:00:00" uid="' + "{$([guid]::NewGuid().ToString().ToUpper())}" + '"><Properties action="U" thisDrive="NOCHANGE" allDrives="NOCHANGE" userName="" path="' + $SharePath + '" label="IT Documents" persistent="1" useLetter="1" letter="Z"/></Drive></Drives>'
        Set-Content -Path "$dir\Drives.xml" -Value $xml -Encoding UTF8
        Set-ADObject -Identity "CN=$guid,CN=Policies,CN=System,$dn" -Replace @{ gPCUserExtensionNames = "[{5794DAFD-BE60-433f-88A2-1A31939AC01F}{2EA1A81B-48E5-45E9-8BB7-A6E3AC170006}]" }
        Write-Host "[ OK ] Drive Z: -> $SharePath" -ForegroundColor Green
    } else { Write-Host "[SKIP] Drive map exists" }

    # 4. Block RegEdit
    Set-GPRegistryValue -Name $GpoName -Key "HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\System" -ValueName DisableRegistryTools -Type DWord -Value 1 | Out-Null
    Write-Host "[ OK ] RegEdit blocked" -ForegroundColor Green

    # 5. Force Windows updates (automatic, daily at 03:00)
    $au = "HKLM\Software\Policies\Microsoft\Windows\WindowsUpdate\AU"
    Set-GPRegistryValue -Name $GpoName -Key $au -ValueName NoAutoUpdate -Type DWord -Value 0 | Out-Null
    Set-GPRegistryValue -Name $GpoName -Key $au -ValueName AUOptions -Type DWord -Value 4 | Out-Null
    Set-GPRegistryValue -Name $GpoName -Key $au -ValueName ScheduledInstallDay -Type DWord -Value 0 | Out-Null
    Set-GPRegistryValue -Name $GpoName -Key $au -ValueName ScheduledInstallTime -Type DWord -Value 3 | Out-Null
    Write-Host "[ OK ] Windows updates enforced" -ForegroundColor Green

    # 6. Only staff-only applies it (no Deny: Deny broke the GPO before, see CHG-003)
    Set-GPPermission -Name $GpoName -TargetName $StaffGroup -TargetType Group -PermissionLevel GpoApply | Out-Null
    Set-GPPermission -Name $GpoName -TargetName "Authenticated Users" -TargetType Group -PermissionLevel GpoRead -Replace | Out-Null
    Write-Host "[ OK ] Applies to '$StaffGroup' only" -ForegroundColor Green

    # 7. Link to the domain
    if (-not ((Get-GPInheritance -Target $dn).GpoLinks | Where-Object DisplayName -eq $GpoName)) {
        New-GPLink -Name $GpoName -Target $dn | Out-Null
        Write-Host "[ OK ] GPO linked to $dns" -ForegroundColor Green
    }
}

function Test {
    $results = @()
    function Check($name, [scriptblock]$test) {
        try   { $detail = & $test; $r = "PASS" }
        catch { $detail = $_.Exception.Message; $r = "FAIL" }
        $script:results += [pscustomobject]@{ Check = $name; Result = $r; Detail = $detail }
    }
    foreach ($ou in $OUs) {
        Check "OU $ou exists" { Get-ADOrganizationalUnit -Identity "OU=$ou,$dn" -ErrorAction Stop | Out-Null; "found" }
    }
    Check "Linux server $LinuxHost is joined to the domain" {
        $c = Get-ADComputer -Filter "Name -eq '$LinuxHost'"; if (-not $c) { throw "not found in AD" }; "found in AD"
    }
    Check "DNS: AD record resolves" { (Resolve-DnsName "_ldap._tcp.$dns" -Type SRV -ErrorAction Stop | Select-Object -First 1).NameTarget }
    Check "Web server https://$WebServer answers" {
        [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }   # lab certificate is self-signed
        "HTTP " + (Invoke-WebRequest "https://$WebServer" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop).StatusCode
    }
    Check "GPO exists and is linked" {
        Get-GPO -Name $GpoName -ErrorAction Stop | Out-Null
        if (-not ((Get-GPInheritance -Target $dn).GpoLinks | Where-Object DisplayName -eq $GpoName)) { throw "not linked" }; "linked"
    }
    Check "GPO blocks RegEdit" {
        $v = (Get-GPRegistryValue -Name $GpoName -Key "HKCU\Software\Microsoft\Windows\CurrentVersion\Policies\System" -ValueName DisableRegistryTools -ErrorAction Stop).Value
        if ($v -ne 1) { throw "value is $v" }; "set"
    }
    Check "GPO forces Windows updates" {
        $v = (Get-GPRegistryValue -Name $GpoName -Key "HKLM\Software\Policies\Microsoft\Windows\WindowsUpdate\AU" -ValueName AUOptions -ErrorAction Stop).Value
        if ($v -ne 4) { throw "value is $v" }; "set"
    }
    Check "GPO maps drive Z:" {
        $id = "{$((Get-GPO -Name $GpoName).Id.ToString().ToUpper())}"
        if (-not (Test-Path "\\$dns\SYSVOL\$dns\Policies\$id\User\Preferences\Drives\Drives.xml")) { throw "not found" }; "found"
    }

    $results | Format-Table -AutoSize -Wrap
    "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File "$PSScriptRoot\validation.log" -Append
    ($results | Format-Table -AutoSize -Wrap | Out-String) | Out-File "$PSScriptRoot\validation.log" -Append
    $failed = @($results | Where-Object Result -eq "FAIL").Count
    if ($failed -eq 0) { Write-Host "ALL CHECKS PASSED" -ForegroundColor Green } else { Write-Host "$failed CHECK(S) FAILED (see validation.log)" -ForegroundColor Red }
}

try {
    if ($Action -in "Deploy", "All") { Deploy }
    if ($Action -in "Test", "All")   { Test }
}
catch { Write-Host "[FAIL] $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
