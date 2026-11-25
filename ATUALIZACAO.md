# Atualização do estoque — 25/11/2026

## Implantação em produção e PWA

Para a VPS Hostinger/EasyPanel, use [DEPLOY_EASYPANEL.md](DEPLOY_EASYPANEL.md), com destino `estoquebc.ldalogistica.com.br` e banco novo. A imagem usa Gunicorn e aplica migrações pendentes antes de abrir o serviço, sem importar catálogo ou criar contas. A revisão do banco continua `f20b20261124`.

A tela `/instalar`, o link no login/menu, as instruções de Android/iOS/desktop e o botão quando oferecido pelo navegador foram adicionados. A instalação exige HTTPS e as operações continuam online. A aplicação valida configuração de produção, Host permitido e cookie seguro. O build Docker, o PostgreSQL real e a instalação nos aparelhos ainda precisam ser conferidos na VPS/CI.

Para rodar no notebook, continuam válidas as instruções abaixo.

Este documento reúne as exigências funcionais e a revisão visual atual. Os detalhes de permissões, lotes, SMTP e recuperação de conta estão em [GUIA_V2.md](GUIA_V2.md). Para instalar do zero, use o [README.md](README.md).

## Atualizar sua instalação

1. Faça backup do PostgreSQL e guarde a pasta atual. Pare o Flask com `Ctrl+C`.
2. Extraia o ZIP em outra pasta. Atualize os arquivos de código, preservando seu `.env`, `.venv` e personalizações próprias. O pacote não contém credenciais nem banco de dados.
3. Com `.venv` ativo, execute na pasta do projeto:

```powershell
python -m pip install -r requirements.txt
python -m flask --app wsgi:app db upgrade
python -m flask --app wsgi:app db current
```

A revisão esperada continua sendo **f20b20261124 (head)**. Esta revisão visual não adiciona migrações. Se sua instalação já está nessa revisão, `db upgrade` não altera o esquema. Se vier de uma versão anterior, aplica as migrações pendentes preservando os registros. Não execute `db init`, não recrie o banco e não remova volumes.

No `.env`, confira:

```env
EXPIRY_ALERT_DAYS=40
COUNT_INTERVAL_DAYS=15
```

O intervalo de contagem pode ser alterado conforme a operação. Inicie e atualize o navegador com **Ctrl+F5**:

```powershell
python -m flask --app wsgi:app run --host 127.0.0.1 --port 5000
```

O CSS compilado, as fontes, as imagens e o GSAP já acompanham o pacote. Node/NPM não são necessários para rodar o sistema em Python.

## Revisão visual e de usabilidade

A referência foi o portfólio público de [Giselle Andrade](https://giselleandrade1-dev.vercel.app/). Os arquivos servidos na data da análise mostram React e Tailwind CSS 4. O repositório público também declara Next.js, React e TypeScript. A aparência publicada e a versão do repositório podem divergir; a análise não pressupõe que todas as bibliotecas citadas pela autora estejam no site atual.

Aplicamos os princípios visuais úteis à operação: hierarquia clara, espaço entre elementos, fontes consistentes, bordas discretas, superfícies com profundidade leve e estados visíveis de foco, seleção e hover. A paleta vinho/laranja/creme, as três logos, o login em duas áreas e o menu lateral foram mantidos. Não foram copiados conteúdos, cores ou componentes do portfólio.

### O que foi corrigido

- **Cards e tabelas:** removidas regras conflitantes que mudavam o padding quando havia uma tabela dentro do card. O conteúdo agora mantém margem interna; somente a tabela tem rolagem horizontal. Nomes longos podem quebrar linha dentro dos seus limites.
- **Sistema de estilos:** uma única base em `app/static/css/app.css`, com variáveis de cor e espaçamento. O antigo `experience.css` e Bootstrap Grid foram retirados. Tailwind gera utilitários locais com prefixo `tw:` e sem reset global, evitando interferir nos componentes existentes.
- **Tipografia:** Inter para leitura e Space Grotesk para títulos/números, servidas localmente com suas licenças. Textos secundários e botões principais receberam contraste maior.
- **Perfil:** seis retratos vetoriais refeitos, com três opções masculinas e três femininas, organizados em grupos e com rótulos. Logos e chocolate continuam em um grupo próprio. A escolha tem borda, marca de seleção e foco visível. Os IDs permanecem iguais, preservando as escolhas dos usuários existentes.
- **Avatares fora do perfil:** dimensões explícitas no cabeçalho, menu e usuários evitam imagens grandes ocupando o card.
- **Formulários:** espaçamento entre rótulos, campos e ações; anexar PDF separado de Extrair prévia; interruptor ativo/inativo proporcional; remover item com área de toque de 44 px. O botão Cadastrar cliente também abre o formulário recolhido.
- **Navegação:** ícones vetoriais com o mesmo traço, tela atual destacada, menu recolhível no desktop e gaveta no celular/tablet. O limite de 900 px é igual em CSS e JavaScript. Escape fecha a gaveta, o foco retorna ao botão e Tab permanece dentro do menu aberto.
- **Mobile:** formulários reorganizados em uma coluna, lotes em duas colunas, campos com fonte de 16 px para evitar zoom automático de foco no iOS, ações acessíveis por toque e contagem com botão flutuante quando há alterações pendentes.
- **Redundâncias:** descrições e avisos repetidos foram encurtados; símbolos antigos de navegação e folhas de estilo concorrentes foram removidos. As orientações necessárias de aprovação, rascunho e validade permanecem visíveis.
- **Movimento:** transições curtas de navegação, botões e cards; GSAP nas entradas do painel. A preferência de redução de movimento é respeitada, inclusive pelos avatares. A rolagem da contagem continua nativa.

A aplicação continua Flask/Jinja. Tailwind e GSAP atendem aos ajustes desta entrega; React não foi introduzido como uma segunda camada de renderização. Os controles e regras permanecem integrados às rotas e validações existentes.

## Requisitos funcionais consolidados

| Área | Comportamento atual |
|---|---|
| Visão geral | Produtos ativos = SKUs ativos do catálogo; loja e armazenado = unidades por local; reposição = entradas externas acumuladas. A visão geral é a primeira opção do menu. |
| Validade | Alerta de lotes com saldo vencidos ou vencendo em até 40 dias, por padrão. Unidades sem validade continuam contabilizadas. Uma variável antiga com valor 30 precisa ser atualizada no `.env`. |
| Catálogo | MIX, INVENTARIO, SAZONAIS e ACESSORIOS; CISS único, código de barras opcional. Até 10 produtos por página e busca. Arquivar preserva o histórico. |
| Produto agrupado | Lotes e conferências mostram uma identidade por produto. Loja e armazenado aparecem juntos; o detalhamento distribui unidades por lote e validade. |
| Lotes | Vários lotes/validades no mesmo produto. Correções geram proposta com motivo e antes/depois; um lojista ou administrador aprova/rejeita. Saldos oficiais mudam somente após aprovação. |
| Clientes | Busca por nome, identificação e contato, filtro ativo/inativo, paginação e os três últimos pedidos de cada cliente. Assistente apenas consulta. |
| Venda direta | Cliente ativo obrigatório, busca antes da seleção, vários itens, baixa da loja. Acessório precisa de pelo menos um item não acessório no mesmo pedido. |
| Movimentações | Entrada, transferência, perda, devolução e bonificação com motivo e autor. Bonificação atende divulgação, degustação, ação comercial e proximidade de vencimento. |
| NF / recebimento | Prévia sem alterar saldos; produtos existentes sugeridos por vínculo ou descrição. Produtos ausentes podem ser criados na confirmação, na própria linha. Código do fornecedor não é assumido como CISS: confira o provisório. |
| Recebimento por lote | Uma linha de 20 unidades pode conter, por exemplo, dois lotes de 10. A soma deve coincidir com o total; alimentos novos exigem lote e validade. Cadastro e entrada confirmam em uma transação. |
| Conferências | Uma linha/card por produto e campos dos dois locais. Rascunho automático no servidor após pausa de digitação, recuperação local de pendências e retorno à busca/posição anterior. Envio e aprovação separados. |
| Acessos | Administrador TI gerencia contas e configurações; lojista opera e aprova; assistente consulta, preenche contagens e propõe correções de lote. O servidor aplica as permissões. |
| Histórico | Movimentos com operador e motivo, CSV e PDF com marca, totais e paginação. Há relatório de lotes e histórico de propostas. |
| Minha conta | Nome, e-mail verificado, avatar e senha; edição protegida por senha atual. Recuperação por token e senha temporária individual pelo administrador; detalhes e SMTP no guia. |
| PWA | Interface responsiva e instalável em HTTPS. Operação online; o service worker não guarda páginas autenticadas ou movimentações offline. |

Vendas de balcão não lançadas individualmente só são conciliadas no inventário. Entre contagens, os saldos refletem as operações registradas. Uma diferença negativa não comprova, isoladamente, perda física. Transferências e baixas usam primeiro os lotes com vencimento mais próximo; lotes sem data ficam por último. Sobras de inventário precisam de conferência posterior de lote/validade.

## Manutenção no VS Code

- Textos e estrutura: `app/templates/`.
- Cores, espaçamento e componentes: `app/static/css/app.css`, formatado e dividido em seções comentadas.
- Interações do menu, filtros, lotes e rascunho: `app/static/js/experience.js`.
- Avatares: `app/static/img/avatars/`; logos: `app/static/img/`.
- Utilitários Tailwind: `frontend/input.css`; versões fixadas no `package-lock.json`.

Se adicionar classes Tailwind aos templates, recompile com Node 20+ instalado:

```powershell
cd frontend
npm ci
npm run build
npm test
cd ..
```

Alterações apenas no CSS dos componentes não exigem build. Não edite o CSS gerado `ui-utilities.css` diretamente. O pacote não inclui `node_modules`.

## Verificações desta entrega

- **14 testes de backend:** autenticação, permissões, estoque, aprovação, recebimentos, múltiplos lotes, clientes e recuperação de conta.
- **6 testes de interação:** menu no desktop/tablet, persistência, Escape, foco por Tab, mudança de largura e abertura do cadastro de cliente.
- Compilação Tailwind e checagem sintática dos scripts.
- Conferência dos seis avatares em imagem conjunta; análise da página de referência no navegador.

Os testes de backend usam SQLite isolado. O PostgreSQL real, SMTP e instalação PWA continuam dependendo da homologação no ambiente da equipe. As telas locais não puderam ser abertas no navegador remoto deste ambiente; a revisão de CSS e de DOM não substitui a conferência final de apresentação no desktop e celular. Não houve alteração do gerador de PDF nesta revisão visual.

## Zerar os saldos para testes

O comando `reset-stock` zera **loja, armazenado e saldo dos lotes**, inclusive de produtos arquivados. Ele exige login e senha de um administrador ativo e a confirmação digitada `ZERAR`. Mantém produtos/CISS, clientes, usuários, histórico de movimentações e documentos. Cada saldo removido gera um ajuste identificado por `RESET-TESTE-...`. Nenhuma senha é passada pela linha de comando.

1. Pare o Flask (`Ctrl+C`), mantenha o PostgreSQL ativo e faça backup pelo pgAdmin.
2. Atualize os arquivos do pacote, preservando `.env` e `.venv`. Se ainda não aplicou a versão funcional anterior, execute `python -m flask --app wsgi:app db upgrade`.
3. Com `.venv` ativo, simule e depois efetive:

```powershell
python -m flask --app wsgi:app reset-stock --dry-run
python -m flask --app wsgi:app reset-stock
```

Informe o login e a senha **do administrador do sistema** (não os do PostgreSQL). A simulação não altera dados. Na execução real, digite `ZERAR` quando solicitado.

Se houver conferências abertas, o comando recusa por padrão. Para cancelá-las e prosseguir com a zeragem, preservando suas linhas:

```powershell
python -m flask --app wsgi:app reset-stock --cancel-open-counts
```

Depois, inicie o Flask normalmente e confira Loja/Armazenado zerados. O total de produtos ativos continuará mostrando os SKUs cadastrados. **Reposição é um acumulado histórico de entradas, portanto não será zerado**; o ajuste fica no histórico. Notas já confirmadas continuam bloqueadas contra duplicidade: a zeragem não autoriza receber novamente a mesma nota. Para repetir cenários com documentos já recebidos e também começar com todo o histórico vazio, use um banco exclusivo de testes com outro nome e aponte seu `.env` para ele.

Para testar: Recebimentos → enviar o PDF → revisar vínculos CISS, quantidade, lotes e validade → confirmar. A extração apenas prepara a prévia; a confirmação aumenta o armazenado. Produtos ausentes podem ser criados na própria prévia; confira o CISS ou o código provisório antes de confirmar.

Esse comando é entregue para você executar no notebook. A atualização do código, sozinha, não zera o banco.
