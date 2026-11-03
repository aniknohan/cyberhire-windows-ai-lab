// Run after `npx cap add android`. Adds the Google Play Billing plugin, camera + microphone permissions,
// edge-to-edge insets (Android 15/16), release signing from environment variables and the version numbers.
const fs = require("fs");
const path = require("path");

const cfg = require("../config.json");
const pkg = cfg.packageName;
const appDir = path.join(__dirname, "..", "android", "app");
const main = path.join(appDir, "src", "main");
const javaDir = path.join(main, "java", ...pkg.split("."));

// 1. Manifest: permissions the interview needs (camera is optional hardware)
const manifestPath = path.join(main, "AndroidManifest.xml");
let xml = fs.readFileSync(manifestPath, "utf8");
for (const p of [
  '<uses-permission android:name="android.permission.RECORD_AUDIO" />',
  '<uses-permission android:name="android.permission.CAMERA" />',
  '<uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />',
  '<uses-feature android:name="android.hardware.camera" android:required="false" />',
  '<uses-feature android:name="android.hardware.camera.front" android:required="false" />',
  '<uses-feature android:name="android.hardware.microphone" android:required="false" />',
]) {
  const name = p.match(/android:name="([^"]+)"/)[1];
  if (!xml.includes(`"${name}"`)) xml = xml.replace("</manifest>", `    ${p}\n</manifest>`);
}
if (!xml.includes("resizeableActivity")) xml = xml.replace("<activity", '<activity android:resizeableActivity="true"');
fs.writeFileSync(manifestPath, xml);

// 2. Java: billing plugin + MainActivity
fs.mkdirSync(javaDir, { recursive: true });
const plugin = fs.readFileSync(path.join(__dirname, "..", "plugin", "PlayBillingPlugin.java"), "utf8").replace("__PACKAGE__", pkg);
fs.writeFileSync(path.join(javaDir, "PlayBillingPlugin.java"), plugin);
fs.writeFileSync(path.join(javaDir, "MainActivity.java"), `package ${pkg};

import android.Manifest;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(PlayBillingPlugin.class);
        super.onCreate(savedInstanceState);

        // Android 15/16 draw apps edge to edge: keep the web screens clear of the status bar, navigation bar and keyboard.
        getWindow().getDecorView().setBackgroundColor(Color.parseColor("#090D14"));
        WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView()).setAppearanceLightStatusBars(false);
        WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView()).setAppearanceLightNavigationBars(false);
        View web = getBridge().getWebView();
        ViewCompat.setOnApplyWindowInsetsListener(web, (v, insets) -> {
            Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout() | WindowInsetsCompat.Type.ime());
            ViewGroup.MarginLayoutParams lp = (ViewGroup.MarginLayoutParams) v.getLayoutParams();
            lp.setMargins(bars.left, bars.top, bars.right, bars.bottom);
            v.setLayoutParams(lp);
            return WindowInsetsCompat.CONSUMED;
        });

        String[] perms = { Manifest.permission.RECORD_AUDIO, Manifest.permission.CAMERA, Manifest.permission.MODIFY_AUDIO_SETTINGS };
        boolean missing = false;
        for (String p : perms) if (ContextCompat.checkSelfPermission(this, p) != PackageManager.PERMISSION_GRANTED) missing = true;
        if (missing) ActivityCompat.requestPermissions(this, perms, 1001);
    }
}
`);

// 3. Gradle: billing library, signing, version
const gradlePath = path.join(appDir, "build.gradle");
let gradle = fs.readFileSync(gradlePath, "utf8");
if (!gradle.includes("com.android.billingclient:billing")) {
  gradle = gradle.replace(/dependencies\s*\{/, 'dependencies {\n    implementation "com.android.billingclient:billing:8.0.0"');
}
if (process.env.CH_KEYSTORE && !gradle.includes("signingConfigs {")) {
  gradle = gradle.replace(/android\s*\{/, `android {
    signingConfigs {
        release {
            storeFile file(System.getenv("CH_KEYSTORE"))
            storePassword System.getenv("CH_KEYSTORE_PASSWORD")
            keyAlias System.getenv("CH_KEY_ALIAS")
            keyPassword System.getenv("CH_KEY_PASSWORD")
        }
    }`);
  gradle = gradle.replace(/buildTypes\s*\{\s*release\s*\{/, "buildTypes {\n        release {\n            signingConfig signingConfigs.release");
  console.log("Release signing configured (upload key).");
}
const code = 100 + Number(process.env.GITHUB_RUN_NUMBER || 1);
gradle = gradle.replace(/versionCode\s*=?\s*\d+/, `versionCode ${code}`).replace(/versionName\s*=?\s*"[^"]*"/, `versionName "${cfg.versionName}"`);
fs.writeFileSync(gradlePath, gradle);
console.log(`Play app ready: ${pkg} ${cfg.versionName} (versionCode ${code}), billing 8.0.0, API base ${cfg.apiBase}`);
