# App desktop (Tauri 2) — protótipo

**Status: protótipo, testado no Linux (WebKitGTK).** `cargo test -p fintrix-core` (5 testes) e `python3 test/desktop.py` passam: pela interface, cria a conta, lança uma despesa, fecha, reabre com os dados vindos do SQLite cifrado, recusa a chave errada e nenhum arquivo da pasta do app tem os textos lançados em claro. Não testado no Windows, macOS nem Android.

## Teste pela interface

`python3 test/desktop.py` compila o app de debug e o abre três vezes numa pasta temporária, com uma chave gerada para o teste (variáveis `FINTRIX_DADOS`, `FINTRIX_CHAVE` e `FINTRIX_TESTE`, que só valem no build de debug e não tocam no chaveiro real). Os roteiros ficam em `test/desktop/`: o app executa o roteiro na página e devolve o resultado pelo comando `teste_fim`. Precisa de tela.

## Como funciona

- A interface é o mesmo `index.html`. Dentro do Tauri (`window.__TAURI__` presente), `Backends.local` usa `persistTauri()` em vez do IndexedDB: cada gravação vai por `invoke` para o Rust.
- `crates/fintrix-core`: guarda os documentos (`caminho` → JSON) num SQLite cifrado com SQLCipher. Chave de 256 bits aleatória.
- `src-tauri`: a casca. Guarda a chave no chaveiro do sistema (crate `keyring`); se o chaveiro não estiver disponível, o app não abre (a chave nunca vai para o disco em texto puro).
- O banco fica em `app_data_dir()/fintrix.db` (no Linux, `~/.local/share/br.com.fintrix.app/`).

## O que ainda não está coberto

- Comprovantes (anexos) e cópias automáticas (`guardarCopia`, feitas antes de restaurar, migrar ou apagar tudo) continuam no IndexedDB da WebView (`webview/` na pasta do app), **sem criptografia**. O teste não passa por esses caminhos; é a próxima coisa a mover para o SQLite.
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
