$ErrorActionPreference = "Stop"
Write-Host "==> Downloading and installing DaVinci Resolve AI Bridge..."

$tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("resolve-ai-bridge-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

try {
    $zipPath = Join-Path $tmpDir "repo.zip"
    Invoke-WebRequest -Uri "https://github.com/flamexnreal/davinci-resolve-ai-bridge/archive/refs/heads/main.zip" -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath $tmpDir -Force
    $extractedFolder = Join-Path $tmpDir "davinci-resolve-ai-bridge-main"
    Set-Location $extractedFolder

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py install.py $args
    } elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
        & python3 install.py $args
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python install.py $args
    } else {
        Write-Error "Python 3.10+ is required but not found in PATH."
    }
} finally {
    Set-Location $HOME
    Remove-Item -Path $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
}
