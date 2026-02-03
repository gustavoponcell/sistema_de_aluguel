# Documentação Completa — RentalManager

> Documento em PT-BR voltado tanto para **usuário final** quanto para **manutenção técnica**.

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Instalação e execução no Windows](#2-instalação-e-execução-no-windows)
3. [Arquitetura do projeto (alto nível)](#3-arquitetura-do-projeto-alto-nível)
4. [Banco de dados (SQLite)](#4-banco-de-dados-sqlite)
5. [Regras de negócio (detalhado)](#5-regras-de-negócio-detalhado)
6. [Interface (tela por tela)](#6-interface-tela-por-tela)
7. [Recibo/Contrato (PDF)](#7-recibocontrato-pdf)
8. [Backup e segurança](#8-backup-e-segurança)
9. [Empacotamento (PyInstaller)](#9-empacotamento-pyinstaller)
10. [Troubleshooting (muito prático)](#10-troubleshooting-muito-prático)
11. [Checklist de uso (manual para usuário leigo)](#11-checklist-de-uso-manual-para-usuário-leigo)
12. [Planejado / Não implementado ainda](#12-planejado--não-implementado-ainda)

---

## 1) Visão geral

**O que o sistema faz**
- O RentalManager é um aplicativo desktop para **gestão de aluguéis de itens para eventos** (cadeiras, mesas, brinquedos, som etc.).
- Permite cadastrar produtos e clientes, criar e gerenciar aluguéis, acompanhar agenda e financeiro, gerar PDF de contrato/recibo e fazer backup/restauração do banco local.

**Público-alvo**
- Usuário leigo, uso em **1 PC local**, com foco em simplicidade.
- Ambiente principal: **Windows**.

**Premissas do sistema**
- **Sem login** e sem acesso remoto.
- Banco de dados **SQLite local**.
- Interface simples e guiada.

---

## 2) Instalação e execução no Windows

### 2.1 Pré-requisitos
- **Python** instalado no Windows (recomendado **3.11+**).
  - O projeto usa PySide6 e bibliotecas atuais; versões antigas podem falhar ao instalar dependências.
- A opção **“Add Python to PATH”** deve estar marcada na instalação do Python.

> Se o Python não estiver no PATH, o `run_app.bat` não conseguirá iniciar o aplicativo.

### 2.2 Estrutura do projeto (src layout)
O código está organizado no padrão **src layout**:

```
/sistema_de_aluguel
├── run_app.bat
├── requirements.txt
├── README.md
├── DOCUMENTATION.md
└── src
    └── rental_manager
        ├── app.py
        ├── db/
        ├── domain/
        ├── repositories/
        ├── services/
        ├── ui/
        └── utils/
```

### 2.3 Como rodar pelo `run_app.bat`
O arquivo `run_app.bat` (na raiz do projeto) faz o seguinte:
1. Vai para a pasta do projeto.
2. Cria um **virtualenv** em `.venv` (se não existir).
3. Ativa o virtualenv.
4. Verifica o `requirements.txt` e instala dependências se houve mudança (por hash SHA256).
5. Ajusta `PYTHONPATH` para `src`.
6. Executa o app via `python -m rental_manager.app`.
7. **Redireciona toda saída para `run_app.log`.**

### 2.4 Onde fica o log e como interpretar erros comuns
- **Log do launcher**: `run_app.log` na raiz do projeto.
  - Use este log quando o app **nem abre**.
  - Procure por mensagens `[ERRO]` ou falhas ao instalar dependências.

- **Log do aplicativo**: `%APPDATA%\RentalManager\logs\app.log`.
  - Use quando o app abriu, mas **algo falhou dentro do app**.
  - Logs rotacionam automaticamente (até 3 arquivos, ~1 MB cada).

### 2.5 Criar atalho na área de trabalho
1. Clique com o botão direito em `run_app.bat` → **Enviar para > Área de trabalho (criar atalho)**.
2. Clique com o botão direito no atalho → **Propriedades**.
3. Em **Iniciar em**, informe a pasta do projeto, por exemplo:
   `C:\caminho\para\sistema_de_aluguel`.
4. Clique em **OK**.

> O campo **Iniciar em** é essencial para garantir que o app encontre `src/` e `requirements.txt`.

---

## 3) Arquitetura do projeto (alto nível)

### 3.1 Pastas e responsabilidades

- `src/rental_manager/ui/` → **Interface (PySide6)**: telas, diálogos, navegação.
- `src/rental_manager/services/` → **Regras de negócio**: validações, estoque, pagamentos.
- `src/rental_manager/repositories/` → **Persistência**: CRUD e consultas SQLite.
- `src/rental_manager/db/` → **Criação do schema** e conexão SQLite.
- `src/rental_manager/domain/` → **Modelos (dataclasses e enums)**.
- `src/rental_manager/utils/` → utilitários (backup, PDF, tema, config).

### 3.2 Ponto de entrada
- Entrada principal: `python -m rental_manager.app`.
- `app.py` configura logs, banco, tema e abre a `MainWindow`.

### 3.3 Fluxo principal de inicialização
1. Configura logs.
2. Garante pastas do AppData.
3. Aplica migrações do banco (`apply_migrations`).
4. Carrega configurações (tema + backup automático).
5. Cria QApplication e aplica tema.
6. Instancia repos/serviços (CustomerRepo, ProductRepo, RentalService etc.).
7. Abre `MainWindow`.

### 3.4 Padrão adotado
- **UI + Services + Repository**.
  - UI chama Services.
  - Services chamam Repositories.
  - Repositories fazem SQL.
- Modelos de domínio (dataclasses) ficam em `domain/models.py`.

### 3.5 Como as telas se atualizam
- Existe um **DataEventBus** com sinal `data_changed`.
- Quando dados são alterados, as telas recebem sinal e **se atualizam automaticamente**.
- Se a tela não estiver visível, ela marca refresh pendente e atualiza ao aparecer.
- Além disso, algumas telas têm botão **Atualizar** ou refresh automático via timers.

---

## 4) Banco de dados (SQLite)

### 4.1 Local do arquivo `.db`
- O banco fica em:
  - `%APPDATA%\RentalManager\rental_manager.db`

### 4.2 Criação/atualização
- O banco é criado automaticamente na primeira execução.
- Existe **versionamento do schema** via tabela `app_meta` e migrações numeradas.
- Cada migração é aplicada **apenas uma vez** e o número atual fica em `app_meta.schema_version`.
- Ao iniciar o app, o sistema chama `apply_migrations` para criar/atualizar o schema.

### 4.3 Tabelas e colunas principais

#### `products`
- `id` (PK)
- `name` (TEXT, **unique**)
- `category` (TEXT)
- `total_qty` (INTEGER)
- `unit_price` (REAL)
- `active` (INTEGER 0/1)
- `created_at`, `updated_at`

#### `customers`
- `id` (PK)
- `name` (TEXT)
- `phone` (TEXT)
- `notes` (TEXT)
- `created_at`, `updated_at`

#### `rentals`
- `id` (PK)
- `customer_id` (FK → customers.id)
- `event_date` (TEXT)
- `start_date` (TEXT)
- `end_date` (TEXT)
- `address` (TEXT)
- `status` (TEXT)
- `total_value` (REAL)
- `paid_value` (REAL)
- `payment_status` (TEXT)
- `created_at`, `updated_at`

#### `rental_items`
- `id` (PK)
- `rental_id` (FK → rentals.id)
- `product_id` (FK → products.id)
- `qty` (INTEGER)
- `unit_price` (REAL)
- `line_total` (REAL)
- `created_at`, `updated_at`

#### `payments`
- `id` (PK)
- `rental_id` (FK → rentals.id)
- `amount` (REAL)
- `method` (TEXT)
- `paid_at` (TEXT ISO)
- `note` (TEXT)

#### `documents`
- `id` (PK)
- `rental_id` (FK → rentals.id)
- `doc_type` (TEXT: `contract` ou `receipt`)
- `file_path` (TEXT)
- `generated_at` (TEXT ISO)
- `checksum` (TEXT SHA256)

> Pagamentos ficam registrados em `payments` e o campo `rentals.paid_value` é derivado da soma dos pagamentos.

### 4.4 Índices
- `idx_rentals_event_date`
- `idx_rentals_start_date`
- `idx_rentals_end_date`
- `idx_rentals_status`
- `idx_rentals_created_at`
- `idx_rental_items_rental_id`
- `idx_rental_items_product_id`

### 4.5 Constraints e integridade
- **Foreign Keys** habilitadas (`PRAGMA foreign_keys = ON`).
- `products.name` é `UNIQUE`.
- `CHECK constraints` garantem valores válidos:
  - `products.total_qty >= 0` e `products.unit_price >= 0` (ou nulo).
  - `rental_items.qty > 0`.
  - `rentals.total_value >= 0` e `rentals.paid_value >= 0`.
  - `payments.amount > 0`.
  - `rentals.end_date > rentals.start_date`.
  - `rentals.status` limitado aos valores reais do app (`draft`, `confirmed`, `canceled`, `completed`).

---

## 5) Regras de negócio (detalhado)

### 5.1 Status de aluguel
- `draft` → **Rascunho**
- `confirmed` → **Confirmado**
- `canceled` → **Cancelado**
- `completed` → **Concluído**

**Impacto no estoque**
- Apenas **confirmed** e **completed** bloqueiam estoque.
- **draft** e **canceled** não bloqueiam.

### 5.2 Pagamento
- `unpaid` → **Pendente**
- `partial` → **Parcial**
- `paid` → **Pago**

**Cálculo do status de pagamento**
- O total pago do aluguel é a **soma dos registros em `payments`**.
- `paid_value` em `rentals` é um campo derivado (atualizado ao inserir/editar/excluir pagamentos).
- Regras:
  - `paid_total <= 0` → `unpaid`
  - `0 < paid_total < total_value` → `partial`
  - `paid_total >= total_value` → `paid`

### 5.3 Cálculo financeiro
**Relatório financeiro por período**:
- A lista de aluguéis usa `event_date` como referência do período.
- **Total recebido**: soma dos pagamentos em `payments` cujo `paid_at` está dentro do período.
  - Pagamentos sem `paid_at` não entram no total recebido do período.
- **Total a receber**: soma de `(total_value - paid_total)` **apenas para aluguéis `confirmed`** no período.
- Aluguéis com status `canceled` **não entram** no relatório.

### 5.4 Estoque por data (crítico)

**Definição de “na rua” vs “comigo”**
- **Na rua** = quantidade reservada em aluguéis que bloqueiam estoque.
- **Comigo** = `total_qty - reservado` (não pode ser negativo).

**Regra de ocupação por intervalo**
- Um aluguel bloqueia estoque no intervalo:

```
start_date <= D < end_date
```

- A data de término é **exclusiva**.
- Isso permite que um aluguel termine no mesmo dia em que outro começa.

**Exemplo rápido**
- Aluguel A: início 10/05, fim 12/05 → bloqueia **10/05 e 11/05**.
- Aluguel B: início 12/05, fim 13/05 → **permitido** (não há sobreposição).

**Quais status bloqueiam estoque**
- `draft` (Rascunho), `confirmed` (Confirmado) e `completed` (Concluído), que são os
  status reais do app.

**Validação ao criar/editar aluguel**
- Para cada item e cada dia do intervalo, verifica se há quantidade disponível.
- Se faltar estoque em qualquer dia, a operação é bloqueada mostrando o **primeiro conflito**
  com produto, data, disponível e solicitado.

**Edição de aluguel existente**
- Na validação de edição, o sistema **exclui o próprio aluguel** do cálculo (para não bloquear a si mesmo).

### 5.5 Endereço e entrega
- Campo `address` é texto livre.
- Usado:
  - Na **Agenda** (resumo de endereço).
  - No **PDF** (contrato/recibo).

---

## 6) Interface (tela por tela)

### 6.1 Tela: **Novo Aluguel**
**Objetivo**
- Criar um aluguel com cliente, datas, itens e valores.

**Componentes**
- Seletor de cliente (combo + botão “Novo Cliente”).
- Datas: evento, início, fim.
- Campo de endereço.
- Lista de itens com produto, quantidade, preço unitário.
- Tabela de itens e total.
- Botões: “Salvar como rascunho”, “Confirmar aluguel”.

**Ações e comportamento**
- Adicionar item: valida quantidade, preço e estoque no período.
- Confirmar aluguel: salva e depois muda status para `confirmed`.
- Salvar rascunho: salva como `draft`.

**Validações e mensagens**
- Cliente obrigatório.
- Data de término deve ser **após** data de início.
- Pelo menos 1 item.
- Estoque validado dia a dia.

**Exemplo de uso (fictício)**
- Cliente: “João Silva”
- Evento: 20/12/2024
- Início: 19/12/2024
- Fim: 21/12/2024
- Itens:
  - 100 cadeiras, R$ 4,00
  - 20 mesas, R$ 10,00

---

### 6.2 Tela: **Agenda** (Aluguéis)
**Objetivo**
- Listar e gerenciar os aluguéis do período.

**Componentes**
- Cartão “Aluguéis de hoje”.
- Filtros: período, status, pagamento, busca.
- Tabela com datas, cliente, endereço, status, total e pago.
- Botões: detalhes, editar, cancelar, concluir, registrar pagamento, gerar PDF.

**Ações e comportamento**
- **Editar**: abre diálogo para alterar datas e itens (revalida estoque).
- **Detalhes/Editar**: seção **Pagamentos** permite adicionar, editar e excluir pagamentos com confirmação.
- **Cancelar**: muda status para `canceled` (não bloqueia estoque).
- **Concluir**: muda status para `completed`.
- **Registrar pagamento**: adiciona um registro em `payments` e recalcula o total pago.
- **Gerar PDF**: contrato ou recibo.
- Carregamento assíncrono da lista com placeholder de “Carregando…”.
- Por padrão, a agenda carrega **hoje + próximos 7 dias** (filtro rápido).
- Cache em memória por alguns segundos para alternar abas sem recarregar.
- Logs registram tempo de query, transformação e renderização.

**Validações e mensagens**
- Confirmação antes de cancelar ou concluir.
- Mensagens de erro em falhas de validação/DB.

---

### 6.3 Tela: **Estoque / Produtos**
**Objetivo**
- Cadastrar e gerenciar produtos e estoque.

**Componentes**
- Data de referência para calcular “na rua”.
- Busca por nome.
- Tabela: produto, total, na rua, comigo.
- Botões: novo, editar, desativar.

**Ações e comportamento**
- “Na rua” é a soma das reservas de aluguéis em rascunho/confirmados/concluídos na data.
- “Comigo” = `total_qty - na_rua`.

**Validações**
- Nome e categoria obrigatórios.
- Quantidade e preço padrão devem ser > 0.

---

### 6.4 Tela: **Clientes**
**Objetivo**
- Cadastrar e editar clientes.

**Componentes**
- Busca por nome.
- Tabela com nome, telefone e observações.
- Botões: novo, editar, excluir.

**Validações**
- Nome obrigatório.

---

### 6.5 Tela: **Financeiro**
**Objetivo**
- Ver resumo financeiro por período.

**Componentes**
- Filtro por data (período baseado em `rentals.start_date`).
- Abas: **Resumo**, **Gráficos** e **Relatórios**.
- Cards: total recebido, total a receber, quantidade de aluguéis.
- Gráficos e rankings (offline) ficam na aba **Gráficos**.
- Tabela com aluguéis do período + botão de exportação CSV nos relatórios.

**Regras**
- **Base temporal**: o período da tela usa `rentals.start_date` (datas ISO `YYYY-MM-DD`).
- **Receita prevista por mês**: soma `rentals.total_value` agrupado por mês de `start_date`.
- **Aluguéis por mês**: contagem por mês de `start_date`.
- **Recebido**:
  - Se a tabela `payments` existir: soma `payments.amount` por `paid_at` no período.
  - Se não existir: usa `rentals.paid_value` do período (agrupado por `start_date`).
- **A receber**: soma de `(total_value - paid_value)` para aluguéis confirmados, por mês de `start_date`.
- **Ranking de produtos (quantidade)**: soma `rental_items.qty` por produto no período.
- **Ranking de produtos (receita)**:
  - Usa `rental_items.unit_price` quando disponível.
  - Caso contrário, usa `products.unit_price`.
  - Se nenhum preço estiver cadastrado, o gráfico é ocultado com aviso ao usuário.
- Ignora aluguéis cancelados.
- CSV salvo em `%APPDATA%\RentalManager\exports`.
- Se Matplotlib não estiver disponível, o app tenta QtCharts. Se ambos falharem, os gráficos são ocultados com aviso; KPIs e tabelas continuam funcionando.
- Gráficos são carregados sob demanda (lazy loading) ao abrir a aba **Gráficos**, com cache por período e atualização ao alterar o filtro ou clicar em **Atualizar**.

---

### 6.6 Tela: **Backup**
**Objetivo**
- Criar e restaurar backups do banco SQLite.

**Componentes**
- Botão “Fazer backup agora”.
- Lista de backups (com data/hora).
- Botão “Restaurar”.
- Checkbox “Backup automático ao iniciar”.

**Regras**
- A restauração pede confirmação extra com o texto “RESTAURAR”.
- Antes de restaurar, o sistema cria um **backup de segurança** do banco atual.
- Após restaurar, roda **PRAGMA integrity_check** e registra o resultado.
- Após restaurar, o app é fechado para reinicialização segura.

---

### 6.7 Menu: **Exibir > Tema**
- Permite escolher **Claro**, **Escuro** ou **Sistema**.
- Preferência salva em `%APPDATA%\RentalManager\config.json`.

---

## 7) Recibo/Contrato (PDF)

**Onde gera**
- Na tela **Agenda**, botões **“Gerar contrato”** e **“Gerar recibo”**.

**O que contém**
- Dados do locador (configurados em `config.py`).
- Dados do cliente (nome e telefone).
- Datas do aluguel e endereço.
- Itens locados, valores e saldo.
- Termos e campo para assinatura.

**Onde é salvo**
- `%APPDATA%\RentalManager\pdfs`.
- Nome do arquivo: `aluguel_<ID>_<timestamp>_contract.pdf` ou `_receipt.pdf`.

**Como reemitir / abrir o último**
- Use os botões **“Abrir último contrato”** e **“Abrir último recibo”** no aluguel selecionado.
- Se não houver documento gerado, os botões ficam desabilitados com dica de motivo.
- Ao regerar, o arquivo é atualizado na pasta `pdfs` e o sistema registra o novo caminho e checksum.

**Observações**
- O PDF é **gerado com ReportLab**.
- A assinatura é manual (linha no final).

---

## 8) Backup e segurança

### 8.1 Estratégia de backup
- **Manual** pela tela de backup.
- **Automático ao iniciar** (opcional, via checkbox).
- **Retenção automática**: mantém somente os últimos 30 backups e remove os mais antigos.

### 8.2 Onde salva
- `%APPDATA%\RentalManager\backups`.
- Nome: `rental_manager_YYYYMMDD_HHMMSS.db`.
- Backup de segurança antes da restauração: `rental_manager_YYYYMMDD_HHMMSS_pre_restore.db`.

### 8.3 Restauração (passo a passo)
1. Abra a tela **Backup**.
2. Selecione um arquivo da lista.
3. Clique em **Restaurar**.
4. Digite **RESTAURAR** para confirmar.
5. O sistema cria um backup de segurança do banco atual.
6. O backup selecionado é restaurado.
7. O sistema roda `PRAGMA integrity_check` e informa o resultado na tela.
8. O app fechará para concluir a restauração.

### 8.4 Considerações de segurança
- Sem login → qualquer pessoa com acesso ao PC pode ver dados.
- Banco local → proteja o computador com senha do Windows.

### 8.5 Boas práticas
- Copie **sempre**:
  - O `.db` principal.
  - A pasta `pdfs/`.
  - A pasta `backups/`.

---

## 9) Empacotamento (PyInstaller)

### 9.1 Como gerar .exe
- Script pronto em `build_windows.ps1`:

```powershell
.\build_windows.ps1
```

- O script usa `src\rental_manager\__main__.py` como entrypoint e aplica ícone + metadados de versão via `tools\windows_version_info.txt`.
- Se quiser chamar o PyInstaller manualmente:

```powershell
pyinstaller --noconsole --name RentalManager --icon assets/icon.ico --version-file tools/windows_version_info.txt --add-data "assets;assets" --paths "src" --clean --noconfirm src/rental_manager/__main__.py
```

### 9.2 Onde fica o executável
- `dist\RentalManager\RentalManager.exe`

### 9.2.1 Pasta de dados do usuário
- `%APPDATA%\RentalManager\`
  - `rental_manager.db`
  - `pdfs\`
  - `backups\`
  - `logs\`

### 9.3 Limitações comuns / troubleshooting
- Algumas máquinas podem bloquear execução por **SmartScreen**.
- Se faltar DLLs do Qt, é preciso revisar a instalação do PyInstaller.
- Certifique-se de que o app grava em `%APPDATA%` e não na pasta do executável.

### 9.4 Distribuição
1. Copie a pasta `dist\RentalManager` completa.
2. Execute `RentalManager.exe` no PC de destino.
3. Para criar atalho: botão direito no `RentalManager.exe` → **Enviar para > Área de trabalho (criar atalho)**.

---

## 10) Troubleshooting (muito prático)

**App não abre**
- Verifique `run_app.log`.
- Erros comuns:
  - Python não encontrado no PATH.
  - Falha ao instalar dependências (pip).

**Problema de tema / contraste**
- Menu **Exibir > Tema** → selecione “Claro”.
- Config fica em `%APPDATA%\RentalManager\config.json`.

**Erros de import (PYTHONPATH/src)**
- Garanta que o app foi iniciado pela **raiz do projeto**.
- Verifique o campo **Iniciar em** no atalho.

**SQLite locked / arquivo em uso**
- Feche outras instâncias do app.
- Evite abrir o `.db` com outro programa ao mesmo tempo.

**Falhas de instalação de deps (pip)**
- Verifique conexão com a internet.
- Rode `pip install -r requirements.txt` manualmente.

**Permissões no AppData**
- O app salva em `%APPDATA%\RentalManager`.
- Se houver restrição, rode como usuário local com permissão de escrita.

---

## 11) Checklist de uso (manual para usuário leigo)

**Fluxo recomendado**
1. Cadastrar produtos com estoque total.
2. Cadastrar cliente.
3. Criar aluguel com itens e datas.
4. Confirmar aluguel.
5. Registrar pagamento.
6. Emitir recibo/contrato.
7. Acompanhar agenda e financeiro.

**Dicas de prevenção de erro**
- Sempre defina **data de devolução posterior** ao início.
- Verifique estoque antes de confirmar um aluguel grande.
- Use o financeiro para acompanhar pendências.

---

## 12) Planejado / Não implementado ainda

- Tela de **Configurações** dedicada (hoje só há tema no menu e backup na tela própria).
- Migrações futuras além das básicas (apenas constraints e versionamento simples já existem).
- **Exportações adicionais** (além do CSV financeiro).
- **Calendário** visual (existe apenas lista/agenda).
- **Alertas** ou notificações automáticas.

---

# Apêndice: exemplos rápidos

### Exemplo de cadastro de produto
- Nome: “Cadeira plástica branca”
- Categoria: “Cadeira”
- Quantidade total: 200
- Preço padrão: R$ 4,00

### Exemplo de aluguel
- Cliente: “Maria Oliveira”
- Evento: 15/03/2025
- Início: 14/03/2025
- Fim: 16/03/2025
- Endereço: “Rua das Flores, 123 - Centro”
- Itens:
  - 80 cadeiras (R$ 4,00)
  - 10 mesas (R$ 12,00)

### Exemplo de recibo
- Recibo gerado em: `%APPDATA%\RentalManager\pdfs\aluguel_5_20250310_140530_receipt.pdf`
