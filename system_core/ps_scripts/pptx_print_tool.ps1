param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('enable-default','print-input','restore-default','doctor')]
    [string]$Action,

    [switch]$SkipExisting
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir '..\..')
$ConfigPath = Join-Path $ProjectRoot 'config\settings.json'
$StateDir = Join-Path $ProjectRoot 'state'
$StatePath = Join-Path $StateDir 'printer_state.json'
$InputDir = if ([string]::IsNullOrWhiteSpace($env:AUDION_SOURCE_PATH)) { Join-Path $ProjectRoot 'input' } else { $env:AUDION_SOURCE_PATH }
$OutputDir = if ([string]::IsNullOrWhiteSpace($env:AUDION_TARGET_PATH)) { Join-Path $ProjectRoot 'output' } else { $env:AUDION_TARGET_PATH }
$LogsDir = Join-Path $ProjectRoot 'logs'
$LogPath = Join-Path $LogsDir ('session_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.log')

New-Item -ItemType Directory -Force -Path $StateDir, $OutputDir, $LogsDir | Out-Null
if (-not (Test-Path -LiteralPath $InputDir)) {
    New-Item -ItemType Directory -Force -Path $InputDir | Out-Null
}

function Write-LogLine {
    param([string]$Message)
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LogPath -Value ("[$stamp] $Message") -Encoding UTF8
}

function Test-GuiAnsiTerminal {
    return ($env:AUDION_GUI_TERMINAL -eq '1' -or $env:FORCE_COLOR -eq '1' -or $env:CLICOLOR_FORCE -eq '1')
}

function Write-TerminalLine {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Sgr
    )
    if (Test-GuiAnsiTerminal) {
        $esc = [char]27
        [Console]::Out.WriteLine("$esc" + "[$Sgr" + "m" + $Text + "$esc" + "[0m")
    }
    else {
        Write-Host $Text
    }
}

function Write-Info { param([string]$Message) Write-TerminalLine "[INFO] $Message" "36"; Write-LogLine "INFO  $Message" }
function Write-Ok   { param([string]$Message) Write-TerminalLine "[OK]   $Message" "32"; Write-LogLine "OK    $Message" }
function Write-Warn { param([string]$Message) Write-TerminalLine "[WARN] $Message" "33"; Write-LogLine "WARN  $Message" }
function Write-Bad  { param([string]$Message) Write-TerminalLine "[ERROR] $Message" "31"; Write-LogLine "ERROR $Message" }

function Load-Config {
    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        return [pscustomobject]@{
            pdf_printer_name = 'Microsoft Print to PDF'
            paper_size = 'Legal'
            landscape = $true
            save_dialog_timeout_sec = 20
            save_dialog_title_patterns = @('Save Print Output As','Save Print Output','Сохранение результата печати как','Сохранение результата печати','Печать в файл')
        }
    }

    return Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

$Config = Load-Config
$PdfPrinterName = [string]$Config.pdf_printer_name

function Test-IsAdmin {
    $current = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($current)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-PrinterSafe {
    param([string]$Name)
    try {
        return Get-Printer -Name $Name -ErrorAction Stop
    }
    catch {
        return $null
    }
}

function Get-DefaultPrinterName {
    try {
        $printer = Get-Printer | Where-Object { $_.Default -eq $true } | Select-Object -First 1
        if ($null -ne $printer) {
            return [string]$printer.Name
        }
    }
    catch {
    }

    try {
        $printer = Get-CimInstance -ClassName Win32_Printer | Where-Object { $_.Default -eq $true } | Select-Object -First 1
        if ($null -ne $printer) {
            return [string]$printer.Name
        }
    }
    catch {
    }

    return ''
}

function Set-DefaultPrinterByName {
    param([Parameter(Mandatory = $true)][string]$Name)

    try {
        $null = Get-Printer -Name $Name -ErrorAction Stop
    }
    catch {
        throw "Printer not found: $Name"
    }

    try {
        $network = New-Object -ComObject WScript.Network
        $network.SetDefaultPrinter($Name)
        return
    }
    catch {
    }

    $printer = Get-CimInstance -ClassName Win32_Printer | Where-Object { $_.Name -eq $Name } | Select-Object -First 1
    if ($null -eq $printer) {
        throw "Printer not found for CIM fallback: $Name"
    }

    $null = Invoke-CimMethod -InputObject $printer -MethodName SetDefaultPrinter
}

function Save-State {
    param([string]$PreviousDefaultPrinter)

    $payload = [pscustomobject]@{
        previous_default_printer = $PreviousDefaultPrinter
        saved_at = (Get-Date).ToString('s')
    }
    $payload | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding UTF8
}

function Get-State {
    if (-not (Test-Path -LiteralPath $StatePath)) {
        return $null
    }

    try {
        return Get-Content -LiteralPath $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Ensure-PreviousPrinterSaved {
    $current = Get-DefaultPrinterName
    if ([string]::IsNullOrWhiteSpace($current)) {
        return
    }

    if ($current -ieq $PdfPrinterName) {
        return
    }

    Save-State -PreviousDefaultPrinter $current
    Write-Ok "Saved previous default printer: $current"
}

function Ensure-MicrosoftPrintToPdfInstalled {
    $printer = Get-PrinterSafe -Name $PdfPrinterName
    if ($null -ne $printer) {
        Write-Ok "$PdfPrinterName is already available."
        return
    }

    if (-not (Test-IsAdmin)) {
        throw "Administrator rights are required to enable Microsoft Print to PDF."
    }

    Write-Info "Trying to enable Microsoft Print to PDF feature..."
    $featureNames = @(
        'Printing-PrintToPDFServices-Features',
        'Printing-PrintToPDFServices-Package',
        'Microsoft-Windows-Printing-PrintToPDFServices-Package'
    )

    $enabled = $false
    foreach ($feature in $featureNames) {
        try {
            Enable-WindowsOptionalFeature -Online -FeatureName $feature -All -NoRestart -ErrorAction Stop | Out-Null
            $enabled = $true
            Write-Ok "Feature enable command accepted: $feature"
            break
        }
        catch {
            Write-Warn "Feature name did not work: $feature"
        }
    }

    Start-Sleep -Seconds 2
    $printer = Get-PrinterSafe -Name $PdfPrinterName
    if ($null -eq $printer) {
        if ($enabled) {
            throw "$PdfPrinterName feature was enabled, but the printer is still not visible yet. A reboot may be required."
        }
        throw "$PdfPrinterName is still missing."
    }

    Write-Ok "$PdfPrinterName is available."
}

$printerModeSource = @"
using System;
using System.Runtime.InteropServices;

public static class PrinterDevModeHelper
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    public struct DEVMODE
    {
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string dmDeviceName;
        public short dmSpecVersion;
        public short dmDriverVersion;
        public short dmSize;
        public short dmDriverExtra;
        public int dmFields;
        public short dmOrientation;
        public short dmPaperSize;
        public short dmPaperLength;
        public short dmPaperWidth;
        public short dmScale;
        public short dmCopies;
        public short dmDefaultSource;
        public short dmPrintQuality;
        public short dmColor;
        public short dmDuplex;
        public short dmYResolution;
        public short dmTTOption;
        public short dmCollate;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string dmFormName;
        public short dmLogPixels;
        public int dmBitsPerPel;
        public int dmPelsWidth;
        public int dmPelsHeight;
        public int dmDisplayFlags;
        public int dmDisplayFrequency;
        public int dmICMMethod;
        public int dmICMIntent;
        public int dmMediaType;
        public int dmDitherType;
        public int dmReserved1;
        public int dmReserved2;
        public int dmPanningWidth;
        public int dmPanningHeight;
    }

    private const int DM_OUT_BUFFER = 0x2;
    private const int DM_IN_BUFFER = 0x8;
    private const int DM_ORIENTATION = 0x1;
    private const int DM_PAPERSIZE = 0x2;
    private const short DMORIENT_LANDSCAPE = 2;
    private const short DMPAPER_LEGAL = 5;

    [DllImport("winspool.drv", CharSet = CharSet.Auto, SetLastError = true)]
    private static extern bool OpenPrinter(string pPrinterName, out IntPtr phPrinter, IntPtr pDefault);

    [DllImport("winspool.drv", SetLastError = true)]
    private static extern bool ClosePrinter(IntPtr hPrinter);

    [DllImport("winspool.drv", CharSet = CharSet.Auto, SetLastError = true)]
    private static extern int DocumentProperties(IntPtr hwnd, IntPtr hPrinter, string pDeviceName, IntPtr pDevModeOutput, IntPtr pDevModeInput, int fMode);

    public static bool SetLegalLandscape(string printerName)
    {
        IntPtr handle;
        if (!OpenPrinter(printerName, out handle, IntPtr.Zero))
        {
            return false;
        }

        try
        {
            int size = DocumentProperties(IntPtr.Zero, handle, printerName, IntPtr.Zero, IntPtr.Zero, 0);
            if (size <= 0)
            {
                return false;
            }

            IntPtr ptr = Marshal.AllocHGlobal(size);
            try
            {
                int r1 = DocumentProperties(IntPtr.Zero, handle, printerName, ptr, IntPtr.Zero, DM_OUT_BUFFER);
                if (r1 < 0)
                {
                    return false;
                }

                DEVMODE dm = (DEVMODE)Marshal.PtrToStructure(ptr, typeof(DEVMODE));
                dm.dmFields |= DM_ORIENTATION | DM_PAPERSIZE;
                dm.dmOrientation = DMORIENT_LANDSCAPE;
                dm.dmPaperSize = DMPAPER_LEGAL;
                Marshal.StructureToPtr(dm, ptr, true);

                int r2 = DocumentProperties(IntPtr.Zero, handle, printerName, ptr, ptr, DM_IN_BUFFER | DM_OUT_BUFFER);
                return r2 >= 0;
            }
            finally
            {
                Marshal.FreeHGlobal(ptr);
            }
        }
        finally
        {
            ClosePrinter(handle);
        }
    }
}
"@

try {
    Add-Type -TypeDefinition $printerModeSource -Language CSharp -ErrorAction Stop | Out-Null
}
catch {
    Write-Warn 'PrinterDevModeHelper was not compiled. Legal landscape will be best-effort only.'
}

function Set-PdfPrinterDefaults {
    $printer = Get-PrinterSafe -Name $PdfPrinterName
    if ($null -eq $printer) {
        throw "$PdfPrinterName is not installed."
    }

    try {
        Set-PrintConfiguration -PrinterName $PdfPrinterName -PaperSize Legal -ErrorAction Stop | Out-Null
        Write-Ok 'Paper size set to Legal.'
    }
    catch {
        Write-Warn 'Set-PrintConfiguration could not set Legal paper size. Continuing.'
    }

    try {
        $result = [PrinterDevModeHelper]::SetLegalLandscape($PdfPrinterName)
        if ($result) {
            Write-Ok 'Landscape + Legal printer defaults were applied.'
        }
        else {
            Write-Warn 'Landscape enforcement did not confirm success. Continuing.'
        }
    }
    catch {
        Write-Warn 'Landscape enforcement failed. Continuing.'
    }
}

function Resolve-PowerShellHostPath {
    $projectPortablePwsh = Join-Path $ProjectRoot 'system_core\powershell\pwsh.exe'
    if (Test-Path -LiteralPath $projectPortablePwsh) {
        return $projectPortablePwsh
    }

    try {
        $currentProcess = Get-Process -Id $PID -ErrorAction Stop
        if (-not [string]::IsNullOrWhiteSpace($currentProcess.Path) -and (Test-Path -LiteralPath $currentProcess.Path)) {
            return $currentProcess.Path
        }
    }
    catch {
    }

    $pwshCommand = Get-Command 'pwsh.exe' -ErrorAction SilentlyContinue
    if ($null -ne $pwshCommand -and -not [string]::IsNullOrWhiteSpace($pwshCommand.Source)) {
        return $pwshCommand.Source
    }

    $powershellCommand = Get-Command 'powershell.exe' -ErrorAction SilentlyContinue
    if ($null -ne $powershellCommand -and -not [string]::IsNullOrWhiteSpace($powershellCommand.Source)) {
        return $powershellCommand.Source
    }

    throw 'PowerShell host was not resolved.'
}

$PowerShellHostPath = Resolve-PowerShellHostPath

function New-PowerPointApplication {
    $app = New-Object -ComObject PowerPoint.Application
    $app.DisplayAlerts = 1
    return $app
}

function Release-ComObject {
    param($Object)

    if ($null -ne $Object) {
        try {
            [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($Object)
        }
        catch {
        }
    }
}

function Set-ClipboardTextSafe {
    param(
        [Parameter(Mandatory = $true)][string]$Text
    )

    try {
        Set-Clipboard -Value $Text -ErrorAction Stop
        return $true
    }
    catch {
    }

    try {
        [System.Windows.Forms.Clipboard]::SetText($Text)
        return $true
    }
    catch {
    }

    return $false
}



function Print-OnePresentation {
    param(
        [Parameter(Mandatory = $true)]$PowerPoint,
        [Parameter(Mandatory = $true)][string]$InputPath,
        [Parameter(Mandatory = $true)][int]$Index,
        [Parameter(Mandatory = $true)][int]$Total
    )

    $source = Get-Item -LiteralPath $InputPath
    $baseName = $source.BaseName
    $outputPath = Join-Path $OutputDir ($baseName + '.pdf')

    if ($SkipExisting -and (Test-Path -LiteralPath $outputPath)) {
        Write-Ok "[$Index/$Total] Skipped existing PDF: $outputPath"
        return
    }

    $clipboardOk = Set-ClipboardTextSafe -Text $outputPath

    Write-Host ""
    Write-Host "------------------------------------------------------------------"
    Write-Info "[$Index/$Total] Printing: $($source.Name)"
    Write-Info "Suggested output folder: $OutputDir"
    Write-Info "Suggested output name  : $(Split-Path -Leaf $outputPath)"
    if ($clipboardOk) {
        Write-Ok "Copied full PDF path to clipboard: $outputPath"
        Write-Warn 'In the Microsoft Print to PDF dialog: press Ctrl+V, then Enter.'
    }
    else {
        Write-Warn "Clipboard copy failed. Type this path manually: $outputPath"
    }
    Write-Warn 'Save the PDF manually.'
    Write-Warn 'After the PDF is fully saved, return to the GUI and confirm.'
    Write-Host "------------------------------------------------------------------"
    Write-Host ""

    $presentation = $null

    try {
        $presentation = $PowerPoint.Presentations.Open($source.FullName, $true, $false, $false)

        try {
            $presentation.PrintOptions.ActivePrinter = $PdfPrinterName
        }
        catch {
            Write-Warn 'PrintOptions.ActivePrinter was not changed directly. Using current default printer.'
        }

        try {
            $presentation.PrintOptions.FitToPage = $true
        }
        catch {
        }

        $presentation.PrintOut()

        [void](Read-Host "Press Enter after saving the PDF")

        if (-not (Test-Path -LiteralPath $outputPath)) {
            throw "PDF was not found after confirmation: $outputPath"
        }
        $saved = Get-Item -LiteralPath $outputPath
        if ($saved.Length -le 0) {
            throw "PDF is empty after confirmation: $outputPath"
        }
        Write-Ok "[$Index/$Total] $outputPath"
    }
    finally {
        if ($null -ne $presentation) {
            try {
                $presentation.Close()
            }
            catch {
            }
            Release-ComObject -Object $presentation
        }
    }
}

function Get-InputPresentations

 {
    $source = Get-Item -LiteralPath $InputDir
    if ($source.PSIsContainer) {
        $files = Get-ChildItem -LiteralPath $source.FullName -File |
            Where-Object { $_.Extension -in '.pptx', '.pptm' } |
            Sort-Object Name
    }
    elseif ($source.Extension -in '.pptx', '.pptm') {
        $files = @($source)
    }
    else {
        $files = @()
    }
    return @($files)
}



function Run-PrintInput {
    $current = Get-DefaultPrinterName
    if ($current -ine $PdfPrinterName) {
        throw "$PdfPrinterName is not the current default printer. Run enable-default first."
    }

    $files = @(Get-InputPresentations)
    if (@($files).Count -eq 0) {
        throw 'No PPTX or PPTM files were found in input.'
    }

    Write-Info "Batch count: $(@($files).Count)"
    Write-Info "Suggested output dir: $OutputDir"
    Write-Info "Skip existing PDFs: $SkipExisting"
    Write-Warn 'For each PPTX: save the PDF manually, then confirm in GUI or press Enter.'

    $app = $null
    try {
        $app = New-PowerPointApplication
        try { $app.Visible = 0 } catch {}
        $index = 0
        foreach ($file in $files) {
            $index += 1
            Print-OnePresentation -PowerPoint $app -InputPath $file.FullName -Index $index -Total @($files).Count
        }
    }
    finally {
        if ($null -ne $app) {
            try { $app.Quit() } catch {}
            Release-ComObject -Object $app
            [GC]::Collect()
            [GC]::WaitForPendingFinalizers()
        }
    }
}

function Run-EnableDefault

 {
    Ensure-MicrosoftPrintToPdfInstalled
    Ensure-PreviousPrinterSaved
    Set-DefaultPrinterByName -Name $PdfPrinterName
    Write-Ok "$PdfPrinterName is now the default printer."
    Set-PdfPrinterDefaults
}

function Run-RestoreDefault {
    $state = Get-State
    if ($null -eq $state) {
        Write-Warn 'No saved printer state was found.'
        return
    }

    $previous = [string]$state.previous_default_printer
    if ([string]::IsNullOrWhiteSpace($previous)) {
        Write-Warn 'Saved state does not contain a printer name.'
        return
    }

    $printer = Get-PrinterSafe -Name $previous
    if ($null -eq $printer) {
        throw "Saved previous printer is no longer available: $previous"
    }

    Set-DefaultPrinterByName -Name $previous
    Write-Ok "Restored default printer: $previous"
}

function Run-Doctor {
    Write-Info "Project root    : $ProjectRoot"
    Write-Info "Input dir       : $InputDir"
    Write-Info "Output dir      : $OutputDir"
    Write-Info "State path      : $StatePath"
    Write-Info "Log path        : $LogPath"
    Write-Info "PowerShell host : $PowerShellHostPath"
    Write-Info "Default printer : $(Get-DefaultPrinterName)"

    $printer = Get-PrinterSafe -Name $PdfPrinterName
    if ($null -eq $printer) {
        Write-Warn "$PdfPrinterName is missing."
    }
    else {
        Write-Ok "$PdfPrinterName is installed."
    }

    $probe = $null
    try {
        $probe = New-Object -ComObject PowerPoint.Application
        Write-Ok 'PowerPoint COM is available.'
    }
    catch {
        Write-Bad 'PowerPoint COM is not available.'
    }
    finally {
        if ($null -ne $probe) {
            try { $probe.Quit() } catch {}
            Release-ComObject -Object $probe
        }
    }

    $state = Get-State
    if ($null -eq $state) {
        Write-Warn 'No previous printer state saved yet.'
    }
    else {
        Write-Info "Saved previous printer: $($state.previous_default_printer)"
        Write-Info "Saved at             : $($state.saved_at)"
    }
}

try {
    Write-Info "Action: $Action"
    switch ($Action) {
        'enable-default' { Run-EnableDefault }
        'print-input'    { Run-PrintInput }
        'restore-default'{ Run-RestoreDefault }
        'doctor'         { Run-Doctor }
        default          { throw "Unsupported action: $Action" }
    }
    exit 0
}
catch {
    Write-Bad $_.Exception.Message
    exit 1
}
