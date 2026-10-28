# Animal name recordings — starter 1.2.0

The six animal cards use actual human speech recordings. Each card plays the whole Mandarin word recording, 450ms of silence, then the whole US English word recording. No text-to-speech model, voice cloning, pitch shift, time stretching or syllable assembly is used. Files are resampled to mono 16kHz PCM16 WAV and their playback levels are adjusted.

The output recordings `starter/audio/card-*.wav` are adaptations licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The original recordings retain the individual licenses below. The license does not extend to unrelated application code or photographs. Attribution, download URLs, original hashes, output hashes and segment frame counts are distributed with the SD pack in `audio-sources.json`.

| Card | Human Mandarin recording | Human English recording |
| --- | --- | --- |
| 猫 / Cat | [猫](https://github.com/hugolpz/audio-cmn/blob/master/96k/hsk/cmn-%E7%8C%AB.mp3), Yue Tan | [Cat](https://commons.wikimedia.org/wiki/File:En-us-cat.ogg), Dvortygirl |
| 狗 / Dog | [狗](https://github.com/hugolpz/audio-cmn/blob/master/96k/hsk/cmn-%E7%8B%97.mp3), Yue Tan | [Dog](https://commons.wikimedia.org/wiki/File:En-us-dog.ogg), Dvortygirl |
| 牛 / Cow | [牛](https://github.com/hugolpz/audio-cmn/blob/master/96k/hsk/cmn-%E7%89%9B.mp3), Yue Tan | [Cow](https://commons.wikimedia.org/wiki/File:En-us-cow.ogg), Dvortygirl |
| 马 / Horse | [马](https://github.com/hugolpz/audio-cmn/blob/master/96k/hsk/cmn-%E9%A9%AC.mp3), Yue Tan | [Horse](https://commons.wikimedia.org/wiki/File:En-us-horse.ogg), Dvortygirl |
| 兔子 / Rabbit | [兔子](https://github.com/hugolpz/audio-cmn/blob/master/96k/hsk/cmn-%E5%85%94%E5%AD%90.mp3), Yue Tan | [Rabbit](https://commons.wikimedia.org/wiki/File:En-us-rabbit.ogg), Dvortygirl |
| 鸭 / Duck | [yā](https://commons.wikimedia.org/wiki/File:Zh-y%C4%81.ogg), Wei Gao / Vion Nicolas | [Duck](https://commons.wikimedia.org/wiki/File:En-us-duck.ogg), Dvortygirl |

- Mandarin: Copyright 2009 Yue Tan, University of Caen / Shtooka, [CC BY-SA 3.0 US](https://creativecommons.org/licenses/by-sa/3.0/us/). The [audio-cmn](https://github.com/hugolpz/audio-cmn) mirror was curated and compressed by Hugo Lopez, with technical support from Nicolas Vion.
- Mandarin yā: Copyright 2006 Wei Gao and Vion Nicolas, Shtooka chi-balm-hsk1, [CC BY 2.0 FR](https://creativecommons.org/licenses/by/2.0/fr/). The original is labeled 呀 (yā), a Mandarin homophone of 鸭 (yā). Its complete human utterance is used, without joining separate syllables.
- English: Dvortygirl (Betsy Megas), original recordings on Wikimedia Commons, [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/), selected from their offered licenses.

Rebuild the cards with `tools/build_recordings.py --ffmpeg <ffmpeg executable> --cache <private source cache>`. Source hashes are verified before decoding. Keep downloads and conversion caches outside Git. `tools/build_speech.ps1` now generates only the separate English practice samples and cannot overwrite the human card recordings.

The eight English practice samples in this release retain their existing Windows Zira synthesis; this change replaces the six animal-name recordings. Microphone repeat/replay remains local and ungraded.
