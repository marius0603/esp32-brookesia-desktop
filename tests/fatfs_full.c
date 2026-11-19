/* FatFs short-write regression on a disposable disk backed entirely by RAM. */
#include <stdio.h>
#include <string.h>
#include "diskio.h"

#define CHECK(condition) do { if (!(condition)) { fputs(#condition "\n", stderr); return 1; } } while (0)

#define SECTORS 70000
#define SECTOR_BYTES 512
static BYTE disk[SECTORS * SECTOR_BYTES];

DSTATUS disk_initialize(BYTE drive) { return drive ? STA_NOINIT : 0; }
DSTATUS disk_status(BYTE drive) { return disk_initialize(drive); }
DRESULT disk_read(BYTE drive, BYTE *buffer, LBA_t sector, UINT count)
{
    if (drive || sector >= SECTORS || count > SECTORS - sector) return RES_PARERR;
    memcpy(buffer, disk + sector * SECTOR_BYTES, count * SECTOR_BYTES);
    return RES_OK;
}
DRESULT disk_write(BYTE drive, const BYTE *buffer, LBA_t sector, UINT count)
{
    if (drive || sector >= SECTORS || count > SECTORS - sector) return RES_PARERR;
    memcpy(disk + sector * SECTOR_BYTES, buffer, count * SECTOR_BYTES);
    return RES_OK;
}
DRESULT disk_ioctl(BYTE drive, BYTE command, void *output)
{
    if (drive) return RES_PARERR;
    switch (command) {
    case GET_SECTOR_COUNT: *(LBA_t *)output = SECTORS; return RES_OK;
    case GET_BLOCK_SIZE: *(DWORD *)output = 1; return RES_OK;
    case GET_SECTOR_SIZE: *(WORD *)output = SECTOR_BYTES; return RES_OK;
    case CTRL_SYNC: return RES_OK;
    default: return RES_PARERR;
    }
}

int main(void)
{
    FATFS volume, *mounted = NULL;
    FIL file;
    BYTE block[4096] = {0};
    const char old[] = "{\"position\":17}";
    MKFS_PARM options = {.fmt = FM_FAT32 | FM_SFD, .au_size = SECTOR_BYTES};
    UINT count;
    CHECK(f_mkfs("0:", &options, block, sizeof block) == FR_OK);
    CHECK(f_mount(&volume, "0:", 1) == FR_OK);
    CHECK(f_open(&file, "0:/BOOK.JSN", FA_CREATE_NEW | FA_WRITE) == FR_OK);
    CHECK(f_write(&file, old, sizeof old, &count) == FR_OK && count == sizeof old);
    CHECK(f_sync(&file) == FR_OK && f_close(&file) == FR_OK);

    CHECK(f_open(&file, "0:/BOOK.TMP", FA_CREATE_NEW | FA_WRITE) == FR_OK);
    unsigned total = 0;
    do {
        CHECK(f_write(&file, block, sizeof block, &count) == FR_OK);
        total += count;
    } while (count == sizeof block && total < sizeof disk);
    DWORD free_clusters;
    CHECK(total > sizeof block && total < sizeof disk && count < sizeof block);
    CHECK(f_getfree("0:", &free_clusters, &mounted) == FR_OK && free_clusters == 0);
    CHECK(f_close(&file) == FR_OK);
    CHECK(f_rename("0:/BOOK.TMP", "0:/BOOK.JSN") == FR_EXIST);
    CHECK(f_unlink("0:/BOOK.TMP") == FR_OK);
    CHECK(f_mount(NULL, "0:", 0) == FR_OK);
    CHECK(f_mount(&volume, "0:", 1) == FR_OK);
    CHECK(f_open(&file, "0:/BOOK.JSN", FA_READ) == FR_OK);
    CHECK(f_read(&file, block, sizeof block, &count) == FR_OK && count == sizeof old);
    CHECK(memcmp(block, old, sizeof old) == 0 && f_close(&file) == FR_OK);
    puts("A full FAT volume returned a short write; the original file survived remount.");
    return 0;
}
