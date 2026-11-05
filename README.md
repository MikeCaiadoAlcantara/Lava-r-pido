# Sistema para Lava-rápido

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

Antes de abrir o aplicativo, inicie o MySQL pelo painel do XAMPP. Para a conexão com o **servidor MySQL** (não para entrar no aplicativo), o padrão é `127.0.0.1:3306`, usuário `root` sem senha, conforme a configuração comum do XAMPP. O programa cria o banco `lava_rapido_alcantara` e suas tabelas automaticamente. Se o MySQL estiver configurado com outros dados, defina `LAVA_DB_HOST`, `LAVA_DB_PORT`, `LAVA_DB_USER`, `LAVA_DB_PASSWORD` e, opcionalmente, `LAVA_DB_NAME` no ambiente antes de iniciar.

O aplicativo não possui usuário ou senha administrativa pré-definidos. Na tela de login, use **Cadastrar administrador** para informar o nome do lava-rápido, criar a primeira conta e, opcionalmente, cadastrar funcionários com telefone e diária. Depois do primeiro cadastro, essa opção fica desabilitada. A senha deve ter pelo menos 6 caracteres e é salva no MySQL como hash PBKDF2, nunca em texto puro. Na área administrativa, a aba **Equipe e frequência** permite cadastrar outros funcionários e alterar uma diária com data de vigência; os valores anteriores são preservados para os relatórios históricos.

## Uso

- A tela de operação registra no MySQL cada serviço, veículo/placa opcional, valor e observação, com data do movimento para consultas futuras.
- A área administrativa exige login e tem relatórios semanais, mensais, dos últimos 3 ou 6 meses, do ano atual ou anterior e por intervalo personalizado. Os relatórios mostram a quantidade de lavagens simples, completas e dos outros serviços, cada atendimento com veículo/placa e valor, faturamento, despesas lançadas, diárias, benefícios, total de saídas e saldo.
- A aba **Estabelecimento** permite salvar nome, CNPJ, telefone, proprietário e endereço. A aba **Benefícios** lista os lançamentos do período do relatório.
- Na aba **Despesas**, os lançamentos podem ser classificados como **Diária do pessoal**, **Produtos**, **Água** ou **Outros**. As presenças marcadas aparecem automaticamente na lista de despesas com o nome do funcionário e na subaba **Diárias por presença**; a subaba **Despesas por tipo** resume os valores. Não lance manualmente diárias já registradas pela frequência.
- Diárias entram nas despesas somente para dias explicitamente marcados como presença na aba **Equipe e frequência**; faltas e dias sem marcação não geram diária. Um valor pago informado na frequência prevalece sobre a diária cadastrada para aquela data.
- O saldo é faturamento menos despesas lançadas, diárias de presenças marcadas e benefícios. A folha estimada aparece separadamente e não é descontada, evitando duplicar pagamentos já informados em frequência.

Os dados ficam no servidor MySQL/MariaDB local, no banco `lava_rapido_alcantara` por padrão. Faça cópias periódicas pelo phpMyAdmin ou com as ferramentas de backup do MySQL. O login controla o acesso pela interface; use uma senha para o usuário MySQL se outras pessoas tiverem acesso ao computador.

## Testes

```powershell
python -m unittest discover -s tests -v
```

## Gerar executável

Instale as dependências e rode o empacotamento no Windows:

```powershell
pyinstaller --noconfirm --clean --windowed --name "Sistema Lava Rapido" --collect-all PySide6 --hidden-import app.main app\__main__.py
```

O aplicativo ficará em `dist\Sistema Lava Rapido`. Distribua a pasta completa, não apenas o `.exe`. O banco MySQL usa o identificador técnico `lava_rapido_alcantara`, que permanece fixo para manter a conexão estável; o nome digitado no cadastro é salvo nas configurações do banco e exibido nas telas. Teste a pasta `dist` em um computador Windows sem Python antes de entregar; para instalação com atalho, pode-se empacotar essa pasta com Inno Setup.
