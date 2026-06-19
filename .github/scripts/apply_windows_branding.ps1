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

    # Резервную копию исходного файла создаём только один раз, чтобы можно было
    # спокойно сравнивать результат брендинга без накопления цепочки *.bak.
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

    # URL собираем через параметры, чтобы не ломаться на пробелах и спецсимволах
    # в имени файла, которое приходит из интерфейса rdgen.
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

function New-RoundedRectanglePath {
    param(
        [Parameter(Mandatory = $true)]
        [System.Drawing.Rectangle]$Rectangle,

        [Parameter(Mandatory = $true)]
        [int]$Radius
    )

    $diameter = [Math]::Max(2, $Radius * 2)
    $path = [System.Drawing.Drawing2D.GraphicsPath]::new()

    # Скруглённую карточку собираем вручную, чтобы одинаково использовать её
    # и в узком баннере, и в вертикальной welcome-полосе MSI.
    $path.AddArc($Rectangle.X, $Rectangle.Y, $diameter, $diameter, 180, 90)
    $path.AddArc($Rectangle.Right - $diameter, $Rectangle.Y, $diameter, $diameter, 270, 90)
    $path.AddArc($Rectangle.Right - $diameter, $Rectangle.Bottom - $diameter, $diameter, $diameter, 0, 90)
    $path.AddArc($Rectangle.X, $Rectangle.Bottom - $diameter, $diameter, $diameter, 90, 90)
    $path.CloseFigure()

    return $path
}

function Set-HighQualityGraphics {
    param(
        [Parameter(Mandatory = $true)]
        [System.Drawing.Graphics]$Graphics
    )

    # Включаем качественный рендер, потому что WiX принимает только BMP, а значит
    # сглаживание и ресемплинг нужно контролировать на нашей стороне.
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

    # Режим cover не даёт логотипу или иконке растягиваться на весь фон, а вместо этого
    # аккуратно вписывает исходное изображение в заданную область.
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

    # Для баннера и welcome-полосы отдельно определяем, чем именно рисовать бренд:
    # иконка приоритетна как главный квадратный знак, а логотип остаётся запасным источником.
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

            # Верхний баннер оставляем безопасным для MSI: слева светлая служебная зона,
            # справа компактный бренд-блок с иконкой, именем и тонким акцентом.
            $bannerGraphics.Clear([System.Drawing.ColorTranslator]::FromHtml("#f7f7f7"))

            $bannerBrandRect = New-DrawingRectangle -X 316 -Y 0 -Width 177 -Height 58
            $bannerGradient = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
                $bannerBrandRect,
                [System.Drawing.ColorTranslator]::FromHtml("#17385f"),
                [System.Drawing.ColorTranslator]::FromHtml("#102947"),
                0
            )
            $bannerGraphics.FillRectangle($bannerGradient, $bannerBrandRect)
            $bannerGradient.Dispose()

            $bannerAccentBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#2d6fe5"))
            $bannerGraphics.FillRectangle($bannerAccentBrush, 316, 0, 6, 58)
            $bannerAccentBrush.Dispose()

            $bannerCardRect = New-DrawingRectangle -X 330 -Y 9 -Width 152 -Height 40
            $bannerCardPath = New-RoundedRectanglePath -Rectangle $bannerCardRect -Radius 8
            $bannerCardBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(28, 255, 255, 255))
            $bannerCardBorder = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(22, 255, 255, 255), 1)
            $bannerGraphics.FillPath($bannerCardBrush, $bannerCardPath)
            $bannerGraphics.DrawPath($bannerCardBorder, $bannerCardPath)
            $bannerCardBrush.Dispose()
            $bannerCardBorder.Dispose()
            $bannerCardPath.Dispose()

            if ($iconImage) {
                $bannerIconRect = New-DrawingRectangle -X 334 -Y 14 -Width 28 -Height 28
                Draw-ImageCover -Graphics $bannerGraphics -Image $iconImage -DestinationRectangle $bannerIconRect
            }
            elseif ($logoImage) {
                $bannerIconRect = New-DrawingRectangle -X 334 -Y 14 -Width 28 -Height 28
                Draw-ImageCover -Graphics $bannerGraphics -Image $logoImage -DestinationRectangle $bannerIconRect
            }

            $bannerFont = [System.Drawing.Font]::new("Segoe UI", 17, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
            $bannerTextBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#f6f8ff"))
            $bannerGraphics.DrawString("NanoDesk", $bannerFont, $bannerTextBrush, 368, 15)
            $bannerFont.Dispose()
            $bannerTextBrush.Dispose()

            $bannerLinePen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(120, 77, 139, 255), 1)
            $bannerGraphics.DrawLine($bannerLinePen, 368, 42, 472, 42)
            $bannerLinePen.Dispose()

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

            # Welcome/finish-экран оформляем только слева, чтобы правая штатная область MSI
            # оставалась полностью читаемой и бренд не спорил с системным текстом.
            $dialogGraphics.Clear([System.Drawing.ColorTranslator]::FromHtml("#f7f7f7"))

            $sidebarRect = New-DrawingRectangle -X 0 -Y 0 -Width 163 -Height 312
            $sidebarGradient = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
                $sidebarRect,
                [System.Drawing.ColorTranslator]::FromHtml("#17385f"),
                [System.Drawing.ColorTranslator]::FromHtml("#102743"),
                90
            )
            $dialogGraphics.FillRectangle($sidebarGradient, $sidebarRect)
            $sidebarGradient.Dispose()

            $sidebarAccentBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#2d6fe5"))
            $dialogGraphics.FillRectangle($sidebarAccentBrush, 163, 0, 7, 312)
            $sidebarAccentBrush.Dispose()

            $glowBrush = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
                [System.Drawing.Rectangle]::new(118, 0, 52, 312),
                [System.Drawing.Color]::FromArgb(0, 77, 139, 255),
                [System.Drawing.Color]::FromArgb(110, 77, 139, 255),
                0
            )
            $dialogGraphics.FillRectangle($glowBrush, 118, 0, 52, 312)
            $glowBrush.Dispose()

            $panelRect = New-DrawingRectangle -X 16 -Y 20 -Width 132 -Height 270
            $panelPath = New-RoundedRectanglePath -Rectangle $panelRect -Radius 14
            $panelBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(26, 255, 255, 255))
            $panelBorder = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(22, 255, 255, 255), 1)
            $dialogGraphics.FillPath($panelBrush, $panelPath)
            $dialogGraphics.DrawPath($panelBorder, $panelPath)
            $panelBrush.Dispose()
            $panelBorder.Dispose()
            $panelPath.Dispose()

            $topCardRect = New-DrawingRectangle -X 28 -Y 34 -Width 108 -Height 96
            $topCardPath = New-RoundedRectanglePath -Rectangle $topCardRect -Radius 12
            $topCardGradient = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
                $topCardRect,
                [System.Drawing.Color]::FromArgb(54, 255, 255, 255),
                [System.Drawing.Color]::FromArgb(24, 128, 86, 255),
                90
            )
            $dialogGraphics.FillPath($topCardGradient, $topCardPath)
            $topCardGradient.Dispose()
            $topCardPath.Dispose()

            if ($iconImage) {
                $dialogIconRect = New-DrawingRectangle -X 34 -Y 44 -Width 92 -Height 92
                Draw-ImageCover -Graphics $dialogGraphics -Image $iconImage -DestinationRectangle $dialogIconRect
            }
            elseif ($logoImage) {
                $dialogLogoRect = New-DrawingRectangle -X 30 -Y 52 -Width 104 -Height 72
                Draw-ImageCover -Graphics $dialogGraphics -Image $logoImage -DestinationRectangle $dialogLogoRect
            }

            $dialogFont = [System.Drawing.Font]::new("Segoe UI", 20, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
            $dialogTextBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#f6f8ff"))
            $dialogGraphics.DrawString("NanoDesk", $dialogFont, $dialogTextBrush, 28, 164)
            $dialogFont.Dispose()
            $dialogTextBrush.Dispose()

            $dividerPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(44, 120, 88, 255), 2)
            $dialogGraphics.DrawLine($dividerPen, 24, 200, 140, 200)
            $dividerPen.Dispose()

            $patternPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(46, 77, 139, 255), 2)
            $patternDotBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(72, 77, 139, 255))
            foreach ($lineY in @(226, 244, 262, 280)) {
                # Нижний тех-паттерн добавляет стиль полосе, но не превращает её в тяжёлый постер.
                $dialogGraphics.DrawLine($patternPen, 36, $lineY, 128, $lineY)
                $dialogGraphics.FillEllipse($patternDotBrush, 28, $lineY - 3, 6, 6)
            }
            $patternPen.Dispose()
            $patternDotBrush.Dispose()

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

        # Исходный icon.png остаётся главным квадратным брендовым ассетом, поэтому
        # обновляем из него все платформенные производные файлы проекта.
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
            # MSI-ресурсы строим отдельным рендером, а не просто копированием logo.png,
            # иначе WiX снова начнёт растягивать бренд в неподходящий формат.
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
