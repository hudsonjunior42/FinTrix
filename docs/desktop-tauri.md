# App desktop (Tauri 2) — protótipo

**Status: protótipo, testado no Linux (WebKitGTK).** `cargo test -p fintrix-core` (6 testes) e `python3 test/desktop.py` passam. Não testado no Windows, macOS nem Android.

## Onde ficam os dados

Tudo em `~/.local/share/io.github.hudsonjunior42.fintrix/` (no Linux; nos outros sistemas, a pasta de dados do app com o mesmo nome). A pasta é só do usuário (permissão 700).

| O quê | Onde | Cifrado |
|---|---|---|
| Lançamentos, contas, cartões, categorias, fixas, orçamento | `fintrix.db` (e `-wal`, `-shm`) | sim (SQLCipher) |
| Comprovantes e cópias automáticas | `fintrix.db`, tabela `itens` | sim |
| Preferências da tela (tema, última tela, ordem, modo discreto) | `webview/` (localStorage da WebView) | não, mas não há valores nem descrições |
| Chave do banco | chaveiro do sistema (Secret Service), serviço `io.github.hudsonjunior42.fintrix`, usuário `chave-do-banco` | protegida pelo chaveiro |

As primeiras versões do protótipo usavam o identificador `br.com.fintrix.app`. Na primeira abertura, o app move o banco e a chave de lá para o lugar novo. O que sobra em `~/.local/share/br.com.fintrix.app/` são só dados da WebView e pode ser apagado.

## Chave de recuperação

- A chave é aleatória (256 bits), gerada na primeira abertura e guardada no chaveiro. Nunca vai para um arquivo.
- **Configurações › Seus dados › Chave de recuperação › Mostrar** exibe a chave em grupos de 4. Anote em papel ou num gerenciador de senhas: com a chave e o arquivo do banco, qualquer pessoa lê os dados.
- Se a chave não está no chaveiro (sistema reinstalado, outro usuário) ou não abre o banco, o app não mostra nada e pede a chave de recuperação. Aceita com ou sem hífens, em maiúsculas ou minúsculas. A chave certa volta para o chaveiro.
- Sem chaveiro e sem banco, o app explica que precisa do gnome-keyring ou do KWallet.
- Outra saída é o backup .json, que restaura em qualquer versão do FinTrix (navegador, claude.ai ou desktop).

## Como funciona

- A interface é o mesmo `index.html`. Dentro do Tauri (`window.__TAURI__` presente), `Backends.local` usa `persistTauri()` em vez do IndexedDB: cada gravação vai por `invoke` para o Rust. Fora do Tauri nada muda.
- `crates/fintrix-core`: guarda os documentos (`caminho` → JSON) num SQLite cifrado com SQLCipher.
- Comprovantes e cópias automáticas também vão para o SQLite cifrado (tabela `itens`, lojas `anexos` e `sistema/copias`): no app desktop, `anxTx` e `sisTx` usam `lojaTauri`, que imita o object store do IndexedDB. Os arquivos vão como bytes crus (`loja_gravar_bytes`, `loja_bytes`).
- Backup, CSV, .zip e comprovantes são salvos pela janela "Salvar como" do sistema (`downloadsTauri` → comando `salvar_arquivo`, com `tauri-plugin-dialog`). A mensagem mostra o caminho escolhido.
- `src-tauri`: a casca. Abre o banco (`Banco`), guarda e lê a chave no chaveiro (crate `keyring`), migra o identificador antigo e cria a janela.
- **Ícone e uma instância só:** o nome do programa no GTK é o identificador (`glib::set_prgname`), que vira o app_id da janela no Wayland. O KDE e o GNOME acham o ícone pelo arquivo `.desktop` e pelo ícone com esse nome. O .deb e o AppImage trazem os dois; ao rodar o AppImage ou o executável solto, o app grava (ou atualiza) `~/.local/share/applications/io.github.hudsonjunior42.fintrix.desktop` e o ícone em `~/.local/share/icons/hicolor/256x256/apps/`, o que também põe o FinTrix no menu. Com `enableGTKAppId`, abrir o app de novo não cria uma segunda janela (duas gravando no mesmo banco perderiam dados).
- **Textos:** no app desktop, `tx(web, desktop)` e `aqui()` trocam "navegador", "página" e "baixar" por "computador", "tela" e "salvar".
- **Sem internet:** o `tools/tauri_prep.py` troca o Google Fonts por `assets/fonts/` (IBM Plex Sans, IBM Plex Mono, Bricolage Grotesque, licença SIL OFL 1.1) na cópia empacotada. A política de conteúdo (`csp` no `tauri.conf.json`) só permite arquivos do próprio app, `blob:`/`data:` para imagens e o canal do Tauri; qualquer pedido para fora é bloqueado.

## Sincronização

Entre aparelhos, por uma pasta sincronizada ou um bucket S3, com tudo cifrado no aparelho: veja [sincronizacao.md](sincronizacao.md).

## O que ainda não está coberto

- Sem senha de abertura e bloqueio por inatividade.
- Sem backup automático numa pasta (a versão do navegador usa uma API do Chrome que a WebView não tem).
- A janela "Salvar como" de verdade não é exercitada pelo teste automático (ele grava direto numa pasta temporária).
- Preferências da tela que estavam na WebView da pasta antiga não são migradas (o app abre com as preferências padrão).

## Teste pela interface

`python3 test/desktop.py` compila o app de debug e o abre várias vezes em pastas temporárias, com chaves geradas para o teste. As variáveis `FINTRIX_DADOS`, `FINTRIX_CHAVE`, `FINTRIX_TESTE` e `FINTRIX_SALVAR_EM` só valem no build de debug e não tocam no chaveiro real. Os roteiros ficam em `test/desktop/`: o app executa o roteiro na página e devolve o resultado pelo comando `teste_fim`. Precisa de tela, e o FinTrix precisa estar fechado (é uma instância só).

1. Cria a conta, lança uma despesa com comprovante, guarda uma cópia automática e salva um backup pela tela de Configurações. Confere a fonte local e que um pedido para a internet é bloqueado.
2. Reabre: dados, comprovante, cópia e .zip voltam do banco; a chave de recuperação aparece em Configurações; Configurações, a janela de cópias e a de restaurar não falam em navegador, página, baixar ou download.
3. Reabre sem a chave no chaveiro e depois com uma chave errada: o app pede a chave, recusa uma errada e abre com a certa digitada com hífens e em maiúsculas.
4. Numa pasta nova, restaura o backup da etapa 1 pela apresentação.
5. A pasta de dados tem permissão 700, o banco não tem o cabeçalho do SQLite e nenhum arquivo tem os textos lançados ou o conteúdo do comprovante em claro.

## Rodar

Pré-requisitos no Arch/CachyOS: `rustup` (ou `rust`), `webkit2gtk-4.1`, `gtk3`, `openssl`, `base-devel`, um chaveiro com Secret Service (gnome-keyring ou KWallet).

```
cargo install tauri-cli --version "^2" --locked   # uma vez
cargo test -p fintrix-core                        # testes do armazenamento cifrado
cargo tauri dev                                   # abre o app
```

## Gerar os pacotes para Linux

```
cargo tauri build --bundles appimage,deb
```

Saída em `target/release/bundle/` (`appimage/FinTrix_<versão>_amd64.AppImage` e `deb/FinTrix_<versão>_amd64.deb`). O AppImage roda em qualquer distribuição (no Arch/CachyOS é o indicado); o .deb é para Debian/Ubuntu e declara `libwebkit2gtk-4.1-0` e `libgtk-3-0` como dependências. Para gerar o AppImage, o Tauri baixa o linuxdeploy do GitHub na primeira vez.
