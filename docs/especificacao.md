# FinTrix: app de finanças pessoais

v1.1 · 11/10/2026 · antes chamado Livro Caixa · substitui a abordagem por planilha (a especificação da planilha fica como referência das regras)

**Onde roda:** publicado como artifact privado no claude.ai (capabilities `db`, `user` e `downloads`) e, fora dele, como página comum com os dados no navegador (veja [rodar-localmente.md](rodar-localmente.md)).

## Decisões

- App web publicado no claude.ai; abre no PC e no celular. Inspirado no Organizze.
- Prioridade: lançar rápido em janelas. Uma janela única com 4 abas: Despesa, Receita, Cartão, Transferência.
- Começa vazio. Apresentação (tela cheia, sem barra lateral): as 3 peças do logo se montam no centro (~1 s), o logo sobe, aparece o texto e, ~2,3 s depois, as opções Adicionar conta (abre o formulário: nome, tipo, saldo, categorias padrão; Voltar) e Restaurar um backup. Clique ou tecla pula a animação; com movimento reduzido tudo aparece de uma vez.
- Dados privados do usuário em `data/users/<id>/livro` (config) e `data/users/<id>/livro/l<ano>/<id>` (lançamentos, uma coleção por ano).
- Valores em centavos (inteiros). Datas `AAAA-MM-DD`, meses `AAAA-MM`.

## Janela de lançamento

- Valor com digitação de centavos (2590 = R$ 25,90). Com valor preenchido, o foco seleciona tudo para substituir.
- Descrição com sugestões do histórico; escolher uma descrição conhecida preenche categoria, conta e valor do último uso.
- Data com atalhos Hoje / Ontem. Situação Pago / Pendente (padrão: pago se a data já passou).
- Cartão: mostra em qual fatura a compra entra (calculada pelo fechamento) e permite trocar a fatura. Opção de estorno.
- Transferência: De / Para com botão de inverter. Se o destino é um cartão, vira pagamento de fatura e escolhe a fatura.
- Mais opções: repetir (não, fixa mensal, parcelado com "valor digitado é a parcela / o total"), tags, observação.
- Teclado: D, R, C, T abrem a janela; Enter salva; Shift+Enter salva e abre outra; Esc fecha; ← → trocam o mês.

- Calculadora no campo de valor: digitar + − × ÷ (ou o botão "Calculadora", com teclas para o celular) abre a conta, ex.: 25,90+12,50; Enter ou = mostra o resultado, Salvar também resolve. Resultado negativo é recusado.
- Dividir entre categorias ("+ Dividir com outra categoria"): a categoria principal fica com o restante. Gravado em `div: [{cat, valor}]` (1ª = principal, igual a `cat`). Só para lançamento único (não em fixa/parcelado). Relatórios, orçamento, filtros, janela da categoria e CSV (uma linha por parte, coluna Divisão) contam cada parte.
- Aviso de limite: com Despesa/Cartão e categoria com limite, a janela avisa a partir de 80% e acima de 100% do limite do mês (já contando este lançamento; na edição desconta o valor antigo).
- Duplicar (na janela de edição) abre uma cópia com os mesmos dados. Excluir mostra aviso com Desfazer por 7 s (recoloca os documentos com o mesmo id e devolve pulos/fim da fixa); pular/encerrar fixa também tem Desfazer.
- Transformar em (janela de edição, Mais opções; campo alinhado à esquerda, mesmo toggle do Repetir): um lançamento único já salvo (conta ou cartão; não parcela, fixa, estorno, transferência ou dividido) vira **Fixa** ou **Parcelado** (label "Transformar em: Não / Fixa / Parcelado").
  - Fixa: cria `recorr` com os dados dele (dia, conta/cartão, repetição, valor varia) e liga o próprio lançamento como o do mês (`recorr` + `recM`); os meses seguintes aparecem como previstos.
  - Parcelado: parcelas n, parcela atual k e se o valor é a parcela ou o total. O lançamento vira a parcela k/n (ganha `grupo`/`parc`, valor da parcela k) e são criadas as parcelas k+1..n: no cartão nas faturas seguintes (`comp` +1 mês cada); na conta nos meses seguintes, pendentes. Parcelas anteriores a k não são lançadas; extras herdam descrição, categoria, tags e observação, sem comprovantes.
- Pagar fatura: o botão Pagar (Cartões, A pagar e a receber, linha da fatura em Lançamentos) registra na hora uma transferência paga, hoje, da conta do cartão (`cartoes[id].conta`) para o cartão com `fatPag` = fatura, no valor que falta; se houver pagamento agendado (pendente) para a fatura, confirma ele e lança só o resto. Aviso com Desfazer. "Outro valor ou conta" abre a janela de transferência preenchida (pagamento parcial, outra conta/data). Cartão sem conta válida: abre a janela.
- Datas: todo campo de data é texto DD/MM/AAAA (máscara: só dígitos, barras automáticas; aceita 5/3/2026), independente do idioma do navegador, com calendário próprio em português (ícone no campo; setas, Enter, Esc; Hoje; Limpar onde pode ficar vazio). Um input escondido com o id antigo (`m-data`, `lt-data`, `iv-d`) lê/grava AAAA-MM-DD (`campoData`, `ligarDatas`); data inválida = valor vazio + borda vermelha e mensagem "Data inválida: use DD/MM/AAAA.". Campos de mês (`type=month`) seguem nativos.
- Editar conta: o campo é "Saldo atual" (`saldoAtual`: inicial + lançamentos pagos); ao salvar, `inicial` muda na mesma diferença (vale para todo o histórico). Conta nova continua com "Saldo inicial". Para lançar a diferença só a partir de hoje: Ajustar saldo.
- Excluir fixa: em Configurações › Fixas cadastradas › editar (rodapé: Excluir sempre; Encerrar enquanto ativa; na lista, fixa encerrada mostra Excluir, que abre a mesma confirmação), na janela de um lançamento da fixa ("Excluir a fixa inteira (N lançamentos)", ao lado de Só este mês / Excluir e encerrar) e num mês pendente (ao lado de Pular / Encerrar). Confirmação mostra quantos lançamentos registrados, período e soma; opções "Excluir a fixa e os N lançamentos" ou "Só a fixa (manter os lançamentos)". Excluir = `arq: true` no `recorr` (some da lista e das previsões) + apagar os lançamentos com `recorr` = id, se escolhido. Desfazer restaura lançamentos e `arq`.
- Editar uma parcela (Mais opções › Repetição: Única / Fixa / Parcelado, com Parcelado marcado):
  - Parcelado: Parcelas e Parcela atual vêm preenchidos; ao mudar, o grupo é renumerado a partir desta (deslocamento d = nova atual − atual). Parcelas que caem fora de 1..n são excluídas; se faltarem parcelas depois da última, são criadas (cartão: faturas seguintes; conta: meses seguintes, pendentes). O escopo (esta / próximas / todas) continua valendo para os outros campos.
  - Única: tira `grupo`/`parc` deste lançamento e exclui as outras parcelas; valor continua o da parcela, com link "Usar o total da compra".
  - Fixa: cria `recorr` a partir desta parcela e liga (`recorr` + `recM`); no cartão a data passa a ser o dia da compra no mês cuja fatura é a desta parcela. Parcelas seguintes são excluídas; anteriores ficam avulsas.
  - Parcela com valor negativo não vira fixa. Toda transformação (inclusive de lançamento único para fixa/parcelado) tem Desfazer no aviso: restaura os documentos originais, apaga os criados e arquiva a fixa criada (`arq: true`, `fim` antes do início).
- Fixa: repetir a cada 1, 2, 3, 6 ou 12 meses (`recorr.cada`) e "o valor varia" (`recorr.varia`): a previsão usa a média dos 3 últimos registros da fixa (`estimado` nas ocorrências previstas). Edição em Configurações › Fixas cadastradas (descrição, valor, dia, repetição, varia).

## Regras

- Compra no cartão conta no mês da fatura (mês de vencimento). O mês fica gravado no lançamento, então mudar o fechamento do cartão não mexe no passado.
- Parcelado: um documento por parcela, ligados por `grupo`. Campo "Parcela atual" (compra que já começou): o lançamento vira a parcela k/n e só são criadas as parcelas k..n (as anteriores não); no modo total, o valor de cada uma vem da divisão da compra inteira. Total: centavos que sobram vão na 1ª parcela. Edição/exclusão: só esta, esta e as próximas, ou todas.
- Fixa mensal: modelo em `config.recorr`; o mês atual é registrado e os próximos aparecem como pendentes (virtuais) até confirmar. Pular um mês (`pulos`) ou encerrar (`fim`).
- Pagamento de fatura = transferência com `fatPag`. Limite usado = compras no cartão − pagamentos.
- Saldo atual = saldo inicial + lançamentos pagos. Saldo previsto = atual + pendentes + fixas previstas + faturas em aberto até o fim do mês.
- Ajuste de saldo cria lançamento marcado `ajuste`, que entra no saldo mas não nos relatórios.
- Contas, cartões, categorias e tags podem ser arquivados (somem das listas, o histórico continua).
- Excluir categoria (janela Editar categoria): sem uso, só confirma (subcategorias saem junto); com lançamentos/fixas, escolhe a categoria destino (padrão da subcategoria = a principal), move lançamentos, partes de divisões (partes iguais se juntam) e fixas, depois apaga; o limite do orçamento dela sai junto. Opção de arquivar em vez disso.
- Patrimônio = saldo de poupança, carteira, benefícios, contas "outro" e investimentos. Contas correntes e gastos no cartão não entram (pedido do usuário em 12/10/2026). A tela Patrimônio mostra "Aportes em 12 meses" no lugar da dívida dos cartões.
- Excluir conta ou cartão: sem lançamentos, só confirma; com lançamentos, oferece arquivar ou excluir junto com os lançamentos e fixas (transferências e pagamentos de fatura também saem, então o saldo das outras contas muda). Cartões pagos por uma conta excluída passam para outra conta.

## Versão instalável (PWA)

**Status: engavetada.** O pacote está pronto e testado, mas só será publicado depois da versão 1.0 do app. Antes de publicar, rodar `python3 tools/pwa_build.py` de novo para pegar as mudanças feitas até lá.

- Gerada por `tools/pwa_build.py` (saída em `dist/pwa/`, fora do Git) a partir do mesmo `index.html`: `index.html` com manifesto, `sw.js` (cópia guardada, abre offline e atualiza em segundo plano; o cache muda de nome a cada build), ícones (192, 512, maskable, apple-touch, favicon) e `LEIAME.md` (cópia de [pwa.md](pwa.md); como publicar: Netlify Drop, GitHub Pages ou servidor local; instalar no Android, iPhone e PC; migrar por backup).
- Sem `window.claude`, o app usa o banco local (IndexedDB) e pede armazenamento persistente. Os dados ficam no aparelho e não sincronizam com o claude.ai.
- Atalhos do ícone: `?novo=despesa|receita|cartao|transf` abre a janela de lançamento (uma vez). A cor da barra do sistema (`theme-color`) acompanha o tema.
- Testado (`test/pwa_v1.py`): manifesto sem erros, instalável pelo Chrome, service worker ativo, dados após reabrir, abre offline, atalho, baixar backup e restaurar em outro perfil.
- Atalho simples da versão do claude.ai: "Adicionar à tela inicial" no navegador. Precisa de internet e login, e o ícone é o do claude.ai.

## Telas

- Lançamentos: período (mês aberto, ano do mês aberto, 12 meses até o mês aberto, todos os meses, período escolhido). Com busca, filtro de categoria/tag, cartão ou período, as compras no cartão aparecem uma a uma (no mês da fatura) no lugar da linha da fatura. Busca também em observação e tags. Agrupa por mês quando é período; mostra 300 e "Mostrar mais"; rodapé com média mensal de despesas. O filtro de conta inclui cartões.
- Relatórios: seletor Mês | Ano no topo (lembrado em `lc.relAno`). No modo Ano, as setas do topo trocam o ano. As somas usam o ano inteiro (anos passados), até o mês atual (ano atual) ou tudo previsto (anos futuros). O modo Ano mostra KPIs (receitas, despesas, balanço, média mensal), receitas e despesas dos 12 meses (meses futuros mais claros = previsto), categorias, "Para onde foi a renda", tags e a matriz "Despesas por categoria, mês a mês" (com sombreamento, total e média; clique abre a categoria). A janela da categoria aberta no modo Ano mostra o total do período, a média por mês, a comparação com o mesmo período do ano anterior, um gráfico mês a mês e até 150 lançamentos; "Ver em Lançamentos" abre com período = ano.
- Relatório por tag (mês ou ano): despesas por tag (barra), receitas com a tag e a quantidade de lançamentos; um lançamento com várias tags conta em cada uma. O clique abre Lançamentos filtrados pela tag no mesmo período.
- Seleção múltipla em Lançamentos: botão "Selecionar" (ou Ctrl/Cmd+clique numa linha, ou toque longo no celular). Clique marca/desmarca, Shift+clique marca o intervalo, "Selecionar todos" pega tudo o que passa nos filtros, Ctrl+A também, Esc sai. Linha da fatura e fixa ainda não registrada não entram. Barra fixa embaixo com quantidade, total, Editar e Excluir.
  - Editar em lote: categoria (só quando a seleção é toda despesa ou toda receita; divididos mantêm a divisão), conta (fora do cartão), data (compra no cartão recalcula a fatura, exceto parcelas), situação, adicionar/remover tag. Só muda o que foi escolhido; aviso com Desfazer.
  - Excluir em lote: confirma, marca o mês das fixas registradas como pulado e tem Desfazer.
- Botão de ordem (só ícone) ao lado dos filtros: mais antigos/mais recentes primeiro; lembrado no aparelho (`lc.ordem`); padrão sem escolha: mês do mais antigo, período do mais recente.
- Ao sair da apresentação (conta nova ou backup restaurado) o app abre na Visão geral, no mês atual.
- Clicar numa categoria (gráficos da Visão geral e Relatórios, nome no Orçamento) abre a janela da categoria: total, previsão, média dos 3 meses anteriores, barra do limite, divisão por subcategoria e lançamentos (partes de divididos marcadas), com troca de mês e "Ver em Lançamentos". "Outras" só destaca.
- Previsão por categoria (`previsaoCat`): mês atual = o que já está no mês (fixas/parcelas/agendados inclusos) + gasto variável (fora do cartão, sem fixa/parcela) no ritmo dos dias passados; antes do dia 7 ou com menos de 3 gastos variáveis usa o típico dos 3 meses anteriores. Mostrada no Orçamento (faixa clara na barra + texto) e na janela da categoria.
- Modo discreto: ícone de olho no topo troca todos os valores da tela por "R$ ••••" (campos de digitação continuam normais). Lembrado por aparelho (`lc.disc`).
- Favicon: o logo em SVG (paleta do tema claro) é colocado no head por script; aparece quando o app abre como página própria (versão local). Dentro do claude.ai, a aba usa o ícone do artifact, escolhido por palavra (não aceita imagem própria).
- Tema: Escuro (padrão) / Claro / Automático em Configurações › Aparência. Salvo na conta (`config.prefs.tema`, vale em todos os aparelhos) e espelhado no navegador (`lc.tema`) para abrir já no tema certo. O padrão é escuro mesmo com o sistema no claro; Automático segue o claude.ai ou o sistema.
- Gráficos por categoria (Visão geral e Relatórios): seletor Barras / Rosca / Blocos (treemap; a pizza foi removida e quem a usava vê a rosca) no cabeçalho do quadro; tipo guardado por quadro no navegador (`localStorage` `lc.graf.<quadro>`). Acima de 7 categorias (9 nos relatórios) as menores viram "Outras". Hover/toque destaca a categoria; na rosca o centro mostra o item.

Visão geral · Lançamentos (por dia, filtros, faturas como linha, totais e saldo previsto) · Contas (transferir, ajustar saldo) · Cartões (fatura do mês, limite, pagar) · Relatórios (6 meses, categorias, essencial/estilo de vida/investido) · Orçamento (limite por categoria) · Configurações (categorias, tags, fixas, exportar CSV (`fintrix-AAAA-MM-DD.csv`), backup JSON, restaurar, apagar tudo).

## Verificação

- `test/novos.py` cobre calculadora, divisão (criar, editar, desfazer divisão, filtro pela parte), aviso de 80%/100%, duplicar, desfazer (lançamento e 3 parcelas), busca por período (mês, ano com compra no cartão, tudo, período escolhido, mostrar mais), janela da categoria (relatórios, pizza, orçamento, troca de mês), previsão, modo discreto, fixa variável (média) e fixa anual/semestral, e a janela no celular.

- Teste local no Chromium com banco simulado: onboarding, conta, cartão, despesa, receita, compra parcelada 3x pelo total, transferência, fixa, salvar e novo, pagar fatura, confirmar fixa, editar parcelas seguintes, orçamento, CSV, backup, ajuste de saldo, apagar tudo. Saldos, faturas, limite e previsto conferidos. Sem erros de console e sem rolagem lateral no celular.
- Após publicar: gravação, leitura e exclusão de um documento de teste no espaço privado do usuário.

## Próximos passos possíveis

- Importar extrato/fatura (CSV/OFX).
- Metas e evolução de patrimônio (investimentos).
- Anexos (comprovantes).
- Orçamento com histórico por mês.
