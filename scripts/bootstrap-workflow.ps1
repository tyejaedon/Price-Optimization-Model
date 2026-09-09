param(
    [int]$IssueNumber,
    [ValidateSet('feature', 'fix', 'chore', 'docs', 'refactor', 'test')]
    [string]$BranchType,
    [string]$BaseBranch = 'master',
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

function Invoke-Git {
    param([string[]]$GitArgs)
    $output = & git @GitArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git $($GitArgs -join ' ') failed: $output"
    }
    return ($output | Out-String).Trim()
}

function Invoke-Gh {
    param([string[]]$GhArgs)
    $output = & gh @GhArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "gh $($GhArgs -join ' ') failed: $output"
    }
    return ($output | Out-String).Trim()
}

function Read-RequiredInput {
    param([string]$Prompt)
    while ($true) {
        $value = Read-Host $Prompt
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            return $value.Trim()
        }
        Write-Host 'Input is required.' -ForegroundColor Yellow
    }
}

function Select-BranchType {
    $types = @('feature', 'fix', 'chore', 'docs', 'refactor', 'test')
    Write-Host 'Select branch type:' -ForegroundColor Cyan
    for ($i = 0; $i -lt $types.Count; $i++) {
        Write-Host "  [$($i + 1)] $($types[$i])"
    }

    while ($true) {
        $raw = Read-Host 'Enter selection number'
        if ([int]::TryParse($raw, [ref]$null)) {
            $index = [int]$raw - 1
            if ($index -ge 0 -and $index -lt $types.Count) {
                return $types[$index]
            }
        }
        Write-Host 'Invalid selection. Choose a number from the list.' -ForegroundColor Yellow
    }
}

function New-Slug {
    param([string]$Text)

    $t = $Text.ToLowerInvariant()
    $t = [Regex]::Replace($t, '^m\d+(\.\d+)?\s+', '')
    $t = [Regex]::Replace($t, '[^a-z0-9]+', '-')
    $t = [Regex]::Replace($t, '-{2,}', '-')
    $t = $t.Trim('-')

    if ([string]::IsNullOrWhiteSpace($t)) {
        return 'issue-work'
    }

    if ($t.Length -gt 50) {
        return $t.Substring(0, 50).Trim('-')
    }

    return $t
}

try {
    Write-Step 'Checking required tooling'
    Assert-Command -Name 'git'
    Assert-Command -Name 'gh'

    $null = Invoke-Gh -GhArgs @('auth', 'status')

    $repoRoot = Invoke-Git -GitArgs @('rev-parse', '--show-toplevel')
    Set-Location $repoRoot

    Write-Step "Repository root: $repoRoot"

    if (-not $IssueNumber) {
        $issueRaw = Read-RequiredInput -Prompt 'Enter issue number'
        if (-not [int]::TryParse($issueRaw, [ref]$IssueNumber)) {
            throw 'Issue number must be an integer.'
        }
    }

    if (-not $BranchType) {
        $BranchType = Select-BranchType
    }

    Write-Step "Fetching issue #$IssueNumber metadata"
    $issueJson = Invoke-Gh -GhArgs @('issue', 'view', "$IssueNumber", '--json', 'number,title,state,milestone,labels,url')
    $issue = $issueJson | ConvertFrom-Json

    if (-not $issue.number) {
        throw "Issue #$IssueNumber could not be loaded."
    }

    if ($issue.state -ne 'OPEN') {
        throw "Issue #$IssueNumber is not OPEN (state: $($issue.state))."
    }

    $slug = New-Slug -Text $issue.title
    $branchName = "$BranchType/$IssueNumber-$slug"

    Write-Step "Planned branch: $branchName"

    $currentBranch = Invoke-Git -GitArgs @('rev-parse', '--abbrev-ref', 'HEAD')
    if ($currentBranch -eq 'HEAD') {
        throw 'Detached HEAD detected. Checkout a branch first.'
    }

    if ($currentBranch -ne $BaseBranch) {
        Write-Host "Current branch is '$currentBranch' (base configured: '$BaseBranch')." -ForegroundColor Yellow
        Write-Host 'Proceeding from current branch HEAD to avoid destructive switching.' -ForegroundColor Yellow
    }

    $existsLocal = $false
    $checkLocal = & git show-ref --verify --quiet "refs/heads/$branchName"
    if ($LASTEXITCODE -eq 0) { $existsLocal = $true }

    if ($DryRun) {
        Write-Step 'Dry run mode: no branch/PR changes will be made'
    }

    if (-not $existsLocal) {
        Write-Step "Creating local branch '$branchName'"
        if (-not $DryRun) {
            $null = Invoke-Git -GitArgs @('checkout', '-b', $branchName)
        }
    } else {
        Write-Step "Branch '$branchName' already exists locally"
        if (-not $DryRun) {
            $null = Invoke-Git -GitArgs @('checkout', $branchName)
        }
    }

    Write-Step 'Checking for existing PR for this branch'
    $existingPrUrl = ''
    try {
        $prJson = Invoke-Gh -GhArgs @('pr', 'view', '--head', $branchName, '--json', 'url')
        $pr = $prJson | ConvertFrom-Json
        if ($pr.url) {
            $existingPrUrl = $pr.url
        }
    } catch {
        # No existing PR is expected for new branches.
    }

    if ($existingPrUrl) {
        Write-Host "PR already exists: $existingPrUrl" -ForegroundColor Green
        exit 0
    }

    $milestoneTitle = ''
    if ($issue.milestone -and $issue.milestone.title) {
        $milestoneTitle = $issue.milestone.title
    }

    $labelNames = @()
    if ($issue.labels) {
        foreach ($label in $issue.labels) {
            if ($label.name) {
                $labelNames += $label.name
            }
        }
    }

    $prTitle = $issue.title
    $prBody = @(
        '## Summary',
        '',
        '- Linked issue implementation',
        '',
        '## Linked Planning Items',
        '',
        "- Closes #$IssueNumber",
        "- Related issue(s): #$IssueNumber",
        $(if ($milestoneTitle) { "- Milestone: $milestoneTitle" } else { '- Milestone: <fill-in-required>' }),
        '',
        '## Workstream Labels',
        '',
        $(if ($labelNames.Count -gt 0) { "- Primary label: $($labelNames[0])" } else { '- Primary label: <fill-in-required>' }),
        $(if ($labelNames.Count -gt 1) { "- Secondary label(s): $($labelNames[1..($labelNames.Count-1)] -join ', ')" } else { '- Secondary label(s): none' }),
        '',
        '## Validation Evidence',
        '',
        '- [ ] Local checks/tests were run',
        '- [ ] No large dataset files were added to version control'
    ) -join "`n"

    $bodyFile = [System.IO.Path]::GetTempFileName()
    [System.IO.File]::WriteAllText($bodyFile, $prBody, (New-Object System.Text.UTF8Encoding($false)))

    Write-Step 'Pushing branch to origin'
    if (-not $DryRun) {
        $null = Invoke-Git -GitArgs @('push', '-u', 'origin', $branchName)
    } else {
        Write-Host "[DryRun] git push -u origin $branchName"
    }

    Write-Step 'Creating draft PR'
    $prArgs = @('pr', 'create', '--draft', '--title', $prTitle, '--body-file', $bodyFile, '--base', $BaseBranch, '--head', $branchName)

    if ($milestoneTitle) {
        $prArgs += @('--milestone', $milestoneTitle)
    }

    foreach ($labelName in $labelNames) {
        $prArgs += @('--label', $labelName)
    }

    if (-not $DryRun) {
        $prUrl = Invoke-Gh -GhArgs $prArgs
        Write-Host "Draft PR created: $prUrl" -ForegroundColor Green
    } else {
        Write-Host "[DryRun] gh $($prArgs -join ' ')" -ForegroundColor Yellow
        Write-Host '[DryRun] Draft PR not created.' -ForegroundColor Yellow
    }

    Remove-Item $bodyFile -Force -ErrorAction SilentlyContinue

    Write-Step 'Done'
    Write-Host "Branch: $branchName"
    Write-Host "Issue: #$IssueNumber ($($issue.title))"
    if ($milestoneTitle) {
        Write-Host "Milestone: $milestoneTitle"
    }
    if ($labelNames.Count -gt 0) {
        Write-Host "Labels: $($labelNames -join ', ')"
    }

} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}




