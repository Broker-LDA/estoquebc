# Publicar Brasil Cacau Estoque na VPS

Destino: **https://estoquebc.ldalogistica.com.br**. Ambiente escolhido: VPS Hostinger com EasyPanel. Banco: **novo**, exclusivo desta aplicação. Não restaure o banco do notebook nesta instalação.

Este pacote prepara a implantação; a publicação só estará concluída quando o build, o banco, o DNS, o certificado HTTPS e o login tiverem sido conferidos na VPS. Os nomes de abas podem variar conforme a versão do painel.

## 1. O que será criado

| Componente | Configuração |
|---|---|
| Projeto EasyPanel | `brasil-cacau`, separado dos outros sistemas |
| Serviço PostgreSQL | `db`, imagem `postgres:16`, banco `estoque_brasilcacau` |
| Serviço App | `web`, com o Dockerfile deste pacote |
| Porta interna do App | `8000`, protocolo HTTP entre proxy e contêiner |
| Endereço público | `estoquebc.ldalogistica.com.br`, com HTTPS no proxy |
| Prontidão | `GET /healthz` retorna `{"status":"ok"}` quando banco e revisão estão prontos |
| Instalação do app | `/instalar`, acessível no login e no menu interno |

O Dockerfile usa Python 3.12 isolado do Python do notebook. Gunicorn atende as requisições; Flask continua sendo o framework da aplicação. As dependências de produção estão fixadas em `requirements.lock`. Tailwind e GSAP já estão prontos dentro da imagem.

## 2. Preparar o PostgreSQL

No projeto novo, crie um serviço **Postgres**. Escolha a imagem `postgres:16` e o nome do banco acima. Use credenciais exclusivas e salve-as no gerenciador de senhas da equipe.

Depois que o serviço estiver saudável, abra suas credenciais e copie a **conexão interna**. Não use o endereço local do notebook, `localhost:5433` ou a porta pública da VPS. O host correto é o que o painel mostrar; não presuma um nome.

No **console psql administrativo do Postgres novo**, execute o conteúdo de `deploy/create_app_role.sql`. O comando `\password estoque_app` pede a senha de forma interativa. Esse papel poderá criar as tabelas e aplicar migrações no banco do estoque, sem privilégios de superusuário ou de criação de outros bancos/contas. Não execute esse script no console Shell do App.

Na URL interna que será usada pelo App, mantenha host, porta e banco do painel, mas use o usuário **estoque_app** e a senha definida nesse passo. As credenciais administrativas do Postgres ficam reservadas à manutenção.

Mantenha a porta do banco privada, sem publicar `5432`. Os dados ficam no volume persistente do serviço PostgreSQL. A aplicação não precisa de volume para PDFs: os documentos recebidos são processados e os registros necessários são gravados no banco.

## 3. Enviar o código

### Caminho imediato: Upload, sem repositório

Crie o serviço **App**, chamado `web`. Em Source/Origem, escolha **Upload** e envie o ZIP desta entrega. O ZIP tem `Dockerfile`, `requirements.lock`, `wsgi.py` e `app/` na raiz. Se extrair no computador para editar, escolha uma pasta de destino exclusiva.

Em Build, selecione **Dockerfile**. Caminho: `Dockerfile`; contexto de build: a raiz dos arquivos enviados. O comando padrão e o entrypoint da imagem já estão configurados. Não substitua o início por `flask run`.

### Caminho para próximas atualizações: GitHub privado

Para manter histórico e publicar por Git, crie um repositório **privado** vazio no GitHub. Dentro da pasta que contém `Dockerfile`, use o terminal do VS Code:

```powershell
git init -b main
git add .
git status
git commit -m "Preparar estoque Brasil Cacau para producao"
git remote add origin https://github.com/SEU_USUARIO/brasil-cacau-estoque.git
git push -u origin main
```

Substitua `SEU_USUARIO` pela conta responsável. Confira `git status` antes do commit: arquivos `.env`, backups e ambientes virtuais não devem entrar. O `.gitignore` inclui essas exclusões. Os exemplos de variáveis contêm somente valores demonstrativos.

No EasyPanel, conecte esse repositório por GitHub ou Git/SSH, branch `main`, Build Path `/`, builder Dockerfile. Use a integração do painel ou uma deploy key de leitura para o repositório privado. Não coloque token na URL do repositório ou no Dockerfile.

Há um workflow opcional em `.github/workflows/ci.yml` que testa o backend, a inicialização em um PostgreSQL 16 efêmero, as interações e o build Docker. Ele ainda precisa executar no seu GitHub. Só habilite publicação automática após os testes e a primeira implantação serem validados.

## 4. Configurar as variáveis do App

Copie o conteúdo de `.env.production.example` para **Environment/Ambiente** do serviço **web**. Não coloque esse arquivo com valores reais dentro do ZIP ou do Git.

Configure os valores abaixo:

| Variável | Valor |
|---|---|
| `DATABASE_URL` | Conexão interna do banco, com prefixo `postgresql+psycopg://` |
| `SECRET_KEY` | Uma chave aleatória nova, gerada uma vez e mantida entre deploys |
| `PUBLIC_BASE_URL` | `https://estoquebc.ldalogistica.com.br` |
| `TRUSTED_HOSTS` | `estoquebc.ldalogistica.com.br` |
| `APP_ENV` | `production` |
| `COOKIE_SECURE` | `true` |
| `TRUST_PROXY` | `true`, com o App acessível apenas pelo proxy do painel |
| `RUN_MIGRATIONS` | `true` |
| `PORT` | `8000` |
| `WEB_CONCURRENCY` / `GUNICORN_THREADS` | `2` / `2` como ponto inicial |
| `EXPIRY_ALERT_DAYS` / `COUNT_INTERVAL_DAYS` | `40` / `15` |

Gere a chave no seu terminal e cole apenas no painel:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

A URL segue este formato; substitua usuário, senha e host pelos dados internos do serviço:

```text
postgresql+psycopg://estoque_app:SENHA_CODIFICADA@HOST_INTERNO:5432/estoque_brasilcacau
```

Se o painel fornecer `postgres://` ou `postgresql://`, altere somente o prefixo para `postgresql+psycopg://`. Preserve o restante da URL de conexão, inclusive parâmetros válidos. A senha na URL deve estar codificada quando tiver caracteres reservados como `@`, `:` ou `/`. Não codifique novamente uma senha já codificada pelo painel.

Deixe os campos SMTP vazios até configurar o servidor de e-mail. Nesse estado, o estoque e o reset administrativo continuam utilizáveis, mas verificação de e-mail e recuperação por link não enviam mensagens. Configure SMTP e teste a entrega antes de oferecer recuperação por e-mail aos usuários.

Não use a senha do banco como `SECRET_KEY` e não altere a chave a cada publicação: isso encerra sessões e invalida tokens emitidos anteriormente.

## 5. Fazer o primeiro deploy

Execute **Deploy** no App e acompanhe a saída. A imagem será construída e iniciará com um usuário Linux sem privilégios de administrador.

Antes de abrir o Gunicorn, o entrypoint aguarda o PostgreSQL e aplica as migrações pendentes. Um lock do PostgreSQL serializa essa preparação se houver duas inicializações. Reiniciar a aplicação não recria o banco, não importa catálogo e não gera usuários. Migração com falha interrompe a inicialização.

Espere encontrar as mensagens de migrações concluídas e Gunicorn escutando na porta `8000`. O healthcheck tem uma tolerância inicial de 150 segundos. A revisão desta entrega continua sendo `f20b20261124`.

Abra **Shell/Console** do serviço App e crie o primeiro administrador:

```sh
python -m flask --app wsgi:app db current
python -m flask --app wsgi:app create-admin
```

Informe login, nome e uma senha com pelo menos 12 caracteres. A senha é digitada em campo oculto; não há uma senha inicial compartilhada no código. Não execute esse comando no notebook se o objetivo é criar a conta na VPS.

O banco começa sem usuários, produtos ou saldos. Produtos podem ser cadastrados pela interface ou criados pela confirmação de uma NF. Caso a equipe queira o catálogo de referência de 82 produtos, execute **opcionalmente** no mesmo console:

```sh
python -m flask --app wsgi:app import-catalog
```

Esse comando cadastra produtos com saldo zero. Ele não recupera os saldos antigos dos PDFs. Faça a primeira contagem física antes da operação efetiva.

## 6. Domínio, DNS e HTTPS

No provedor que gerencia a zona `ldalogistica.com.br`, crie apenas o registro do novo subdomínio:

| Campo | Valor |
|---|---|
| Tipo | `A` |
| Nome / host | `estoquebc` |
| Destino | IP público **da VPS Hostinger** |
| TTL | Padrão / automático |

Não use o IP do site principal sem verificar que ele é a mesma VPS. Mantenha os registros de e-mail e dos outros sistemas. Se já houver um registro para `estoquebc`, confira o destino antes de alterá-lo. Caso use Cloudflare, comece com **Somente DNS** para validar o acesso direto ao proxy do EasyPanel.

Em Domains/Domínios do serviço App, configure o host `estoquebc.ldalogistica.com.br`, caminho `/`, destino interno **HTTP, porta 8000**. Ative o certificado HTTPS e o redirecionamento HTTP → HTTPS. A VPS precisa aceitar tráfego público nas portas 80 e 443. Não publique as portas 8000 ou 5432 diretamente na internet.

O HTTPS público termina no proxy do painel; isso não exige certificado dentro do contêiner Flask. O `TRUST_PROXY=true` está preparado para um proxy confiável na frente do App. Uma cadeia adicional de proxies exige revisão dos cabeçalhos; não aumente esse número sem verificar a configuração.

Um domínio automático do EasyPanel diferente do configurado retornará 400 por validação de Host. Para usar um endereço temporário de homologação, ajuste `PUBLIC_BASE_URL` e `TRUSTED_HOSTS` para esse endereço HTTPS e faça novo deploy.

## 7. Validar antes de liberar à equipe

1. Abra `https://estoquebc.ldalogistica.com.br/healthz`: esperado `{"status":"ok"}` e HTTP 200.
2. Confirme que a raiz abre o login e que HTTP redireciona para HTTPS.
3. Entre como administrador, crie um lojista e um assistente; confira as restrições de cada perfil.
4. Teste um cadastro, recebimento com divisão de lotes e contagem com aprovação; confira o histórico. Use dados de homologação identificados e combine a preparação definitiva com a gerente.
5. Teste logout, novo acesso e reset de senha; se houver SMTP, confirme também a entrega e o uso do link.
6. Confira instalação e abertura do PWA em um celular e um computador reais.
7. Configure backup do PostgreSQL em destino externo à VPS. Faça uma restauração de teste em outro banco antes de depender do agendamento.

Não execute `reset-stock` em produção para limpar uma homologação sem uma decisão explícita da equipe. O sistema mantém auditoria das operações.

## 8. Instalar como PWA

Depois do HTTPS estar válido, abra `/instalar` pelo link do login ou do menu interno.

- **Android:** Chrome → menu → Instalar aplicativo / Adicionar à tela inicial. O botão dentro da página aparece quando o navegador disponibiliza a instalação.
- **iPhone/iPad:** Safari → Compartilhar → Adicionar à Tela de Início.
- **Windows:** Chrome/Edge → ícone de instalação na barra de endereços ou opção no menu.

O aplicativo abre em janela própria, com nome e ícone da Brasil Cacau. É uma instalação pela web, sem APK e sem publicação em loja de aplicativos. A apresentação e a oferta de instalação variam por navegador e aparelho.

O PWA exige conexão para consultas, login e operações. O service worker não armazena respostas autenticadas, saldos, PDFs ou movimentações. Fora da rede, a navegação mostra um aviso genérico. O rascunho de contagem ainda não enviado continua sendo um recurso local de recuperação e deve ser conferido ao reconectar.

Ao publicar uma atualização no mesmo domínio, o aplicativo instalado usa a nova versão no próximo carregamento; não é preciso distribuir outro instalador. Recomende concluir/salvar contagens antes de atualizar ou trocar de dispositivo.

## 9. Atualizações e recuperação

Antes de alterações futuras de esquema, faça backup e use uma janela de manutenção. Publique código e migrações revisados juntos. A preparação automática aplica somente as revisões pendentes. Para rodá-la manualmente em uma janela de manutenção, use `python -m deploy.release` no console do App.

O lock evita migrações simultâneas, mas não substitui uma estratégia de compatibilidade: em mudanças de esquema incompatíveis, não deixe a versão antiga atendendo enquanto migra. Na primeira implantação, use uma réplica; mantenha o modo de troca sem sobreposição para mudanças desse tipo. Publicações de CSS/JS não acrescentam migrações.

Se um deploy de código falhar, volte à imagem/versão anterior compatível. Se uma migração incompatível já tiver sido aplicada, recupere o backup junto com o código correspondente. Não use `db init`, `drop_all`, remoção de volume ou recriação do serviço Postgres como forma de atualizar.

### Diagnóstico rápido

| Sintoma | Conferir |
|---|---|
| Inicialização interrompida | Valores reais no ambiente; host interno do Postgres; esquema `postgresql+psycopg`; chave aleatória; HTTPS e cookie seguro |
| Host inválido / HTTP 400 | Domínio acessado e `TRUSTED_HOSTS` iguais; não incluir `https://` nessa variável |
| 502 / serviço sem resposta | Logs do App; porta de destino 8000; banco disponível; migração concluída |
| `/healthz` retorna 503 | Banco acessível e `db current` na revisão do código |
| Login volta à tela inicial sem autenticar | HTTPS válido; `COOKIE_SECURE=true`; proxy repassando o protocolo correto |
| Erro de CSRF após mudança de domínio | Acessar somente o domínio final e abrir novamente a página de login |
| Não aparece Instalar | HTTPS e manifest válidos; abrir Chrome/Edge/Safari externo, sem modo privado; usar o menu manual; conferir se já foi instalado |
| Senha por e-mail não chega | SMTP, remetente, caixa de spam e e-mail do usuário verificado |

## 10. Verificações técnicas

Nesta preparação, passaram **24 testes de backend/configuração** e **10 testes de interação**. Também foram conferidos manifest/ícones e o atendimento HTTP com Gunicorn: instalação e manifest disponíveis, Host incorreto rejeitado, cookie Secure/HttpOnly e readiness indisponível quando não há banco. O teste de migração e serialização com PostgreSQL real ficou **não executado** neste ambiente; está preparado no CI com um papel sem superusuário e precisa executar no GitHub ou na homologação.

Este ambiente de desenvolvimento não tem Docker nem PostgreSQL instalados. Por isso, o build Docker e a inicialização completa com PostgreSQL ainda precisam ser conferidos na VPS/CI. O domínio, o certificado, o SMTP e a instalação em aparelhos reais dependem da implantação.

Referências oficiais consultadas em 25/11/2026: [App EasyPanel](https://easypanel.io/docs/services/app), [PostgreSQL EasyPanel](https://easypanel.io/docs/services/postgres), [produção Flask](https://flask.palletsprojects.com/en/stable/deploying/), [proxy Flask](https://flask.palletsprojects.com/en/stable/deploying/proxy_fix/), [segurança Flask](https://flask.palletsprojects.com/en/stable/web-security/), [instalação PWA](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable).
