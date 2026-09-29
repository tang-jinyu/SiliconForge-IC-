[CmdletBinding()]
param(
    [string]$Output = "dist/video/SiliconForge_Introduction_CN.mp4",
    [switch]$ReuseRenderedClips
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Assets = Join-Path $Root "video_assets"
$OutputPath = [System.IO.Path]::GetFullPath((Join-Path $Root $Output))
$OutputRoot = [System.IO.Path]::GetFullPath((Join-Path $Root "dist\video"))
if (-not $OutputPath.StartsWith($OutputRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Output must stay inside dist/video."
}
New-Item -ItemType Directory -Path $Assets -Force | Out-Null
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Ffmpeg = "C:\Users\27882\AppData\Local\JianyingPro\Apps\10.5.0.13988\ffmpeg.exe"
if (-not (Test-Path -LiteralPath $Python)) { throw "Python environment is missing: $Python" }
if (-not (Test-Path -LiteralPath $Ffmpeg)) { throw "FFmpeg is missing: $Ffmpeg" }

if (-not $ReuseRenderedClips) {
    & $Python (Join-Path $PSScriptRoot "render_intro_assets.py")
    if ($LASTEXITCODE -ne 0) { throw "Scene rendering failed." }
}

$Narration = @(
    "如果大模型写出一段RTL，谁来证明它真的正确？",
    "语言模型可以生成看似合理的代码，但对于芯片设计，答案必须经过可重复的工程验证。",
    "SiliconForge把需求理解、RTL生成、测试平台生成与EDA工具连接成一个完整闭环。",
    "从自然语言需求开始，系统生成结构化规格、可综合RTL和自检测试平台。每个节点都有明确的输入、输出和失败边界。",
    "当真实仿真发现错误，任务不会被包装成成功。失败日志会成为下一轮修复的直接证据。",
    "Agent读取错误位置和接口约束，只修改相关逻辑，再使用原测试重新回归，完整保存每一次差异。",
    "仿真与综合共同通过，才算真正完成。阶段一的三个确定性基线案例已经全部通过，平均得分一百。",
    "同时，技能目录、安全扫描、可重复评测、产物摘要和最小权限，让每次能力调用都可以追溯。",
    "工程已经完成跨平台与容器化准备。Windows负责开发和演示，迁移包不包含密钥；双H100本地模型将在服务器上完成真实验证。",
    "SiliconForge。让每一条RTL结论，都有证据支持。"
)

if (-not $ReuseRenderedClips) {
    Add-Type -AssemblyName System.Speech
    $Voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $Voice.SelectVoice("Microsoft Huihui Desktop")
    $Voice.Rate = 0
    $Voice.Volume = 100
    for ($i = 0; $i -lt $Narration.Count; $i++) {
        $Wav = Join-Path $Assets ("voice_{0:D2}.wav" -f ($i + 1))
        $Voice.SetOutputToWaveFile($Wav)
        $Voice.Speak($Narration[$i])
        $Voice.SetOutputToNull()
    }
    $Voice.Dispose()
}

$Durations = & $Python -c @'
import json, sys, wave
from pathlib import Path
p=Path(sys.argv[1])
out=[]
for i in range(1,11):
    with wave.open(str(p/f"voice_{i:02d}.wav"),'rb') as w:
        out.append(round(w.getnframes()/w.getframerate()+0.8,3))
print(json.dumps(out))
'@ $Assets
$SceneDurations = $Durations | ConvertFrom-Json

$ClipList = Join-Path $Assets "clips.txt"
$ClipLines = @()
for ($i = 1; $i -le 10; $i++) {
    $Scene = Join-Path $Assets ("scene_{0:D2}.png" -f $i)
    $VoiceWav = Join-Path $Assets ("voice_{0:D2}.wav" -f $i)
    $Clip = Join-Path $Assets ("clip_{0:D2}.mp4" -f $i)
    $Duration = [double]$SceneDurations[$i - 1]
    $FadeOut = [Math]::Max(0.1, $Duration - 0.35)
    $Frames = [Math]::Ceiling($Duration * 30)
    $Zoom = if (($i % 2) -eq 0) { "min(zoom+0.00035,1.035)" } else { "min(zoom+0.00025,1.025)" }
    $Filter = "scale=2016:1134,zoompan=z='$Zoom':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${Frames}:s=1920x1080:fps=30,fade=t=in:st=0:d=0.35,fade=t=out:st=${FadeOut}:d=0.35,format=yuv420p"
    if (-not $ReuseRenderedClips) {
        & $Ffmpeg -y -hide_banner -loglevel error -loop 1 -i $Scene -i $VoiceWav -vf $Filter -af "apad=pad_dur=0.8,afade=t=out:st=${FadeOut}:d=0.3" -t $Duration -c:v h264_nvenc -preset p5 -b:v 6M -maxrate 8M -bufsize 12M -c:a aac -b:a 192k $Clip
        if ($LASTEXITCODE -ne 0) { throw "Failed to render clip $i" }
    } elseif (-not (Test-Path -LiteralPath $Clip)) {
        throw "Reusable clip is missing: $Clip"
    }
    $ClipLines += "file '$($Clip.Replace("'", "''"))'"
}
[System.IO.File]::WriteAllLines($ClipList, $ClipLines, [System.Text.UTF8Encoding]::new($false))

$Joined = Join-Path $Assets "joined.mp4"
& $Ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i $ClipList -c copy $Joined
if ($LASTEXITCODE -ne 0) { throw "Clip concatenation failed." }

$TotalDuration = ($SceneDurations | Measure-Object -Sum).Sum
$Bgm = Join-Path $Assets "bgm.wav"
& $Python (Join-Path $PSScriptRoot "generate_ambient.py") $Bgm $TotalDuration
if ($LASTEXITCODE -ne 0) { throw "Background audio generation failed." }

& $Ffmpeg -y -hide_banner -loglevel error -i $Joined -i $Bgm -filter_complex "[0:a]volume=1.0[voice];[1:a]volume=0.65[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=2[aout]" -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 224k -movflags +faststart $OutputPath
if ($LASTEXITCODE -ne 0) { throw "Final video mix failed." }

$Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $OutputPath
Write-Host "Video: $OutputPath"
Write-Host "Duration: $([Math]::Round($TotalDuration, 1)) seconds"
Write-Host "SHA256: $($Hash.Hash)"
