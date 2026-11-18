/* Compare the fast seek output with full PCM decoding for each supplied MP3. */
#define DR_MP3_IMPLEMENTATION
#define DR_MP3_NO_SIMD
#include "dr_mp3.h"

#include <stdio.h>
#include <string.h>

enum { block_frames = 1024, sample_capacity = block_frames * 2 };

static int seek_by_full_decode(drmp3 *decoder, drmp3_uint64 target)
{
    if (target == 0) {
        return drmp3_seek_to_start_of_stream(decoder);
    }
    if (target < decoder->currentPCMFrame && !drmp3_seek_to_start_of_stream(decoder)) {
        return 0;
    }
    drmp3_uint64 remaining = target - decoder->currentPCMFrame;
    drmp3_int16 discard[sample_capacity];
    while (remaining) {
        const drmp3_uint64 block = remaining < block_frames ? remaining : block_frames;
        if (drmp3_read_pcm_frames_s16(decoder, block, discard) != block) {
            return 0;
        }
        remaining -= block;
    }
    return 1;
}

static int check_track(const char *path)
{
    drmp3 fast, reference;
    drmp3_int16 fast_output[sample_capacity], reference_output[sample_capacity];
    if (!drmp3_init_file(&fast, path, NULL)) {
        return 0;
    }
    if (!drmp3_init_file(&reference, path, NULL)) {
        drmp3_uninit(&fast);
        return 0;
    }
    int passed = 1;
    const drmp3_uint64 duration = drmp3_get_pcm_frame_count(&fast);
    const drmp3_uint64 targets[] = {duration * 9 / 10, duration / 4,
                                   duration / 4 + 17, 0, duration / 2,
                                   duration - (duration >= 250 ? 250 : duration)};
    for (size_t i = 0; i < sizeof(targets) / sizeof(targets[0]); ++i) {
        const drmp3_uint64 target = targets[i];
        if (!drmp3_seek_to_pcm_frame(&fast, target) || !seek_by_full_decode(&reference, target)) {
            fprintf(stderr, "Seek failed at sample %llu in %s\n", (unsigned long long)target, path);
            passed = 0;
            break;
        }
        const drmp3_uint64 frames = drmp3_read_pcm_frames_s16(&fast, block_frames, fast_output);
        const drmp3_uint64 expected = drmp3_read_pcm_frames_s16(&reference, block_frames, reference_output);
        if (frames != expected || fast.currentPCMFrame != reference.currentPCMFrame ||
                memcmp(fast_output, reference_output, (size_t)frames * fast.channels * sizeof(*fast_output))) {
            fprintf(stderr, "PCM differs at sample %llu in %s\n", (unsigned long long)target, path);
            passed = 0;
            break;
        }
    }
    drmp3_uninit(&reference);
    drmp3_uninit(&fast);
    return passed;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "Supply at least one MP3 fixture.\n");
        return 2;
    }
    for (int i = 1; i < argc; ++i) {
        if (!check_track(argv[i])) {
            return 1;
        }
    }
    printf("Six seeks per fixture matched full-decoder PCM for %d MP3 files.\n", argc - 1);
    return 0;
}
