param(
    [Parameter(Mandatory=$true)]
    [string]$InputPath,

    [Parameter(Mandatory=$true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

$word = $null
$doc = $null

function Release-ComObject {
    param([object]$Object)

    if ($null -ne $Object) {
        try {
            [System.Runtime.InteropServices.Marshal]::ReleaseComObject($Object) | Out-Null
        } catch {}
    }
}

try {
    if (!(Test-Path $InputPath)) {
        throw "Input file not found: $InputPath"
    }

    $outputFolder = Split-Path $OutputPath -Parent
    if (!(Test-Path $outputFolder)) {
        New-Item -ItemType Directory -Force -Path $outputFolder | Out-Null
    }

    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0

    # Open with current signed-in Office identity.
    # If the current user has Purview rights, Word should decrypt it.
    $doc = $word.Documents.Open(
        [ref]$InputPath,
        [ref]$false,
        [ref]$true
    )

    # Save as standard DOCX.
    # 16 = wdFormatDocumentDefault / DOCX
    $doc.SaveAs2(
        [ref]$OutputPath,
        [ref]16
    )

    $doc.Close([ref]$false)
    $word.Quit()

    Write-Output "SUCCESS:$OutputPath"
    exit 0
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
finally {
    if ($null -ne $doc) {
        try { $doc.Close([ref]$false) } catch {}
        Release-ComObject $doc
    }

    if ($null -ne $word) {
        try { $word.Quit() } catch {}
        Release-ComObject $word
    }

    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}
