# App desktop (Tauri 2) — protótipo

**Status: protótipo, ainda não compilado nem testado.** Escrito sem o toolchain Rust instalado; o primeiro `cargo test` e `cargo tauri dev` podem apontar ajustes (nomes de features do `keyring`, versões das crates).

## Como funciona

- A interface é o mesmo `index.html`. Dentro do Tauri (`window.__TAURI__` presente), `Backends.local` usa `persistTauri()` em vez do IndexedDB: cada gravação vai por `invoke` para o Rust.
- `crates/fintrix-core`: guarda os documentos (`caminho` → JSON) num SQLite cifrado com SQLCipher. Chave de 256 bits aleatória.
- `src-tauri`: a casca. Guarda a chave no chaveiro do sistema (crate `keyring`); se o chaveiro não estiver disponível, o app não abre (a chave nunca vai para o disco em texto puro).
- O banco fica em `app_data_dir()/fintrix.db` (no Linux, `~/.local/share/br.com.fintrix.app/`).

## O que ainda não está coberto

- Comprovantes (anexos) e cópias automáticas continuam no IndexedDB da WebView.
- Textos do app ainda dizem "neste navegador".
- Fontes ainda vêm do Google Fonts (sem internet, usa as de reserva).
- Sem senha de abertura, bloqueio por inatividade nem sincronização (fases seguintes do plano).
- `csp` está `null` para o protótipo; endurecer antes de distribuir.

## Rodar

Pré-requisitos no Arch/CachyOS: `rustup` (ou `rust`), `webkit2gtk-4.1`, `gtk3`, `openssl`, `base-devel`, um chaveiro com Secret Service (gnome-keyring ou KWallet).

```
cargo test -p fintrix-core        # testes do armazenamento cifrado
cargo install tauri-cli --version "^2"
cargo tauri dev                   # abre o app
```
