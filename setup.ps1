param(
    [string]$Python,
    [string]$CreoRoot,
    [string]$VcVars64,
    [hashtable]$VcVars64Env,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'Windows x64 is required.'
}

# pip writes progress and [notice] lines to stderr. PowerShell 5.1 turns redirected
# native stderr into ErrorRecords, and the script-wide 'Stop' preference then aborts
# a pip run that actually exited 0 (BUG-086). Tolerate those records only inside this
# helper, leave the text visible, and judge the real exit code.
function Invoke-PipStep {
    param(
        [Parameter(Mandatory)][string]$Executable,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$FailureMessage
    )
    $previousPreference = $ErrorActionPreference
    $launchFailure = $null
    $exitCode = $null
    # Drop the previous native exit code so a launch failure cannot inherit it.
    $global:LASTEXITCODE = $null
    try {
        $ErrorActionPreference = 'Continue'
        & $Executable @Arguments
        # Save the real code immediately, before any other statement can replace it.
        $exitCode = $global:LASTEXITCODE
    } catch {
        $launchFailure = $_
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($null -ne $launchFailure) {
        throw ("{0} Could not start {1}: {2}" -f $FailureMessage, $Executable, $launchFailure.Exception.Message)
    }
    if ($null -eq $exitCode) {
        throw ("{0} {1} reported no exit code." -f $FailureMessage, $Executable)
    }
    if ($exitCode -ne 0) {
        throw ("{0} {1} exited with code {2}." -f $FailureMessage, $Executable, $exitCode)
    }
}

$settingsPath = Join-Path $PSScriptRoot 'config.json'
$settingsSource = if (Test-Path -LiteralPath $settingsPath) { $settingsPath } else { Join-Path $PSScriptRoot 'config.example.json' }
$settings = Get-Content -LiteralPath $settingsSource -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $CreoRoot) { $CreoRoot = $settings.creo_root }
if (-not $PSBoundParameters.ContainsKey('VcVars64Env') -and -not $PSBoundParameters.ContainsKey('VcVars64')) {
    if ($null -ne $settings.vcvars64_env) {
        $VcVars64Env = @{}
        foreach ($property in $settings.vcvars64_env.PSObject.Properties) { $VcVars64Env[$property.Name] = $property.Value }
    }
}
if ($null -ne $VcVars64Env) {
    $envKeys = @('INCLUDE', 'LIB', 'PATH')
    # Match bridge validation: the three keys above must be present with this
    # exact case (PowerShell hashtables otherwise ignore key case).
    $missing = @($envKeys | Where-Object { @($VcVars64Env.Keys) -cnotcontains $_ })
    if ($missing.Count) {
        throw ("vcvars64_env is missing required keys: {0}. Minimal example: -VcVars64Env @{{INCLUDE='...';LIB='...';PATH='...'}}." -f ($missing -join ', '))
    }
    $extraKeys = @($VcVars64Env.Keys | Where-Object { $_ -cnotin $envKeys } | Sort-Object)
    if ($extraKeys.Count) {
        Write-Output ("vcvars64_env: ignoring extra keys not used by the build: {0}" -f ($extraKeys -join ', '))
    }
    foreach ($key in $envKeys) {
        $value = $VcVars64Env[$key]
        if ($value -isnot [string] -or [string]::IsNullOrWhiteSpace($value) -or $value -match '[\x00\r\n"%]') {
            throw 'Invalid vcvars64_env: use nonempty INCLUDE/LIB/PATH strings without quotes, percent signs or newlines.'
        }
    }
}
if ($null -eq $VcVars64Env -and -not $VcVars64 -and $settings.vcvars64 -and (Test-Path -LiteralPath $settings.vcvars64 -PathType Leaf)) { $VcVars64 = $settings.vcvars64 }
if ($null -eq $VcVars64Env -and -not $VcVars64) {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (Test-Path -LiteralPath $vswhere -PathType Leaf) {
        $vsInstallation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($LASTEXITCODE -eq 0 -and $vsInstallation) {
            $VcVars64 = Join-Path ($vsInstallation | Select-Object -First 1) 'VC\Auxiliary\Build\vcvars64.bat'
        }
    }
}
if ($null -eq $VcVars64Env -and -not $VcVars64) { throw 'MSVC x64 tools not found. Install Visual Studio C++ Build Tools, or pass -VcVars64 or -VcVars64Env.' }
foreach ($localPath in @($CreoRoot, $VcVars64, $PSScriptRoot)) {
    if ($localPath -match '[\x00\r\n"%]') { throw 'Installation paths cannot contain quotes, percent signs or newlines.' }
}
if (-not (Test-Path -LiteralPath $CreoRoot -PathType Container)) { throw 'Creo installation not found. Pass -CreoRoot with your Creo 9, 10 or 12 installation directory.' }
$CreoRoot = (Resolve-Path -LiteralPath $CreoRoot).ProviderPath
if ($null -eq $VcVars64Env) {
    if (-not (Test-Path -LiteralPath $VcVars64 -PathType Leaf)) { throw 'vcvars64.bat not found. Pass -VcVars64 with the installed compiler setup file, or use -VcVars64Env.' }
    $VcVars64 = (Resolve-Path -LiteralPath $VcVars64).ProviderPath
}
$required = @(
    'Parametric\bin\parametric.exe',
    'Common Files\protoolkit\includes\ProToolkit.h',
    'Common Files\protoolkit\x86e_win64\obj\ptasyncmd.lib',
    'Common Files\protoolkit\x86e_win64\obj\protkmd_NU.lib',
    'Common Files\protoolkit\x86e_win64\obj\protk_dllmd_NU.lib',
    'Common Files\protoolkit\x86e_win64\obj\ucore.lib',
    'Common Files\protoolkit\x86e_win64\obj\udata.lib',
    'Common Files\x86e_win64\obj\pro_comm_msg.exe',
    'Common Files\templates\mmns_part_solid_abs.prt',
    'Common Files\templates\mmns_asm_design_abs.asm'
)
foreach ($relative in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $CreoRoot $relative) -PathType Leaf)) {
        throw "Missing Creo prerequisite: $relative. Install the matching Creo Toolkit SDK and metric templates."
    }
}

$pythonPrefix = @()
if (-not $Python) {
    $launcher = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($launcher) { $Python = $launcher.Source; $pythonPrefix = @('-3') }
    else {
        $pythonCommand = Get-Command python.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($pythonCommand) { $Python = $pythonCommand.Source }
    }
}
if (-not $Python) { throw 'Python not found. Install Python 3.12+ x64, or pass -Python with python.exe.' }
$pythonCommand = Get-Command $Python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $pythonCommand) { throw 'Python executable not found. Pass -Python with its full path.' }
$Python = $pythonCommand.Source
if ($Python -match '(?i)(^|[\\/])WindowsApps([\\/]|$)') {
    throw 'WindowsApps Python is a Microsoft Store placeholder. Install Python 3.12+ x64 and pass -Python with the real python.exe path.'
}
if ($Python -match '[\x00\r\n"%]') { throw 'Python path cannot contain quotes, percent signs or newlines.' }
$pythonInfoText = & $Python @pythonPrefix -c 'import json,struct,sys; print(json.dumps(dict(version=list(sys.version_info[:3]),bits=struct.calcsize(chr(80))*8)))'
if ($LASTEXITCODE -ne 0) { throw 'Cannot run Python. Pass -Python with a working Python 3.12+ x64 executable.' }
$pythonInfo = $pythonInfoText | ConvertFrom-Json
if ($pythonInfo.bits -ne 64 -or $pythonInfo.version[0] -ne 3 -or $pythonInfo.version[1] -lt 12) {
    throw 'Python 3.12+ x64 is required. Pass -Python with a compatible executable.'
}
Write-Output ("Prerequisites found: Python {0}, Creo SDK and MSVC x64." -f ($pythonInfo.version -join '.'))
if ($CheckOnly) { Write-Output 'File checks passed. Toolkit license and the live Creo connection still require runtime verification.'; return }

$localSettings = [ordered]@{}
# Preserve session selection and future local options when reinstalling/upgrading.
foreach ($property in $settings.PSObject.Properties) { $localSettings[$property.Name] = $property.Value }
$localSettings['creo_root'] = $CreoRoot
$localSettings['vcvars64'] = $VcVars64
if ($null -ne $VcVars64Env) {
    # Persist only the normalized three required keys; extra keys were ignored above.
    $normalizedEnv = @{}
    foreach ($key in @('INCLUDE', 'LIB', 'PATH')) { $normalizedEnv[$key] = $VcVars64Env[$key] }
    $localSettings['vcvars64_env'] = $normalizedEnv
} else {
    $localSettings['vcvars64_env'] = $null
}
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$stage = 'local configuration'
$completed = @()
try {
    $localSettings | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $settingsPath -Encoding UTF8
    $completed += $stage
    $stage = 'Python virtual environment'
    & $Python @pythonPrefix -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python venv creation failed.' }
    $completed += $stage
    $stage = 'client configuration'
    $connection = @{ mcpServers = @{ 'MCP_CREO_MechDog' = @{ command = $projectPython; args = @((Join-Path $PSScriptRoot 'server.py')) } } }
    $connection | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'client-config.json') -Encoding UTF8
    $completed += $stage
    $stage = 'Python dependencies'
    Invoke-PipStep -Executable $projectPython -Arguments @('-m', 'pip', 'install', '-r', (Join-Path $PSScriptRoot 'requirements.lock.txt')) -FailureMessage 'Dependency installation failed. Check internet/PyPI access and requirements.lock.txt.'
    $completed += $stage
    $stage = 'Python source package'
    Invoke-PipStep -Executable $projectPython -Arguments @('-m', 'pip', 'install', '--no-deps', '--editable', $PSScriptRoot) -FailureMessage 'Source package installation failed. Restore pyproject.toml and src, then rerun setup.ps1.'
    & $projectPython -c 'import creo_mechdog.paths'
    if ($LASTEXITCODE -ne 0) { throw 'Source package import failed. Reinstall the package for this source directory.' }
    $completed += $stage
    $stage = 'native Blend seed library'
    & $projectPython (Join-Path $PSScriptRoot 'seeds.py') --install
    if ($LASTEXITCODE -ne 0) { throw 'Seed library verification failed. Restore the packaged seed_library, or register the original published library.' }
    $completed += $stage
    $stage = 'SDK constants and native worker'
    & $projectPython (Join-Path $PSScriptRoot 'bridge.py') build
    if ($LASTEXITCODE -ne 0) { throw 'Toolkit worker build failed; inspect build\generate_constants.log and build\build.log.' }
    $completed += $stage
} catch {
    Write-Output ("INSTALL_INCOMPLETE: failed at {0}. Completed: {1}." -f $stage, ($completed -join ', '))
    Write-Output 'Existing models/jobs and local settings are retained. client-config.json, if generated, does not mean the native worker is ready.'
    Write-Output 'Fix the reported prerequisite/network/compiler error and rerun the same setup.ps1 command. No cleanup is required; existing .venv and unchanged native builds are reused.'
    throw
}
Write-Output 'Ready. Import client-config.json into your local MCP client. Creo detection/optional startup runs in the background.'
Write-Output 'Poll creo_startup_status until ready before modeling; installation alone does not prove Toolkit license availability.'
