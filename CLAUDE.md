# FinTrix — instruções para o Claude

App de finanças pessoais. Duas formas de rodar o mesmo `index.html`:
- **Web** (GitHub Pages, claude.ai ou servidor local): dados no IndexedDB do navegador ou na conta claude.ai.
- **App desktop** (branch `feat/tauri-desktop`): Tauri 2 + Rust, dados num SQLite cifrado (SQLCipher), sincronização entre aparelhos por cofre cifrado (pasta ou bucket S3).

## Regras

- **Não consultar os dados locais do usuário em verificações.** Não abrir, ler ou contar o que está em `~/.local/share/io.github.hudsonjunior42.fintrix/`, `~/.local/share/br.com.fintrix.app/`, no chaveiro do sistema (serviço `io.github.hudsonjunior42.fintrix`) nem no IndexedDB do navegador do usuário. Não rodar o app (debug ou release) sem `FINTRIX_DADOS` apontando para uma pasta temporária. Para verificar algo, use `test/desktop.py` ou crie dados de teste numa pasta temporária.
- Tudo em português do Brasil: código (nomes de funções e variáveis), comentários, documentação, textos da interface e mensagens de commit (`feat: …`, `fix: …`, `docs: …`, `test: …`, `build: …`).
- `docs/especificacao.md` é a fonte de verdade das regras do app; atualize junto quando mudar comportamento.
- Não fazer push: esta máquina não tem credenciais do GitHub (nem `gh`). O usuário faz o push.
- Commits só quando o usuário pedir ou ao fechar uma etapa combinada; nunca no `main` (trabalho do desktop vai no `feat/tauri-desktop`).

## Estrutura

```
index.html               o app inteiro (HTML, CSS e JS num arquivo só, sem build)
crates/fintrix-core/     Rust: banco cifrado (lib.rs), campos com carimbo (campos.rs), sincronização (sync.rs)
src-tauri/               casca Tauri: janela, chave no chaveiro, comandos invoke, empacotamento
tools/tauri_prep.py      copia index.html + assets para dist/tauri/ (troca Google Fonts por assets/fonts/)
test/desktop.py          testa o app desktop pela interface; roteiros em test/desktop/*.js
test/ui/, test/*.py      testes da versão web (Playwright, não instalado nesta máquina)
docs/                    especificacao.md, desktop-tauri.md, sincronizacao.md, bucket-s3.md
```

## Comandos

O Rust está em `~/.cargo/bin` (não está no PATH dos shells do Claude): use `export PATH=$HOME/.cargo/bin:$PATH`. O shell do usuário é fish.

```bash
cargo test -p fintrix-core                 # núcleo: banco, mesclagem, cifra, dois aparelhos por pasta
python3 test/desktop.py                    # app desktop pela interface (precisa de tela e do FinTrix fechado)
cargo tauri build --bundles appimage,deb   # pacotes em target/release/bundle/ (copiar para dist/linux/)
python3 tools/tauri_prep.py                # só a cópia do app web (o build já chama)
```

Checagem rápida da versão web: servir a pasta (`.claude/launch.json` tem `fintrix-web` na porta 8765) e conferir `S.fase`, sem dados reais. Sintaxe do JS: extrair o maior `<script>` do index.html e rodar `node --check`.

## Convenções do código

- Valores em centavos (inteiros), datas `AAAA-MM-DD`, meses `AAAA-MM`.
- Todo acesso a dados passa pela "camada de dados" (`Backends`, `localDb` com um `persist`): `persistIdb` no navegador, `persistTauri` no desktop. Nunca chamar `window.claude` nem `window.__TAURI__` fora desse bloco e das funções do desktop já existentes (`invT`, `downloadsTauri`, `lojaTauri`).
- Textos que mudam no desktop: `tx(textoWeb, textoDesktop)` e `aqui()` ("neste navegador"/"neste computador"); `nativoTauri()` diz se está no app desktop. Não usar "navegador", "página", "baixar" ou "download" em texto visível no desktop (o teste `fase2.js` confere).
- Rust: comandos Tauri devolvem `Result<_, String>` com mensagens em português que a interface mostra direto.
- Variáveis `FINTRIX_DADOS`, `FINTRIX_CHAVE`, `FINTRIX_TESTE`, `FINTRIX_SALVAR_EM` só valem no build de debug (testes).
- Sincronização: a unidade de mesclagem é o registro inteiro (lançamento; `contas/<id>`, `cartoes/<id>`… na configuração). Ids que precisam ser iguais em dois aparelhos são determinísticos (ex.: `idFixa`). Limitações em `docs/sincronizacao.md`.
- Segurança: nunca registrar valores ou descrições em log; segredos (chave do banco no chaveiro; cofre e credenciais S3 dentro do banco cifrado); a política de conteúdo (CSP) bloqueia pedidos para fora do app.
