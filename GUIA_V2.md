# Guia funcional — inventário, lotes e acessos

Implantação na VPS e instalação PWA: [DEPLOY_EASYPANEL.md](DEPLOY_EASYPANEL.md).

A revisão visual e as instruções atuais de atualização estão em [ATUALIZACAO.md](ATUALIZACAO.md). Este guia detalha as regras de negócio e a configuração de contas.

## Instalação sobre o projeto atual

1. Faça backup do PostgreSQL e pare o Flask. Atualize os arquivos preservando seu `.env` e `.venv`.
2. No terminal da pasta, com ambiente virtual ativo:

```powershell
python -m pip install -r requirements.txt
python -m flask --app wsgi:app db upgrade
python -m flask --app wsgi:app db current
```

A revisão esperada é **f20b20261124 (head)**. A migração preserva produtos, usuários, saldos, lotes, pedidos, recebimentos e conferências existentes. Adiciona permissões, campos de perfil, controle de versões de rascunho, vínculos entre fornecedor e produto e tabelas de auditoria. Não é necessário reimportar o catálogo ou executar reset de estoque.

No `.env`, defina `EXPIRY_ALERT_DAYS=40`. Se a variável não existir, o padrão agora é 40. Depois inicie normalmente:

```powershell
python -m flask --app wsgi:app run --host 127.0.0.1 --port 5000
```

Use Ctrl+F5 na primeira abertura para carregar o CSS/JS atualizados. O frontend usa Tailwind compilado localmente, GSAP e componentes HTML/CSS/JS integrados ao Flask. Os arquivos prontos acompanham o pacote. Node/NPM são necessários somente para recompilar utilitários ou executar testes de interação; veja ATUALIZACAO.md.

## Permissões

| Função | Administrador TI | Lojista / gestor | Assistente |
|---|---|---|---|
| Consultar painel, produtos, clientes e histórico | Sim | Sim | Sim |
| Ver últimas 3 compras do cliente | Sim | Sim | Sim |
| Criar/editar clientes e produtos | Sim | Sim | Não |
| Registrar movimentos, vendas e recebimentos | Sim | Sim | Não |
| Abrir, preencher e enviar inventário | Sim | Sim | Sim |
| Propor quantidades/lotes/validades | Sim | Sim | Sim |
| Aprovar/rejeitar propostas de lote | Sim | Sim | Não |
| Aprovar ou cancelar inventário | Sim | Sim | Não |
| Gerenciar usuários e resetar senhas | Sim | Não | Não |
| Editar o próprio perfil | Sim | Sim | Sim |

As restrições são conferidas pelo servidor em cada rota; esconder botões é apenas a apresentação. As contas antigas mantêm seu perfil. O TI pode selecionar **Assistente** ao criar/editar usuário. O lojista é o perfil de gestor autorizado a aprovar.

## Um produto, um card

- **Lotes:** cada produto aparece uma vez, com total, loja e armazenado. Abra o detalhamento para separar quantidades por lote + validade; cada linha de lote contém os dois locais.
- **Inventário:** uma linha/card por produto, com contagem de loja e armazenado lado a lado. Há apenas uma identidade de produto. Diferenças continuam separadas por local.
- **Produtos:** lista paginada com até 10 itens, filtro por nome/CISS/barras e linha. Acessórios e sazonais possuem identificação visual correta. O link de detalhamento leva aos lotes do produto.
- **Painel:** visão geral no topo do menu, cards de resumo maiores e alerta agrupado por produto. A janela padrão de validade passou para 40 dias; unidades sem validade permanecem contabilizadas.

## Quantidade por lote e aprovação

Em Lotes, abra o produto e distribua unidades em um ou mais lotes, cada qual com sua validade e quantidades de loja/armazenado. Pode adicionar/remover linhas e propor correção de quantidade. Informe o motivo e envie para aprovação.

A proposta contém os valores anteriores, os novos, o autor e o momento do envio. Os saldos oficiais não mudam até um lojista/administrador aprovar na tela **Alterações e aprovações**. O gestor vê os dois estados; pode aprovar ou rejeitar. A aplicação da proposta gera movimentos de ajuste quando há diferença de quantidade. Alterações apenas de lote/validade também ficam no histórico de propostas. Isso vale para os três perfis, inclusive para manter rastreabilidade de alterações do gestor.

Se o estoque ou a composição dos lotes mudar durante a edição ou após o envio, a aplicação recusa a proposta antiga. É necessário conferir os valores novos e propor novamente. Para lotes antigos sem data, o campo pode permanecer sem validade até conferência física; o recebimento de alimento novo continua exigindo validade.

## Recebimento em massa e novos produtos

Envie o PDF e revise a prévia. Produtos já vinculados pelo código do fornecedor são sugeridos automaticamente; na ausência de vínculo, descrições idênticas geram sugestão.

Produtos ausentes são preparados como **Criar produto automaticamente** na própria linha: descrição extraída, categoria selecionável e código provisório `NF-<código do fornecedor>`. Troque o provisório pelo CISS verdadeiro se já souber. Código do fornecedor e CISS podem ser diferentes; o programa não inventa um CISS. Produtos com código provisório podem ser corrigidos depois em Produtos. O vínculo futuro usa o ID do produto e continua válido após corrigir o CISS.

No mesmo item, adicione quantos lotes forem necessários. Exemplo: 20 unidades recebidas = 10 do lote A/validade X + 10 do lote B/validade Y. A soma é validada contra o total da linha. Todos os lotes alimentícios precisam de identificação e validade; acessórios podem ficar sem validade. Cadastro dos produtos e entrada são efetivados juntos na confirmação. Qualquer erro desfaz a transação inteira. Notas confirmadas permanecem protegidas contra duplicidade.

O importador continua limitado ao DANFE textual do padrão homologado; PDFs digitalizados ou outro layout podem exigir lançamento manual.

## Rascunho automático de inventário

Após uma breve pausa de digitação (cerca de 700 ms), as alterações válidas são salvas em lote no servidor. A mensagem distingue pendência de rascunho efetivamente salvo. O botão Salvar agora permanece acessível; no celular, flutua no rodapé quando existem alterações não enviadas.

O rascunho ainda não enviado também fica neste aparelho/navegador, associado ao usuário e à conferência, e é recuperado ao retornar ou recarregar. Busca e posição de rolagem são retomadas. Ao fazer logout, o rascunho local é removido; alterações já salvas permanecem no servidor. Não é necessário ficar clicando em salvar a cada campo. A aplicação continua online: sem rede, o rascunho local não significa alteração confirmada no banco.

Edições simultâneas são verificadas por revisão. Em conflito com outra pessoa, a tela não sobrescreve silenciosamente: é possível manter os valores do servidor ou reaplicar o rascunho conscientemente. O envio para aprovação espera o salvamento pendente. A aprovação do inventário continua bloqueada se houver movimentação de estoque desde a abertura.

## Clientes, venda direta e relatórios

Clientes possuem busca por nome, identificação e contato, filtro ativo/inativo e paginação. Cada card mostra os últimos três **pedidos**, com data, total em unidades e itens detalhados. Para Assistentes, não existem formulários de cadastro/edição. Os gestores abrem a edição dentro do próprio card. A situação é exibida com um indicador compacto e um interruptor proporcional no formulário.

Venda direta possui pesquisa do cliente antes da seleção. O botão de remover item foi reposicionado com identificação acessível; ao remover a única linha, ela é limpa. A regra de acessório acompanhado por alimento continua validada no servidor.

O histórico mantém CSV e PDF. O novo PDF incorpora a fonte, inclui resumo de registros/unidades e separa a rastreabilidade da posição atual por lote. A posição atual é explicitamente identificada, sem sugerir que seja o saldo histórico em cada venda. Existe também PDF próprio de lotes, com totais por local e propostas recentes. A página de auditoria detalha antes/depois e responsáveis. Os horários dos relatórios são UTC, conforme os rótulos.

## Perfil e recuperação de conta

Meu perfil permite editar nome, e-mail, senha e avatar; alterações exigem a senha atual. Inclui **seis avatares vetoriais animados**, chocolate animado e as três logos. As animações respeitam a preferência de redução de movimento do aparelho.

O novo e-mail só passa a ser usado para recuperação após confirmação por link de uso único com validade de 30 minutos. Um e-mail anterior já verificado permanece válido até confirmar o novo. O link pode ser reenviado pelo perfil. O administrador pode preencher um e-mail ao cadastrar/editar a conta, mas a verificação é feita pelo usuário.

### Configurar SMTP para envio real

As funcionalidades locais não exigem SMTP; o envio de e-mail depende de um serviço configurado pelo TI:

```env
PUBLIC_BASE_URL=https://estoque.seudominio.com.br
SMTP_HOST=smtp.seuprovedor.com
SMTP_PORT=587
SMTP_SSL=false
SMTP_FROM=estoque@seudominio.com.br
SMTP_USER=estoque@seudominio.com.br
SMTP_PASSWORD=senha-ou-senha-de-aplicativo
```

Na porta 587, a conexão usa STARTTLS. Para SMTP com TLS implícito, utilize a porta do provedor (normalmente 465) e `SMTP_SSL=true`. Use o endereço HTTPS real em `PUBLIC_BASE_URL`; os links não são montados a partir de um cabeçalho Host não confiável. Para homologação exclusivamente local, a configuração admite `http://localhost:5000` ou `http://127.0.0.1:5000`.

No login, **Esqueci minha senha** envia um link apenas para contas ativas com e-mail verificado. A resposta é genérica para não revelar quem tem cadastro. Há limite persistente de solicitações por origem. O link expira em 30 minutos e deixa de funcionar após uso. A troca invalida sessões antigas.

### Reset pelo administrador

Em Usuários → Gerar senha temporária, o administrador confirma sua própria senha. O sistema gera uma senha individual aleatória, válida por 24 horas e com troca obrigatória no próximo acesso. Não há uma senha padrão compartilhada entre todos os usuários.

Se o usuário tem e-mail verificado e SMTP funciona, a senha é enviada a ele. Sem e-mail verificado ou em falha de entrega, a senha aparece uma única vez na resposta do administrador, com botão Copiar e fallback para seleção manual. Não fica gravada em sessão, histórico ou texto puro no banco. O administrador encaminha pelo canal combinado. A ação é auditada sem registrar a senha; a própria tela Usuários mostra as últimas 50 ações de conta.

No primeiro acesso com senha temporária, a navegação fica limitada ao perfil até que a senha seja trocada. O usuário não pode reutilizar a própria senha temporária como nova senha. A conta é revalidada após troca/desativação/alteração de perfil.

## Visual e mobile

Menu lateral recolhível no desktop e gaveta lateral no celular, com logo, indicador de tela ativa e atalhos conforme as permissões. Tailwind com prefixo e o sistema de componentes em CSS sustentam o layout responsivo. GSAP cuida das transições de entrada sem impor rolagem artificial durante a contagem. Não houve migração de arquitetura para React: não é necessária para os fluxos atuais. Recursos visuais são servidos localmente, sem CDN em produção.

PWA continua online e depende de HTTPS para instalação no celular. O service worker não armazena páginas autenticadas ou transações. Apenas o rascunho de inventário não enviado é guardado localmente para recuperar uma saída acidental.

## Verificações realizadas

- 14 testes automatizados de backend: autenticação, permissões, estoque, propostas de lotes, aprovação por gestor, bloqueio de Assistente, recebimentos com produto novo e múltiplos lotes, rollback, duplicidade, clientes/paginação, verificação de e-mail, senha temporária, troca obrigatória e recuperação de token de uso único.
- Teste de DOM/JavaScript: salvamento automático dos dois locais em um lote, recuperação do rascunho, conflito explícito e menu recolhível.
- Migração sobre o esquema anterior com conta existente e 42 unidades: preservação conferida.
- PDFs renderizados e conferidos visualmente.

Testes de banco executados em SQLite isolado; o PostgreSQL de implantação ainda precisa de homologação. E-mail foi testado com transporte simulado; a entrega real depende do SMTP do TI. A revisão visual atual está documentada em ATUALIZACAO.md. A homologação final das telas no desktop/celular e da instalação PWA deve ocorrer no ambiente da equipe.
