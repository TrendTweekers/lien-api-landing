# PostgreSQL backup script for Railway Postgres (PowerShell version)
# Usage: .\backup_postgres.ps1 [DATABASE_URL]
# If DATABASE_URL is not provided, it will use the environment variable

$Date = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = "backups"
$BackupFile = "$BackupDir\pre_cleanup_$Date.sql"

# Use provided DATABASE_URL or environment variable
if ($args.Count -gt 0) {
    $env:DATABASE_URL = $args[0]
} elseif (-not $env:DATABASE_URL) {
    Write-Host "❌ Error: DATABASE_URL not provided and not set in environment" -ForegroundColor Red
    Write-Host "Usage: .\backup_postgres.ps1 [DATABASE_URL]"
    Write-Host "   or: `$env:DATABASE_URL='your-url'; .\backup_postgres.ps1"
    exit 1
}

# Create backup directory if it doesn't exist
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

Write-Host "🔄 Starting PostgreSQL backup..."
$MaskedUrl = $env:DATABASE_URL -replace ':[^:]*@', ':***@'
Write-Host "   Database: $MaskedUrl"

# Check if pg_dump is available
$pgDumpPath = Get-Command pg_dump -ErrorAction SilentlyContinue
if (-not $pgDumpPath) {
    Write-Host "❌ Error: pg_dump not found in PATH" -ForegroundColor Red
    Write-Host "   Install PostgreSQL client tools:" -ForegroundColor Yellow
    Write-Host "   - Download from: https://www.postgresql.org/download/windows/"
    Write-Host "   - Or use Chocolatey: choco install postgresql"
    exit 1
}

# Perform pg_dump
try {
    & pg_dump $env:DATABASE_URL | Out-File -FilePath $BackupFile -Encoding UTF8
    
    # Check if backup file was created and has content
    if (Test-Path $BackupFile) {
        $FileSize = (Get-Item $BackupFile).Length
        if ($FileSize -gt 0) {
            $FileSizeMB = [math]::Round($FileSize / 1MB, 2)
            Write-Host "✅ Backup completed successfully!" -ForegroundColor Green
            Write-Host "   File: $BackupFile"
            Write-Host "   Size: $FileSizeMB MB"
            Write-Host ""
            Write-Host "💡 To restore this backup:" -ForegroundColor Cyan
            Write-Host "   psql `$env:DATABASE_URL < $BackupFile"
        } else {
            Write-Host "❌ Error: Backup file is empty" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "❌ Error: Backup file was not created" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Error: pg_dump failed" -ForegroundColor Red
    Write-Host "   $_" -ForegroundColor Yellow
    Write-Host "   Make sure DATABASE_URL is correct and accessible"
    exit 1
}

