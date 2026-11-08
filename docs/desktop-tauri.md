# App desktop (Tauri 2) — protótipo

**Status: protótipo, testado no Linux (WebKitGTK).** `cargo test -p fintrix-core` (6 testes) e `python3 test/desktop.py` passam: pela interface, cria a conta, lança uma despesa com comprovante, guarda uma cópia automática, fecha, reabre com tudo vindo do SQLite cifrado (inclusive o .zip de comprovantes), recusa a chave errada e nenhum arquivo da pasta do app tem os textos lançados ou o conteúdo do comprovante em claro. Não testado no Windows, macOS nem Android.

## Teste pela interface

`python3 test/desktop.py` compila o app de debug e o abre três vezes numa pasta temporária, com uma chave gerada para o teste (variáveis `FINTRIX_DADOS`, `FINTRIX_CHAVE` e `FINTRIX_TESTE`, que só valem no build de debug e não tocam no chaveiro real). Os roteiros ficam em `test/desktop/`: o app executa o roteiro na página e devolve o resultado pelo comando `teste_fim`. Precisa de tela.

## Como funciona

- A interface é o mesmo `index.html`. Dentro do Tauri (`window.__TAURI__` presente), `Backends.local` usa `persistTauri()` em vez do IndexedDB: cada gravação vai por `invoke` para o Rust.
- `crates/fintrix-core`: guarda os documentos (`caminho` → JSON) num SQLite cifrado com SQLCipher. Chave de 256 bits aleatória.
- Comprovantes e cópias automáticas também vão para o SQLite cifrado (tabela `itens`, lojas `anexos` e `sistema/copias`): no app desktop, `anxTx` e `sisTx` usam `lojaTauri`, que imita o object store do IndexedDB. Os arquivos vão como bytes crus (`loja_gravar_bytes`, `loja_bytes`).
- Dados de uma versão anterior deste protótipo que já estejam no IndexedDB da WebView não são migrados.
- `src-tauri`: a casca. Guarda a chave no chaveiro do sistema (crate `keyring`); se o chaveiro não estiver disponível, o app não abre (a chave nunca vai para o disco em texto puro).
- O banco fica em `app_data_dir()/fintrix.db` (no Linux, `~/.local/share/br.com.fintrix.app/`).

## O que ainda não está coberto

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

## Gerar os pacotes para Linux

```
cargo install tauri-cli --version "^2" --locked   # uma vez
cargo tauri build --bundles appimage,deb
```

Saída em `target/release/bundle/` (`appimage/FinTrix_<versão>_amd64.AppImage` e `deb/FinTrix_<versão>_amd64.deb`). O AppImage roda em qualquer distribuição (no Arch/CachyOS é o indicado); o .deb é para Debian/Ubuntu e declara `libwebkit2gtk-4.1-0` e `libgtk-3-0` como dependências. Para gerar o AppImage, o Tauri baixa o linuxdeploy do GitHub na primeira vez.

O identificador `br.com.fintrix.app` gera um aviso (no macOS conflita com a extensão `.app`). Trocar muda a pasta de dados, então é melhor decidir antes do primeiro uso de verdade.
