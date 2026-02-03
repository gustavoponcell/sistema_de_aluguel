# RentalManager

Aplicativo desktop para gerenciamento de aluguéis, focado em uso offline no Windows.

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
- Aluguéis com status **confirmado** ou **concluído** bloqueiam estoque.
- Aluguéis **rascunho** ou **cancelado** não bloqueiam estoque.

> Dica: para um aluguel de um único dia, informe a devolução no dia seguinte.

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

O script gera automaticamente um ícone mínimo em `assets\icon.ico` caso o arquivo não exista.
Para personalizar, substitua o ícone por um `.ico` próprio.

Ou execute o comando diretamente:

```powershell
pyinstaller --noconsole --name RentalManager --icon assets/icon.ico --add-data "assets;assets" --paths "src" --clean --noconfirm src/rental_manager/app.py
```

### Onde fica o executável

O executável principal será gerado em:

```
dist\RentalManager\RentalManager.exe
```

### Como instalar (uso offline)

1) Copie a pasta inteira `dist\RentalManager` para o computador de destino.
2) Execute `RentalManager.exe` diretamente (não requer instalação).

### Checklist pós-build

- Abrir o executável e confirmar que não aparece console.
- Confirmar criação do banco em `%APPDATA%\RentalManager\rental_manager.db`.
- Confirmar criação de logs em `%APPDATA%\RentalManager\logs\`.
- Criar um aluguel de teste e gerar PDF em `%APPDATA%\RentalManager\pdfs\`.
- Executar backup e verificar arquivo em `%APPDATA%\RentalManager\backups\`.
