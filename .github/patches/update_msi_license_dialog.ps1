param(
    [Parameter(Mandatory = $true)]
    [string]$MsiPath,

    [string]$LicensePath,

    [switch]$VerifyOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Open-MsiDatabase {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [int]$Mode
    )

    # Открываем MSI через штатный COM API Windows Installer,
    # чтобы движок сам корректно обновил таблицы, строковый пул и служебные индексы.
    $installer = New-Object -ComObject WindowsInstaller.Installer
    $database = $null
    $lastError = $null

    # MSI после транзакционного обновления может ещё короткое время удерживаться системой.
    # Небольшой retry делает проверку стабильной и убирает случайные падения на file lock.
    for ($attempt = 1; $attempt -le 10; $attempt++) {
        try {
            $database = $installer.GetType().InvokeMember(
                'OpenDatabase',
                'InvokeMethod',
                $null,
                $installer,
                @($Path, $Mode)
            )
            break
        }
        catch {
            $lastError = $_
            Start-Sleep -Milliseconds 200
        }
    }

    if ($null -eq $database) {
        throw $lastError
    }

    return @{
        Installer = $installer
        Database  = $database
    }
}

function Get-MsiSingleValue {
    param(
        [Parameter(Mandatory = $true)]
        $Database,

        [Parameter(Mandatory = $true)]
        [string]$Query
    )

    # Для коротких проверок читаем одно значение из MSI-таблицы.
    # Этого достаточно, чтобы валидировать ProductCode и сам текст лицензии.
    $view = $Database.OpenView($Query)
    $record = $null
    try {
        [void]$view.Execute()
        $record = $view.Fetch()
        if ($null -eq $record) {
            return ''
        }

        return $record.GetType().InvokeMember('StringData', 'GetProperty', $null, $record, 1)
    }
    finally {
        [void]$view.Close()
        if ($null -ne $record) {
            [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($record)
        }
        if ($null -ne $view) {
            [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($view)
        }
    }
}

function Set-MsiLicenseText {
    param(
        [Parameter(Mandatory = $true)]
        $Installer,

        [Parameter(Mandatory = $true)]
        $Database,

        [Parameter(Mandatory = $true)]
        [string]$LicenseText
    )

    # Обновляем именно поле Control.Text у LicenseAgreementDlg/LicenseText.
    # Это штатное место, из которого MSI-диалог читает RTF-лицензию при показе окна установки.
    $query = "SELECT Text FROM Control WHERE Dialog_='LicenseAgreementDlg' AND Control='LicenseText'"
    $view = $Database.OpenView($query)
    $record = $null
    try {
        # Сначала читаем существующую запись диалога, а затем обновляем её через Modify.
        # Такой путь корректно поддерживается Windows Installer Automation API.
        [void]$view.Execute()
        $record = $view.Fetch()
        if ($null -eq $record) {
            throw 'LicenseAgreementDlg/LicenseText row was not found in MSI Control table.'
        }

        $record.GetType().InvokeMember('StringData', 'SetProperty', $null, $record, @(1, $LicenseText))
        [void]$view.Modify(2, $record)
    }
    finally {
        [void]$view.Close()
        if ($null -ne $record) {
            [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($record)
        }
        if ($null -ne $view) {
            [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($view)
        }
    }

    # Коммитим транзакцию только после успешного обновления поля,
    # чтобы не оставить MSI в промежуточном или частично изменённом состоянии.
    [void]$Database.Commit()
}

function Test-MsiIntegrity {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    # Читаем именно те поля MSI-базы, которые реально участвуют в показе лицензионного окна и запуске установки.
    # Это точнее, чем глобальный поиск по бинарнику, потому что в MSI могут оставаться неиспользуемые строки.
    $dbInfo = Open-MsiDatabase -Path $Path -Mode 0
    try {
        $productCode = Get-MsiSingleValue -Database $dbInfo.Database -Query "SELECT Value FROM Property WHERE Property='ProductCode'"
        if ([string]::IsNullOrWhiteSpace($productCode)) {
            throw 'MSI ProductCode is empty.'
        }

        $licenseText = Get-MsiSingleValue -Database $dbInfo.Database -Query "SELECT Text FROM Control WHERE Dialog_='LicenseAgreementDlg' AND Control='LicenseText'"
        if ([string]::IsNullOrWhiteSpace($licenseText)) {
            throw 'MSI license dialog text is empty.'
        }

        if ($licenseText.Contains('https://NanoDesk.')) {
            throw 'Legacy NanoDesk URL is still present in MSI license dialog.'
        }

        if ($licenseText.Contains('rdgen.NanoDesk/privacy.html')) {
            throw 'Legacy privacy URL is still present in MSI license dialog.'
        }

        if (-not $licenseText.Contains('https://nanodesk.ru')) {
            throw 'Canonical NanoDesk URL is missing in MSI license dialog.'
        }
    }
    finally {
        if ($null -ne $dbInfo.Database) {
            [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($dbInfo.Database)
        }
        if ($null -ne $dbInfo.Installer) {
            [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($dbInfo.Installer)
        }
    }

    # Затем просим сам Windows Installer выполнить административное развёртывание.
    # Если ProductCode, таблицы или строковый пул повреждены, здесь прилетит тот же 1605/1603,
    # который видит пользователь при запуске сломанного MSI.
    $verificationRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("rdgen-msi-check-" + [Guid]::NewGuid().ToString('N'))
    $targetDir = Join-Path $verificationRoot 'target'
    $logPath = Join-Path $verificationRoot 'msiexec.log'
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

    try {
        $process = Start-Process msiexec.exe -ArgumentList @(
            '/a',
            $Path,
            "TARGETDIR=$targetDir",
            '/qn',
            '/l*v',
            $logPath
        ) -Wait -PassThru

        if ($process.ExitCode -ne 0) {
            $tail = ''
            if (Test-Path -LiteralPath $logPath) {
                $tail = (Get-Content -LiteralPath $logPath -Tail 60) -join [Environment]::NewLine
            }

            throw "Windows Installer validation failed with exit code $($process.ExitCode).`n$tail"
        }

        Write-Host 'Verified MSI payload and Windows Installer execution successfully.'
    }
    finally {
        if (Test-Path -LiteralPath $verificationRoot) {
            Remove-Item -LiteralPath $verificationRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

if (-not (Test-Path -LiteralPath $MsiPath)) {
    throw "MSI file not found: $MsiPath"
}

if (-not $VerifyOnly) {
    if ([string]::IsNullOrWhiteSpace($LicensePath)) {
        throw 'LicensePath is required when VerifyOnly is not set.'
    }

    if (-not (Test-Path -LiteralPath $LicensePath)) {
        throw "License file not found: $LicensePath"
    }

    # Читаем уже подготовленный License.rtf из рабочего дерева сборки.
    # Этот файл ранее нормализуется нашими шагами и содержит нужный русский текст.
    $licenseText = Get-Content -LiteralPath $LicensePath -Raw

    $dbInfo = Open-MsiDatabase -Path $MsiPath -Mode 1
    try {
        Set-MsiLicenseText -Installer $dbInfo.Installer -Database $dbInfo.Database -LicenseText $licenseText
    }
    finally {
        if ($null -ne $dbInfo.Database) {
            [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($dbInfo.Database)
        }
        if ($null -ne $dbInfo.Installer) {
            [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($dbInfo.Installer)
        }
    }

    Write-Host 'MSI license dialog text updated successfully.'

    # После транзакционного обновления даём COM-объектам гарантированно освободить файл,
    # чтобы следующая проверка не упала на повторном открытии MSI из-за временной блокировки.
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    Start-Sleep -Milliseconds 200
}

if ($VerifyOnly) {
    Test-MsiIntegrity -Path $MsiPath
}
