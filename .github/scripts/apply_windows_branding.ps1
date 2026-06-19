param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryRoot,

    [Parameter(Mandatory = $false)]
    [string]$DistDir = "",

    [Parameter(Mandatory = $false)]
    [string]$IconBaseUrl = "false",

    [Parameter(Mandatory = $false)]
    [string]$IconUuid = "",

    [Parameter(Mandatory = $false)]
    [string]$IconFileName = "",

    [Parameter(Mandatory = $false)]
    [string]$LogoBaseUrl = "false",

    [Parameter(Mandatory = $false)]
    [string]$LogoUuid = "",

    [Parameter(Mandatory = $false)]
    [string]$LogoFileName = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-NormalizedPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,

        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )

    return [System.IO.Path]::GetFullPath((Join-Path $BasePath $RelativePath))
}

function Backup-IfExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathToBackup
    )

    # Резервную копию создаём только один раз, чтобы повторные прогоны брендинга
    # не засоряли дерево сборки каскадом лишних *.bak-файлов.
    if ((Test-Path $PathToBackup) -and -not (Test-Path "$PathToBackup.bak")) {
        Move-Item -LiteralPath $PathToBackup -Destination "$PathToBackup.bak" -Force
    }
}

function Ensure-ParentDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetPath
    )

    $parentDirectory = Split-Path -Path $TargetPath -Parent
    if ($parentDirectory -and -not (Test-Path $parentDirectory)) {
        New-Item -ItemType Directory -Path $parentDirectory -Force | Out-Null
    }
}

function Download-PngAsset {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BaseUrl,

        [Parameter(Mandatory = $true)]
        [string]$Uuid,

        [Parameter(Mandatory = $true)]
        [string]$FileName,

        [Parameter(Mandatory = $true)]
        [string]$DestinationPath
    )

    Ensure-ParentDirectory -TargetPath $DestinationPath

    # URL собираем через параметры, чтобы корректно переживать пробелы и спецсимволы
    # в имени загружаемого файла, который пришёл из интерфейса генератора.
    $query = "filename=$([System.Uri]::EscapeDataString($FileName))&uuid=$([System.Uri]::EscapeDataString($Uuid))"
    $assetUrl = "$BaseUrl/get_png?$query"
    Invoke-WebRequest -Uri $assetUrl -OutFile $DestinationPath
}

function New-EmbeddedSvgFromPng {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PngPath,

        [Parameter(Mandatory = $true)]
        [string]$SvgPath
    )

    $base64 = [Convert]::ToBase64String([System.IO.File]::ReadAllBytes($PngPath))
    $svgContent = @"
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <image href="data:image/png;base64,$base64" width="512" height="512" preserveAspectRatio="xMidYMid meet" />
</svg>
"@

    Ensure-ParentDirectory -TargetPath $SvgPath
    [System.IO.File]::WriteAllText($SvgPath, $svgContent, [System.Text.UTF8Encoding]::new($false))
}

function Set-FileFromSource {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourcePath,

        [Parameter(Mandatory = $true)]
        [string]$DestinationPath
    )

    Ensure-ParentDirectory -TargetPath $DestinationPath
    Backup-IfExists -PathToBackup $DestinationPath
    Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force
}

function New-DrawingRectangle {
    param(
        [Parameter(Mandatory = $true)]
        [int]$X,

        [Parameter(Mandatory = $true)]
        [int]$Y,

        [Parameter(Mandatory = $true)]
        [int]$Width,

        [Parameter(Mandatory = $true)]
        [int]$Height
    )

    return [System.Drawing.Rectangle]::new($X, $Y, $Width, $Height)
}

function Set-HighQualityGraphics {
    param(
        [Parameter(Mandatory = $true)]
        [System.Drawing.Graphics]$Graphics
    )

    # BMP для WiX очень примитивен, поэтому качество масштабирования и текста
    # нужно заранее настроить на нашей стороне, пока изображение ещё рендерится.
    $Graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $Graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $Graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $Graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
    $Graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
}

function Draw-ImageCover {
    param(
        [Parameter(Mandatory = $true)]
        [System.Drawing.Graphics]$Graphics,

        [Parameter(Mandatory = $true)]
        [System.Drawing.Image]$Image,

        [Parameter(Mandatory = $true)]
        [System.Drawing.Rectangle]$DestinationRectangle
    )

    # Режим cover нужен для квадратной иконки: она аккуратно встаёт в заданную область
    # без растягивания на весь фон и без пустых полос вокруг.
    $scale = [Math]::Max(
        $DestinationRectangle.Width / [double]$Image.Width,
        $DestinationRectangle.Height / [double]$Image.Height
    )

    $sourceWidth = [Math]::Min($Image.Width, [int][Math]::Round($DestinationRectangle.Width / $scale))
    $sourceHeight = [Math]::Min($Image.Height, [int][Math]::Round($DestinationRectangle.Height / $scale))
    $sourceX = [int][Math]::Max(0, [Math]::Round(($Image.Width - $sourceWidth) / 2))
    $sourceY = [int][Math]::Max(0, [Math]::Round(($Image.Height - $sourceHeight) / 2))
    $sourceRectangle = [System.Drawing.Rectangle]::new($sourceX, $sourceY, $sourceWidth, $sourceHeight)

    $Graphics.DrawImage($Image, $DestinationRectangle, $sourceRectangle, [System.Drawing.GraphicsUnit]::Pixel)
}

function Save-BitmapAsBmp {
    param(
        [Parameter(Mandatory = $true)]
        [System.Drawing.Bitmap]$Bitmap,

        [Parameter(Mandatory = $true)]
        [string]$DestinationPath
    )

    Ensure-ParentDirectory -TargetPath $DestinationPath
    Backup-IfExists -PathToBackup $DestinationPath
    $Bitmap.Save($DestinationPath, [System.Drawing.Imaging.ImageFormat]::Bmp)
}

function New-MsiBitmaps {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LogoSourcePath,

        [Parameter(Mandatory = $false)]
        [string]$IconSourcePath = "",

        [Parameter(Mandatory = $true)]
        [string]$ResourcesDirectory
    )

    Ensure-ParentDirectory -TargetPath (Join-Path $ResourcesDirectory "placeholder.tmp")

    $bannerPath = Join-Path $ResourcesDirectory "WixUIBannerBmp.bmp"
    $dialogPath = Join-Path $ResourcesDirectory "WixUIDialogBmp.bmp"

    Add-Type -AssemblyName System.Drawing

    # Для MSI-элементов держим приоритет на icon.png, потому что это компактный квадратный знак,
    # который лучше всего подходит и для узкого баннера, и для левой welcome-колонки.
    $resolvedIconPath = ""
    if ($IconSourcePath -and (Test-Path $IconSourcePath)) {
        $resolvedIconPath = $IconSourcePath
    }
    elseif ($LogoSourcePath -and (Test-Path $LogoSourcePath)) {
        $resolvedIconPath = $LogoSourcePath
    }

    $resolvedLogoPath = ""
    if ($LogoSourcePath -and (Test-Path $LogoSourcePath)) {
        $resolvedLogoPath = $LogoSourcePath
    }
    elseif ($resolvedIconPath) {
        $resolvedLogoPath = $resolvedIconPath
    }

    $iconImage = $null
    $logoImage = $null

    try {
        if ($resolvedIconPath) {
            $iconImage = [System.Drawing.Image]::FromFile($resolvedIconPath)
        }

        if ($resolvedLogoPath) {
            $logoImage = [System.Drawing.Image]::FromFile($resolvedLogoPath)
        }

        $bannerBitmap = [System.Drawing.Bitmap]::new(493, 58)
        $bannerGraphics = [System.Drawing.Graphics]::FromImage($bannerBitmap)

        try {
            Set-HighQualityGraphics -Graphics $bannerGraphics

            # Верхний баннер делаем в белой корпоративной стилистике:
            # мастер остаётся визуально чистым, а бренд живёт только в правом углу.
            $bannerGraphics.Clear([System.Drawing.ColorTranslator]::FromHtml("#ffffff"))

            $bannerDividerPen = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml("#d9dde6"), 1)
            $bannerGraphics.DrawLine($bannerDividerPen, 0, 57, 492, 57)
            $bannerDividerPen.Dispose()

            if ($iconImage) {
                $bannerIconRect = New-DrawingRectangle -X 444 -Y 12 -Width 28 -Height 28
                Draw-ImageCover -Graphics $bannerGraphics -Image $iconImage -DestinationRectangle $bannerIconRect
            }
            elseif ($logoImage) {
                $bannerIconRect = New-DrawingRectangle -X 444 -Y 12 -Width 28 -Height 28
                Draw-ImageCover -Graphics $bannerGraphics -Image $logoImage -DestinationRectangle $bannerIconRect
            }

            $bannerBrandTextFont = [System.Drawing.Font]::new("Segoe UI", 10, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
            $bannerBrandTextBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#2f3542"))
            $bannerGraphics.DrawString("NanoDesk", $bannerBrandTextFont, $bannerBrandTextBrush, 390, 18)
            $bannerBrandTextFont.Dispose()
            $bannerBrandTextBrush.Dispose()

            # Тонкая фиолетовая линия даёт фирменный акцент, но не превращает баннер в тяжёлую плашку.
            $bannerAccentPen = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml("#6b3dff"), 1)
            $bannerGraphics.DrawLine($bannerAccentPen, 390, 38, 436, 38)
            $bannerAccentPen.Dispose()

            Save-BitmapAsBmp -Bitmap $bannerBitmap -DestinationPath $bannerPath
        }
        finally {
            $bannerGraphics.Dispose()
            $bannerBitmap.Dispose()
        }

        $dialogBitmap = [System.Drawing.Bitmap]::new(493, 312)
        $dialogGraphics = [System.Drawing.Graphics]::FromImage($dialogBitmap)

        try {
            Set-HighQualityGraphics -Graphics $dialogGraphics

            # Welcome/finish-экран делаем ближе к mature software installer:
            # светлая колонка слева, тонкий вертикальный разделитель и компактный логотип с именем.
            $dialogGraphics.Clear([System.Drawing.ColorTranslator]::FromHtml("#ffffff"))

            $sidebarBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#f5f6f8"))
            $dialogGraphics.FillRectangle($sidebarBrush, 0, 0, 163, 312)
            $sidebarBrush.Dispose()

            $dialogDividerPen = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml("#d9dde6"), 1)
            $dialogGraphics.DrawLine($dialogDividerPen, 163, 0, 163, 311)
            $dialogDividerPen.Dispose()

            if ($iconImage) {
                $dialogIconRect = New-DrawingRectangle -X 28 -Y 146 -Width 32 -Height 32
                Draw-ImageCover -Graphics $dialogGraphics -Image $iconImage -DestinationRectangle $dialogIconRect
            }
            elseif ($logoImage) {
                $dialogLogoRect = New-DrawingRectangle -X 28 -Y 146 -Width 32 -Height 32
                Draw-ImageCover -Graphics $dialogGraphics -Image $logoImage -DestinationRectangle $dialogLogoRect
            }

            $dialogBrandTextFont = [System.Drawing.Font]::new("Segoe UI", 11, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
            $dialogBrandTextBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#2f3542"))
            $dialogGraphics.DrawString("NanoDesk", $dialogBrandTextFont, $dialogBrandTextBrush, 64, 154)
            $dialogBrandTextFont.Dispose()
            $dialogBrandTextBrush.Dispose()

            Save-BitmapAsBmp -Bitmap $dialogBitmap -DestinationPath $dialogPath
        }
        finally {
            $dialogGraphics.Dispose()
            $dialogBitmap.Dispose()
        }
    }
    finally {
        if ($iconImage) {
            $iconImage.Dispose()
        }

        if ($logoImage) {
            $logoImage.Dispose()
        }
    }
}

function Apply-BrandingToSourceTree {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootPath,

        [Parameter(Mandatory = $false)]
        [string]$DownloadedIconPath,

        [Parameter(Mandatory = $false)]
        [string]$DownloadedLogoPath
    )

    if ($DownloadedIconPath -and (Test-Path $DownloadedIconPath)) {
        $resIconPng = Get-NormalizedPath -BasePath $RootPath -RelativePath "res/icon.png"
        $resIconIco = Get-NormalizedPath -BasePath $RootPath -RelativePath "res/icon.ico"
        $trayIconIco = Get-NormalizedPath -BasePath $RootPath -RelativePath "res/tray-icon.ico"
        $icon32 = Get-NormalizedPath -BasePath $RootPath -RelativePath "res/32x32.png"
        $icon64 = Get-NormalizedPath -BasePath $RootPath -RelativePath "res/64x64.png"
        $icon128 = Get-NormalizedPath -BasePath $RootPath -RelativePath "res/128x128.png"
        $icon128x2 = Get-NormalizedPath -BasePath $RootPath -RelativePath "res/128x128@2x.png"

        # Квадратный icon.png остаётся первичным источником бренда для иконок,
        # tray-ресурсов и Windows runner-ресурсов.
        Set-FileFromSource -SourcePath $DownloadedIconPath -DestinationPath $resIconPng
        Backup-IfExists -PathToBackup $resIconIco
        Backup-IfExists -PathToBackup $trayIconIco
        Backup-IfExists -PathToBackup $icon32
        Backup-IfExists -PathToBackup $icon64
        Backup-IfExists -PathToBackup $icon128
        Backup-IfExists -PathToBackup $icon128x2

        magick $resIconPng -define icon:auto-resize=256,64,48,32,16 $resIconIco
        Copy-Item -LiteralPath $resIconIco -Destination $trayIconIco -Force
        magick $resIconPng -resize 32x32 $icon32
        magick $resIconPng -resize 64x64 $icon64
        magick $resIconPng -resize 128x128 $icon128
        magick $icon128 -resize 200% $icon128x2

        $runnerAppIcon = Get-NormalizedPath -BasePath $RootPath -RelativePath "flutter/windows/runner/resources/app_icon.ico"
        if (Test-Path $runnerAppIcon) {
            Set-FileFromSource -SourcePath $resIconIco -DestinationPath $runnerAppIcon
        }

        $flutterAssetsDir = Get-NormalizedPath -BasePath $RootPath -RelativePath "flutter/assets"
        if (Test-Path $flutterAssetsDir) {
            Set-FileFromSource -SourcePath $resIconPng -DestinationPath (Join-Path $flutterAssetsDir "icon.png")
            Set-FileFromSource -SourcePath $resIconIco -DestinationPath (Join-Path $flutterAssetsDir "icon.ico")

            $flutterIconSvg = Join-Path $flutterAssetsDir "icon.svg"
            Backup-IfExists -PathToBackup $flutterIconSvg
            New-EmbeddedSvgFromPng -PngPath $resIconPng -SvgPath $flutterIconSvg
        }

        $msiResourcesDir = Get-NormalizedPath -BasePath $RootPath -RelativePath "res/msi/Package/Resources"
        if (Test-Path (Split-Path $msiResourcesDir -Parent)) {
            Set-FileFromSource -SourcePath $resIconIco -DestinationPath (Join-Path $msiResourcesDir "icon.ico")
        }
    }

    if ($DownloadedLogoPath -and (Test-Path $DownloadedLogoPath)) {
        $flutterAssetsDir = Get-NormalizedPath -BasePath $RootPath -RelativePath "flutter/assets"
        if (Test-Path $flutterAssetsDir) {
            Set-FileFromSource -SourcePath $DownloadedLogoPath -DestinationPath (Join-Path $flutterAssetsDir "logo.png")
        }

        $msiResourcesDir = Get-NormalizedPath -BasePath $RootPath -RelativePath "res/msi/Package/Resources"
        if (Test-Path (Split-Path $msiResourcesDir -Parent)) {
            # MSI-ресурсы рендерим отдельно, а не просто копируем logo.png,
            # иначе мастер установки снова начинает растягивать графику в неподходящий формат.
            New-MsiBitmaps -LogoSourcePath $DownloadedLogoPath -IconSourcePath $DownloadedIconPath -ResourcesDirectory $msiResourcesDir
        }
    }
}

function Apply-BrandingToDistTree {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BuiltDistDir,

        [Parameter(Mandatory = $false)]
        [string]$DownloadedIconPath,

        [Parameter(Mandatory = $false)]
        [string]$DownloadedLogoPath
    )

    $distAssetsDir = Get-NormalizedPath -BasePath $BuiltDistDir -RelativePath "data/flutter_assets/assets"
    if (-not (Test-Path $distAssetsDir)) {
        return
    }

    if ($DownloadedIconPath -and (Test-Path $DownloadedIconPath)) {
        $distIconPng = Join-Path $distAssetsDir "icon.png"
        $distIconIco = Join-Path $distAssetsDir "icon.ico"
        $distIconSvg = Join-Path $distAssetsDir "icon.svg"

        Set-FileFromSource -SourcePath $DownloadedIconPath -DestinationPath $distIconPng
        Backup-IfExists -PathToBackup $distIconIco
        magick $DownloadedIconPath -define icon:auto-resize=256,64,48,32,16 $distIconIco
        Backup-IfExists -PathToBackup $distIconSvg
        New-EmbeddedSvgFromPng -PngPath $DownloadedIconPath -SvgPath $distIconSvg
    }

    if ($DownloadedLogoPath -and (Test-Path $DownloadedLogoPath)) {
        Set-FileFromSource -SourcePath $DownloadedLogoPath -DestinationPath (Join-Path $distAssetsDir "logo.png")
    }
}

$resolvedRepositoryRoot = [System.IO.Path]::GetFullPath($RepositoryRoot)
$brandingWorkDir = Get-NormalizedPath -BasePath $resolvedRepositoryRoot -RelativePath ".rdgen-branding"
New-Item -ItemType Directory -Path $brandingWorkDir -Force | Out-Null

$downloadedIconPath = $null
if ($IconBaseUrl -and $IconBaseUrl -ne "false" -and $IconUuid -and $IconFileName) {
    $downloadedIconPath = Join-Path $brandingWorkDir "icon.png"
    Download-PngAsset -BaseUrl $IconBaseUrl -Uuid $IconUuid -FileName $IconFileName -DestinationPath $downloadedIconPath
}

$downloadedLogoPath = $null
if ($LogoBaseUrl -and $LogoBaseUrl -ne "false" -and $LogoUuid -and $LogoFileName) {
    $downloadedLogoPath = Join-Path $brandingWorkDir "logo.png"
    Download-PngAsset -BaseUrl $LogoBaseUrl -Uuid $LogoUuid -FileName $LogoFileName -DestinationPath $downloadedLogoPath
}

Apply-BrandingToSourceTree -RootPath $resolvedRepositoryRoot -DownloadedIconPath $downloadedIconPath -DownloadedLogoPath $downloadedLogoPath

if ($DistDir) {
    $resolvedDistDir = [System.IO.Path]::GetFullPath((Join-Path $resolvedRepositoryRoot $DistDir))
    if (Test-Path $resolvedDistDir) {
        Apply-BrandingToDistTree -BuiltDistDir $resolvedDistDir -DownloadedIconPath $downloadedIconPath -DownloadedLogoPath $downloadedLogoPath
    }
}
