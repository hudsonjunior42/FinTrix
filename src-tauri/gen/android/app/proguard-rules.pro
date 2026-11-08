# Regras do R8 (encolhimento do release). As dos plugins do Tauri vêm em proguard-tauri.pro e nos próprios plugins.

# ML Kit (leitor de QR code do plugin barcode-scanner): acha os próprios componentes por reflexão; encolhido pelo
# R8, InputImage.fromMediaImage dava NullPointerException e o app fechava ao abrir a câmera (só no release).
-keep class com.google.mlkit.** { *; }
-keep class com.google.android.gms.internal.mlkit_** { *; }
-keep class com.google.firebase.components.** { *; }
