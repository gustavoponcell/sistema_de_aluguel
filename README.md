# RentalManager

Aplicativo desktop para gerenciamento de produtos, serviços e pedidos de locação, focado em uso offline no Windows.

📘 **Documentação completa:** [DOCUMENTATION.md](DOCUMENTATION.md)

## Como rodar em desenvolvimento

1) Crie e ative um ambiente virtual:

```bash
python -m venv .venv
.venv\\Scripts\\activate
```

2) Instale as dependências:

```bash
pip install -r requirements.txt
```

3) Execute o aplicativo:

```bash
python -m rental_manager.app
```

## Rodar com um clique no Windows

1) Execute o arquivo `run_app.bat` na raiz do projeto (duplo clique).
   - Se a pasta `.venv` não existir, o script mostra as instruções para criar o
     ambiente e instalar as dependências.
   - Se algo falhar, o log detalhado fica em `run_app.log` na raiz do projeto.

### Criar um atalho na área de trabalho

1) Clique com o botão direito em `run_app.bat` e selecione **Enviar para > Área de trabalho (criar atalho)**.
2) Na área de trabalho, clique com o botão direito no atalho e escolha **Propriedades**.
3) No campo **Iniciar em**, informe a pasta do projeto (ex.: `C:\\caminho\\para\\sistema_de_aluguel`).
4) Clique em **OK**.

### (Opcional) Trocar o ícone do atalho

1) Clique com o botão direito no atalho e escolha **Propriedades**.
2) Clique em **Alterar Ícone...**.
3) Selecione um arquivo `.ico` (ex.: `assets\\app.ico`) e confirme.

## Onde fica o banco de dados

O banco SQLite fica na pasta de dados do usuário, em `%APPDATA%\\RentalManager`.

## Regra de ocupação de estoque por data

- A disponibilidade é calculada pelo intervalo **[início, fim)** (data de fim é exclusiva).
- A data de término deve ser **posterior** à data de início.
- Aluguéis com status **rascunho** ou **confirmado** bloqueiam estoque.
- Aluguéis **cancelado** ou **concluído** não bloqueiam estoque.

> Dica: para um pedido de um único dia, informe a devolução no dia seguinte.

## Teste manual básico

1) Cadastrar um serviço no Estoque:
   - Selecione **Tipo: Serviço** e verifique que a quantidade padrão é aplicada automaticamente.
2) Criar um pedido com o serviço:
   - Confirme que o pedido não bloqueia por falta de estoque.
3) Financeiro:
   - Verifique que o **Resumo** mostra a tabela de **Pendências por mês**.
   - Abra a aba **Gráficos** e confirme que os gráficos estão em cards grandes com rolagem vertical.

## Como mudar o tema

Abra o menu **Exibir > Tema** e escolha entre **Claro**, **Escuro** ou **Sistema**.
A preferência é salva em `%APPDATA%\\RentalManager\\config.json` e aplicada
imediatamente (sem precisar reiniciar). Se o modo **Sistema** estiver selecionado,
o app segue o tema do Windows; caso a detecção falhe, o tema claro é usado.

## Build com PyInstaller

### Pré-requisitos

1) Instale as dependências do projeto:

```bash
pip install -r requirements.txt
```

2) Instale o PyInstaller:

```bash
pip install pyinstaller
```

### Comando de build (Windows)

Use o script PowerShell já configurado:

```powershell
.\build_windows.ps1
```

O script:
- Usa o entrypoint `src\rental_manager\__main__.py` para garantir abertura do app.
- Aplica o ícone e os metadados de versão (arquivo `tools\windows_version_info.txt`).
- Gera automaticamente um ícone mínimo em `assets\app.ico` caso o arquivo não exista.

Para personalizar, substitua o ícone por um `.ico` próprio e edite o arquivo de versão.

Ou execute o comando diretamente:

```powershell
pyinstaller --noconsole --name RentalManager --icon assets/app.ico --version-file tools/windows_version_info.txt --add-data "assets;assets" --paths "src" --clean --noconfirm src/rental_manager/__main__.py
```

### Onde fica o executável

O executável principal será gerado em:

```
dist\RentalManager\RentalManager.exe
```

### Pasta de dados do usuário

Ao iniciar, o app cria automaticamente a pasta de dados em:

```
%APPDATA%\RentalManager\
```

Lá ficam o banco (`rental_manager.db`), backups (`backups\`), logs (`logs\`) e o
`config.json` (com `documents_dir` para a pasta padrão dos documentos).

### Como instalar (uso offline)

1) Copie a pasta inteira `dist\RentalManager` para o computador de destino.
2) Execute `RentalManager.exe` diretamente (não requer instalação).

### Como criar um atalho

1) Clique com o botão direito em `RentalManager.exe`.
2) Selecione **Enviar para > Área de trabalho (criar atalho)**.
3) (Opcional) Renomeie o atalho para “Rental Manager”.

### Checklist pós-build

- Abrir o executável e confirmar que não aparece console.
- Confirmar criação do banco em `%APPDATA%\RentalManager\rental_manager.db`.
- Confirmar criação de logs em `%APPDATA%\RentalManager\logs\`.
- Criar um pedido de teste e gerar PDF na pasta configurada em `documents_dir`.
- Executar backup e verificar arquivo em `%APPDATA%\RentalManager\backups\`.
