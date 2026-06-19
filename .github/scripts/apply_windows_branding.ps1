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

    # Сохраняем исходный файл только один раз, чтобы можно было спокойно
    # запускать скрипт повторно без размножения *.bak и без шума в сборке.
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

    # Явно собираем URL через параметры, чтобы исключить ошибки со склейкой
    # строки и получить предсказуемый путь до PNG на rdgen.
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

    # WiX подхватывает кастомные bitmap-ресурсы только если они реально лежат
    # в каталоге Package/Resources, поэтому создаём обе стандартные картинки
    # установщика из пользовательского логотипа.
    $bannerPath = Join-Path $ResourcesDirectory "WixUIBannerBmp.bmp"
    $dialogPath = Join-Path $ResourcesDirectory "WixUIDialogBmp.bmp"

    # Размеры берём из документации WiX/WixUI:
    # `WixUIBannerBmp` должен быть `493x58`, а `WixUIDialogBmp` должен быть `493x312`.
    # Именно эти размеры ожидает мастер установки, поэтому так мы избегаем
    # растяжения, обрезки и наезда брендовой графики на системный текст.

    # Для верхнего баннера больше не вставляем широкий логотип как есть,
    # потому что на высоте 58px он легко обрезается и выглядит «криво».
    # Вместо этого собираем компактный header: слева светлая системная зона,
    # а справа небольшой фирменный блок с иконкой и названием продукта.
    if ($IconSourcePath -and (Test-Path $IconSourcePath)) {
        magick `
            -size 493x58 xc:"#f7f7f7" `
            -fill "#13345a" -draw "rectangle 316,0 492,57" `
            -fill "#2d6fe5" -draw "rectangle 316,0 321,57" `
            -fill "rgba(255,255,255,0.08)" -draw "rectangle 330,9 482,48" `
            "$IconSourcePath" -resize 28x28^> `
            -gravity northwest -geometry +332+14 -composite `
            -font "Segoe UI" -fill "#f6f8ff" -pointsize 18 -gravity northwest -annotate +368+18 "NanoDesk" `
            -stroke "rgba(77,139,255,0.45)" -strokewidth 1 -draw "line 368,42 472,42" `
            -alpha off -type TrueColor `
            "bmp3:$bannerPath"
    }
    else {
        # Если иконка недоступна, используем безопасный fallback:
        # помещаем широкий логотип только в правую бренд-зону и не даём
        # ему залезать в системную часть баннера.
        magick `
            -size 493x58 xc:"#f7f7f7" `
            -fill "#13345a" -draw "rectangle 316,0 492,57" `
            -fill "#2d6fe5" -draw "rectangle 316,0 321,57" `
            "$LogoSourcePath" -resize 120x24^> `
            -gravity east -geometry +12+0 -composite `
            -alpha off -type TrueColor `
            "bmp3:$bannerPath"
    }

    # Для welcome/finish/license-фона больше не используем широкий логотип как
    # полноценный фон: из-за прозрачного полотна и крупного wordmark он визуально
    # растягивается на всю зону мастера и лезет под системный текст.
    #
    # Возвращаемся к логике, максимально похожей на стандартный MSI-мастер:
    # слева узкая бренд-полоса, а справа светлая спокойная область под системный
    # текст. Так мастер выглядит привычно, а бренд остаётся аккуратным акцентом,
    # а не фоновым изображением.
    $dialogSourcePath = $LogoSourcePath
    $dialogResize = "120x54^>"
    $dialogComposite = "+24+104"

    if ($IconSourcePath -and (Test-Path $IconSourcePath)) {
        # Квадратная иконка лучше подходит для левой колонки welcome/finish-экрана:
        # она не оставляет длинный хвост текста и не создаёт ощущение «растянутого фона».
        $dialogSourcePath = $IconSourcePath
        $dialogResize = "92x92^>"
        $dialogComposite = "+34+110"
    }

    # Полосу собираем в несколько слоёв: глубокая база, тонкая световая кромка,
    # полупрозрачная внутренняя карточка, заметная иконка и подпись NanoDesk.
    # Это делает welcome-экран полноценным бренд-элементом, а не пустым блоком.
    magick `
        -size 493x312 xc:"#f7f7f7" `
        -fill "#112846" -draw "rectangle 0,0 163,311" `
        -fill "#2a5ea1" -draw "rectangle 164,0 170,311" `
        -fill "rgba(255,255,255,0.10)" -draw "rectangle 16,20 148,290" `
        -fill "rgba(255,255,255,0.08)" -draw "rectangle 16,20 148,132" `
        -stroke "rgba(255,255,255,0.12)" -strokewidth 1 -fill none -draw "rectangle 16,20 148,290" `
        -stroke "rgba(77,139,255,0.22)" -strokewidth 2 -draw "line 34,226 128,226 line 34,244 128,244 line 34,262 128,262 line 34,280 128,280" `
        -fill "rgba(77,139,255,0.28)" -draw "circle 46,226 49,226 circle 46,244 49,244 circle 46,262 49,262 circle 46,280 49,280" `
        "$dialogSourcePath" -resize $dialogResize `
        -gravity northwest -geometry $dialogComposite -composite `
        -font "Segoe UI" -fill "#f6f8ff" -pointsize 20 -gravity northwest -annotate +32+155 "NanoDesk" `
        -fill "rgba(255,255,255,0.68)" -pointsize 11 -annotate +34+178 "Безопасное администрирование" `
        -alpha off -type TrueColor `
        "bmp3:$dialogPath"
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
