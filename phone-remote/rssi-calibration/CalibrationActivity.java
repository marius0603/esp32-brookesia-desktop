package com.xiaoma.rssicalibration;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanFilter;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelUuid;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

public final class CalibrationActivity extends Activity {
    private static final UUID REMOTE_SERVICE = UUID.fromString("1775244d-6b43-439b-877c-060f2d9bed07");
    private static final int[] DISTANCES = {300, 200, 100, 50, 30};
    private static final int SAMPLES = 16;
    private static final int SAMPLE_DELAY_MS = 400;
    private static final int PERMISSIONS = 1;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final Set<String> seen = new HashSet<>();
    private final int[][] samples = new int[DISTANCES.length][SAMPLES];
    private final TextView[] rows = new TextView[DISTANCES.length];
    private final int ink = Color.rgb(233, 246, 250);
    private final int muted = Color.rgb(172, 202, 213);
    private final int back = Color.rgb(8, 24, 36);
    private final int action = Color.rgb(23, 105, 105);
    private BluetoothAdapter adapter;
    private BluetoothLeScanner scanner;
    private BluetoothGatt gatt;
    private String measuredDevice;
    private boolean ready;
    private boolean collecting;
    private boolean awaiting;
    private int point;
    private int count;
    private int failedReads;
    private TextView status;
    private LinearLayout devices;
    private Button scanButton, sampleButton, copyButton;

    private final Runnable scanTimeout = () -> {
        stopScan();
        if (seen.isEmpty()) status.setText("未发现设备。请开启设备的蓝牙遥控。");
    };
    private final Runnable connectionTimeout = () -> linkLost("连接超时，请重新扫描。");
    private final Runnable sampleTimeout = () -> linkLost("读取超时。重新连接后测这一档。");
    private final Runnable nextSample = this::sample;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        BluetoothManager manager = getSystemService(BluetoothManager.class);
        adapter = manager == null ? null : manager.getAdapter();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().setStatusBarColor(back);
        getWindow().setNavigationBarColor(back);
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(back);
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(20), dp(16), dp(20), dp(20));
        if (Build.VERSION.SDK_INT >= 30) {
            scroll.setOnApplyWindowInsetsListener((view, insets) -> {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
                return insets;
            });
        }
        scroll.addView(page);
        setContentView(scroll);
        text(page, "蓝牙距离校准", 27, ink);
        status = text(page, "先开启设备的蓝牙遥控。", 16, muted);
        scanButton = button(page, "扫描设备", 54, () -> scan());
        devices = new LinearLayout(this);
        devices.setOrientation(LinearLayout.VERTICAL);
        page.addView(devices);
        text(page, "手机离设备外壳的距离", 19, ink);
        for (int i = 0; i < rows.length; i++) {
            rows[i] = text(page, distance(i) + " · 待测", 16, muted);
        }
        sampleButton = button(page, "开始测量", 66, () -> startPoint());
        copyButton = button(page, "复制测试结果", 52, () -> copy());
        button(page, "清空读数", 52, () -> resetSamples());
        updateButtons();
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private TextView text(LinearLayout parent, String value, int size, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setPadding(0, dp(6), 0, dp(6));
        parent.addView(view);
        return view;
    }

    private Button button(LinearLayout parent, String label, int height, Runnable click) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextColor(ink);
        button.setTextSize(17);
        button.setAllCaps(false);
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(action);
        shape.setCornerRadius(dp(12));
        button.setBackground(shape);
        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(-1, dp(height));
        layout.setMargins(0, dp(5), 0, dp(5));
        parent.addView(button, layout);
        button.setOnClickListener(v -> click.run());
        return button;
    }

    private String distance(int index) {
        return DISTANCES[index] >= 100 ? (DISTANCES[index] / 100) + " 米" : DISTANCES[index] + " 厘米";
    }

    private void updateButtons() {
        sampleButton.setEnabled(ready && !collecting && point < DISTANCES.length);
        sampleButton.setAlpha(sampleButton.isEnabled() ? 1f : .5f);
        sampleButton.setText(point < DISTANCES.length ? "测量 " + distance(point) : "采样完成");
        scanButton.setEnabled(!collecting);
        copyButton.setEnabled(point == DISTANCES.length);
        copyButton.setAlpha(copyButton.isEnabled() ? 1f : .5f);
    }

    private void resetSamples() {
        if (collecting) return;
        point = count = 0;
        for (int i = 0; i < rows.length; i++) rows[i].setText(distance(i) + " · 待测");
        updateButtons();
    }

    private String[] neededPermissions() {
        return Build.VERSION.SDK_INT >= 31
                ? new String[]{Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT}
                : new String[]{Manifest.permission.ACCESS_FINE_LOCATION};
    }

    private void scan() {
        String[] permissions = neededPermissions();
        for (String permission : permissions) {
            if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(permissions, PERMISSIONS);
                return;
            }
        }
        if (adapter == null || !adapter.isEnabled()) {
            status.setText("请先开启手机蓝牙。");
            return;
        }
        stopScan();
        closeLink();
        seen.clear();
        devices.removeAllViews();
        scanner = adapter.getBluetoothLeScanner();
        if (scanner == null) {
            status.setText("蓝牙扫描暂不可用。");
            return;
        }
        ScanFilter filter = new ScanFilter.Builder().setServiceUuid(new ParcelUuid(REMOTE_SERVICE)).build();
        try {
            scanner.startScan(Collections.singletonList(filter),
                    new ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), scans);
            status.setText("正在扫描小马设备…");
            ui.postDelayed(scanTimeout, 12000);
        } catch (RuntimeException failure) {
            stopScan();
            status.setText("无法扫描，请检查蓝牙和附近设备权限。");
        }
    }

    private final ScanCallback scans = new ScanCallback() {
        @Override public void onScanResult(int callbackType, ScanResult result) {
            String name = result.getScanRecord() == null ? null : result.getScanRecord().getDeviceName();
            BluetoothDevice device = result.getDevice();
            ui.post(() -> {
                if (scanner == null || !seen.add(device.getAddress())) return;
                status.setText("选择开发板屏幕上显示的设备。");
                button(devices, name == null ? "小马设备 " + seen.size() : name, 52, () -> connect(device));
            });
        }

        @Override public void onScanFailed(int errorCode) {
            ui.post(() -> {
                stopScan();
                status.setText("扫描失败，请检查蓝牙和权限。");
            });
        }
    };

    private void stopScan() {
        ui.removeCallbacks(scanTimeout);
        if (scanner == null) return;
        try { scanner.stopScan(scans); } catch (RuntimeException ignored) {}
        scanner = null;
    }

    private void connect(BluetoothDevice device) {
        stopScan();
        closeLink();
        devices.removeAllViews();
        if (!device.getAddress().equals(measuredDevice)) resetSamples();
        measuredDevice = device.getAddress();
        status.setText("正在连接设备…");
        try { gatt = device.connectGatt(this, false, link, BluetoothDevice.TRANSPORT_LE); }
        catch (RuntimeException failure) { gatt = null; }
        if (gatt == null) linkLost("连接失败，请重新扫描。");
        else ui.postDelayed(connectionTimeout, 15000);
    }

    private final BluetoothGattCallback link = new BluetoothGattCallback() {
        @Override public void onConnectionStateChange(BluetoothGatt owner, int code, int state) {
            ui.post(() -> {
                if (owner != gatt) return;
                if (code == BluetoothGatt.GATT_SUCCESS && state == BluetoothProfile.STATE_CONNECTED) {
                    try {
                        if (owner.discoverServices()) return;
                    } catch (RuntimeException ignored) {}
                }
                linkLost("蓝牙连接已断开，请重新扫描。");
            });
        }

        @Override public void onServicesDiscovered(BluetoothGatt owner, int code) {
            ui.post(() -> {
                if (owner != gatt) return;
                if (code == BluetoothGatt.GATT_SUCCESS && owner.getService(REMOTE_SERVICE) != null) {
                    ui.removeCallbacks(connectionTimeout);
                    ready = true;
                    status.setText("已连接。到对应距离站稳，再点测量。保持平时的握持方式。");
                    updateButtons();
                } else linkLost("设备的遥控服务不可用。");
            });
        }

        @Override public void onReadRemoteRssi(BluetoothGatt owner, int rssi, int code) {
            ui.post(() -> {
                if (owner != gatt || !awaiting) return;
                ui.removeCallbacks(sampleTimeout);
                awaiting = false;
                if (collecting) acceptSample(code == BluetoothGatt.GATT_SUCCESS ? rssi : 127);
            });
        }
    };

    private void startPoint() {
        if (!ready || collecting || point >= DISTANCES.length) return;
        collecting = true;
        count = failedReads = 0;
        status.setText("正在测量 " + distance(point) + " · 保持稳定");
        updateButtons();
        sample();
    }

    private void sample() {
        if (!ready || !collecting || awaiting || gatt == null) return;
        try {
            awaiting = gatt.readRemoteRssi();
        } catch (RuntimeException failure) {
            linkLost("读取蓝牙信号失败，请检查权限并重新连接。");
            return;
        }
        if (awaiting) ui.postDelayed(sampleTimeout, 2200);
        else acceptSample(127);
    }

    private void acceptSample(int rssi) {
        if (rssi >= -127 && rssi < 0) {
            samples[point][count++] = rssi;
            rows[point].setText(distance(point) + " · " + count + "/" + SAMPLES + " · " + rssi + " dBm");
        } else if (++failedReads >= 4) {
            rows[point].setText(distance(point) + " · 待重测");
            collecting = false;
            status.setText("有效读数不足，请重测这一档。");
            updateButtons();
            return;
        }
        if (count < SAMPLES) {
            ui.postDelayed(nextSample, SAMPLE_DELAY_MS);
            return;
        }
        collecting = false;
        rows[point].setText(distance(point) + " · 已记录 " + SAMPLES + " 次");
        point++;
        status.setText(point < DISTANCES.length ? "移到 " + distance(point) + " 再测下一档。" : "五档测量完成。复制结果进行阈值分析。");
        updateButtons();
    }

    private void copy() {
        if (point != DISTANCES.length) return;
        StringBuilder csv = new StringBuilder("distance_cm,rssi_dbm\n");
        for (int i = 0; i < DISTANCES.length; i++) {
            for (int rssi : samples[i]) csv.append(DISTANCES[i]).append(',').append(rssi).append('\n');
        }
        ClipboardManager clipboard = getSystemService(ClipboardManager.class);
        clipboard.setPrimaryClip(ClipData.newPlainText("蓝牙校准读数", csv));
        status.setText("结果已复制。");
    }

    private void linkLost(String message) {
        closeLink();
        status.setText(message);
    }

    private void closeLink() {
        if (collecting) rows[point].setText(distance(point) + " · 待重测");
        ready = collecting = awaiting = false;
        count = 0;
        ui.removeCallbacks(connectionTimeout);
        ui.removeCallbacks(sampleTimeout);
        ui.removeCallbacks(nextSample);
        BluetoothGatt previous = gatt;
        gatt = null;
        if (previous != null) {
            try { previous.close(); } catch (RuntimeException ignored) {}
        }
        updateButtons();
    }

    @Override public void onRequestPermissionsResult(int request, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(request, permissions, results);
        if (request != PERMISSIONS) return;
        for (String permission : neededPermissions()) {
            if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) {
                status.setText("请允许蓝牙扫描所需的系统权限。");
                return;
            }
        }
        scan();
    }

    @Override protected void onStop() {
        stopScan();
        if (gatt != null) linkLost("已暂停。回到校准页后请重新连接。");
        super.onStop();
    }
}
