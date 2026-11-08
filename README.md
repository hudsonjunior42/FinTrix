<p align="center">
  <img src="assets/logo.svg" alt="" width="88">
</p>

<h1 align="center">FinTrix</h1>

<p align="center">Controle financeiro pessoal: contas, cartões, faturas, orçamento e relatórios.<br>
Um app web em um arquivo só, sem instalação e sem servidor, e um app desktop (protótipo) com os dados cifrados.</p>

<p align="center">
  <img src="docs/img/visao-geral.png" alt="Visão geral do FinTrix no tema escuro: saldos, contas a pagar, gastos por categoria e cartões" width="820">
</p>

## O que ele faz

- **Lançamentos rápidos** numa janela só, com quatro abas: Despesa, Receita, Cartão e Transferência. O campo de valor aceita contas (25,90+12,50), um lançamento pode ser dividido entre categorias e as datas são sempre DD/MM/AAAA, com calendário.
- **Contas** corrente, poupança, carteira, benefícios e investimentos, com saldo atual, saldo previsto no fim do mês e ajuste de saldo.
- **Cartões de crédito** com a fatura calculada pelo dia de fechamento, limite disponível, pagamento e ajuste de fatura.
- **Fixas e parcelados.** As fixas podem repetir todo mês ou a cada 2, 3, 6 ou 12 meses, inclusive com valor variável (luz, água). Os parcelados aceitam informar a parcela atual. Um lançamento pode virar único, fixo ou parcelado depois de salvo.
- **Orçamento** por categoria, com histórico mês a mês, previsão de fechamento e aviso a partir de 80% do limite, já na janela de lançamento.
- **Relatórios** por categoria e por tag, com análise mensal ou anual e gráficos em barras, rosca ou blocos.
- **Patrimônio e metas**, importação de extrato e fatura (CSV e OFX) e comprovantes anexados aos lançamentos.
- **No dia a dia:** busca em qualquer período, seleção múltipla para editar ou excluir vários lançamentos, Desfazer depois de excluir, modo discreto (esconde os valores), tema escuro e claro e atalhos de teclado (D, R, C, T).
- **Seus dados:** backup e restauração em JSON e exportação em CSV (abre no Excel e no OnlyOffice).

<p align="center">
  <img src="docs/img/lancamentos-claro.png" alt="Lista de lançamentos no tema claro" width="620">
  <img src="docs/img/celular-lancamento.png" alt="Janela de nova despesa no celular" width="190">
</p>

## Como usar

O app inteiro é o [`index.html`](index.html).
Também pode ser acessado a partir de https://hudsonjunior42.github.io/FinTrix/

### App desktop (protótipo)

O mesmo app como programa para Linux, feito com [Tauri 2](https://tauri.app): a interface é o `index.html` e a parte em Rust guarda os dados.

- **Dados cifrados no computador.** Lançamentos, comprovantes e cópias automáticas ficam num SQLite cifrado com SQLCipher, em `~/.local/share/io.github.hudsonjunior42.fintrix/`. A chave é aleatória e fica no chaveiro do sistema (gnome-keyring ou KWallet), nunca num arquivo. Anote a chave de recuperação em Configurações › Seus dados.
- **Funciona sem internet** (fontes incluídas) e não faz pedidos para fora. Backup e CSV são salvos pela janela "Salvar como" do sistema.
- **Pacotes:** AppImage (qualquer distribuição) e .deb (Debian e Ubuntu). Gere com os comandos em [Desenvolvimento](#app-desktop-tauri).
- **Para trazer os dados** do navegador ou do claude.ai: baixe um backup lá e use *Restaurar um backup* no app desktop.
- **Ainda é protótipo:** testado só no Linux, sem senha de abertura e sem sincronização entre aparelhos. Detalhes e limitações em [docs/desktop-tauri.md](docs/desktop-tauri.md). A versão Android é a próxima fase.

## Estrutura

```
index.html            o app completo (HTML, CSS e JavaScript num arquivo só)
assets/               logo (SVG e PNG) e fontes que vão no app desktop (fonts/)
Cargo.toml            workspace Rust do app desktop
crates/fintrix-core/  armazenamento cifrado (SQLCipher) usado pelo app desktop
src-tauri/            casca Tauri: janela, chave no chaveiro do sistema, ícones e configuração dos pacotes
docs/
  especificacao.md    regras e decisões do app (fonte de verdade para mudanças)
  rodar-localmente.md uso fora do claude.ai e migração dos dados
  desktop-tauri.md    app desktop: como funciona, limitações, testes e pacotes
  pwa.md              instruções do pacote instalável (vai junto com ele)
  img/                capturas de tela deste README
tools/
  pwa_build.py        gera o pacote instalável (PWA) em dist/pwa/
  tauri_prep.py       copia o app web para dist/tauri/, a pasta que o Tauri empacota
  capturas.py         gera as capturas de tela de docs/img/ com dados fictícios
test/
  ui/                 testes de interface com banco simulado (um arquivo por funcionalidade)
  desktop.py          testa o app desktop pela interface (dados, comprovantes, backup e restauração, chave de recuperação, nada em claro)
  desktop/            roteiros que o app desktop executa durante esse teste
  v1.py, v11.py       testes de integração das versões 1.0 e 1.1 (segurança dos dados, importação, migração)
  regressao.py        compara duas versões do app com a mesma base grande
  pwa_v1.py           testa o pacote instalável (offline, atualização)
```

## Desenvolvimento

- **Sem build e sem dependências.** É JavaScript puro num arquivo só. As fontes vêm do Google Fonts (no app desktop, de `assets/fonts/`).
- **Camada de dados.** Todo acesso a dados passa pelo bloco "camada de dados" no início do script (`Backends.local`). Para hospedar com sincronização própria (PocketBase, Supabase…), basta acrescentar outro backend que cumpra o mesmo contrato.
- **Valores em centavos** (inteiros), datas `AAAA-MM-DD` e meses `AAAA-MM`.
- **Testes** com Playwright (Python). Como instalar e rodar: [test/README.md](test/README.md).

### App desktop (Tauri)

Precisa de Rust ([rustup](https://rustup.rs)), `webkit2gtk-4.1`, `gtk3`, `openssl` e as ferramentas de compilação (`base-devel` no Arch, `build-essential` no Debian/Ubuntu).

```bash
cargo install tauri-cli --version "^2" --locked   # uma vez
cargo tauri dev                                   # abre o app em modo de desenvolvimento
cargo test -p fintrix-core                        # testes do armazenamento cifrado
python3 test/desktop.py                           # testa o app pela interface (precisa de tela)
cargo tauri build --bundles appimage,deb          # pacotes em target/release/bundle/
```

O `index.html` continua funcionando sozinho no navegador: dentro do app desktop ele usa o armazenamento do Rust, e fora dele o IndexedDB, como antes.

### Versão instalável (PWA)

O `tools/pwa_build.py` gera um pacote que instala como app no celular e no computador e funciona sem internet. Ele está pronto e testado, mas a publicação fica para a versão 1.0.

```bash
python3 tools/pwa_build.py   # saída em dist/pwa/ (fora do Git)
```

## Licença

[MIT](LICENSE) © 2026 Hudson Santos Menezes Júnior
