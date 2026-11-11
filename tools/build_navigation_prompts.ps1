param([Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Path $Output -Force | Out-Null
$synth=New-Object System.Speech.Synthesis.SpeechSynthesizer
$format=New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono)
$actions=@('请继续直行','请向左转','请向右转','请向左前方行进','请向右前方行进','请掉头','已到达目的地','请按照手机导航提示行进')
$texts=[ordered]@{}
try {
 $synth.SelectVoice('Microsoft Huihui Desktop');$synth.Rate=0;$synth.Volume=80
 for($turn=0;$turn -lt 8;$turn++) {
  for($stage=0;$stage -lt 3;$stage++) {
   $prefix=if($turn -ge 6 -or $stage -eq 0){''}elseif($stage -eq 1){'前方一百米，'}else{'即将到达路口，'}
   $words=$prefix+$actions[$turn]+'。';$name='turn-'+$turn+'-'+$stage+'.wav'
   $synth.SetOutputToWaveFile((Join-Path $Output $name),$format);$synth.Speak($words);$synth.SetOutputToNull()
   $texts[$name]=$words
  }
 }
} finally {$synth.Dispose()}
$manifest=[ordered]@{voice='Microsoft Huihui Desktop';synthesis='Windows System.Speech, offline';format='16000 Hz signed 16-bit mono WAV';phrases=$texts}
[IO.File]::WriteAllText((Join-Path $Output 'sources.json'),($manifest | ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
Write-Output 'Generated 24 local Chinese navigation phrases; no cloud requests.'
