# Plano: app Android

O Tauri 2 gera app Android a partir do mesmo projeto (`cargo tauri android init|dev|build`). A ideia é a mesma do desktop: o `index.html` roda na WebView do sistema, o Rust (`fintrix-core`) guarda os dados num SQLite cifrado e sincroniza pelo mesmo cofre. Assim o celular entra no cofre do computador com o código de pareamento ("Parear com outro aparelho" na apresentação) e os dois ficam iguais.

O que já serve sem mudança: a interface (já funciona em 380 px, com toque, e já respeita as áreas seguras com `viewport-fit=cover` e `env(safe-area-inset-*)`), o formato dos dados, a mesclagem e a cifra do cofre (`sync.rs`), e o pareamento.

## Decisões (nov/2026)

- **Testes num celular real** pela depuração USB (`adb`). Esta máquina não tem `/dev/kvm`, então o emulador seria lento demais; se a virtualização for ligada na BIOS, o emulador x86_64 entra depois.
- **Ambiente pelo Android Studio** (traz o JDK, o SDK Manager e o NDK).
- **Sincronização no Android só por bucket S3** na primeira versão; pasta pelo seletor do sistema (SAF) fica para depois (item 3).
- **Distribuição por APK assinado no GitHub Releases.** F-Droid e Play Store ficam para depois.

## 0. Ambiente

Esta máquina já tem o `adb` (pacote `android-tools`) e o `tauri-cli` 2.12; falta o resto:

- Android Studio → SDK Manager: Android SDK Platform 34, Build-Tools, Platform-Tools, NDK (Side by side) 26+ e Command-line Tools. Variáveis (no fish, em `~/.config/fish/config.fish`): `JAVA_HOME` (o JBR do Android Studio, `…/android-studio/jbr`), `ANDROID_HOME=~/Android/Sdk`, `NDK_HOME=$ANDROID_HOME/ndk/<versão>`.
- Alvos Rust: `rustup target add aarch64-linux-android armv7-linux-androideabi` (celulares atuais são aarch64; o armv7 cobre os antigos). O `x86_64-linux-android` só se o emulador entrar.
- No celular: opções do desenvolvedor → depuração USB; `adb devices` precisa listar o aparelho.
- `cargo tauri android init` cria `src-tauri/gen/android/` (projeto Gradle). Vai para o git, com o ícone e o nome do app ajustados.

## 1. Compilar o núcleo para Android

| Ponto | Problema | Saída |
|---|---|---|
| SQLCipher | `bundled-sqlcipher` usa o OpenSSL do sistema, que não existe no NDK | trocar para `bundled-sqlcipher-vendored-openssl` só no alvo Android (`[target.'cfg(target_os = "android")'.dependencies]`), ou compilar o SQLCipher com a cripto do próprio Rust se o OpenSSL vendorizado der trabalho no NDK |
| S3 (`object_store` + `reqwest`/rustls) | `rustls-native-certs` não acha os certificados do Android | usar as raízes do `webpki-roots` (ou `rustls-platform-verifier`) no Android; conferir com um bucket de teste |
| `getrandom`, `chacha20poly1305`, `flate2` | nada | funcionam no Android |

Primeiro marco: `cargo build -p fintrix-core --target aarch64-linux-android` e `cargo test -p fintrix-core` no host continuam passando.

## 2. A casca Tauri no celular (`src-tauri/src/lib.rs`)

- **Ponto de entrada**: mover o `main()` para `lib.rs` com `#[cfg_attr(mobile, tauri::mobile_entry_point)] pub fn run()`, e o `main.rs` só chama `run()`. `Cargo.toml` ganha `[lib] crate-type = ["staticlib", "cdylib", "rlib"]`.
- **Janela**: no celular não existem `inner_size`, `min_inner_size`, ícone nem `data_directory`; separar com `#[cfg(desktop)]`. `glib::set_prgname` e `registrar_atalho` já são só Linux.
- **Chave do banco (o ponto mais delicado)**: o crate `keyring` não tem Android. Opções:
  1. Plugin Tauri próprio (Kotlin, pequeno) que guarda a chave cifrada com uma chave do **Android Keystore** (AES-GCM, sem exportar), num arquivo da pasta privada do app. Recomendado.
  2. Plugin `tauri-plugin-stronghold` ou similar: mais pesado e muda o modelo de senha.
  A interface já tem a tela "Informe a chave de recuperação" para quando a chave some (troca de celular, app reinstalado); ela vale igual no Android.
- **Pasta de dados**: `app_data_dir()` no Android já é privada do app (`/data/data/<id>/`); `restringir` (700) não é necessário lá. `FINTRIX_*` continuam só no debug.
- **Salvar arquivo** (`salvar_arquivo`: backup, CSV, comprovantes): o `tauri-plugin-dialog` no Android abre o seletor do sistema (SAF) e devolve um `content://`; gravar por ele em vez de `fs::write` no caminho. Alternativa: compartilhar pelo menu do Android (plugin de compartilhamento).
- **Abrir arquivo** (restaurar backup, anexar comprovante): o `<input type="file">` da WebView do Android funciona; conferir também a câmera para foto de comprovante (`accept="image/*"`).
- **Permissões**: só `INTERNET` (para o S3). Nada de armazenamento externo.

## 3. Sincronização no celular

- **Bucket S3**: funciona igual; é o destino recomendado para quem usa o celular.
- **Pasta sincronizada**: no Android o app não enxerga a pasta do Syncthing pelo caminho. Duas saídas: (a) usar SAF (`ACTION_OPEN_DOCUMENT_TREE`) e um destino novo em `sync.rs` que lê e grava por um plugin Kotlin; (b) na primeira versão, aceitar só S3 no Android e avisar no pareamento quando o código for de pasta. **Decidido: (b) primeiro**, (a) depois.
- **Quando sincronizar**: o laço `sincronizar_sempre` só roda com o app aberto, e o Android suspende apps em segundo plano. Sincronizar ao abrir, ao voltar para o app (evento de foco/`visibilitychange`) e depois de cada gravação, como hoje. Segundo plano de verdade (WorkManager) fica para depois.
- **Pareamento pelo celular**: digitar o código é ruim. Adicionar um QR code na janela "Código de pareamento" do desktop e um leitor no Android (plugin `barcode-scanner` do Tauri). O QR fica só na tela, como o código.

## 4. Interface (`index.html`)

- `nativoTauri()` continua valendo; acrescentar `celular()` (Android) para os poucos textos diferentes: "neste celular" em `aqui()`, e esconder "Escolher…" da pasta se a opção (b) do item 3 for a escolhida.
- Teclas de atalho e arrastar arquivo não existem no celular: já são opcionais, nada quebra.
- Áreas seguras (barra de status e de gestos): já feitas para o PWA (topo, barra de abas, botão flutuante, rodapé das janelas); só conferir no celular se a WebView do Tauri desenha atrás das barras (edge-to-edge) ou não.
- Botão voltar do Android: fechar a janela aberta (modal) antes de sair do app.
- Tema: a barra de status acompanha o tema claro/escuro (`theme-color`).

## 5. Testes

- `cargo test -p fintrix-core` no host (cobre a mesclagem e a cifra, que são as mesmas).
- Celular real pela USB com `cargo tauri android dev` (build de debug), dados de teste e um bucket de teste (ou MinIO rodando no PC, na mesma rede); nunca os dados reais. O build de debug usa a chave fixa de teste e fica ao lado de um eventual FinTrix de verdade só se tiver outro `identifier` (sufixo `.debug`), para não misturar dados.
- Adaptar o `test/desktop.py` para Android é caro (o roteiro entra por `FINTRIX_TESTE`, que lê um arquivo do PC). Mais simples: `adb push` do roteiro para `/data/local/tmp/` e `adb shell run-as <id> cp …` para a pasta do app (o `run-as` só funciona no build de debug); o resultado sai pelo log (`adb logcat`). Depuração da WebView: `chrome://inspect` no Chrome do PC.
- Teste manual de ponta a ponta: desktop liga o cofre S3 → celular pareia pela apresentação → lança dos dois lados → os dois veem tudo.

## 6. Empacotar e distribuir

- `cargo tauri android build --apk --target aarch64` (ou `--aab` para a Play Store).
- Chave de assinatura própria (`keytool`), guardada fora do repositório; configurar em `gen/android/keystore.properties` (no `.gitignore`).
- `identifier` continua `io.github.hudsonjunior42.fintrix`; `versionCode` sobe a cada versão.
- Distribuição: APK assinado no GitHub Releases (o usuário sobe; esta máquina não faz push). F-Droid ou Play Store depois (a Play exige `.aab`, política de privacidade e revisão).
- Atualização: o APK novo instala por cima só se for assinado com a mesma chave; perder a chave obriga a desinstalar (e os dados locais vão junto, voltando pelo cofre ou pela chave de recuperação + backup).

## Andamento

- Feito: alvos Rust do Android instalados; casca movida para `lib.rs` com `run()` e `mobile_entry_point` (o `main.rs` só chama `run`); `keyring`, `migrar_do_antigo`, ícone e tamanho da janela só no desktop; no celular, `escolher_pasta` responde que lá é só bucket e a chave é fixa de teste no debug (release ainda sem chaveiro); SQLCipher com OpenSSL vendorizado no alvo Android. Desktop conferido (`cargo test -p fintrix-core`, `test/desktop.py`).
- Falta para fechar a etapa 1: Android Studio (SDK + NDK), `cargo tauri android init` e o app abrindo no celular. O código do celular (`cfg(mobile)`) ainda não foi compilado: o `ring` e o SQLCipher precisam do clang do NDK.

## Ordem sugerida

0. Fechar o que está pendente no desktop (mensagens de erro do bucket em `sync.rs`, `contexto()` no `main.rs`) num commit, porque a etapa 2 mexe muito no `main.rs`.
1. Ambiente + `android init` + app abrindo no celular com a chave fixa de teste (só debug).
2. SQLCipher e S3 compilando no Android; banco abrindo.
3. Plugin da chave no Keystore.
4. Salvar e abrir arquivos pelo seletor do sistema.
5. Sincronização por S3, pareamento pela apresentação, QR code.
6. Ajustes de interface (áreas seguras, voltar, textos).
7. Assinatura, APK, documentação (`docs/android.md` vira o guia, `especificacao.md` ganha as diferenças do Android).

Estimativa grosseira: etapas 1–2 são as de maior risco (compilação cruzada); 3 e 5 são o grosso do código novo; o resto é ajuste.
