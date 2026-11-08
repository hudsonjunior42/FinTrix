# App Android

O mesmo projeto do desktop (Tauri 2) gera o app Android: o `index.html` roda na WebView do sistema, e o Rust (`fintrix-core`) guarda os dados num SQLite cifrado e sincroniza pelo mesmo cofre. O celular entra no cofre do computador lendo o QR code do pareamento, e os dois ficam iguais. As diferenças que a pessoa vê estão em [especificacao.md](especificacao.md) ("App Android").

Feito em nov/2026 e conferido num Redmi Note 11 (Android 13, arm64). Dois apps no celular:

| | Release | Debug |
|---|---|---|
| Nome | FinTrix | FinTrix (teste) |
| Id | `io.github.hudsonjunior42.fintrix` | `io.github.hudsonjunior42.fintrix.debug` |
| Assinatura | chave em `~/.config/fintrix/` | chave de debug do Android Studio |
| Dados | os de verdade: **não mexer em testes** | só de teste; DevTools e `run-as` ligados |

## Ambiente

- **Android Studio** → SDK Manager: Android SDK Platform 37 (o `compileSdk`/`targetSdk` do tauri-cli 2.12; o `minSdk` é 24, Android 7+), Build-Tools, Platform-Tools, NDK (Side by side) e Command-line Tools. O JDK é o que vem com ele (`/opt/android-studio/jbr`).
- **Rust**: `rustup target add aarch64-linux-android armv7-linux-androideabi` (o `cargo tauri android init` instala os outros).
- **Variáveis** (no fish, em `~/.config/fish/conf.d/android.fish`, com `set -gx`):

```bash
export JAVA_HOME=/opt/android-studio/jbr ANDROID_HOME=$HOME/Android/Sdk
export NDK_HOME=$ANDROID_HOME/ndk/30.0.16248370
```

- **Celular**: opções do desenvolvedor → depuração USB; `adb devices` precisa listar o aparelho. Em Xiaomi (MIUI), ligar também "Instalar via USB"; cada instalação pede confirmação na tela (uns 10 s), senão `adb install` falha com `INSTALL_FAILED_USER_RESTRICTED`. Se a confirmação nem aparecer, desligar e ligar de novo "Instalar via USB".

## Compilar e instalar

```bash
cargo tauri android build --debug --apk --target aarch64     # FinTrix (teste)
adb install -r src-tauri/gen/android/app/build/outputs/apk/universal/debug/app-universal-debug.apk
adb shell am start -n io.github.hudsonjunior42.fintrix.debug/io.github.hudsonjunior42.fintrix.MainActivity

cargo tauri android build --apk --target aarch64             # release assinado (~28 MB)
cp src-tauri/gen/android/app/build/outputs/apk/universal/release/app-universal-release.apk dist/android/FinTrix-<versão>.apk
cp src-tauri/gen/android/app/build/outputs/mapping/universalRelease/mapping.txt dist/android/FinTrix-<versão>-mapping.txt
```

- Só `aarch64` (todo celular atual). Para aparelhos antigos de 32 bits, acrescentar `--target armv7` (o APK cresce).
- O id do debug vem de `bundle.android.debugApplicationIdSuffix` no `tauri.conf.json`: o tauri-cli reescreve o `applicationIdSuffix` do `app/build.gradle.kts` a cada build, então não adianta mudar lá. O nome ("FinTrix (teste)") vem de `resValue` no mesmo arquivo.
- `versionName` e `versionCode` saem do `version` do `tauri.conf.json` (0.1.0 → 1000). Subir a versão antes de cada APK publicado, senão o Android não instala por cima.
- `src-tauri/gen/android/` vai para o git (o `.gitignore` dele tira o que é gerado). Ícones: `python3 tools/icones_android.py` gera o ícone adaptativo (logo de `assets/logo.svg` dentro da área segura, fundo `#0E1117`), a camada monocromática (ícones temáticos do Android 13+) e os PNGs antigos.

## Assinatura

- A chave do release está em `~/.config/fintrix/fintrix-release.jks` (RSA 4096, alias `fintrix`, até 2054), com a senha em `~/.config/fintrix/assinatura.properties` (`storeFile`, `storePassword`, `keyAlias`, `keyPassword`). A pasta é 700 e fica fora do repositório. O `app/build.gradle.kts` lê esse arquivo (ou o caminho em `FINTRIX_ASSINATURA`); sem ele, o release sai sem assinatura e não instala.
- **Guarde uma cópia dos dois arquivos fora deste computador** (pendrive, gerenciador de senhas). Toda atualização precisa da mesma chave; sem ela, o app novo só instala depois de desinstalar o antigo, e os dados do celular vão junto (voltam pelo cofre de sincronização, ou pelo backup + chave de recuperação).
- Impressão digital (SHA-256) do certificado: `2D:D6:F8:E4:F3:D9:01:92:80:D8:3C:DA:F7:27:1D:3D:27:33:13:91:0C:F5:E5:8A:35:1E:C3:A7:E5:AC:DB:10`. Conferir um APK: `apksigner verify --print-certs <apk>` (do `build-tools`, com o `java` do Android Studio no PATH).

## Distribuir

- APK assinado no GitHub Releases (o usuário sobe; esta máquina não faz push). Quem instala precisa permitir "instalar apps desconhecidos" para o navegador ou o app de arquivos.
- F-Droid ou Play Store depois (a Play exige `.aab` com `--aab`, política de privacidade e revisão).

## Testar

- **Núcleo**: `cargo test -p fintrix-core` no PC cobre a mesclagem e a cifra, que são as mesmas no celular.
- **No celular, só o FinTrix (teste)**, com dados de teste. O DevTools da WebView de debug permite testar sem tocar na tela (o MIUI bloqueia toques simulados):

```bash
adb forward tcp:9333 localabstract:webview_devtools_remote_$(adb shell pidof io.github.hudsonjunior42.fintrix.debug)
node test/android/avaliar.mjs 9333 'S.fase'      # avalia na página; aceita await dentro de uma função async
```

  Ou `chrome://inspect` no Chrome do PC. Para zerar os dados de teste (o MIUI bloqueia `pm clear`): `adb shell "run-as io.github.hudsonjunior42.fintrix.debug rm -f fintrix.db fintrix.db-wal fintrix.db-shm no_backup/chave-do-banco.bin"`.
- **Sincronização PC ↔ celular**: `python3 test/android_sync.py` sobe um S3 local (`test/s3_local.py`; http só no build de debug, o celular chega nele por `adb reverse`), abre o FinTrix de teste no PC com os dados de `fase1.js` e o QR code, e espera o celular ler o QR, receber tudo e lançar "Farmácia do celular" (R$ 45,00); depois confere o cofre (dois aparelhos, nada em claro).
- **O release passa pelo R8** (encolhe e renomeia o código Java/Kotlin) e o debug não: o que funciona no FinTrix (teste) pode travar no release. Bibliotecas que acham classes por reflexão precisam de regras em `app/proguard-rules.pro`; o ML Kit do leitor de QR já tem (sem elas, o app fechava ao abrir a câmera). Para testar o R8 no app de teste, ligar por um momento no bloco `debug` do `app/build.gradle.kts` o mesmo `optimization { enable = true }` e `proguardFiles(...)` do release.
- **Travamento no release**: `adb logcat -d -b crash` mostra o rastro com nomes trocados; `retrace dist/android/FinTrix-<versão>-mapping.txt rastro.txt` (das Command-line Tools, com o `java` do Android Studio no PATH) devolve os nomes de verdade. O log de travamento não tem dados do app.
- O que só se testa à mão: botão voltar, seletores de arquivo ("Restaurar backup", "Anexar foto ou PDF": a WebView só abre com toque de verdade), câmera do QR.

## Como funciona no celular

**Casca** (`src-tauri/src/lib.rs`): o código fica em `run()` com `#[cfg_attr(mobile, tauri::mobile_entry_point)]`; o `main.rs` do desktop só chama `run()`. O que existe só num lado fica em `#[cfg(desktop)]`/`#[cfg(mobile)]` (chaveiro, ícone e tamanho da janela, escolher pasta). Plugins Kotlin próprios, em `gen/android/app/src/main/java/…`, não têm manifesto de permissões: só o Rust os chama, e a interface recebe "not allowed" se tentar.

- **Chave do banco**: `ChavePlugin.kt` guarda a chave em `no_backup/chave-do-banco.bin`, cifrada com AES-GCM por uma chave do **Android Keystore** (`fintrix-chave-do-banco`, não exportável); o Rust chama em `chaveiro::ler`/`guardar`. Sem a chave (app reinstalado, troca de celular), a interface pede a chave de recuperação, como no desktop.
- **Backup do Android desligado** (`allowBackup="false"`): o banco não vai para o Google Drive nem sai por `adb backup`.
- **Banco**: `app_data_dir()` já é privada do app (`/data/data/<id>/fintrix.db`). SQLCipher com OpenSSL compilado junto (`bundled-sqlcipher-vendored-openssl` só no alvo Android, porque o NDK não tem OpenSSL).
- **S3 e TLS**: o rustls não acha sozinho as raízes do Android (`UnknownIssuer`); `sync::opcoes_android` carrega as do sistema (`/apex/com.android.conscrypt/cacerts` ou `/system/etc/security/cacerts`), que se atualizam com o Android. Todas as opções do cliente HTTP vão num objeto só (`with_client_options` troca o objeto inteiro).
- **Bytes pelo IPC**: no Android o `invoke` vai por postMessage em JSON, e um `Uint8Array` chega ao Rust como lista de números (`bytes_do_pedido` aceita os dois formatos); na volta o Tauri entrega `ArrayBuffer`. Custo: gravar um comprovante de 3 MB leva ~4 s.
- **Salvar arquivo**: o "Salvar como" do sistema devolve um `content://`, gravado pelo `tauri-plugin-fs` (`app.fs().open`), que também abre caminhos no desktop.
- **Ver PDF**: a WebView do Android não mostra PDF em `<iframe>`. O botão **Abrir** grava uma cópia em `cache/abrir/` (`abrir_arquivo`, apagada depois de 1 h) e entrega ao leitor do sistema por `FileProvider` (`SistemaPlugin.abrir`), só com leitura. O `file_paths.xml` libera só essa pasta e a das fotos da câmera.
- **Sincronização**: só por bucket S3 (`destino_aceito` recusa cofre em pasta, porque o app não enxerga a pasta do Syncthing pelo caminho). O laço de 1 minuto para com o app em segundo plano; a interface sincroniza ao abrir, ao voltar para o app (`visibilitychange`) e depois de cada gravação.
- **Pareamento pelo QR code**: a janela "Código de pareamento" mostra o QR (`qr_svg`, crate `qrcode`); no celular, **Ler QR code** usa o plugin oficial `barcode-scanner` (permissões em `capabilities/celular.json`) e já pareia.
- **Botão voltar**: o Tauri entrega o voltar ao histórico da WebView e, sem histórico, fecha o app. Enquanto houver algo aberto (visualizador, menu, janela, seleção, ou uma tela que não é o Início), fica uma entrada extra no histórico (`acertarVoltar`, chamado por um `MutationObserver`); o `popstate` dá um passo, como o Esc (`voltarUmPasso`).
- **Barras do sistema**: o app desenha atrás das barras (`enableEdgeToEdge`); `barrasTauri()` → `barras` → `SistemaPlugin.barras` deixa os ícones escuros no tema claro do app e claros no escuro. O fundo da abertura segue o tema do sistema (`values*/fundo.xml`).
- **Textos**: `celular()` e `aparelho()` na interface ("neste celular" em `aqui()`); sem o painel de atalhos de teclado; cabeçalho com "Geral" e o mês em 3 letras (`mesAbrev`).
- **Área segura do topo**: a WebView desenha atrás da barra de status e o `:root` desconta a área segura (`padding-top: env(safe-area-inset-top)`); o cabeçalho (`.top`) não soma de novo (somava, e sobrava uma faixa vazia da altura da barra, também na versão web instalada no celular).
- **Leitor de QR no release**: o ML Kit (Google) acha os próprios componentes por reflexão; encolhido pelo R8, `InputImage.fromMediaImage` dava `NullPointerException` no primeiro quadro da câmera. `app/proguard-rules.pro` mantém `com.google.mlkit.**`, `com.google.android.gms.internal.mlkit_**` e `com.google.firebase.components.**`.
- **Permissões**: `INTERNET` (S3) e `CAMERA` (QR code, pedida na hora). Nada de armazenamento externo.

## Pendências e ideias

- Conferir as áreas seguras num Android 15+, onde o desenho atrás das barras é obrigatório (no Android 13 a tela fica certa).
- Cofre em pasta no celular: pelo seletor de pasta do sistema (`ACTION_OPEN_DOCUMENT_TREE`) e um destino novo em `sync.rs` que lê e grava por um plugin Kotlin.
- Sincronizar em segundo plano (WorkManager).
- Comprovantes grandes mais rápidos: mandar em base64 ou em partes.
- Emulador: esta máquina não tem `/dev/kvm`; com a virtualização ligada na BIOS, o alvo `x86_64-linux-android` serve para testes sem o celular.
