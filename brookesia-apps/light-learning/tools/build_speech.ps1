$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$learningPack = Join-Path $PSScriptRoot '../packs/starter'
$learningData = Get-Content -LiteralPath (Join-Path $learningPack 'pack.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$learningSynth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$learningFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono)
try {
    $learningSynth.Rate = -2
    $learningSynth.Volume = 70
    foreach ($learningCard in $learningData.cards) {
        $learningSynth.SelectVoice('Microsoft Huihui Desktop')
        $learningSynth.SetOutputToWaveFile((Join-Path $learningPack $learningCard.audio),$learningFormat)
        $learningSynth.Speak($learningCard.name)
        $learningSynth.SelectVoice('Microsoft Zira Desktop')
        $learningSynth.Speak($learningCard.english)
        $learningSynth.SetOutputToNull()
    }
    foreach ($learningCard in $learningData.english) {
        $learningSynth.SelectVoice('Microsoft Zira Desktop')
        $learningSynth.SetOutputToWaveFile((Join-Path $learningPack $learningCard.audio),$learningFormat)
        $learningSynth.Speak($learningCard.text)
        $learningSynth.SetOutputToNull()
    }
} finally {
    $learningSynth.Dispose()
}
