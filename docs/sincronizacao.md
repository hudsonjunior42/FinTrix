# Sincronização entre aparelhos (app desktop)

**Status: primeira versão.** Testada com dois aparelhos por uma pasta (`cargo test -p fintrix-core` e `python3 test/desktop.py`). O caminho por bucket S3 usa o mesmo código, com o cliente S3 do crate `object_store`, mas **ainda não foi testado contra um bucket de verdade** (R2, B2, AWS ou MinIO).

## Para usar

1. No aparelho que já tem os dados: **Configurações › Seus dados › Sincronização › Ligar**. Escolha onde fica o cofre:
   - **Pasta sincronizada**: uma pasta que o Syncthing, o Nextcloud ou o Dropbox já leva para os outros aparelhos.
   - **Bucket S3**: Cloudflare R2, Backblaze B2, AWS ou outro compatível. Passo a passo para criar o bucket e uma chave restrita a ele: [bucket-s3.md](bucket-s3.md).
2. Aparece o **código de pareamento**. No outro aparelho: na apresentação, **Parear com outro aparelho**; ou, se ele já tem dados, **Configurações › Seus dados › Sincronização › Entrar num cofre** (os dados dele são trocados pelos do cofre, depois de uma cópia automática). No cofre em pasta, informe onde a pasta está nesse aparelho.
   No bucket, o primeiro envio (estado e todos os comprovantes) pode levar alguns minutos. O app espera até 15 s para pegar erros rápidos (endpoint, chave, bucket) e mostra o código; o envio continua em segundo plano, com o andamento em Configurações ("enviando os dados pela primeira vez…"). Se esse primeiro envio falhar, a sincronização volta a ficar desligada, com o motivo na tela. Pareie os outros aparelhos depois que aparecer a hora da última sincronização.
3. A partir daí cada aparelho sincroniza ao abrir, alguns segundos depois de cada mudança e a cada minuto. **Sincronizar agora** força um ciclo.

O código de pareamento tem a chave do cofre e o acesso ao destino: quem tiver o código lê os dados. Copie de um aparelho para o outro; não mande por e-mail ou mensagem. Enquanto o cofre existir, ele também serve para recuperar os dados num aparelho novo.

## Como funciona

```
fintrix/<cofre>/estado/<aparelho>.bin   estado completo de UM aparelho, cifrado; só ele grava
fintrix/<cofre>/anexos/<código>.bin     um comprovante cifrado; código = HMAC do id; nunca muda
```

- **Carimbos.** Cada gravação também atualiza a tabela `campos` do banco: cada folha do JSON com um carimbo de relógio lógico híbrido (milissegundos, contador e id do aparelho). Ao mesclar, em cada campo vale o carimbo maior. Mesclar é idempotente e não depende da ordem.
- **Unidade de mesclagem.** Uma gravação carimba a unidade inteira que mudou: o lançamento todo, ou o registro da configuração (`contas/<id>`, `cartoes/<id>`, `recorr/<id>`…). Registros diferentes editados em aparelhos diferentes se juntam; no mesmo registro vale a última edição inteira. Assim, apagar uma conta num aparelho e editá-la no outro nunca deixa uma conta pela metade.
- **Anos.** A lista `anos` da configuração vale inteira, então depois de mesclar o app devolve a ela os anos que têm lançamentos (dois aparelhos que criaram anos diferentes não perdem nenhum).
- **Fixas.** O mês registrado de uma fixa tem id fixo (`fx_<fixa>_<mês>`): confirmado em dois aparelhos, vira um lançamento só.
- **Relógio errado.** Carimbos mais de um dia no futuro são ignorados.
- **Versões.** Um aparelho com app mais antigo não mescla dados de uma versão mais nova (`VERSAO_DADOS`); ele avisa para atualizar.
- **Cifra.** A chave do cofre (256 bits aleatórios) gera, por HKDF-SHA256, uma chave de cifra e uma de nomes. Arquivo: `FTX1` · formato · id do aparelho · nonce de 24 bytes · XChaCha20-Poly1305(deflate(JSON)), com o cabeçalho autenticado. O destino vê só quantos aparelhos existem, o tamanho dos arquivos e a hora das gravações.
- **O que fica só no aparelho:** cópias automáticas e preferências da tela. A configuração do cofre (destino, credenciais e chave) fica no banco cifrado do aparelho.

Código: `crates/fintrix-core/src/campos.rs` (achatar, remontar, relógio), `Store::lote`/`Store::mesclar` em `lib.rs`, `crates/fintrix-core/src/sync.rs` (cifra, destino, ciclo) e os comandos `sync_*` em `src-tauri/src/main.rs`. Na interface, `persistTauri().ouvir` aplica no cache os documentos que chegam (evento `db-remoto`), e o bloco Sincronização fica em `blocoSync`.

## Limitações conhecidas

- **S3 não testado de verdade** (veja o status no topo).
- **Duplicações que a mesclagem não evita:** o mesmo extrato importado em dois aparelhos antes de sincronizar, ajuste de saldo feito nos dois (cada um lança a diferença que via) e a mesma fatura paga nos dois. Por enquanto, sincronize antes de importar, ajustar ou pagar fatura.
- **Meses pulados de uma fixa** (`pulos`) valem como lista inteira: pular meses diferentes da mesma fixa em dois aparelhos ao mesmo tempo mantém só um dos pulos.
- **Celular perdido:** desligar não revoga nada. É preciso revogar a credencial do bucket (ou tirar o aparelho da pasta sincronizada) e criar um cofre novo, pareando de novo os aparelhos que ficam.
- **Apagados nunca saem** do estado (crescem devagar; dá para compactar depois).
- **Só o app desktop** sincroniza. A versão web não participa.
