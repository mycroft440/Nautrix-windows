param(
    [string]$Output = "$env:LOCALAPPDATA\Nautrix\nic-diagnostics.txt"
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Output) | Out-Null

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("Nautrix Windows/NIC low-latency diagnostics")
$lines.Add("Generated: $(Get-Date -Format o)")
$lines.Add("Read-only: this tool does not modify Windows or adapter settings.")
$lines.Add("")

$adapters = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object Status -eq 'Up'
foreach ($adapter in $adapters) {
    $lines.Add("Adapter: $($adapter.Name)")
    $lines.Add("  InterfaceDescription: $($adapter.InterfaceDescription)")
    $lines.Add("  LinkSpeed: $($adapter.LinkSpeed)")

    $rss = Get-NetAdapterRss -Name $adapter.Name -ErrorAction SilentlyContinue
    if ($rss) {
        $lines.Add("  RSS Enabled: $($rss.Enabled)")
        $lines.Add("  RSS Queues: $($rss.NumberOfReceiveQueues)")
    }

    $rsc = Get-NetAdapterRsc -Name $adapter.Name -ErrorAction SilentlyContinue
    if ($rsc) {
        $lines.Add("  RSC IPv4: $($rsc.IPv4Enabled)")
        $lines.Add("  RSC IPv6: $($rsc.IPv6Enabled)")
    }

    $advanced = Get-NetAdapterAdvancedProperty -Name $adapter.Name -ErrorAction SilentlyContinue
    foreach ($propertyName in @('Interrupt Moderation','Interrupt Moderation Rate','Energy Efficient Ethernet','Green Ethernet','Receive Buffers','Transmit Buffers')) {
        $match = $advanced | Where-Object DisplayName -eq $propertyName | Select-Object -First 1
        if ($match) { $lines.Add("  $propertyName: $($match.DisplayValue)") }
    }
    $lines.Add("")
}

$tcp = netsh int tcp show global 2>&1
$lines.Add("TCP global settings:")
foreach ($line in $tcp) { $lines.Add("  $line") }
$lines.Add("")
$lines.Add("Interpretation:")
$lines.Add("- Interrupt Moderation may reduce CPU/interrupt rate but can add latency; measure before changing it.")
$lines.Add("- RSC can improve throughput/CPU efficiency but can be unfavorable to some low-throughput latency-sensitive workloads.")
$lines.Add("- RSS should normally remain enabled on modern multi-core systems.")
$lines.Add("- Nautrix intentionally does not change any of these values automatically.")

$lines | Set-Content -LiteralPath $Output -Encoding utf8
Write-Host "[Nautrix] NIC diagnostics written to $Output"
