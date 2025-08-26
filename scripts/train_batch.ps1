
param(
  [string]$Cfg = "configs\ml.yaml",
  [string]$Symbols = "",
  [int]$TopN = 20,
  [switch]$Fast
)

$py = ".\.venv\Scripts\python.exe"
if (!(Test-Path $py)) { $py = "python" }

$cmd = "$py -m pro_ml.tools.train_batch --cfg `"$Cfg`""
if ($Symbols -ne "") { $cmd += " --symbols `"$Symbols`"" }
if ($TopN -gt 0) { $cmd += " --topN $TopN" }
if ($Fast) { $cmd += " --fast" }

Write-Host "Running: $cmd"
Invoke-Expression $cmd
