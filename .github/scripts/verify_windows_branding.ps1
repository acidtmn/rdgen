param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryRoot,

    [Parameter(Mandatory = $true)]
    [string]$ExecutablePath,

    [Parameter(Mandatory = $false)]
    [string]$DistDir = "",

    [Parameter(Mandatory = $false)]
    [double]$MaximumIconDifference = 0.12
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RequiredPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,

        [Parameter(Mandatory = $true)]
        [string]$RelativePath,

        [Parameter(Mandatory = $true)]
        [string]$AssetName
    )

    $resolvedPath = [System.IO.Path]::GetFullPath((Join-Path $BasePath $RelativePath))
    if (-not (Test-Path $resolvedPath)) {
        throw "Branding validation failed: $AssetName was not found at $resolvedPath"
    }

    return $resolvedPath
}

function Assert-FilesMatch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExpectedPath,

        [Parameter(Mandatory = $true)]
        [string]$ActualPath,

        [Parameter(Mandatory = $true)]
        [string]$AssetName
    )

    $expectedHash = (Get-FileHash -LiteralPath $ExpectedPath -Algorithm SHA256).Hash
    $actualHash = (Get-FileHash -LiteralPath $ActualPath -Algorithm SHA256).Hash
    if ($expectedHash -ne $actualHash) {
        throw "Branding validation failed: $AssetName differs from the approved source"
    }

    Write-Host "Branding verified: $AssetName ($actualHash)"
}

function Get-EmbeddedIconDifference {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExpectedPngPath,

        [Parameter(Mandatory = $true)]
        [string]$BinaryPath
    )

    Add-Type -AssemblyName System.Drawing

    $expectedImage = $null
    $embeddedIcon = $null
    $actualBitmap = $null
    $expectedBitmap = $null
    $graphics = $null

    try {
        # ExtractAssociatedIcon читает именно ресурс Windows-бинарника, а не лежащий рядом PNG.
        # Поэтому проверка ловит ситуацию, когда CI скопировал картинки, но EXE сохранил чужой значок.
        $expectedImage = [System.Drawing.Image]::FromFile($ExpectedPngPath)
        $embeddedIcon = [System.Drawing.Icon]::ExtractAssociatedIcon($BinaryPath)
        if (-not $embeddedIcon) {
            throw "Branding validation failed: executable icon cannot be extracted from $BinaryPath"
        }

        $actualBitmap = $embeddedIcon.ToBitmap()
        $expectedBitmap = [System.Drawing.Bitmap]::new($actualBitmap.Width, $actualBitmap.Height)
        $graphics = [System.Drawing.Graphics]::FromImage($expectedBitmap)
        $graphics.Clear([System.Drawing.Color]::Transparent)
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $graphics.DrawImage($expectedImage, 0, 0, $actualBitmap.Width, $actualBitmap.Height)

        [double]$difference = 0
        for ($y = 0; $y -lt $actualBitmap.Height; $y++) {
            for ($x = 0; $x -lt $actualBitmap.Width; $x++) {
                $expectedPixel = $expectedBitmap.GetPixel($x, $y)
                $actualPixel = $actualBitmap.GetPixel($x, $y)
                $difference += [Math]::Abs($expectedPixel.A - $actualPixel.A)
                $difference += [Math]::Abs($expectedPixel.R - $actualPixel.R)
                $difference += [Math]::Abs($expectedPixel.G - $actualPixel.G)
                $difference += [Math]::Abs($expectedPixel.B - $actualPixel.B)
            }
        }

        return $difference / ($actualBitmap.Width * $actualBitmap.Height * 4 * 255)
    }
    finally {
        if ($graphics) { $graphics.Dispose() }
        if ($expectedBitmap) { $expectedBitmap.Dispose() }
        if ($actualBitmap) { $actualBitmap.Dispose() }
        if ($embeddedIcon) { $embeddedIcon.Dispose() }
        if ($expectedImage) { $expectedImage.Dispose() }
    }
}

$root = [System.IO.Path]::GetFullPath($RepositoryRoot)
$approvedIcon = Resolve-RequiredPath -BasePath $root -RelativePath ".rdgen-branding/icon.png" -AssetName "approved icon"
$approvedLogo = Resolve-RequiredPath -BasePath $root -RelativePath ".rdgen-branding/logo.png" -AssetName "approved logo"
$binary = Resolve-RequiredPath -BasePath $root -RelativePath $ExecutablePath -AssetName "Windows executable"

if ($DistDir) {
    $distRoot = Resolve-RequiredPath -BasePath $root -RelativePath $DistDir -AssetName "built distribution"
    $distIcon = Resolve-RequiredPath -BasePath $distRoot -RelativePath "data/flutter_assets/assets/icon.png" -AssetName "built icon"
    $distLogo = Resolve-RequiredPath -BasePath $distRoot -RelativePath "data/flutter_assets/assets/logo.png" -AssetName "built logo"
    Assert-FilesMatch -ExpectedPath $approvedIcon -ActualPath $distIcon -AssetName "built application icon"
    Assert-FilesMatch -ExpectedPath $approvedLogo -ActualPath $distLogo -AssetName "built application logo"
}

$iconDifference = Get-EmbeddedIconDifference -ExpectedPngPath $approvedIcon -BinaryPath $binary
Write-Host "Embedded Windows icon difference: $iconDifference"
if ($iconDifference -gt $MaximumIconDifference) {
    throw "Branding validation failed: embedded executable icon difference $iconDifference exceeds $MaximumIconDifference"
}

Write-Host "Branding verified inside executable: $binary"
