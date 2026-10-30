# 一键用本地模型跑修复环（需要先安装 Ollama 并 pull 模型）
param(
    [string]$Model = "qwen2.5-coder:7b",
    [string]$Jar = "D:/TLA/tla2tools.jar",
    [string]$Specs = "benchmark/specs",
    [int]$MaxRounds = 5
)

$ErrorActionPreference = "Stop"

# 1. 检查 Ollama 服务是否在运行
$ollamaUp = $false
$tags = $null
try {
    $tags = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3
    $ollamaUp = $true
} catch {
    Write-Host "[!] Ollama 服务未运行。请先启动 Ollama（桌面图标，或在终端执行 ollama serve）。" -ForegroundColor Yellow
}

# 2. 若服务在运行但模型缺失，自动 pull
if ($ollamaUp) {
    $names = @($tags.models.name)
    if ($names -notcontains $Model) {
        Write-Host "[*] 模型 $Model 不存在，正在 pull（首次较慢）..." -ForegroundColor Yellow
        ollama pull $Model
    }
} else {
    Write-Host "[!] 跳过模型检查。请先启动 Ollama 后再运行本脚本。" -ForegroundColor Yellow
}

# 3. 运行修复环
$env:DEEPSEEK_API_KEY = "ollama"
python repair_loop.py `
    --jar $Jar `
    --specs $Specs `
    --max-rounds $MaxRounds `
    --base-url http://localhost:11434/v1 `
    --model $Model
