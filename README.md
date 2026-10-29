# Lava Rápido Alcantara

Aplicativo desktop para registrar atendimentos de um lava-rápido e consultar informações administrativas. Feito com Python, PySide6/Qt Widgets e MySQL/MariaDB.

## Requisitos

- Windows 10/11 (o empacotamento para Windows deve ser feito em Windows)
- Python 3.10 ou mais recente

## Instalar e executar

No terminal, dentro da pasta do projeto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m app
```

Antes de abrir o aplicativo, inicie o MySQL pelo painel do XAMPP. Por padrão, o programa conecta em `127.0.0.1:3306` usando o usuário `root` sem senha, configuração padrão do XAMPP, e cria o banco `lava_rapido_alcantara` e suas tabelas automaticamente. Se o MySQL estiver configurado com outros dados, defina `LAVA_DB_HOST`, `LAVA_DB_PORT`, `LAVA_DB_USER`, `LAVA_DB_PASSWORD` e, opcionalmente, `LAVA_DB_NAME` no ambiente antes de iniciar.

Na primeira execução, o programa cria o administrador padrão `José`, com senha `941225`. Altere essa senha após o primeiro acesso. A senha é guardada como hash PBKDF2.

## Uso

- A tela de operação registra serviço, veículo/placa opcional, valor e forma de pagamento, além da contagem diária.
- A área administrativa exige login e tem resumo por período, despesas, cadastro de funcionários, frequência, cesta básica e bônus.
- O saldo do relatório é faturamento menos despesas lançadas e benefícios registrados. A folha estimada aparece separadamente e não é descontada automaticamente, evitando contar salário duas vezes. Registre em despesas os pagamentos efetivamente realizados.
- Faltas são contabilizadas apenas quando há um lançamento de frequência para o dia. Dias sem marcação não são presumidos como presença.

Os dados ficam no servidor MySQL/MariaDB local, no banco `lava_rapido_alcantara` por padrão. Faça cópias periódicas pelo phpMyAdmin ou com as ferramentas de backup do MySQL. O login controla o acesso pela interface; use uma senha para o usuário MySQL se outras pessoas tiverem acesso ao computador.

## Testes

```powershell
python -m unittest discover -s tests -v
```

## Gerar executável

Instale as dependências e rode o empacotamento no Windows:

```powershell
pyinstaller --noconfirm --clean --windowed --name "Lava Rápido Alcantara" --collect-all PySide6 --hidden-import app.main app\__main__.py
```

O aplicativo ficará em `dist\Lava Rápido Alcantara`. Distribua a pasta completa, não apenas o `.exe`. O banco fica fora dela para que atualizações do executável não apaguem os dados. Teste a pasta `dist` em um computador Windows sem Python antes de entregar; para instalação com atalho, pode-se empacotar essa pasta com Inno Setup.
