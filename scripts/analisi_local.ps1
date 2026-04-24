# ============================================================
# ANALISI SPAZIO C:\Users\gabri\.local
# Identifica cartelle pesanti e quelle sicure da archiviare
# ============================================================

$basePath = "C:\Users\gabri\.local"
$outputFile = "$env:USERPROFILE\Desktop\analisi_local_$(Get-Date -Format 'yyyyMMdd_HHmm').txt"

function Get-FolderSize {
    param([string]$Path)
    try {
        $size = (Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue |
                 Measure-Object -Property Length -Sum).Sum
        return [math]::Round($size / 1MB, 2)
    } catch { return 0 }
}

function Format-Size {
    param([double]$SizeMB)
    if ($SizeMB -ge 1024) { return "$([math]::Round($SizeMB/1024, 2)) GB" }
    return "$SizeMB MB"
}

# Categorie sicure da archiviare (non necessarie per il sistema)
$safeCategories = @{
    "pip"          = "Cache pip (pacchetti Python scaricati)"
    "uv"           = "Cache/tools uv (pacchetti Python)"
    "npm"          = "Cache npm (pacchetti Node.js)"
    "yarn"         = "Cache yarn"
    "cargo"        = "Cache Rust/Cargo"
    "conda"        = "Ambienti/cache Conda"
    "virtualenvs"  = "Ambienti virtuali Python"
    "pypoetry"     = "Cache/ambienti Poetry"
    "gems"         = "Gem Ruby"
    "go"           = "Cache Go modules"
    "nuget"        = "Cache NuGet (.NET)"
    "programs"     = "Programmi installati localmente"
    "fontconfig"   = "Cache font (rigenerabile)"
    "themes"       = "Temi UI"
    "icons"        = "Icone"
    "Temp"         = "File temporanei"
    "temp"         = "File temporanei"
    "cache"        = "Cache generica"
    "Cache"        = "Cache generica"
    "log"          = "File di log"
    "logs"         = "File di log"
    "Logs"         = "File di log"
}

# Categorie da NON toccare
$unsafeCategories = @(
    "microsoft", "windowsapps", "packages", "programs", "application data",
    "history", "recently-used", "bookmarks", "recently_used"
)

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  ANALISI SPAZIO: $basePath" -ForegroundColor Cyan
Write-Host "============================================================`n" -ForegroundColor Cyan

if (-not (Test-Path $basePath)) {
    Write-Host "ATTENZIONE: La cartella $basePath non esiste." -ForegroundColor Red
    Write-Host "Provo a cercare .local in posizioni alternative...`n" -ForegroundColor Yellow
    $alternatives = @(
        "$env:USERPROFILE\.local",
        "$env:APPDATA\.local",
        "$env:LOCALAPPDATA"
    )
    foreach ($alt in $alternatives) {
        if (Test-Path $alt) {
            Write-Host "Trovata cartella alternativa: $alt" -ForegroundColor Green
            $basePath = $alt
            break
        }
    }
}

Write-Host "Scansione in corso... (potrebbe richiedere qualche minuto)" -ForegroundColor Yellow
Write-Host ""

$results = @()

# Scansiona primo livello
$firstLevel = Get-ChildItem -Path $basePath -Directory -ErrorAction SilentlyContinue

foreach ($dir in $firstLevel) {
    Write-Host "  Analisi: $($dir.Name)..." -ForegroundColor DarkGray
    $sizeMB = Get-FolderSize -Path $dir.FullName

    # Determina se sicura
    $isSafe = $false
    $reason = "Verifica manuale consigliata"
    $dirLower = $dir.Name.ToLower()

    foreach ($key in $safeCategories.Keys) {
        if ($dirLower -like "*$($key.ToLower())*") {
            $isSafe = $true
            $reason = $safeCategories[$key]
            break
        }
    }

    foreach ($unsafe in $unsafeCategories) {
        if ($dirLower -like "*$unsafe*") {
            $isSafe = $false
            $reason = "NON SPOSTARE - Dati utente/sistema"
            break
        }
    }

    # Scansiona anche secondo livello per le cartelle grandi
    $subDetails = @()
    if ($sizeMB -gt 10) {
        $subDirs = Get-ChildItem -Path $dir.FullName -Directory -ErrorAction SilentlyContinue
        foreach ($sub in $subDirs) {
            $subSize = Get-FolderSize -Path $sub.FullName
            if ($subSize -gt 1) {
                $subDetails += [PSCustomObject]@{
                    Name   = "  └─ $($sub.Name)"
                    SizeMB = $subSize
                    Safe   = $isSafe
                    Reason = ""
                }
            }
        }
    }

    $results += [PSCustomObject]@{
        Name    = $dir.Name
        SizeMB  = $sizeMB
        Safe    = $isSafe
        Reason  = $reason
        SubDirs = $subDetails
    }
}

# Ordina per dimensione decrescente
$results = $results | Sort-Object SizeMB -Descending

# ---- OUTPUT REPORT ----
$report = @()
$report += "============================================================"
$report += "  ANALISI SPAZIO: $basePath"
$report += "  Data: $(Get-Date -Format 'dd/MM/yyyy HH:mm')"
$report += "============================================================`n"

$totalMB = ($results | Measure-Object -Property SizeMB -Sum).Sum
$report += "TOTALE OCCUPATO: $(Format-Size $totalMB)`n"

$report += "------------------------------------------------------------"
$report += "CARTELLE ORDINATE PER DIMENSIONE:"
$report += "------------------------------------------------------------"

foreach ($r in $results) {
    $safeLabel = if ($r.Safe) { "[ARCHIVIABILE]" } else { "[NON TOCCARE] " }
    $color = if ($r.Safe) { "Green" } else { "Red" }
    $line = "{0,-16} {1,-12} {2} - {3}" -f $safeLabel, (Format-Size $r.SizeMB), $r.Name, $r.Reason
    $report += $line
    Write-Host $line -ForegroundColor $(if ($r.Safe) { "Green" } else { "Red" })

    foreach ($sub in $r.SubDirs) {
        $subLine = "                   {0,-12} {1}" -f (Format-Size $sub.SizeMB), $sub.Name
        $report += $subLine
        Write-Host $subLine -ForegroundColor DarkCyan
    }
}

$report += "`n------------------------------------------------------------"
$safeMB  = ($results | Where-Object { $_.Safe } | Measure-Object -Property SizeMB -Sum).Sum
$unsafeMB = ($results | Where-Object { -not $_.Safe } | Measure-Object -Property SizeMB -Sum).Sum

$report += "RIEPILOGO:"
$report += "  Spazio archiviabile su D:\  : $(Format-Size $safeMB)"
$report += "  Spazio da NON spostare      : $(Format-Size $unsafeMB)"
$report += "  TOTALE                      : $(Format-Size $totalMB)"
$report += "------------------------------------------------------------"

$report += "`nCARTELLE SICURE DA ARCHIVIARE:"
foreach ($r in ($results | Where-Object { $_.Safe } | Sort-Object SizeMB -Descending)) {
    $report += "  $($r.FullPath ?? "$basePath\$($r.Name)") -- $(Format-Size $r.SizeMB)"
}

Write-Host "`n------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "RIEPILOGO FINALE:" -ForegroundColor Cyan
Write-Host "  Spazio archiviabile su D:\  : $(Format-Size $safeMB)" -ForegroundColor Green
Write-Host "  Spazio da NON spostare      : $(Format-Size $unsafeMB)" -ForegroundColor Red
Write-Host "  TOTALE                      : $(Format-Size $totalMB)" -ForegroundColor White
Write-Host "------------------------------------------------------------`n" -ForegroundColor Cyan

# Salva report su Desktop
$report | Out-File -FilePath $outputFile -Encoding UTF8
Write-Host "Report salvato su: $outputFile" -ForegroundColor Yellow
Write-Host "`nQuando sei pronto, esegui lo script di COPIA su D:\" -ForegroundColor Cyan
