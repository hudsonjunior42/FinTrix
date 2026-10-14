# FinTrix: app instalável (PWA)

> **No repositório:** este texto é o `LEIAME.md` que vai dentro do pacote gerado por `tools/pwa_build.py` (pasta `dist/pwa/`). "Esta pasta", abaixo, é essa pasta gerada.

Esta pasta é o FinTrix completo, pronto para instalar no celular e no computador como um app: ícone próprio, tela cheia e funcionamento sem internet. É o mesmo app do claude.ai, só que os dados ficam guardados no próprio aparelho.

## 1. Publicar a pasta (uma vez)

O navegador só instala apps servidos por um endereço `https://`. Escolha um dos caminhos:

**Netlify Drop (o mais rápido, grátis)**
1. Abra https://app.netlify.com/drop no computador.
2. Arraste esta pasta inteira (a que tem o `index.html`) para a página.
3. Copie o endereço que aparece (algo como `https://nome-aleatorio.netlify.app`). Criando uma conta grátis, dá para trocar o nome e manter o site.

**GitHub Pages (grátis, com conta no GitHub)**
1. Crie um repositório, por exemplo `fintrix`, e envie todos os arquivos desta pasta para ele.
2. Em Settings › Pages, escolha "Deploy from a branch", branch `main`, pasta `/ (root)`.
3. Em um ou dois minutos o app fica em `https://SEU-USUARIO.github.io/fintrix/`.

**Só neste computador (sem publicar)**
Na pasta, rode `python3 -m http.server 8080` e abra `http://localhost:8080`. Funciona e instala, mas só neste computador.

**Escolha um endereço e não mude mais.** O navegador guarda os dados por endereço: `http://localhost:8080`, `http://localhost:8081` e `http://127.0.0.1:8080` são três bancos diferentes. Se um dia o FinTrix abrir vazio, confira primeiro se o endereço é o de sempre. Para testar versões novas sem mexer nos dados reais, use outra porta (por exemplo 8081): ela tem um banco separado.

## 2. Instalar

- **Android (Chrome):** abra o endereço, toque no menu ⋮ e em "Instalar app" (ou "Adicionar à tela inicial").
- **iPhone/iPad (Safari):** abra o endereço, toque em Compartilhar e em "Adicionar à Tela de Início".
- **Computador (Chrome ou Edge):** clique no ícone de instalar no fim da barra de endereço.

Depois de aberto uma vez, o app funciona sem internet.

Instalar também ajuda a proteger os dados: o navegador costuma liberar a "proteção contra limpeza automática" para apps instalados. Confira em Configurações › Seus dados.

No Android e no computador, segurar (ou clicar com o botão direito) no ícone mostra atalhos para Nova despesa, Nova receita, Compra no cartão e Transferência.

## 3. Levar os dados que já estão no claude.ai

1. Na versão do claude.ai: Configurações › Seus dados › **Baixar backup**.
2. No app instalado, na tela de abertura: **Restaurar um backup** e escolha o arquivo `.json`.

## Onde ficam os dados

- No navegador do aparelho em que o app está instalado. Cada navegador, cada sistema operacional (num dual boot, o Linux e o Windows têm bancos separados), cada aparelho e cada endereço tem os seus dados, e eles **não sincronizam** entre si nem com a versão do claude.ai. Escolha um lugar para ser a "casa" dos dados e lance só nele.
- Desinstalar o app ou limpar os dados do site no navegador apaga os lançamentos. Por isso:
  - **Backup automático (Chrome ou Edge no computador):** em Configurações › Seus dados › Backup automático, escolha uma pasta uma vez. O app grava `fintrix-backup-AAAA-MM-DD.json` sempre que algo muda e guarda os últimos 15 dias. Uma pasta sincronizada (Google Drive, Syncthing…) leva a cópia para fora do computador. Se o navegador pedir de novo a permissão da pasta, a Visão geral mostra o botão Permitir.
  - **Sem backup automático** (Firefox, celular): a Visão geral avisa quando está na hora de baixar um backup (Configurações › Baixar backup).
  - **Cópias automáticas:** antes de restaurar um backup, atualizar o formato dos dados ou apagar tudo, o app guarda uma cópia neste navegador (as 5 mais recentes, em Configurações › Seus dados). Elas ajudam a desfazer um engano, mas somem junto se os dados do navegador forem limpos.
- O app pede ao navegador para guardar os dados de forma permanente, o que reduz o risco de limpeza automática. Configurações mostra se o pedido foi aceito.
- **Comprovantes** (fotos e PDFs anexados aos lançamentos) ficam só neste aparelho e não entram no backup .json. O backup automático copia cada um para a subpasta `comprovantes` da pasta; sem ele, use Configurações › Seus dados › Comprovantes › Baixar .zip.
- Se a tela der erro, use **Baixar backup de emergência** (aparece na própria tela do erro) antes de qualquer outra coisa.

## Atualizar para uma versão nova

Substitua os arquivos publicados pelos da versão nova (no Netlify, arraste a pasta de novo no mesmo site; no GitHub, envie os arquivos por cima; no servidor local, troque os arquivos na pasta). O app instalado baixa a atualização em segundo plano e mostra **"Há uma versão nova do FinTrix pronta"** com o botão **Atualizar agora**; se você ignorar, ela vale na próxima abertura. Os dados não são afetados.

Quando uma versão muda o formato dos dados, o app atualiza os dados sozinho na abertura e guarda uma cópia antes. Uma versão antiga do app nunca abre dados de uma versão mais nova (mostra um aviso para recarregar), para não estragar nada.

A versão e o número da build ficam em Configurações › Sobre.

## Atalho da versão do claude.ai (sem instalar nada)

Se preferir continuar com os dados na sua conta claude.ai, sincronizados em todos os aparelhos:

- **Android (Chrome):** abra o link do FinTrix no claude.ai, toque no menu ⋮ e em "Adicionar à tela inicial".
- **iPhone (Safari):** abra o link, toque em Compartilhar e em "Adicionar à Tela de Início".

O atalho abre a página do claude.ai: precisa de internet e de estar logado, e o ícone é o do claude.ai, não o logo do FinTrix.
