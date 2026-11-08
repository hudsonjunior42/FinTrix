import java.util.Properties
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("rust")
}

val tauriProperties = Properties().apply {
    val propFile = file("tauri.properties")
    if (propFile.exists()) {
        propFile.inputStream().use { load(it) }
    }
}

// Chave de assinatura do release, fora do repositório (docs/android.md, "Assinatura"): storeFile, storePassword,
// keyAlias e keyPassword. Sem o arquivo, o release sai sem assinatura (não instala).
val assinatura = Properties().apply {
    val arq = file(System.getenv("FINTRIX_ASSINATURA") ?: "${System.getProperty("user.home")}/.config/fintrix/assinatura.properties")
    if (arq.exists()) {
        arq.inputStream().use { load(it) }
    }
}

android {
    compileSdk = 37
    namespace = "io.github.hudsonjunior42.fintrix"
    defaultConfig {
        manifestPlaceholders["usesCleartextTraffic"] = "false"
        applicationId = "io.github.hudsonjunior42.fintrix"
        minSdk = 24
        targetSdk = 37
        versionCode = tauriProperties.getProperty("tauri.android.versionCode", "1").toInt()
        versionName = tauriProperties.getProperty("tauri.android.versionName", "1.0")
    }
    signingConfigs {
        if (assinatura.getProperty("storeFile") != null) {
            create("release") {
                storeFile = file(assinatura.getProperty("storeFile"))
                storePassword = assinatura.getProperty("storePassword")
                keyAlias = assinatura.getProperty("keyAlias")
                keyPassword = assinatura.getProperty("keyPassword")
            }
        }
    }
    buildTypes {
        getByName("debug") {
            applicationIdSuffix = ".debug"
            // outro app no celular ("FinTrix (teste)", id com o sufixo de bundle.android.debugApplicationIdSuffix do
            // tauri.conf.json, que o tauri-cli escreve acima): convive com o de verdade, com dados e chave próprios
            resValue("string", "app_name", "FinTrix (teste)")
            resValue("string", "main_activity_title", "FinTrix (teste)")
            manifestPlaceholders["usesCleartextTraffic"] = "true"
            isDebuggable = true
            isJniDebuggable = true
            isMinifyEnabled = false
            packaging {
                jniLibs.keepDebugSymbols.add("*/arm64-v8a/*.so")
                jniLibs.keepDebugSymbols.add("*/armeabi-v7a/*.so")
                jniLibs.keepDebugSymbols.add("*/x86/*.so")
                jniLibs.keepDebugSymbols.add("*/x86_64/*.so")
            }
        }
        getByName("release") {
            signingConfig = signingConfigs.findByName("release")
            resValue("string", "app_name", "FinTrix")
            resValue("string", "main_activity_title", "FinTrix")
            optimization {
               enable = true
            }
            proguardFiles(
                *fileTree(".") {
                  include("**/*.pro")
                  exclude("build/**")
                }.files.toTypedArray()
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
    buildFeatures {
        buildConfig = true
        resValues = true // nome do app por build type (resValue)
    }
}

kotlin {
    compilerOptions {
        jvmTarget = JvmTarget.JVM_1_8
    }
}

rust {
    rootDirRel = "../../../"
}

dependencies {
    implementation("androidx.webkit:webkit:1.14.0")
    implementation("androidx.appcompat:appcompat:1.7.1")
    implementation("androidx.activity:activity-ktx:1.10.1")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.lifecycle:lifecycle-process:2.10.0")
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.1.4")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.0")
}

apply(from = file("tauri.build.gradle.kts"))
