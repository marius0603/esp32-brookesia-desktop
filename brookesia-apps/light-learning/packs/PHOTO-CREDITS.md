# Animal photograph credits — starter 1.1.0

The animal cards use real photographs, not generated animals. Each photograph was resized, fitted without cropping onto a 256×192 background, and converted to PNG. The derived photo retains the license listed below. Padding is part of the display asset. The source URLs, original SHA256 values and changes are also included in `photo-sources.json`, distributed with the SD content pack.

| Asset | Photographer | Original photograph | License for the photo and resized copy |
| --- | --- | --- | --- |
| cat.png | Alvesgaspar | [Cat November 2010-1a](https://commons.wikimedia.org/wiki/File:Cat_November_2010-1a.jpg) | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |
| dog.png | Jiyoon Leee | [Sitting golden retriever](https://commons.wikimedia.org/wiki/File:Sitting_golden_retriever.jpg) | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |
| cow.png | Hokkaido-man | [Holstein cow](https://commons.wikimedia.org/wiki/File:Holstein_cow.jpg) | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |
| horse.png | Flocci Nivis | [20181129 White Horse](https://commons.wikimedia.org/wiki/File:20181129_White_Horse.jpg) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| rabbit.png | Miscellaneous contributor | [Rabbit on grass (2)](https://commons.wikimedia.org/wiki/File:Rabbit_on_grass_(2).jpg) | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |
| duck.png | I13Robin | [2014-08-31-domestic-duck](https://commons.wikimedia.org/wiki/File:2014-08-31-domestic-duck.jpg) | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |

The photo credit and license follow the image when reused, including in UI previews. Other application code and unrelated assets are not relicensed by this document. The old SVG illustrations remain in the source tree for historical reference and are not included in the 1.1.0 SD content package.

Rebuild using Node.js, sharp, and `tools/build_card_images.cjs [private-download-cache]`. The tool verifies each source photo against its recorded hash before resizing. Original downloads and caches do not belong in Git.
