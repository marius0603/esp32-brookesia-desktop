param([Parameter(Mandatory=$true)][string]$Output,[switch]$DiagnosticsOnly)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Path $Output -Force | Out-Null
$voicePromptDir=Join-Path $Output 'prompts'
$voiceDiagnosticDir=Join-Path $Output 'diagnostic'
New-Item -ItemType Directory -Path $voicePromptDir,$voiceDiagnosticDir -Force | Out-Null
$synth=New-Object System.Speech.Synthesis.SpeechSynthesizer
$voiceFormat=New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono)
function Get-VoicePcm([string]$Words) {
 $stream=New-Object IO.MemoryStream
 try {
  $synth.SetOutputToAudioStream($stream,$voiceFormat)
  $synth.Speak($Words)
  $synth.SetOutputToNull()
  return ,$stream.ToArray()
 } finally {$stream.Dispose()}
}
function Get-ChineseNumber([int]$Number) {
 $digits=@('零','一','二','三','四','五','六','七','八','九')
 if($Number -lt 10){return $digits[$Number]}
 $tens=[int][Math]::Floor($Number/10);$ones=$Number%10
 $word=if($tens -eq 1){'十'}else{$digits[$tens]+'十'}
 if($ones -gt 0){$word+=$digits[$ones]};return $word
}
try {
 $synth.SelectVoice('Microsoft Huihui Desktop');$synth.Rate=-2;$synth.Volume=75
 if(-not $DiagnosticsOnly){
 for($number=0;$number -le 46;$number++) {
  $words=if($number -eq 0){'还没有设置睡眠定时。'}elseif($number -eq 46){'还剩不到一分钟。'}else{'还剩'+(Get-ChineseNumber $number)+'分钟。'}
  $pcm=Get-VoicePcm $words
  [IO.File]::WriteAllBytes((Join-Path $voicePromptDir ('remaining-{0:00}.pcm' -f $number)),$pcm)
 }
 }
 $commands=@('讲故事','暂停故事','还要听','下一篇','大声一点','小声点','我要睡觉了','还剩几分钟','我想吃苹果','今天天气不错','一二三四五')
 # Digital fixtures exercise inference, separately from physical microphone/child testing.
 $wake=Get-VoicePcm '你好小智。'
 for($id=1;$id -le $commands.Count;$id++) {
  $speech=Get-VoicePcm $commands[$id-1]
  $stream=New-Object IO.MemoryStream
  try {
   $silence=New-Object byte[] 16000
   $stream.Write($silence,0,$silence.Length);$stream.Write($wake,0,$wake.Length)
   $stream.Write($silence,0,$silence.Length);$stream.Write($speech,0,$speech.Length)
   $stream.Write($silence,0,$silence.Length)
   [IO.File]::WriteAllBytes((Join-Path $voiceDiagnosticDir ('test-{0:00}.pcm' -f $id)),$stream.ToArray())
  }finally{$stream.Dispose()}
 }
}finally{$synth.Dispose()}
$voiceFiles=[ordered]@{}
foreach($voiceFile in (Get-ChildItem -LiteralPath $Output -Recurse -Filter '*.pcm' | Sort-Object FullName)) {
 $relative=$voiceFile.FullName.Substring([IO.Path]::GetFullPath($Output).TrimEnd('\').Length+1).Replace('\','/')
 $voiceFiles[$relative]=[ordered]@{bytes=$voiceFile.Length;sha256=(Get-FileHash -LiteralPath $voiceFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
}
$voiceCases=[ordered]@{}
for($id=1;$id -le $commands.Count;$id++){$voiceCases[('diagnostic/test-{0:00}.pcm' -f $id)]=$commands[$id-1]}
$voiceMetadata=[ordered]@{test_texts=$voiceCases;format='16000 Hz signed 16-bit mono raw PCM';voice='Microsoft Huihui Desktop';rate=-2;files=$voiceFiles}
[IO.File]::WriteAllText((Join-Path $Output 'audio.json'),($voiceMetadata | ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
Write-Output 'Updated offline audio manifest; generated 11 digital fixtures including 3 unrelated phrases.'
