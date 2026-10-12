# MemoryPal installers

The installers themselves live on the [Releases page](https://github.com/TKSMG/MemoryPal/releases/latest), not in this folder: binaries in git would make every clone download every old build. The links below always point at the newest release.

| Platform | Download | How to install |
|---|---|---|
| Windows 10/11 | [MemoryPal-Windows-Setup.exe](https://github.com/TKSMG/MemoryPal/releases/latest/download/MemoryPal-Windows-Setup.exe) | Run it. SmartScreen may say "Windows protected your PC" because the installer isn't code-signed yet: choose **More info**, then **Run anyway**. |
| Mac with Apple silicon (M1 and later) | [MemoryPal-macOS-AppleSilicon.dmg](https://github.com/TKSMG/MemoryPal/releases/latest/download/MemoryPal-macOS-AppleSilicon.dmg) | Open it and drag MemoryPal to Applications. Until the app is notarized, the first launch needs right-click (or Control-click) on MemoryPal, then **Open**. |
| Mac with Intel | [MemoryPal-macOS-Intel.dmg](https://github.com/TKSMG/MemoryPal/releases/latest/download/MemoryPal-macOS-Intel.dmg) | Same as above. |
| Android 7+ | [MemoryPal-Android.apk](https://github.com/TKSMG/MemoryPal/releases/latest/download/MemoryPal-Android.apk) | Open the file on the phone and allow installing from this source when asked. |
| iPhone and iPad | [MemoryPal-iOS-unsigned.ipa](https://github.com/TKSMG/MemoryPal/releases/latest/download/MemoryPal-iOS-unsigned.ipa) | Apple only installs signed apps. Sign and install it with a sideloading tool (AltStore or Sideloadly, using any Apple ID), or use TestFlight once the Apple Developer account is set up (below). |
| iOS Simulator | [MemoryPal-iOS-Simulator.zip](https://github.com/TKSMG/MemoryPal/releases/latest/download/MemoryPal-iOS-Simulator.zip) | Unzip and drag `MemoryPal.app` onto a running simulator in Xcode. |

Each release also has `SHA256SUMS.txt` to check a download.

## Making a new release

1. Bump the version: `pyproject.toml`, `installer/inno/MemoryPal.iss`, `build_nuitka_windows.cmd` and `mobile/app.json` (`version`, `ios.buildNumber`, `android.versionCode`).
2. Push a tag: `git tag v0.48.1 && git push origin v0.48.1`.
3. The **Release Installers** workflow builds all six files and publishes them as a GitHub Release. It can also be run by hand from the Actions tab with a tag name.

## Signing for the stores

The builds work without any accounts. Adding these repository secrets (Settings → Secrets and variables → Actions) turns on signing automatically:

| Secret | What it's for | Where it comes from |
|---|---|---|
| `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD` | Signs the APK and adds a Play Store bundle (`MemoryPal-Android-PlayStore.aab`). | A Google Play developer account ($25 once). Make an upload key with `keytool -genkeypair -v -keystore upload.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload`, then `base64 -i upload.jks`. Keep the file and passwords safe: Play needs the same key for every update. |
| `MACOS_CERTIFICATE_P12_BASE64`, `MACOS_CERTIFICATE_PASSWORD` | Signs the Mac app with a Developer ID, so Gatekeeper trusts it. | An Apple Developer Program membership ($99 a year). Create a "Developer ID Application" certificate, export it from Keychain Access as .p12, then `base64 -i cert.p12`. |
| `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD` | Notarizes the Mac app, so it opens with a normal double-click. | Your Apple ID, the Team ID from the developer account, and an app-specific password from appleid.apple.com. |

For the App Store and TestFlight, the simplest route is Expo's build service, which handles Apple certificates and provisioning for you: from `mobile/`, run `npx eas-cli login`, then `npx eas-cli build -p ios --profile production` and `npx eas-cli submit -p ios`. The same works for Google Play with `-p android`. The profiles are in `mobile/eas.json`.

Windows code signing (to remove the SmartScreen warning) needs a code-signing certificate from a certificate authority, or Azure Trusted Signing; it can be added to `build_installer_windows.cmd` with Inno Setup's `SignTool` setting once you have one.
