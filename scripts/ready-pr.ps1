param(
    [int]$PrNumber,
    [switch]$Wait,
    [int]$PollSeconds = 15,
    [int]$TimeoutMinutes = 30,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' is not available in PATH."
    }
}

function Invoke-Gh {
    param([string[]]$GhArgs)
    $output = & gh @GhArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "gh $($GhArgs -join ' ') failed: $output"
    }
    return ($output | Out-String).Trim()
}

function Invoke-Git {
    param([string[]]$GitArgs)
    $output = & git @GitArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git $($GitArgs -join ' ') failed: $output"
    }
    return ($output | Out-String).Trim()
}

function Get-PrContext {
    param([int]$InputPrNumber)

    if ($InputPrNumber -gt 0) {
        $json = Invoke-Gh -GhArgs @('pr', 'view', "$InputPrNumber", '--json', 'number,title,state,isDraft,url,baseRefName,headRefName')
        return ($json | ConvertFrom-Json)
    }

    $branch = Invoke-Git -GitArgs @('rev-parse', '--abbrev-ref', 'HEAD')
    if ($branch -eq 'HEAD') {
        throw 'Detached HEAD detected. Checkout a branch before running this script.'
    }

    $json = Invoke-Gh -GhArgs @('pr', 'view', '--head', $branch, '--json', 'number,title,state,isDraft,url,baseRefName,headRefName')
    return ($json | ConvertFrom-Json)
}

function Get-RequiredChecks {
    param([int]$TargetPrNumber)

    $json = Invoke-Gh -GhArgs @('pr', 'checks', "$TargetPrNumber", '--required', '--json', 'name,bucket,state,workflow,link')
    if ([string]::IsNullOrWhiteSpace($json)) {
        return @()
    }

    return @($json | ConvertFrom-Json)
}

function Format-CheckLine {
    param($Check)
    $workflow = if ($Check.workflow) { $Check.workflow } else { 'n/a' }
    return "[$($Check.bucket)] $($Check.name) (state=$($Check.state), workflow=$workflow)"
}

try {
    Write-Step 'Checking required tooling'
    Assert-Command -Name 'git'
    Assert-Command -Name 'gh'
    $null = Invoke-Gh -GhArgs @('auth', 'status')

    Write-Step 'Resolving pull request context'
    $pr = Get-PrContext -InputPrNumber $PrNumber

    if (-not $pr.number) {
        throw 'Could not resolve a pull request from the current branch or supplied PR number.'
    }

    Write-Host "PR #$($pr.number): $($pr.title)"
    Write-Host "State: $($pr.state); Draft: $($pr.isDraft)"
    Write-Host "URL: $($pr.url)"

    if ($pr.state -ne 'OPEN') {
        throw "PR #$($pr.number) is not OPEN."
    }

    if (-not $pr.isDraft) {
        Write-Host 'PR is already Ready for Review. Nothing to do.' -ForegroundColor Green
        exit 0
    }

    Write-Step 'Evaluating required checks'

    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ($true) {
        $checks = Get-RequiredChecks -TargetPrNumber $pr.number

        if ($checks.Count -eq 0) {
            if ($Wait) {
                if ((Get-Date) -ge $deadline) {
                    throw 'Timed out waiting for required checks to appear.'
                }
                Write-Host 'No required checks available yet. Waiting...' -ForegroundColor Yellow
                Start-Sleep -Seconds $PollSeconds
                continue
            }
            throw 'No required checks available yet. Re-run with -Wait or try again later.'
        }

        $failed = @($checks | Where-Object { $_.bucket -in @('fail', 'cancel') })
        if ($failed.Count -gt 0) {
            Write-Host 'Failing required checks detected:' -ForegroundColor Red
            foreach ($check in $failed) {
                Write-Host "  - $(Format-CheckLine -Check $check)" -ForegroundColor Red
            }
            throw 'Cannot mark PR ready while required checks are failing.'
        }

        $pending = @($checks | Where-Object { $_.bucket -eq 'pending' })
        if ($pending.Count -gt 0) {
            Write-Host 'Pending required checks:' -ForegroundColor Yellow
            foreach ($check in $pending) {
                Write-Host "  - $(Format-CheckLine -Check $check)" -ForegroundColor Yellow
            }

            if (-not $Wait) {
                throw 'Required checks are still pending. Re-run with -Wait to auto-poll.'
            }

            if ((Get-Date) -ge $deadline) {
                throw "Timed out after $TimeoutMinutes minute(s) waiting for checks to finish."
            }

            Start-Sleep -Seconds $PollSeconds
            continue
        }

        $passed = @($checks | Where-Object { $_.bucket -in @('pass', 'skipping') })
        Write-Host "All required checks are complete. Passing/skipping checks: $($passed.Count)" -ForegroundColor Green
        break
    }

    if ($DryRun) {
        Write-Step 'Dry run mode'
        Write-Host "[DryRun] gh pr ready $($pr.number)" -ForegroundColor Yellow
        Write-Host '[DryRun] PR not modified.' -ForegroundColor Yellow
        exit 0
    }

    Write-Step 'Marking draft PR as ready for review'
    $null = Invoke-Gh -GhArgs @('pr', 'ready', "$($pr.number)")
    Write-Host "PR #$($pr.number) is now Ready for Review." -ForegroundColor Green

} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

