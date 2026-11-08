# Criar o bucket para a sincronização

A sincronização do app desktop pode guardar o cofre num bucket compatível com S3. O FinTrix cifra tudo no aparelho antes de enviar: o provedor só guarda arquivos ilegíveis. Mesmo assim, siga os passos abaixo para que a chave de acesso só alcance esse bucket.

Você vai precisar, no fim, de cinco dados para colar no FinTrix (Configurações › Seus dados › Sincronização › Ligar › Bucket S3):

| Campo no FinTrix | O que é |
|---|---|
| Endpoint | Endereço do serviço (vazio na AWS) |
| Bucket | Nome do bucket |
| Região | Região do bucket (`auto` no R2) |
| Access key | Identificador da chave de acesso |
| Secret key | Segredo da chave de acesso (aparece uma vez só) |

Recomendado: **Cloudflare R2** (camada grátis generosa e sem cobrança de download). Alternativa: **Backblaze B2** (guarda versões antigas dos arquivos, o que protege contra apagamento).

Passos conferidos na documentação dos provedores em novembro de 2026; as telas podem mudar de nome.

## Cloudflare R2

**Custo:** 10 GB por mês, 1 milhão de operações de escrita/listagem e 10 milhões de leitura por mês grátis; download sem cobrança. O FinTrix lista o cofre a cada minuto enquanto está aberto (cerca de 86 mil listagens por mês por aparelho aberto o tempo todo), bem abaixo do limite. O R2 exige ativar a assinatura (com forma de pagamento) antes de criar chaves, mesmo dentro da camada grátis.

1. Crie uma conta em https://dash.cloudflare.com (ou entre na sua).
2. No menu, abra **R2 Object Storage** e ative o R2 (assinatura, com forma de pagamento).
3. **Create bucket**:
   - Nome: algo como `fintrix-<seu-nome>` (só minúsculas, números e hífens).
   - Localização: automática. Não escolha jurisdição (EU, FedRAMP), porque ela muda o endpoint.
   - Classe de armazenamento: **Standard** (a camada grátis não vale para Infrequent Access).
   - Não ative acesso público nem domínio personalizado.
4. Volte à página do R2. Em **Account Details**, ao lado de **API Tokens**, clique em **Manage** e crie um token:
   - **Create Account API token** (continua valendo mesmo se o seu usuário mudar).
   - Permissão: **Object Read & Write**.
   - Escopo: **apenas o bucket** criado no passo 3 (não "todos os buckets").
   - Validade: sem expiração, ou uma data longa que você vá lembrar de renovar.
5. Na tela de confirmação, copie o **Access Key ID** e o **Secret Access Key**. O segredo não aparece de novo.
6. Anote o **Account ID** (na página do R2 ou na barra lateral da conta). O endpoint é:
   ```
   https://<ACCOUNT_ID>.r2.cloudflarestorage.com
   ```

No FinTrix: **Endpoint** = o endereço acima · **Bucket** = o nome · **Região** = deixe vazio (`auto`) · **Access key** e **Secret key** = os do passo 5.

## Backblaze B2

**Custo:** os primeiros 10 GB são grátis. Por padrão, o B2 guarda as versões antigas de cada arquivo: se alguém apagar ou sobrescrever o cofre, dá para recuperar pelo painel.

1. Crie uma conta em https://www.backblaze.com (B2 Cloud Storage).
2. **Buckets › Create a Bucket**:
   - Nome único (`fintrix-<seu-nome>-<algo aleatório>`; os nomes do B2 são globais).
   - **Private**.
   - Criptografia do lado do servidor: pode deixar desligada (o FinTrix já cifra) ou ligar, tanto faz.
   - Object Lock: desligado.
3. Na lista de buckets, anote o **Endpoint** do bucket, algo como `s3.us-west-004.backblazeb2.com`. A região é o trecho do meio: `us-west-004`.
4. **Application Keys › Add a New Application Key**:
   - Nome: `fintrix`.
   - **Allow access to Bucket(s)**: só o bucket do passo 2.
   - **Type of Access**: Read and Write.
5. Copie o **keyID** e o **applicationKey**. A applicationKey não aparece de novo.

No FinTrix: **Endpoint** = o endpoint do passo 3 (com ou sem `https://`) · **Bucket** = o nome · **Região** = `us-west-004` (a do seu endpoint) · **Access key** = keyID · **Secret key** = applicationKey.

## AWS S3

Para quem já usa AWS. Crie um bucket privado (Block Public Access ligado) e ligue o **Versioning**. Crie um usuário IAM só para o FinTrix com esta política, que não permite apagar nada (o FinTrix nunca apaga arquivos do cofre):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": "s3:ListBucket", "Resource": "arn:aws:s3:::NOME-DO-BUCKET" },
    { "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"], "Resource": "arn:aws:s3:::NOME-DO-BUCKET/*" }
  ]
}
```

No FinTrix: **Endpoint** vazio · **Região** = a do bucket (ex.: `sa-east-1`) · chaves do usuário IAM.

## Depois de criar

1. No FinTrix: **Configurações › Seus dados › Sincronização › Ligar › Bucket S3**, preencha e clique em **Ligar**. Se algo estiver errado (endpoint, região ou chave), a mensagem de erro aparece na própria janela e nada é ligado.
2. Guarde o **código de pareamento** que aparece. Ele tem a chave do cofre e a chave de acesso ao bucket: quem tiver o código lê seus dados. Não mande por e-mail ou mensagem.
3. Nos outros aparelhos: **Entrar num cofre** (ou, num aparelho novo, **Parear com outro aparelho**) e cole o código.

## Cuidados

- **Um bucket e uma chave só para o FinTrix.** Não reaproveite chaves de outros projetos nem dê acesso a todos os buckets.
- **Bucket privado.** Nada de acesso público, link público ou domínio personalizado.
- **Se um aparelho for perdido ou o código vazar:** revogue a chave no painel do provedor, crie outra, ligue um cofre novo no FinTrix e pareie de novo os aparelhos que ficam. Só trocar a chave não basta: quem copiou o código também tem a chave do cofre.
- **Backups continuam valendo.** A sincronização não substitui o backup .json de vez em quando, guardado fora do bucket.
- O que o provedor consegue ver: quantos aparelhos existem, o tamanho dos arquivos e a hora das gravações. Valores, descrições e comprovantes, não.
