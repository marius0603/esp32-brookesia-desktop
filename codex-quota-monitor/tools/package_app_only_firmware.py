"""Package the reviewed application plus a partition table used only for verification."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    build = args.build.resolve()
    desc = json.loads((build / 'project_description.json').read_text(encoding='utf-8'))
    versions = json.loads((ROOT / 'versions.json').read_text(encoding='utf-8'))
    assert desc['project_name'] == 'brookesia_s3_216' and desc['project_version'] == versions['firmware']
    config = json.loads((build / 'flasher_args.json').read_text(encoding='utf-8'))
    keep = {offset: name for offset, name in config['flash_files'].items()
        if Path(name).name == desc['app_bin'] or int(offset, 0) == 0x8000}
    assert len(keep) == 2 and any(int(k, 0) == 0x8000 for k in keep)
    slim = {key: config[key] for key in ('write_flash_args', 'flash_settings', 'extra_esptool_args')}
    slim['flash_files'] = keep
    description = {key: desc[key] for key in ('project_name', 'project_version', 'app_bin')}
    output = ROOT / 'packages/firmware' / ('brookesia-' + desc['project_version'] + '-app-only.zip')
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'version': desc['project_version'], 'device': 'ESP32-S3-Touch-AMOLED-2.16',
        'app_only': True, 'files': {}}
    sdkconfig = json.loads((build / 'config/sdkconfig.json').read_text(encoding='utf-8'))
    manifest['features'] = {'separate_websocket_tx_lock': bool(sdkconfig.get('ESP_WS_CLIENT_SEPARATE_TX_LOCK'))}
    if desc['project_version'] in ('0.8.3-s3.40','0.8.3-s3.41','0.8.3-s3.42','0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features'].update(buffered_story_pcm=True,pitch_preserving_story_speed=True,default_story_speed=1.0)
    if desc['project_version'] in ('0.8.3-s3.41','0.8.3-s3.42','0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features']['transparent_launcher_icons']=True
    if desc['project_version'] in ('0.8.3-s3.36','0.8.3-s3.37','0.8.3-s3.38','0.8.3-s3.39','0.8.3-s3.40','0.8.3-s3.41','0.8.3-s3.42','0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features'].update(single_foreground_apps=True,independent_ble_command_worker=True,
            display_bounded_dma=True,serialized_app_store_callbacks=True,synchronous_task_exception_completion=True,
            wait_for_assistant_release=True)
    if desc['project_version'] in ('0.8.3-s3.37','0.8.3-s3.38','0.8.3-s3.39','0.8.3-s3.40','0.8.3-s3.41','0.8.3-s3.42','0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features'].update(four_digit_remote_pop=True,remote_audiobook_foreground=True)
    if desc['project_version'] in ('0.8.3-s3.38','0.8.3-s3.39','0.8.3-s3.40','0.8.3-s3.41','0.8.3-s3.42','0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features'].update(remote_story_modes=True,chinese_story_titles=True)
    if desc['project_version'] in ('0.8.3-s3.42','0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features'].update(buffered_wifi_radio=True,radio_mp3_aac_hls=True)
        manifest['features'].update(radio_mp3_push=True,
            tcp_receive_window=sdkconfig.get('LWIP_TCP_WND_DEFAULT'),
            tcp_receive_mailbox=sdkconfig.get('LWIP_TCP_RECVMBOX_SIZE'),
            wifi_static_rx_buffers=sdkconfig.get('ESP_WIFI_STATIC_RX_BUFFER_NUM'),
            wifi_rx_aggregation_window=sdkconfig.get('ESP_WIFI_RX_BA_WIN'),
            radio_disables_modem_sleep=True,radio_preserves_mp3_tail=True)
    if desc['project_version'] in ('0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features'].update(global_volume_badge=True,global_battery_badge=True)
    if desc['project_version'] in ('0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features'].update(status_badge_scope='desktop',hide_status_inside_apps=True)
    if desc['project_version'] in ('0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features']['phone_ble_radio']=True
    if desc['project_version'] in ('0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features'].update(sd_runtime_apps=True,sd_package_staging=True,install_space_preflight=True,transactional_app_install=True,flash_foundation=True)
    if desc['project_version'] in ('0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features'].update(separate_nursery_song_library=True,nursery_songs_child_policy='audiobook')
    if desc['project_version'] in ('0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features'].update(phone_ble_songs=True,shared_song_mode=True)
    if desc['project_version'] in ('0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features']['dma_internal_reserve_bytes']=sdkconfig['SPIRAM_MALLOC_RESERVE_INTERNAL']
        assert manifest['features']['dma_internal_reserve_bytes']==(98304 if desc['project_version'] in ('0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57') else 65536)
        manifest['features']['ble_warm_start_memory_diagnostics']=True
    if desc['project_version'] in ('0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features'].update(launcher_columns=3,launcher_rows=3,launcher_page_size=9,launcher_icon_size=92,launcher_item_size=112)
    if desc['project_version'] in ('0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features']['launcher_item_gap']=18
    if desc['project_version'] in ('0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features']['microphone_read_reopen_retries']=2
    if desc['project_version'] in ('0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features']['shared_codec_lifetime_pinned']=True
    if desc['project_version'] in ('0.8.3-s3.56','0.8.3-s3.57'):
        manifest['features'].update(display_spi_queue_depth=1,display_spi_max_transfer_request=3840)
    if desc['project_version']=='0.8.3-s3.57':
        manifest['features']['display_fixed_dma_stage_bytes']=4096
    temporary = output.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
        native_scroll=desc['project_version'] in ('0.8.3-s3.30','0.8.3-s3.31','0.8.3-s3.32','0.8.3-s3.33','0.8.3-s3.34','0.8.3-s3.35','0.8.3-s3.36','0.8.3-s3.37','0.8.3-s3.38','0.8.3-s3.39','0.8.3-s3.40','0.8.3-s3.41','0.8.3-s3.42','0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57')
        launcher=ROOT/('packages/resources/desktop-themes-launcher-s3.51.json' if desc['project_version'] in ('0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57') else 'packages/resources/desktop-themes-launcher-s3.50.json' if desc['project_version'] in ('0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57') else 'packages/resources/desktop-themes-launcher-s3.31.json' if desc['project_version'] in ('0.8.3-s3.31','0.8.3-s3.32','0.8.3-s3.33','0.8.3-s3.34','0.8.3-s3.35','0.8.3-s3.36','0.8.3-s3.37','0.8.3-s3.38','0.8.3-s3.39','0.8.3-s3.40','0.8.3-s3.41','0.8.3-s3.42','0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57') else 'packages/resources/phone-launcher-s3.30.json' if native_scroll else 'packages/resources/phone-launcher-s3.28.json')
        if desc['project_version'] in ('0.8.3-s3.28','0.8.3-s3.29','0.8.3-s3.30','0.8.3-s3.31','0.8.3-s3.32','0.8.3-s3.33','0.8.3-s3.34','0.8.3-s3.35','0.8.3-s3.36','0.8.3-s3.37','0.8.3-s3.38','0.8.3-s3.39','0.8.3-s3.40','0.8.3-s3.41','0.8.3-s3.42','0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
            data=launcher.read_bytes()
            archive.writestr('launcher/app_launcher.json',data)
            manifest['files']['launcher/app_launcher.json']={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
            manifest['features']['phone_launcher']=True
            manifest['features']['native_launcher_scroll']=native_scroll
            manifest['features']['desktop_theme_switch']=desc['project_version'] in ('0.8.3-s3.31','0.8.3-s3.32','0.8.3-s3.33','0.8.3-s3.34','0.8.3-s3.35','0.8.3-s3.36','0.8.3-s3.37','0.8.3-s3.38','0.8.3-s3.39','0.8.3-s3.40','0.8.3-s3.41','0.8.3-s3.42','0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57')
            if desc['project_version'] in ('0.8.3-s3.32','0.8.3-s3.33','0.8.3-s3.34','0.8.3-s3.35','0.8.3-s3.36','0.8.3-s3.37','0.8.3-s3.38','0.8.3-s3.39','0.8.3-s3.40','0.8.3-s3.41','0.8.3-s3.42','0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
                manifest['features']['phone_ble_provisioning']=bool(sdkconfig.get('BT_NIMBLE_ENABLED') and sdkconfig.get('ESP_PROTOCOMM_SUPPORT_SECURITY_VERSION_1'))
                assert manifest['features']['phone_ble_provisioning'] and not sdkconfig.get('ESP_PROTOCOMM_SUPPORT_SECURITY_VERSION_0')
                manifest['features']['ble_controller_flash_code']=bool(sdkconfig.get('BT_CTRL_RUN_IN_FLASH_ONLY'))
                assert manifest['features']['ble_controller_flash_code'],'Phone provisioning needs controller RAM savings with Settings open'
                manifest['features']['phone_ble_remote']=desc['project_version'] in ('0.8.3-s3.33','0.8.3-s3.34','0.8.3-s3.35','0.8.3-s3.36','0.8.3-s3.37','0.8.3-s3.38','0.8.3-s3.39','0.8.3-s3.40','0.8.3-s3.41','0.8.3-s3.42','0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57')
                data=(ROOT/('packages/resources/bluetooth-settings-s3.34/screens/wifi.json' if desc['project_version'] in ('0.8.3-s3.34','0.8.3-s3.35','0.8.3-s3.36','0.8.3-s3.37','0.8.3-s3.38','0.8.3-s3.39','0.8.3-s3.40','0.8.3-s3.41','0.8.3-s3.42','0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57') else 'packages/resources/phone-remote-wifi-s3.33.json' if manifest['features']['phone_ble_remote'] else 'packages/resources/phone-provisioning-wifi-s3.32.json')).read_bytes()
                if desc['project_version'] in ('0.8.3-s3.34','0.8.3-s3.35','0.8.3-s3.36','0.8.3-s3.37','0.8.3-s3.38','0.8.3-s3.39','0.8.3-s3.40','0.8.3-s3.41','0.8.3-s3.42','0.8.3-s3.43','0.8.3-s3.44','0.8.3-s3.45','0.8.3-s3.46','0.8.3-s3.47','0.8.3-s3.48','0.8.3-s3.49','0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57'):
                    for path in (ROOT/'packages/resources/bluetooth-settings-s3.34').rglob('*.json'):
                        name='settings/'+path.relative_to(ROOT/'packages/resources/bluetooth-settings-s3.34').as_posix();payload=path.read_bytes();archive.writestr(name,payload);manifest['files'][name]={'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}
                archive.writestr('settings/wifi.json',data)
                manifest['files']['settings/wifi.json']={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        for name in keep.values():
            path = (build / name).resolve()
            assert path.is_relative_to(build) and path.is_file()
            data = path.read_bytes()
            archive.writestr(Path(name).as_posix(), data)
            manifest['files'][name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        archive.writestr('flasher_args.json', json.dumps(slim, indent=2) + '\n')
        archive.writestr('project_description.json', json.dumps(description, indent=2) + '\n')
        archive.writestr('manifest.json', json.dumps(manifest, indent=2) + '\n')
        archive.writestr('README.txt',
            'App-only update for ESP32-S3-Touch-AMOLED-2.16.\n'
            'Use tools/backup_current_firmware.py first; keep its verified private backup.\n'
            'Extract this package, then run tools/update_brookesia_app_only.py with --port, --build and --backup.\n'
            'The partition table is included for comparison; the updater writes only the application.\n'
            'NVS, LittleFS, installed apps and SD contents are preserved.\n'
            'After reboot install the matching application packages described in the release documentation.\n'
            + ('For s3.50/s3.51 run tools/deploy_nine_grid_launcher.py before flashing, preserving original icon sizes and custom resources.\n' if desc['project_version'] in ('0.8.3-s3.50','0.8.3-s3.51','0.8.3-s3.53','0.8.3-s3.54','0.8.3-s3.55','0.8.3-s3.56','0.8.3-s3.57') else '')
            + ('Before updating to s3.30, run tools/deploy_phone_launcher.py to install the native-scroll launcher document.\n'
               'launcher/app_launcher.json is a separate filesystem resource, not a Flash partition image.\n'
               's3.28 and s3.29 share the earlier document; restoring those versions also requires restoring that document.\n'
               if desc['project_version'] in ('0.8.3-s3.28','0.8.3-s3.29','0.8.3-s3.30') else 's3.31 additionally needs tools/deploy_desktop_themes.py to install the desktop artwork and theme chooser.\n' if desc['project_version']=='0.8.3-s3.31' else 's3.32 additionally needs tools/deploy_phone_provisioning.py to install the Wi-Fi Settings entry; existing themes and launcher resources stay in place.\n' if desc['project_version']=='0.8.3-s3.32' else ''))
    with zipfile.ZipFile(temporary) as archive:
        assert archive.testzip() is None
    temporary.replace(output)
    print(output)
    print('SHA256:', hashlib.sha256(output.read_bytes()).hexdigest())

if __name__ == '__main__':
    main()
