param([string]$RootsFile)
$ErrorActionPreference = 'Stop'
$scope = Get-Content -LiteralPath $RootsFile -Encoding UTF8 | ConvertFrom-Json
$roots = @($scope.roots | Sort-Object Length -Descending)
function Find-Roots([string]$text) {
    $matchesFound = @()
    if ($text) {
        $normalized = $text.Replace('/', '\')
        foreach ($candidate in $roots) {
            if ($normalized.IndexOf($candidate, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
                if (-not @($matchesFound | Where-Object { $_.StartsWith($candidate + '\', [StringComparison]::OrdinalIgnoreCase) }).Count) {
                    $matchesFound += $candidate
                }
            }
        }
    }
    return @($matchesFound)
}
$result = @{ processes = @(); services = @(); tasks = @(); startup = @(); registry_run = @(); errors = @() }
try {
    $result.processes = @(Get-CimInstance Win32_Process | ForEach-Object {
        $proc = $_
        if ($proc.ProcessId -notin $scope.audit_pids -and $proc.CommandLine -notmatch '\.audit-175') {
            $found = @(Find-Roots $proc.CommandLine)
            if ($found.Count -or $proc.Name -match 'tailscale') {
                $executable = $null
                if ($proc.ExecutablePath -and $proc.ExecutablePath.StartsWith('D:\Projects\VRAE', [StringComparison]::OrdinalIgnoreCase)) { $executable = $proc.ExecutablePath }
                @{ pid=$proc.ProcessId; name=$proc.Name; roots=$found; project_executable=$executable; command_available=[bool]$proc.CommandLine }
            }
        }
    })
} catch { $result.errors += 'PROCESS_METADATA_UNAVAILABLE' }
try {
    $result.services = @(Get-CimInstance Win32_Service | ForEach-Object {
        $found = @(Find-Roots $_.PathName)
        if ($found.Count -or $_.Name -match 'vrae|tailscale') {
            @{ name=$_.Name; state=$_.State; start_mode=$_.StartMode; roots=$found }
        }
    })
} catch { $result.errors += 'SERVICE_METADATA_UNAVAILABLE' }
try {
    $result.tasks = @(Get-ScheduledTask | ForEach-Object {
        $task = $_
        foreach ($action in $task.Actions) {
            $text = [string]$action.Execute + ' ' + [string]$action.Arguments + ' ' + [string]$action.WorkingDirectory
            $found = @(Find-Roots $text)
            if ($found.Count -or $text -match 'vrae|tailscale' -or $task.TaskName -match 'vrae|tailscale') {
                @{ name=$task.TaskName; state=[string]$task.State; roots=$found; command_redacted=$true }
            }
        }
    })
} catch { $result.errors += 'SCHEDULED_TASK_METADATA_UNAVAILABLE' }
try {
    $shell = New-Object -ComObject WScript.Shell
    $folders = @([Environment]::GetFolderPath('Startup'), [Environment]::GetFolderPath('CommonStartup'))
    foreach ($folder in $folders) {
        if ($folder -and (Test-Path -LiteralPath $folder)) {
            foreach ($entry in Get-ChildItem -LiteralPath $folder -File -Force) {
                $found = @()
                $text = $entry.Name
                if ($entry.Extension -eq '.lnk') {
                    $shortcut = $shell.CreateShortcut($entry.FullName)
                    $text += ' ' + $shortcut.TargetPath + ' ' + $shortcut.Arguments + ' ' + $shortcut.WorkingDirectory
                    $found = @(Find-Roots $text)
                }
                if ($found.Count -or $text -match 'vrae|tailscale') {
                    $result.startup += @{ name=$entry.Name; scope=$(if ($folder -eq $folders[0]) {'USER'} else {'ALL_USERS'}); roots=$found; command_redacted=$true }
                }
            }
        }
    }
} catch { $result.errors += 'STARTUP_SHORTCUT_METADATA_UNAVAILABLE' }
try {
    foreach ($key in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Run','HKLM:\Software\Microsoft\Windows\CurrentVersion\Run')) {
        if (Test-Path -LiteralPath $key) {
            $properties = Get-ItemProperty -LiteralPath $key
            foreach ($prop in $properties.PSObject.Properties) {
                if ($prop.Name -notmatch '^PS') {
                    $text = [string]$prop.Value
                    $found = @(Find-Roots $text)
                    if ($found.Count -or $text -match 'vrae|tailscale' -or $prop.Name -match 'vrae|tailscale') {
                        $result.registry_run += @{ name=$prop.Name; hive=$(if ($key.StartsWith('HKCU')) {'HKCU'} else {'HKLM'}); roots=$found; command_redacted=$true }
                    }
                }
            }
        }
    }
} catch { $result.errors += 'REGISTRY_RUN_METADATA_UNAVAILABLE' }
$result | ConvertTo-Json -Depth 8 -Compress
