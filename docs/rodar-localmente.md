# Rodar o FinTrix localmente

O mesmo `index.html` funciona em dois modos, escolhidos sozinhos ao abrir:

- **claude.ai** (pelo link do artifact): dados na sua conta claude.ai.
- **local** (fora do claude.ai): dados no navegador (IndexedDB), só neste aparelho e neste navegador.

## Abrir

Não abra o arquivo com duplo clique (`file://`): sirva a pasta por HTTP.

```
cd FinTrix          # a pasta do repositório, onde está o index.html
python -m http.server 8000
```

Depois abra http://localhost:8000 no navegador. Use sempre o mesmo endereço e a mesma porta,
porque os dados ficam presos ao endereço (`localhost:8000` e `127.0.0.1:8000` são "lugares" diferentes).

## Passar os dados do claude.ai para cá

1. No FinTrix do claude.ai: Configurações → Seus dados → **Baixar backup**.
2. No FinTrix local, na tela de boas-vindas: **Restaurar um backup** e escolha o arquivo.

A partir daí, as duas versões têm dados separados. Escolha uma como oficial.

## Cuidados

- Baixe um backup de vez em quando. Guarde fora do repositório ou na pasta `privado/`, que o `.gitignore` não deixa subir para o GitHub. Limpar os dados do navegador apaga o FinTrix local.
- Janelas anônimas não guardam nada.
- Para testar o modo local dentro de outro ambiente, acrescente `?modo=local` ao endereço.

## Desenvolvimento

Todo acesso a dados passa pelo bloco **"camada de dados"** no início do script (`Backends.claude` e
`Backends.local`). Funcionalidades novas não devem chamar `window.claude` fora dele.
Para hospedar depois com sincronização (PocketBase, Supabase…), basta acrescentar outro backend
que cumpra o mesmo contrato descrito no comentário do bloco.
