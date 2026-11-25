# Brasil Cacau · Controle interno de estoque

**Produção na VPS / PWA:** siga [DEPLOY_EASYPANEL.md](DEPLOY_EASYPANEL.md). O pacote inclui Dockerfile, Gunicorn, migração antes da inicialização e tela de instalação. O ZIP desta entrega tem os arquivos na raiz para permitir Upload no EasyPanel. Ao extrair no Windows, escolha uma pasta exclusiva `brasil-cacau-estoque`.

**Atualização de 25/11/2026:** comece por [ATUALIZACAO.md](ATUALIZACAO.md) para atualizar uma instalação existente e conferir os requisitos atendidos. [GUIA_V2.md](GUIA_V2.md) detalha permissões, lotes, rascunhos e configuração de e-mail.

Aplicação web em Python/Flask para controlar unidades em **LOJA** e **ARMAZENADO**, com PostgreSQL, contas por perfil, histórico de movimentos e conferências periódicas.

## Dados dos relatórios

Os dois PDFs fornecidos são conferências encerradas em **21/08/2026**. O arquivo `data/catalogo_referencia_2026-08-21.csv` contém **82 SKUs**, com descrição, código de barras e categoria: 61 MIX (total histórico 3.177) e 21 INVENTÁRIO (total histórico 14.301). O campo `reference_quantity_2026_08_21` é apenas documental. O importador **não aplica** esses saldos ao banco: eles são antigos e não têm separação por local.

Para iniciar com dados confiáveis, faça uma **primeira conferência física** nas duas áreas, incluindo zero para produtos ausentes. Após aprovação de um lojista ou administrador, os saldos são ajustados e os lançamentos ficam no histórico.

## Requisitos

- Python 3.11+;
- PostgreSQL 16 local ou outra instância PostgreSQL compatível;
- Docker Desktop, opcional para subir o banco de desenvolvimento;
- VS Code com a extensão Python.

## Instalação no VS Code (Windows / PowerShell)

1. Extraia o ZIP e abra **a pasta `brasil-cacau-estoque`** no VS Code.
2. No terminal integrado:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

3. Cole a chave gerada em `SECRET_KEY` dentro de `.env`. Defina uma senha forte em `POSTGRES_PASSWORD` e coloque **a mesma senha** no trecho correspondente de `DATABASE_URL`. Caso a senha contenha caracteres como `@`, `:` ou `/`, codifique esses caracteres como percent encoding no endereço do banco.
4. Se usar Docker Desktop, inicie o banco:

```powershell
docker compose up -d db
```

5. Prepare o esquema e o catálogo:

```powershell
python -m flask --app wsgi:app db upgrade
python -m flask --app wsgi:app import-catalog
python -m flask --app wsgi:app create-admin
```

6. Digite login, nome e senha inicial (mínimo 12 caracteres) no comando de criação. Inicie a aplicação:

```powershell
python -m flask --app wsgi:app run --host 127.0.0.1 --port 5000
```

Acesse `http://127.0.0.1:5000`. No VS Code, selecione `.venv` como interpretador Python. Em Linux/macOS, ative com `source .venv/bin/activate` e copie o exemplo com `cp .env.example .env`.

Se já houver PostgreSQL, pule `docker compose up` e aponte `DATABASE_URL` para a instância. O banco deve existir antes de executar a migração.

## Uso operacional

1. **Administrador** cria contas na tela Usuários. O perfil **lojista** movimenta estoque, cadastra/edita/arquiva produtos, realiza contagens e consulta histórico. O perfil **assistente** consulta informações, preenche contagens e propõe ajustes de lote. Lojistas e administradores aprovam conferências/propostas; apenas o administrador gerencia contas.
2. **Entrada externa** adiciona unidades em loja ou armazenado. **Transferência** move unidades entre áreas sem alterar o total. **Venda** baixa da loja. **Perda** baixa da área informada. **Devolução** adiciona novamente. Cada registro pede motivo, identifica o operador e pode incluir referência de nota/cupom.
3. Para itens INVENTÁRIO vendidos em conjuntos ou por unidade, ajuste o **fator de venda** no produto após validar a regra com a operação. Informe sempre **unidades físicas** na baixa. O sistema não infere embalagens, valores ou receitas de composição dos PDFs.
4. Em Conferências, abra uma contagem e preencha cada produto nas duas áreas; zero significa que não há unidades. Envie para aprovação. Se o saldo de qualquer item contado mudar depois da abertura, a aprovação recusa a conferência; cancele e abra outra para evitar aplicar uma contagem antiga. O prazo recomendado usa `COUNT_INTERVAL_DAYS=15`, ajustável em `.env`.
5. Painel e Produtos consultam o banco a cada requisição e atualizam automaticamente a cada 30 segundos quando a aba está visível. Não há integração com caixa/POS nem atualização automática por venda não lançada. Para um saldo confiável entre conferências, é necessário registrar entradas e saídas.
6. Use Histórico → **Exportar CSV** ou **PDF** para auditoria. Arquivar itens ou desativar usuários preserva as movimentações anteriores.

## Organização do projeto

```text
app/__init__.py          configuração, proteções HTTP e extensões
app/models.py            tabelas e vínculos de dados
app/services.py          regras de saldo e conferência transacionais
app/views.py             rotas, autenticação e permissões
app/commands.py          comandos de implantação e importação
app/templates/           textos e telas HTML editáveis
app/static/css/app.css   cores e apresentação
app/static/js/app.js     interações básicas de formulário
app/static/js/experience.js  menu, filtros, lotes e rascunho automático
frontend/                build Tailwind e testes de interação
app/static/img/           três logos, usados em favicon, login e cabeçalho
data/                    catálogo de referência extraído dos PDFs
migrations/              mudanças versionadas do esquema
tests/                   testes da lógica crítica
```

Para personalizar textos, edite os arquivos `app/templates/`; para cores, `app/static/css/app.css`; para imagens, `app/static/img/`. As três logos estão nomeadas como os arquivos originais. O histórico preserva também o código e a descrição existentes quando cada movimento foi realizado.

## Alterações futuras do banco

Após mudar os modelos em `app/models.py`, gere e **revise** uma migração antes de aplicar:

```powershell
python -m flask --app wsgi:app db migrate -m "Descricao da alteracao"
python -m flask --app wsgi:app db upgrade
```

Faça backup do banco antes de aplicar migrações em produção. A migração inicial já está incluída.

## Segurança e produção

Senhas têm hash scrypt, formulários usam CSRF, sessões são invalidadas após troca de senha/desativação, login bloqueia temporariamente após falhas sucessivas e saldos são atualizados em transação com bloqueio de linha no PostgreSQL. O banco impõe saldo não negativo. Operações de estoque registradas não podem ser apagadas pelas telas.

Não publique o servidor de desenvolvimento `flask run`. Para operação interna em servidor, use Gunicorn atrás de proxy HTTPS e defina `APP_ENV=production`, `COOKIE_SECURE=true`, `TRUST_PROXY=true` apenas se estiver atrás de um proxy confiável configurado corretamente, e uma `SECRET_KEY` própria. Restrinja acesso ao banco, mantenha backups e teste restauração. `docker-compose.yml` é para desenvolvimento local; ele só expõe PostgreSQL em `127.0.0.1`.

Para testes locais, instale `pytest` e rode `python -m pytest -q`. Os testes de lógica usam SQLite isolado; valide concorrência e conexões também no PostgreSQL do ambiente de implantação.





