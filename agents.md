# agents.md — Rental Manager Desktop (Windows)

## 1) Objetivo do Produto
Construir um aplicativo desktop para Windows (uso único, offline) para gerenciar aluguéis de itens para eventos (mesas, cadeiras, pula-pula, som, piscina de bolinhas e itens novos). O usuário é leigo em tecnologia, portanto a interface deve ser simples, guiada e muito clara.

O sistema deve:
- Cadastrar itens e controlar estoque (total, reservado, disponível).
- Registrar aluguéis (agendamentos futuros), com endereço e dados do cliente.
- Controlar pagamentos (pago / não pago / parcial opcional).
- Permitir editar e cancelar aluguéis com confirmações.
- Emitir recibo/contrato em PDF.
- Gerar relatórios financeiros simples (recebidos, a receber, por período).
- Fazer backup e restauração do banco local.
- Garantir robustez e segurança básica (integridade dos dados, logs, permissões de arquivo, backups).

## 2) Escopo (MVP + incrementos)
### MVP (obrigatório)
- Itens (CRUD) + estoque.
- Clientes (CRUD básico).
- Aluguéis (CRUD + validações + conflito de estoque por data).
- Tela de agenda/lista de aluguéis (filtro por data, pago/não pago, status).
- Pagamentos (marcar pago, valor, data).
- Relatório financeiro por período (soma recebidos, soma em aberto).
- Recibo/Contrato em PDF a partir de um aluguel.
- Backup (exportar) e Restore (importar) do .db (com validações e confirmação).

### Incrementos (após MVP)
- Visão de calendário.
- Alertas (ex.: aluguéis de hoje / amanhã).
- Exportação CSV.
- Gráficos simples.
- Mais campos (observações, taxa de entrega, desconto).

## 3) Restrições e decisões técnicas
- Plataforma: Windows 10/11.
- Linguagem: Python 3.11+ (preferível).
- GUI: PySide6 (Qt6).
- Banco: SQLite local (arquivo .db).
- PDF: ReportLab (contrato/recibo).
- Empacotamento: PyInstaller (1 executável/pasta).
- Offline, sem login.
- Código organizado em camadas, evitando “SQL espalhado na GUI”.

## 4) Arquitetura
### Padrão recomendado
- Camada de UI (PySide6): telas, diálogos, tabelas, navegação.
- Camada de Services (regras de negócio): estoque, validações, conflito de datas, pagamentos.
- Camada de Repository/DAO: acesso ao SQLite (CRUD e queries).
- Camada de Domain/Models: dataclasses/entidades.
- Camada de Utils: logger, paths, backup, pdf.

### Diretrizes
- UI chama Services; Services chama Repository.
- Repository nunca chama UI.
- Transações SQLite em operações críticas (criar aluguel + itens + reserva de estoque).
- Sempre validar entradas na UI e novamente no Service (defesa dupla).

## 5) Banco de Dados (SQLite)
### Tabelas
1) products
- id (PK)
- name (TEXT, unique)
- category (TEXT) ex: "mesa", "cadeira", "brinquedo", "som"
- total_qty (INTEGER)
- unit_price (REAL) (opcional, pode ser preço padrão)
- active (INTEGER 0/1)
- created_at, updated_at

2) customers
- id (PK)
- name (TEXT)
- phone (TEXT)
- notes (TEXT)
- created_at, updated_at

3) rentals
- id (PK)
- customer_id (FK -> customers.id)
- event_date (DATE) (data do evento)
- start_date (DATE) (retirada/entrega)
- end_date (DATE) (devolução)
- address (TEXT)
- status (TEXT) ex: "draft", "confirmed", "canceled", "completed"
- total_value (REAL)
- paid_value (REAL)
- payment_status (TEXT) ex: "unpaid", "partial", "paid"
- created_at, updated_at

4) rental_items
- id (PK)
- rental_id (FK -> rentals.id)
- product_id (FK -> products.id)
- qty (INTEGER)
- unit_price (REAL) (preço aplicado no aluguel)
- line_total (REAL)

### Regras principais
- Estoque disponível depende da soma de qty reservadas em aluguéis que conflitam por data (status confirmed ou draft, dependendo da regra).
- Cancelar aluguel deve “liberar” reserva (ou seja, deixar de contar na disponibilidade).
- Confirmar aluguel fixa status e deve exigir validação de estoque.
- Concluir aluguel marca completed (mantém histórico, não volta a ser reservável).

## 6) Regras de conflito e disponibilidade
- Um aluguel conflita com outro se os intervalos [start_date, end_date] se sobrepõem.
- Para calcular disponibilidade de um product:
  available = total_qty - sum(qty) de rental_items
  onde rental.status in ("draft","confirmed") e datas conflitantes.
- Se available < qty solicitada -> bloquear criação/edição.

## 7) UX/UI (usuário leigo)
- Tela inicial com botões grandes:
  - "Novo Aluguel"
  - "Agenda"
  - "Estoque"
  - "Clientes"
  - "Financeiro"
  - "Backup"
- Listas com busca (campo de pesquisa).
- Botões claros: "Salvar", "Confirmar", "Cancelar", "Gerar PDF".
- Confirmações para ações destrutivas:
  - Cancelar aluguel
  - Excluir item/cliente
  - Importar backup (sobrescreve banco)
- Mensagens em português simples.

## 8) Segurança e confiabilidade (sem login)
- Integridade:
  - foreign keys ON
  - transações em escrita
- Backups:
  - exportar .db com timestamp
  - opção de restaurar (import)
  - opcional: backup automático ao iniciar/fechar (rotativo)
- Logs:
  - arquivo logs/app.log com rotação
- Permissões:
  - colocar app data em pasta do usuário (ex: %APPDATA%/RentalManager/)
  - nunca gravar o .db na raiz do executável se estiver em Program Files (evitar permissão).

## 9) Empacotamento (Windows)
- PyInstaller:
  - gerar build em dist/
  - incluir ícone, assets
  - garantir path correto do banco (AppData)
- Instruções no README:
  - como rodar em dev
  - como buildar .exe

## 10) Definition of Done (DoD)
Um incremento está “pronto” quando:
- roda no Windows sem erro
- opera com banco SQLite criado/migrado automaticamente
- telas principais funcionam (criar/editar/confirmar/cancelar/concluir aluguel)
- validações impedem estoque negativo
- gera PDF corretamente
- backup/export e restore/import funcionam com confirmação e testes manuais
- logs registram erros

## 11) Padrões de código
- Formatação: black
- Lint: ruff (opcional)
- Tipagem: type hints (mínimo em services/repo)
- Pastas e nomes claros.
