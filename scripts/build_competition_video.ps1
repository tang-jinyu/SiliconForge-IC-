[CmdletBinding()]
param(
    [string]$Output = "dist/video/SiliconForge_Competition_Demo_CN.mp4"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Assets = Join-Path $Root "video_assets\competition"
$OutputPath = [System.IO.Path]::GetFullPath((Join-Path $Root $Output))
$OutputRoot = [System.IO.Path]::GetFullPath((Join-Path $Root "dist\video"))
if (-not $OutputPath.StartsWith($OutputRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "输出文件必须位于 dist/video。"
}
New-Item -ItemType Directory -Path $Assets -Force | Out-Null
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Ffmpeg = "C:\Users\27882\AppData\Local\JianyingPro\Apps\10.5.0.13988\ffmpeg.exe"
if (-not (Test-Path -LiteralPath $Ffmpeg)) { throw "未找到 FFmpeg：$Ffmpeg" }

& $Python (Join-Path $PSScriptRoot "render_competition_video_assets.py")
if ($LASTEXITCODE -ne 0) { throw "画面资产生成失败。" }

$Narration = @(
    "这是 SiliconForge。它不只生成代码，而是把每一条 RTL 结论交给工具验证。",
    "大模型写出的 RTL 可能隐藏位宽、复位和握手错误。对芯片设计而言，生成结果不是工程结论。",
    "SiliconForge 把需求、代码、测试平台、仿真、综合和自动修复放进同一个中文工作台。",
    "用户只需粘贴赛题。以六十六位乘法器为例，接口、位宽、规格、RTL 和测试平台都由智能体设计。",
    "新问题走模型生成，常见问题优先命中模板。两条路径都必须通过真实仿真和综合，失败则进入局部修复。",
    "五类常见电路已参数化。修改位宽、深度或序列后重新验证；模板命中时不调用模型，Token 消耗为零。",
    "每个任务对应一个交付目录。RTL、测试平台、规格、日志和质量报告集中保存，并支持一键下载。",
    "工作台内置文件树和编辑器。修改代码后可直接重跑仿真与综合，让人工编辑也服从同一质量门。",
    "实测数据如实保留：确定性基线三项全过，五个模板全过，六十六位乘法器闭环通过。首轮五类模型盲测仅一项通过、均分二十八，这些失败成为下一轮优化基线。",
    "我们对齐 Verified Skills 的编目、扫描、评估、签名和文档化。当前已有本地证据，外部签名待接入，因此不宣称获得官方认证。",
    "工程解耦应用、模型和工具链。先在 Windows 跑通产品，再把无密钥迁移包部署到双 H100 服务器。",
    "SiliconForge，从赛题到可验证交付。让每一行 RTL，都经过工具证明。"
)

Add-Type -AssemblyName System.Speech
$Voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$Voice.SelectVoice("Microsoft Huihui Desktop")
$Voice.Rate = 1
$Voice.Volume = 100
for ($i = 0; $i -lt $Narration.Count; $i++) {
    $Wav = Join-Path $Assets ("voice_{0:D2}.wav" -f ($i + 1))
    $Voice.SetOutputToWaveFile($Wav)
    $Voice.Speak($Narration[$i])
    $Voice.SetOutputToNull()
}
$Voice.Dispose()

$DurationsJson = & $Python -c @'
import json, sys, wave
from pathlib import Path
p=Path(sys.argv[1]); out=[]
for i in range(1,13):
    with wave.open(str(p/f"voice_{i:02d}.wav"),'rb') as w:
        out.append(round(w.getnframes()/w.getframerate()+0.7,3))
print(json.dumps(out))
'@ $Assets
$Durations = $DurationsJson | ConvertFrom-Json
$ClipList = Join-Path $Assets "clips.txt"
$ClipLines = @()

for ($i = 1; $i -le 12; $i++) {
    $Scene = Join-Path $Assets ("scene_{0:D2}.png" -f $i)
    $VoiceWav = Join-Path $Assets ("voice_{0:D2}.wav" -f $i)
    $Clip = Join-Path $Assets ("clip_{0:D2}.mp4" -f $i)
    $Duration = [double]$Durations[$i - 1]
    $FadeOut = [Math]::Max(0.1, $Duration - 0.30)
    $Frames = [Math]::Ceiling($Duration * 30)
    # GUI scenes stay perfectly framed; other scenes use a restrained push-in.
    if ($i -in 3,4,6,7,8) {
        $VideoFilter = "scale=1920:1080,fade=t=in:st=0:d=0.25,fade=t=out:st=${FadeOut}:d=0.30,format=yuv420p"
    } else {
        $VideoFilter = "scale=1960:1103,zoompan=z='min(zoom+0.00018,1.018)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${Frames}:s=1920x1080:fps=30,fade=t=in:st=0:d=0.25,fade=t=out:st=${FadeOut}:d=0.30,format=yuv420p"
    }
    & $Ffmpeg -y -hide_banner -loglevel error -loop 1 -i $Scene -i $VoiceWav -vf $VideoFilter -af "apad=pad_dur=0.7,afade=t=out:st=${FadeOut}:d=0.25" -t $Duration -c:v h264_nvenc -preset p5 -b:v 5M -maxrate 7M -bufsize 10M -c:a aac -b:a 192k $Clip
    if ($LASTEXITCODE -ne 0) { throw "第 $i 段渲染失败。" }
    $ClipLines += "file '$($Clip.Replace("'", "''"))'"
}
[System.IO.File]::WriteAllLines($ClipList, $ClipLines, [System.Text.UTF8Encoding]::new($false))

$Joined = Join-Path $Assets "joined.mp4"
& $Ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i $ClipList -c copy $Joined
if ($LASTEXITCODE -ne 0) { throw "视频拼接失败。" }

$TotalDuration = ($Durations | Measure-Object -Sum).Sum
$Bgm = Join-Path $Assets "bgm.wav"
& $Python (Join-Path $PSScriptRoot "generate_ambient.py") $Bgm $TotalDuration
if ($LASTEXITCODE -ne 0) { throw "背景音乐生成失败。" }

& $Ffmpeg -y -hide_banner -loglevel error -i $Joined -i $Bgm -filter_complex "[0:a]volume=1.0[voice];[1:a]volume=0.36[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=2[aout]" -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k $OutputPath
if ($LASTEXITCODE -ne 0) { throw "最终音轨混合失败。" }

$Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $OutputPath
Write-Host "Video: $OutputPath"
Write-Host "Duration: $([Math]::Round($TotalDuration, 1)) seconds"
Write-Host "SHA256: $($Hash.Hash)"
